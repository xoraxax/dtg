# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

import os
import sys
import shutil
from threading import Lock, current_thread
from datetime import timedelta, date, time
from time import sleep

from flask import Flask, request, session, redirect, url_for, render_template, jsonify, send_from_directory
from flask.ext.sqlalchemy import SQLAlchemy
from flask.ext.assets import Environment, Bundle
from flaskext.kvsession import KVSessionExtension
from flaskext.babel import Babel, format_date
import flaskext.babel
from simplekv.db.sql import SQLAlchemyStore
from sqlalchemy import create_engine, MetaData, event
from sqlalchemy.exc import IntegrityError
from migrate.versioning import genmodel, schemadiff
import markdown
from slimit import minify

from dtg.model import generate_db_model
from dtg.transtools import _, get_translations, ngettext, Markup, locale_choices
from dtg.backgroundjobs import JOBS
from dtg.version import __version__


app = Flask("dtg")
app.config['SQLALCHEMY_DATABASE_URI'] = sys.dtg_db_path("main")
app.config["SQLALCHEMY_ECHO"] = sys.dtg_debug
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config['ASSETS_DEBUG'] = sys.dtg_debug
SEQID_SLEEP = 10 # seconds
NIGHTLY_RUNTIME = time(1, 42), time(2, 42)

# initialize DB
db = SQLAlchemy(app)
generate_db_model(db)
from dtg.model import *
from dtg.forms import *
db.create_all()
if not SystemInfo.query.first():
    initialize_db(db)

# setup secret key, do DB migrations
sys_info = SystemInfo.query.first()
app.secret_key = sys_info.secret_app_key
if sys_info.db_rev != APP_DB_REV:
    if not sys.dtg_do_upgrade:
        raise Exception("Old database version, please backup your database and enable DB migrations.")
    diff = schemadiff.getDiffOfModelAgainstDatabase(db.metadata, db.engine)
    genmodel.ModelGenerator(diff, db.engine).runB2A()
    sys_info = SystemInfo.query.first()
    sys_info.db_rev = APP_DB_REV
    db.session.commit()


@app.before_first_request
def init_background_jobs():
    # setup background jobs
    app.background_jobs = []
    for JOB in JOBS:
        job = JOB(app, NIGHTLY_RUNTIME)
        app.background_jobs.append(job)
        job.start()


def before_commit(session):
    try:
        request.workspace
    except (RuntimeError, AttributeError):
        return
    if request.workspace is not None:
        request.workspace.seqid += 1
event.listen(db.Session, "before_commit", before_commit)

# initialize session handling
session_engine = create_engine(sys.dtg_db_path("sessions"))
session_metadata = MetaData(bind=session_engine)
store = SQLAlchemyStore(session_engine, session_metadata, 'kvstore')
session_metadata.create_all()
KVSessionExtension(store, app)

# initialize i18n
app.jinja_env.add_extension('jinja2.ext.i18n')
app.babel_translations_dict = {}
app.babel_translations_lock = Lock()
babel = Babel(app, configure_jinja=False)
app.jinja_env.globals.update(gettext=_, ngettext=ngettext, _=_, version=__version__)
def finalizer(x):
    if isinstance(x, Markup):
        return x
    return unicode(x)
app.jinja_env.finalize = finalizer
# monkeypatch flask-babel
flaskext.babel.get_translations = get_translations

@babel.localeselector
def get_locale():
    # try to guess the language from the user accept
    # header the browser transmits.
    if request.user is None or not request.user.locale:
        return request.accept_languages.best_match([x[0] for x in locale_choices])
    return request.user.locale


def flash(message):
    f = FlashMessage(unicode(message), request.user)
    db.session.add(f)

def get_last_flash_id():
    if request.user is None:
        return -42
    max_id = FlashMessage.query_class(db.func.max(FlashMessage.id), session=FlashMessage.query.session).filter_by(owner=request.user).first()[0]
    if max_id is None:
        return 0
    return max_id


def needs_login(func):
    def innerfunc(*args, **kwargs):
        if request.user is None:
            return redirect(url_for('login', url=request.url))
        return func(*args, **kwargs)
    innerfunc.__name__ = func.__name__
    return innerfunc

def gets_workspace(func):
    def innerfunc(workspace, *args, **kwargs):
        workspace = Workspace.query.filter_by(name=workspace, owner=request.user).first()
        if workspace is None:
            return render_error(_("Workspace not found")), 404
        request.workspace = workspace
        return func(workspace, *args, **kwargs)
    innerfunc.__name__ = func.__name__
    return innerfunc


