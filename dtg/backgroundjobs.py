# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

import traceback
from datetime import date, datetime, timedelta
from threading import Thread
from time import sleep

import markdown
from flask import render_template, request

from dtg.mail import send_html_message, MailAttachment

POLL_INTERVAL = 10 # seconds


class DailyBackgroundJob(Thread):
    def __init__(self, app, runtime):
        Thread.__init__(self)
        self.app = app
        self.last_run = None
        self.daemon = True
        self.runtime_start, self.runtime_end = runtime

    def run(self):
        is_first_run = True
        while True:
            is_suitable_time = self.runtime_start <= datetime.today().time() <= self.runtime_end
            if self.last_run is None or (is_suitable_time and self.last_run != date.today()):
                self.last_run = date.today()
                try:
                    with self.app.test_request_context():
                        self.fire(is_first_run and not is_suitable_time)
                except Exception:
                    traceback.print_exc()
                is_first_run = False
            sleep(POLL_INTERVAL)


class RecurrencePlanner(DailyBackgroundJob):
    """ This class handles the recurrence logic. Its tasks are:
         - Create new slave tasks from master tasks on a regular fashion if they are hard-scheduled
        These are not the tasks of this class
         - Create new slave tasks from master tasks upon completion of slave tasks if they are not hard-scheduled
         - Create the first slave task
    """

    def fire(self, is_first_run):
        from dtg.model import Task
        from dtg.webapp import db
        for task in Task.query.filter(db.and_(db.or_(Task.recur_procedure != None, Task.recur_data != None), Task.completed, Task.recur_hardschedule)).all():
            if task.visible_from is not None and task.compute_next_date - (task.due - task.visible_from) >= today or \
                    task.recur_last <= today:
                task.reschedule(False)
        db.session.commit()
    

class NightlyMailer(DailyBackgroundJob):
    """
    Mails the tasks to be done every night.
    """

    def fire(self, is_first_run):
        if is_first_run:
            return
        from dtg.model import User
        from dtg.transtools import _

        today = date.today()
        tomorrow = today + timedelta(days=1)

        for user in User.query.filter_by(do_notify=True).all():
            if not user.email:
                continue
            request.user = user
            for workspace in user.workspaces:
                contexts = []
                for context in workspace.contexts:
                    tasks = []
                    for task in context.tasks:
                        if not task.completed and not (task.recur_procedure or task.recur_data) and task.notify and task.due is not None and task.due < tomorrow \
                                and (task.visible_from is None or task.visible_from < tomorrow):
                            tasks.append({"name": task.summary, "id": task.id, "due_marker": task.due_marker, "is_recurring": task.master_task is not None,
                                  "body": markdown.markdown(task.description, safe_mode="escape"),
                                  "tags": ", ".join(tag.name for tag in task.tags)})
                    contexts.append({"name": context.name, "tasks": tasks})
                mail_body = render_template("mail.html", contexts=contexts, workspace_name=workspace.name)
                send_html_message(u"⌚ DTG – " + workspace.name + _(u" – Upcoming tasks"), "DTG <" + user.email + ">", user.email, mail_body, [], "localhost")

class FlashesCleaner(DailyBackgroundJob):
    """
    Removes old flashes.
    """
    def fire(self, is_first_run):
        from dtg.model import FlashMessage
        from dtg.webapp import db
        for flashmsg in FlashMessage.query.filter(FlashMessage.created_datetime < datetime.now() - timedelta(hours=4)).all():
            db.session.delete(flashmsg)
        db.session.commit()

JOBS = [RecurrencePlanner, NightlyMailer, FlashesCleaner]

