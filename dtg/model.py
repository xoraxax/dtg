# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

import time
import random
import hashlib
import json
from datetime import date, datetime

from dateutil.rrule import rrule, YEARLY, WEEKLY, MONTHLY, DAILY
from sqlalchemy.ext.orderinglist import ordering_list
from sqlalchemy.types import TypeDecorator, VARCHAR
from sqlalchemy import event
from flask import request

from dtg.transtools import _
from dtg.recur import get_rrule_args, localeEnglish


APP_DB_REV = 3


class RecurInfoException(Exception):
    pass

_initialized = False

def make_global(cls):
    globals()[cls.__name__] = cls
    return cls


SALT_LENGTH = 16
def get_password_hash(salt, password):
    sha1 = hashlib.sha1()
    sha1.update(salt)
    sha1.update(password)
    return sha1.hexdigest()

def make_salt(SALT_LENGTH=SALT_LENGTH):
    data = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return "".join(data[random.randint(0, len(data) - 1)] for _ in xrange(SALT_LENGTH))

def generate_db_model(db):
    global _initialized, make_global
    assert not _initialized

    class CreationTimeMixin(object):
        created_datetime = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now())

    @make_global
    class User(CreationTimeMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String(80), unique=True)
        password = db.Column(db.String(80), nullable=False)
        salt = db.Column(db.String(SALT_LENGTH), nullable=False)
        email = db.Column(db.String(256), nullable=False)
        do_notify = db.Column(db.Boolean, nullable=False)
        locale = db.Column(db.String(64), nullable=False)

        def __init__(self, username, password, email="", do_notify=False, locale=""):
            self.username = username
            self.set_password(password)
            self.email = email
            self.do_notify = do_notify
            self.locale = locale

        def set_password(self, password):
            self.salt = make_salt()
            self.password = get_password_hash(self.salt, password)

        def __repr__(self):
            return "<User username=%r>" % (self.username, )

        def delete(self):
            for workspace in self.workspaces:
                workspace.delete()
            db.session.delete(self)

    def notice_changed_locale(target, value, oldvalue, initiator):
        try:
           req_user = request.user
        except RuntimeError:
            return
        if target is req_user and value != oldvalue:
            request.changed_locale = True
    event.listen(User.locale, 'set', notice_changed_locale)

    @make_global
    class FlashMessage(CreationTimeMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True)
        text = db.Column(db.String(1024), nullable=False)
        owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        owner = db.relationship("User", backref=db.backref("flashes", order_by=[id]))

        def __init__(self, text, owner):
            self.text = text
            self.owner = owner

    @make_global
    class Workspace(CreationTimeMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(80))
        owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
        owner = db.relationship("User", backref=db.backref("workspaces", order_by=[name]))
        seqid = db.Column(db.Integer, nullable=False, default=0)
        __table_args__ = (
            db.UniqueConstraint('owner_id', 'name'),
        )

        def __init__(self, name, owner):
            self.name = name
            self.owner = owner

        def __repr__(self):
            return "<Workspace name=%r owner=%r>" % (self.name, self.owner)

        def delete(self):
            for context in self.contexts:
                context.delete()
            for tag in self.tags:
                tag.delete()
            db.session.delete(self)

    @make_global
    class Context(CreationTimeMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True)
        position = db.Column(db.Integer, nullable=False)
        name = db.Column(db.String(255), nullable=False)
        workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False)
        workspace = db.relationship("Workspace", backref=db.backref("contexts", collection_class=ordering_list("position"), order_by=[position]))
        __table_args__ = (
            db.UniqueConstraint('workspace_id', 'name'),
        )

        def __init__(self, name):
            self.name = name
        
        def delete(self):
            for task in self.tasks:
                db.session.delete(task)
            db.session.delete(self)
    
    global tasks2tags
    tasks2tags = db.Table("tasks2tags",
            db.Column("task_id", db.Integer, db.ForeignKey("task.id"), primary_key=True),
            db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
            )

    @make_global
    class Tag(CreationTimeMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(255), nullable=False)
        position = db.Column(db.Integer, nullable=False)
        workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False)
        workspace = db.relationship("Workspace", backref=db.backref("tags", collection_class=ordering_list("position"), order_by=[position]))
        __table_args__ = (
            db.UniqueConstraint('workspace_id', 'name'),
        )

        def __init__(self, name):
            self.name = name

        def __eq__(self, other):
            return self.name == other.name and self.workspace == other.workspace

        def __hash__(self):
            return hash(str(self.workspace_id) + self.name)

        def __repr__(self):
            return "<Tag name=%r workspace=%r>" % (self.name, self.workspace)

        def delete(self):
            db.session.delete(self)

    @make_global
    class Task(CreationTimeMixin, db.Model):
        """ A task can have one of three types: single event, master task, slave task.
        A master task contains the recurrence pattern (either as a procedure or a data field) and creates many slave tasks
        as long as it is not completed yet.
        Deleting and completing a slave task whose master task is not hard-scheduled forces a new slave task to be created immediately.
        Disabling hard-scheduling for a master task creates a slave task if there is no non-completed one.
        Creating a non-hard-scheduled master task creates a slave task.
        """
        id = db.Column(db.Integer, primary_key=True)
        position = db.Column(db.Integer, nullable=False)
        summary = db.Column(db.String(255), nullable=False)
        description = db.Column(db.Text(), nullable=False)
        visible_from = db.Column(db.Date)
        due = db.Column(db.Date)
        notify = db.Column(db.Boolean, nullable=False)
        completed = db.Column(db.Boolean, nullable=False)
        context_id = db.Column(db.Integer, db.ForeignKey("context.id"), nullable=False)
        context = db.relationship("Context", backref=db.backref("tasks", collection_class=ordering_list("position"), order_by=[position]))
        master_task_id = db.Column(db.Integer, db.ForeignKey("task.id"))
        master_task = db.relationship("Task", backref=db.backref("slaves", remote_side=[id], uselist=True), remote_side=[master_task_id], uselist=False)
        tags = db.relationship('Tag', secondary=tasks2tags, backref=db.backref('tasks'), order_by=[Tag.position])
        completion_time = db.Column(db.DateTime)

        recur_data = db.Column(db.String(1024))
        recur_procedure = db.Column(db.String(256))
        recur_last = db.Column(db.Date)
        recur_hardschedule = db.Column(db.Boolean)
        recur_fields = ["interval", "setpos", "bymonth", "bymonthday", "byyearday",
                        "byweekno", "byweekday", "byeaster"]
        recur_last_arg_field = 0
        recur_reschedule_this = False

        def __init__(self, summary, description, context=None, visible_from=None, due=None, notify=True, completed=False, master_task=None, tags=None):
            self.summary = summary
            self.description = description
            if context is not None: # set via context.tasks
                self.context = context
            self.visible_from = visible_from
            self.due = due
            self.notify = notify
            self.completed = completed
            self.master_task = master_task
            if tags is None:
                self.tags = []
            else:
                self.tags = tags
       
        def create_slave_task(self, newduedate):
            if self.visible_from is None:
                visfrom = None
            else:
                visfrom = newduedate - (self.due - self.visible_from)
            task = Task(self.summary, self.description, None, visfrom, newduedate, self.notify, self.completed, self, self.tags)
            self.context.tasks.insert(0, task)
            return task

        def compute_next_date(self):
            if self.recur_last is None or not self.recur_hardschedule:
                self.recur_last = date.today()
            rrule = self.rrule
            if not rrule:
                return None
            next, next2 = rrule[:2]
            next = next.date()
            next2 = next2.date()
            if next == self.recur_last:
                next = next2
            return next

        def reschedule(self, flash=True):
            from dtg.webapp import flash
            next = self.compute_next_date()
            assert next, "Can only schedule master tasks"
            self.recur_last = next
            self.create_slave_task(next)
            if flash:
                flash(_("Rescheduled task"))

        def delete(self):
            if self.master_task and not self.master_task.recur_hardschedule:
                self.master_task.reschedule()
            db.session.delete(self)

        @property
        def recur_next(self):
            if not (self.recur_data or self.recur_procedure):
                return
            return self.compute_next_date().isoformat()

        def get_default_rrule_args(self):
            return {"dtstart": self.recur_last}

        @property
        def due_marker(self):
            if not self.due:
                return
            days = (self.due - date.today()).days
            if days < 0:
                days_text = _("Overdue for %i days", (-days, ))
                klass = "overdue"
            elif days == 0:
                days_text = _("Due today")
                klass = "duetoday"
            elif days > 0:
                if days == 1:
                    days_text = _("Due tomorrow")
                else:
                    days_text = _("Due in %i days", (days, ))
                if days > 7:
                    klass = "duefuture"
                else:
                    klass = "duesoon"

            return days, unicode(days_text), klass 

        @classmethod
        def generate_recur_data(cls, type, **data):
            retval = [type]
            for i, kwargname in enumerate(cls.recur_fields):
                value = data[kwargname]
                if i <= self.recur_last_arg_field:
                    if value is None:
                        retval.append("")
                    else:
                        retval.append(str(value))
                elif value is not None:
                    retval.append("%s=%s" % (kwargname, value))
            return ";".join(retval)

        @property
        def rrule(self):
            _ = lambda x: x
            kwargs = {}
            if self.recur_data:
                values = self.recur_data.split(";")
                if values[0] not in ("Y", "M", "W", "D"):
                    raise RecurInfoException((_("Invalid recurrence type"), {}))
                for i, value in enumerate(values[1:]):
                    if i <= self.recur_last_arg_field:
                        field_name = self.recur_fields[i]
                        kwargs[field_name] = int(value)
                    else:
                        try:
                            kwargname, value = value.split("=", 1)
                        except ValueError:
                            raise RecurInfoException((_("Invalid token '%(field)s', expected parameter name"), {"field": value}))
                        try:
                            value = json.loads(value)
                        except ValueError, e:
                            raise RecurInfoException((_("Invalid data in field '%(field)s'"), {"field": kwargname}))
                        kwargs[kwargname] = value
                kwargs.update(self.get_default_rrule_args())
                freq = {"Y": YEARLY,
                        "M": MONTHLY,
                        "W": WEEKLY,
                        "D": DAILY}[values[0]]
                return rrule(freq, **kwargs)
            elif self.recur_procedure:
                try:
                    freq, args = get_rrule_args(localeEnglish, self.recur_procedure)
                except ValueError, e:
                    raise RecurInfoException((_("Invalid recurrence procedure, see examples")))
                args.update(self.get_default_rrule_args())
                return rrule(freq, **args)

    def reschedule_on_set_completed(target, value, oldvalue, initiator):
        if value and not oldvalue and target.master_task and (not target.master_task.recur_hardschedule or
                all(t.completed for t in target.slaves)):
            target.master_task.reschedule()

    event.listen(Task.completed, 'set', reschedule_on_set_completed)
    def set_completion_time(target, value, oldvalue, initiator):
        if value:
            target.completion_time = datetime.now()
    event.listen(Task.completed, 'set', set_completion_time)

    def reschedule_on_disable_hardschedule(target, value, oldvalue, initiator):
        if not value and oldvalue is True and target.rrule and all(t.completed for t in target.slaves):
            target.reschedule()

    event.listen(Task.recur_hardschedule, 'set', reschedule_on_disable_hardschedule)

    def reschedule_on_new_recurinfo(target, value, oldvalue, initiator):
        if value and value != oldvalue:
            target.recur_reschedule_this = True # defer rescheduling
    event.listen(Task.recur_procedure, 'set', reschedule_on_new_recurinfo)
    event.listen(Task.recur_data, 'set', reschedule_on_new_recurinfo)
    
    @make_global
    class SystemInfo(CreationTimeMixin, db.Model):
        id = db.Column(db.Integer, primary_key=True) # ignored
        db_rev = db.Column(db.Integer, nullable=False)
        secret_app_key = db.Column(db.String(256), nullable=False)

    del make_global


def initialize_db(db):
    s = SystemInfo()
    s.db_rev = APP_DB_REV
    s.secret_app_key = make_salt(32)
    db.session.add(s)
    db.session.commit()