def render_error(error_msg, json=False):
    if json:
        return jsonify({"error": error_msg})
    return render_template("error.html", error_msg=error_msg)

@app.errorhandler(500)
def errorhandler_500(e):
    return render_error(e), 500

@app.errorhandler(404)
def errorhandler_404(e):
    return render_error(e), 404


@app.route('/')
@needs_login
def index():
    return render_template("workspaces.html", last_flash_id=get_last_flash_id())

@app.route('/<workspace>')
@needs_login
@gets_workspace
def index_workspace(workspace):
    return render_template("workspace.html", workspace=workspace, last_flash_id=get_last_flash_id())

@app.route('/_workspaces', methods=["POST"])
@needs_login
def _workspace():
    action = request.form.get("action")
    if action == "create":
        w = Workspace(request.form.get("name"), request.user)
        c = Context(unicode(_("Unsorted")))
        w.contexts.append(c)
        db.session.add(w)
        db.session.commit()
    return jsonify({})

@app.route('/<workspace>/delete', methods=["POST"])
@needs_login
@gets_workspace
def delete_workspace(workspace):
    workspace.delete()
    db.session.commit()
    return jsonify({})

@app.route('/<workspace>/seqid')
@needs_login
@gets_workspace
def delete_workspace(workspace):
    oldseqid = int(request.args.get("seqid"))
    slept = 0
    set_daemonic = False
    while oldseqid == workspace.seqid and slept <= 180:
        if not set_daemonic:
            set_daemonic = True
            current_thread()._Thread__daemonic = True
        sleep(SEQID_SLEEP)
        slept += SEQID_SLEEP
        db.session.expire(workspace, ["seqid"])
    return jsonify({"seqid": workspace.seqid})

@app.route('/<workspace>/tags', methods=["GET", "POST"])
@needs_login
@gets_workspace
def workspace_tags(workspace):
    if request.method == "GET":
        return jsonify({"data": [{"name": tag.name, "id": tag.id} for tag in workspace.tags], "seqid": workspace.seqid})
    else:
        action = request.form.get("action")
        tag = Tag.query.filter_by(id=int(request.form.get("id")), workspace=workspace).first()
        edittitle = _("Edit tag") if tag else _("Add tag")
        if action == "move":
            previous_tag = Tag.query.filter_by(id=int(request.form.get("previous_id")), workspace=workspace).first()
            if previous_tag is None:
                new_index = 0
            else:
                new_index = workspace.tags.index(previous_tag) + 1
            workspace.tags.pop(workspace.tags.index(tag))
            workspace.tags.insert(new_index, tag)
        elif action == "editinitial":
            form = TagForm(obj=tag)
            return jsonify({"title": edittitle, "body": render_template("edit.html", form=form, type="tag")})
        elif action == "edit":
            form = TagForm(request.form, obj=tag)
            try:
                if form.validate():
                    if tag is None:
                        tag = Tag(form["name"].data)
                        workspace.tags.append(tag)
                    else:
                        form.populate_obj(tag)
                    flash(_("Saved tag '%s'", tag.name))
                    db.session.commit()
                    return jsonify({"id": tag.id})
            except IntegrityError:
                form["name"].errors.append(_("Duplicate name"))
            return jsonify({"status": "AGAIN", "title": edittitle, "body": render_template("edit.html", form=form, type="tag")})
        elif action == "delete":
            flash(_("Deleted tag '%s'", tag.name))
            tag.delete()
        else:
            return jsonify({"error": "Invalid action"})
        db.session.commit()
        return jsonify({"result": "OK"})

@app.route('/preferences', methods=["POST"])
@needs_login
def preferences():
    edittitle = unicode(_("Preferences"))
    if not request.form:
        form = PreferencesForm(obj=request.user)
        return jsonify({"title": edittitle, "body": render_template("edit.html", form=form, type="prefs")})
    form = PreferencesForm(request.form, obj=request.user)
    if form.validate():
        form.populate_obj(request.user)
        flash(_("Saved preferences"))
        db.session.commit()
        return jsonify({"status": "LOCALECHANGE" if request.changed_locale else ""})
    return jsonify({"status": "AGAIN", "title": edittitle, "body": render_template("edit.html", form=form, type="prefs")})

@app.route('/<workspace>/rename', methods=["POST"])
@needs_login
@gets_workspace
def workspace_rename(workspace):
    name = request.form.get("name")
    if name is not None:
        name = name.replace("/", "")
        if name in ("_flashes", "login", "logout", "_workspaces", "preferences", ""):
            name += "_"
        workspace.name = name
        db.session.commit()
    return jsonify({"name": name})

