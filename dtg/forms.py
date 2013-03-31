# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

from datetime import date
from wtforms import Form, ValidationError
from wtforms import widgets
from wtforms.validators import EqualTo, Required
from wtforms.fields import TextField, SelectField, Label, PasswordField
from wtforms.widgets import TextInput
from wtforms.ext.sqlalchemy.orm import model_form
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from flaskext.babel import get_locale

from dtg.model import *
from dtg.transtools import locale_choices


# monkeypatch compatible i18n support into WTForms
def __call__(self, text=None, **kwargs):
    from dtg.transtools import _
    kwargs['for'] = self.field_id
    attributes = widgets.html_params(**kwargs)
    return widgets.HTMLString(u'<label %s>%s</label>' % (attributes, unicode(_(text or self.text))))
Label.__call__ = __call__


_txtinput = TextInput()

def datepicker(*args, **kwargs):
    today = date.today()
    return _txtinput(*args, **kwargs) + """
<script type="text/javascript">
  $(function() {$('#%(id)s').datepicker({autoclose: true, weekStart: "1", date: "%(today)s", format: "%(format)s", language: "%(language)s"});});
</script>
""" % {"id": args[0].id, "today": today.isoformat(), "format": "yyyy-mm-dd", "language": get_locale().language}


class SmallerEqualThan(object):
    def __init__(self, smaller_than_fieldname, message):
        self.smaller_than_fieldname = smaller_than_fieldname
        self.message = message

    def __call__(self, form, field):
        other_field = form[self.smaller_than_fieldname]
        if field.data is not None and other_field.data is not None and not field.data <= other_field.data:
            raise ValidationError(_(self.message, {"otherfield": other_field.label}))

class ExclusiveWith(object):
    def __init__(self, fieldname, message):
        self.fieldname = fieldname
        self.message = message

    def __call__(self, form, field):
        other_field = form[self.fieldname]
        if other_field.data and field.data:
            raise ValidationError(_(self.message))

class RequireField(object):
    def __init__(self, fieldname, message):
        self.fieldname = fieldname
        self.message = message

    def __call__(self, form, field):
        other_field = form[self.fieldname]
        if field.data and not other_field.data:
            raise ValidationError(_(self.message))

def is_recur_info(form, field):
    t = Task("", "")
    t.recur_data = field.data
    try:
        t.rrule
    except RecurInfoException, e:
        raise ValidationError(_(e.message[0], e.message[1]))

def is_recur_proc(form, field):
    t = Task("", "")
    t.recur_procedure = field.data
    try:
        t.rrule
    except RecurInfoException, e:
        raise ValidationError(_(e.args[0][0], e.args[0][1]))

_ = lambda x, *args: x % args
to_exclude = ["id", "position", "master_task_id", "context_id", "recur_last", "created_datetime", "completion_time"]
TaskFormBase = model_form(Task, Form, exclude=to_exclude,
        field_args={
            "visible_from": {
                "widget": datepicker,
                "validators": [SmallerEqualThan("due", _("Visible from date must be earlier than due date."))],
                "description": _("The task will be invisible until this day."),
                },
            "due": {
                "widget": datepicker,
                "description": _("Until when should the task be completed"),
                },
            "recur_hardschedule": {
                "label": _("Hard scheduling"),
                "description": _("If ticked, tasks will be rescheduled regardless of the completion. If not ticked, rescheduling happens when a task is completed."),
                },
            "recur_data": {
                "label": _("Expert scheduling code"),
                "description": _("If you are an expert, you may compose a complex code that controls the schedule of this task."),
                "validators": [is_recur_info, ExclusiveWith("recur_procedure", _("Please enter either the easy or the expert string, but not both."))],
                },
            "recur_procedure": {
                "label": _("Recurrence procedure"),
                "description": _("Here you may use your English words to describe the recurrence pattern. Supported examples include 'Every month', 'Every 3 months', 'Every Monday', 'Every 3 years', 'Every 42 weeks'."),
                "validators": [is_recur_proc, ExclusiveWith("recur_data", _("Please enter either the easy or the expert string, but not both."))],
                },
            "notify": {
                "description": _("Whether reminders should be generated for this task"),
                },
            "description": {
                "description": _("Detailed information about this task. In Markdown syntax."),
                },
            "completed": {
                "description": _("Tick here if the task has been performed."),
                }
            })
# get the field names into the gettext extractor
_("Description"), _("Visible From"), _("Due"), _("Notify"), _("Context"), _("Summary")

class TaskForm(TaskFormBase):
    context = QuerySelectField(get_label="name")

TaskForm.context.creation_counter = -1

ContextForm = model_form(Context, Form, exclude=["id", "position", "workspace_id", "created_datetime"])
TagForm = model_form(Tag, Form, exclude=["id", "position", "workspace_id", "created_datetime"])
PreferencesBaseForm = model_form(User, Form, exclude=["id", "username", "password", "salt", "created_datetime"], field_args={
    "do_notify": {
        "label": _("Send nightly mail notifications"),
        "validators": [RequireField("email", _("You need to supply your e-mail address to use this feature!"))],
        },
    "email": {
        "label": _("E-mail"),
    },
})
class PreferencesForm(PreferencesBaseForm):
    locale = SelectField(_("Language"), choices=locale_choices)
    pwd1 = PasswordField(_('New Password'), [EqualTo('pwd2', message=_('Passwords must match'))])
    pwd2  = PasswordField(_('Repeat Password'))

from dtg.transtools import _