@app.route('/<workspace>/contexts', methods=["POST", "GET"])
@needs_login
@gets_workspace
def workspace_contexts(workspace):
    if request.method == "GET":
        return jsonify({"data": [{"name": context.name, "id": context.id} for context in workspace.contexts],
                        "seqid": workspace.seqid})
    else:
        action = request.form.get("action")
        context = Context.query.filter_by(id=int(request.form.get("id")), workspace=workspace).first()
        edittitle = unicode(_("Edit context") if context else _("Add context"))
        if action == "move":
            previous_context = Context.query.filter_by(id=int(request.form.get("previous_id")), workspace=workspace).first()
            if previous_context is None:
                new_index = 0
            else:
                new_index = workspace.contexts.index(previous_context) + 1
            workspace.contexts.pop(workspace.contexts.index(context))
            workspace.contexts.insert(new_index, context)
        elif action == "move_task":
            task = Task.query.filter_by(id=int(request.form.get("task_id"))).first()
            if task.context.workspace != workspace:
                return render_error(_("Wrong workspace"), True)
            task.context.tasks.remove(task)
            context.tasks.insert(0, task)
        elif action == "editinitial":
            form = ContextForm(obj=context)
            return jsonify({"title": edittitle, "body": render_template("edit.html", form=form, type="context")})
        elif action == "edit":
            form = ContextForm(request.form, obj=context)
            try:
                if form.validate():
                    if context is None:
                        context = Context(form["name"].data)
                        workspace.contexts.append(context)
                    else:
                        form.populate_obj(context)
                    flash(_("Saved context '%s'", context.name))
                    db.session.commit()
                    return jsonify({})
            except IntegrityError:
                form["name"].errors.append(_("Duplicate name"))
            return jsonify({"status": "AGAIN", "title": edittitle, "body": render_template("edit.html", form=form, type="context")})
        elif action == "delete":
            if len(workspace.contexts) == 1:
                return render_error(_("Last context cannot be deleted"), True)
            context.delete()
            flash(_("Deleted context '%s'", context.name))
        else:
            return jsonify({"error": "Invalid action"})
        db.session.commit()
        return jsonify({"result": "OK"})


@app.route('/<workspace>/tasks', methods=["POST"])
@needs_login
@gets_workspace
def workspace_tasks(workspace):
    action = request.form.get("action", None)
    if action is None:
        tagexcl = bool(int(request.form.get("tagexcl")))
        timefilter = request.form.get("timefilter")
        kindfilter = request.form.get("kindfilter")
        today = date.today()
        tomorrow = today + timedelta(days=1)
        dayaftertomorrow = tomorrow + timedelta(days=1)
        inaweek = tomorrow + timedelta(days=7)
        if kindfilter == "flttodo":
            def fltr(item):
                return not item.completed and not (item.recur_procedure or item.recur_data)
        elif kindfilter == "fltdone":
            def fltr(item):
                return item.completed
        elif kindfilter == "fltinvisible":
            def fltr(item):
                return not item.completed and not (item.recur_procedure or item.recur_data)
        elif kindfilter == "flttmpl":
            def fltr(item):
                return not item.completed and (item.recur_procedure or item.recur_data)

        if timefilter == "fltall":
            def fltr2(item):
                return (item.visible_from is not None and item.visible_from > today) if kindfilter == "fltinvisible" else (item.visible_from is None or item.visible_from <= today)
        elif timefilter == "flttoday":
            def fltr2(item):
                return not item.completed and (item.due is None or item.due < tomorrow) and (item.visible_from is None or item.visible_from < tomorrow)
        elif timefilter == "fltplus1":
            def fltr2(item):
                return not item.completed and (item.due is None or item.due < dayaftertomorrow) and (item.visible_from is None or item.visible_from < dayaftertomorrow)
        elif timefilter == "fltplus7":
            def fltr2(item):
                return not item.completed and (item.due is None or item.due < inaweek) and (item.visible_from is None or item.visible_from < inaweek)
        elif timefilter == "fltnodate":
            def fltr2(item):
                return not item.completed and not item.due and (item.visible_from is None or item.visible_from < tomorrow)
        else:
            return render_error(_("Invalid filter name."), True)
        context = Context.query.filter_by(id=int(request.form.get("selected_context")), workspace=workspace).first()
        tags = set(Tag.query.filter_by(id=int(key), workspace=workspace).first() for key in request.form.getlist("selected_tags[]"))
        func = tags.__ge__ if tagexcl else lambda tasktags: not tags or (tags & tasktags)
        return jsonify({"data": [{"name": task.summary, "id": task.id, "due_marker": task.due_marker, "is_recurring": task.master_task is not None,
                                  "body": markdown.markdown(task.description, safe_mode="escape"), "completion_time": task.completion_time.isoformat() if task.completion_time else None,
                                  "completed": task.completed, "master_task_id": task.master_task.id if task.master_task is not None else None,
                                  "tags": [{"name": tag.name, "id": tag.id} for tag in task.tags]} for task in context.tasks
                                            if fltr(task) and fltr2(task) and func(set(task.tags))],
                        "seqid": workspace.seqid})
    else:
        if action == "create":
            context = Context.query.filter_by(id=int(request.form.get("selected_context")), workspace=workspace).first()
            assert context is not None
            summary = request.form.get("summary") + " "
            tags = []

            if ":" in summary:
                contextname, suffix = summary.split(":", 1)
                newcontext = Context.query.filter_by(name=contextname, workspace=workspace).first()
                if newcontext is not None:
                    context = newcontext
                    summary = suffix.lstrip()
            if "#" in summary:
                for tag in Tag.query.filter_by(workspace=workspace).all():
                    search_for = ("#%s " % (tag.name, ))
                    if search_for in summary:
                        tags.append(tag)
                        summary = summary.replace(search_for, "")
            summary = summary.rstrip()

            task = Task(summary, "", tags=tags)
            context.tasks.insert(0, task)
            db.session.add(task)
            flash(_("Created task '%s'", task.summary))
            db.session.commit()
            return jsonify({})
        elif action == "typeahead":
            items = []
            prefix = request.form.get("summary")
            if " #" in prefix:
                start, end = prefix.rsplit(" #", 1)
                for tag in Tag.query.filter_by(workspace=workspace).all():
                    if tag.name.lower().startswith(end.lower()) and " #%s " % (tag.name, ) not in (prefix + " "):
                        items.append("%s #%s" % (start, tag.name))
            elif ":" not in prefix and prefix:
                for context in Context.query.filter_by(workspace=workspace).all():
                    if context.name.lower().startswith(prefix.lower()):
                        items.append("%s: " % (context.name, ))
            return jsonify({"list": items})

        task = Task.query.filter_by(id=int(request.form.get("id"))).first()
        if task.context.workspace != workspace:
            return render_error(_("Wrong workspace"), True)
        if action == "move":
            context = task.context
            previous_task = Task.query.filter_by(id=int(request.form.get("previous_id"))).first()
            if previous_task is None:
                new_index = 0
            else:
                if previous_task.context.workspace != workspace:
                    return render_error(_("Wrong workspace"), True)
                new_index = context.tasks.index(previous_task) + 1
            context.tasks.pop(context.tasks.index(task))
            context.tasks.insert(new_index, task)
            db.session.commit()
            return jsonify({})
        query = Context.query.filter_by(workspace=workspace)
        edittitle = unicode(_("Edit task") if task else _("Add task"))
        if action == "editinitial":
            form = TaskForm(obj=task)
            form.context.query = query
            return jsonify({"title": edittitle, "body": render_template("edit.html", form=form, type="task", task=task)})
        elif action == "edit":
            form = TaskForm(request.form, obj=task)
            form.context.query = query
            if form.validate():
                form.populate_obj(task)
                if task.recur_reschedule_this:
                    task.reschedule()
                flash(_("Saved task '%s'", task.summary))
                db.session.commit()
                return jsonify({})
            return jsonify({"status": "AGAIN", "title": edittitle, "body": render_template("edit.html", form=form, type="task", task=task)})
        elif action == "delete":
            flash(_("Deleted task '%s'", task.summary))
            task.delete()
            db.session.commit()
            return jsonify({})
        elif action == "remove_tag":
            tag = Tag.query.filter_by(id=int(request.form.get("tag_id")), workspace=workspace).first()
            task.tags.remove(tag)
            db.session.commit()
            return jsonify({})
        elif action == "add_tag":
            tag = Tag.query.filter_by(id=int(request.form.get("tag_id")), workspace=workspace).first()
            task.tags.append(tag)
            db.session.commit()
            return jsonify({})
        elif action == "togglecomplete":
            task.completed = not task.completed
            flash(_("Marked task '%s' as completed", (task.summary, )))
            db.session.commit()
            return jsonify({})
        elif action == "postpone":
            earliest_due = date.today()
            if not task.due:
                task_due = earliest_due
                flash(_("Set due date to tomorrow"))
            else:
                task_due = task.due
                flash(_("Postponed task by one day"))
            task.due = max(earliest_due, task_due + timedelta(days=1))
            db.session.commit()
            return jsonify({})

        return render_error(_("Unknown action"), True)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get("username") is not None:
        flash(_("You are already logged in!"))
        db.session.commit()
        return redirect(url_for("index"))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if not user or user.password != get_password_hash(user.salt, password):
            return render_error(_("Invalid credentials."))
        session['username'] = username
        if request.args.get('url'):
            return redirect(request.args['url'].encode("ascii"))
        else:
            return redirect(url_for('index'))
    return render_template("login.html", last_flash_id=get_last_flash_id())


@app.route('/logout')
@needs_login
def logout():
    session.pop('username', None)
    return redirect(url_for("index"))

@app.route('/_flashes')
def flashes():
    last_id = int(request.args['id'])
    flashes = FlashMessage.query.filter(db.and_(FlashMessage.id > last_id, FlashMessage.owner == request.user)).all()
    return jsonify({"data": [{"text": x.text, "id": x.id} for x in flashes]})

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static', 'img'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.before_request
def setup_user():
    request.workspace = None
    request.changed_locale = False
    if "username" in session:
        request.user = User.query.filter_by(username=session["username"]).first()
    else:
        request.user = None

# setup webassets

def minifier(_in, out, **kw):
    out.write(minify(_in.read(), mangle=True))
def minifier_strong(_in, out, **kw):
    out.write(minify(_in.read(), mangle=True, mangle_toplevel=True))
def copyrighter_lib(_in, out, **kw):
    out.write("""/* Webasset generated for DTG. Copyright (c) 2012 The DTG Team. Licensed under AGPLv3.
See https://bitbucket.org/xoraxax/dtg/raw/tip/LICENSE for details.
Portions copyright Rodney Rehm (Parts licensed under GPL v3)
Portions copyright 2012 Twitter, Inc. (Parts licensed under Apache License v2.0)
Portions copyright (c) 2009-2012 Hunter Perrin (Parts licensed under GPLv3)
Portions copyright (c) jQuery UI Team (Parts licensed under MIT license)
Portions copyright (c) 2011, Benjamin Arthur Lupton (Parts licensed under BSD license)
Portions copyright 2012 Stefan Petre, Andrew Rowls (Parts licensed under Apache License v2.0)
*/
""")
    shutil.copyfileobj(_in, out)
def copyrighter_app(_in, out, **kw):
    out.write("""/* Webasset generated for DTG. Copyright (c) 2012 The DTG Team. Licensed under AGPLv3.
See https://bitbucket.org/xoraxax/dtg/raw/tip/LICENSE for details.
*/
""")
    shutil.copyfileobj(_in, out)

assets = Environment(app)
assets.register('js_lib', Bundle(*["js/" + name for name in (
                    "jquery-1.7.2.js", "jquery-ui-1.8.21.custom.js", "jquery.history.js",
                    "bootstrap.js", "jquery.pnotify.js", # "jquery.hotkeys.js",
                    "URI.js", "bootstrap-datepicker.js", "locales/bootstrap-datepicker.de.js")],
                    filters=(minifier_strong, copyrighter_lib), output="gen/packed_lib.js"))
assets.register('js_app', Bundle("js/app.js", filters=(minifier, copyrighter_app), output="gen/packed_app.js"))

css_all = Bundle(*["css/" + name for name in (
                    "bootstrap.css", "bootstrap-responsive.css", "style.css",
                    "cupertino/jquery-ui-1.8.21.custom.css", "jquery.pnotify.default.css",
                    "datepicker.css")], filters=("cssrewrite", "cssmin"), output="gen/packed.css")
assets.register("css_all", css_all)


# command line code

def add_user(username, password):
    u = User(username, password)
    db.session.add(u)
    db.session.commit()
    return "User %r created successfully" % (username, )

def del_user(username):
    u = User.query.filter_by(username=username).first()
    if u is None:
        return "User %r not found" % (username, )
    u.delete()
    db.session.commit()
    return "User %r successfully deleted" % (username, )

def change_pwd(username, password):
    u = User.query.filter_by(username=username).first()
    if u is None:
        return "User %r not found" % (username, )
    u.set_password(password)
    db.session.commit()
    return "User %r has a new password now" % (username, )

