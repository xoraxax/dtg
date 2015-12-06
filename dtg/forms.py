# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

from datetime import date
from wtforms import ValidationError
from wtforms import widgets
from wtforms.validators import EqualTo, Required
from wtforms.fields import TextField, SelectField, Label, PasswordField, BooleanField, TextAreaField, DateField
from wtforms.widgets import TextInput
from wtforms.ext.sqlalchemy.orm import model_form, ModelConverter, converts
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from flask.ext.babel import get_locale

from dtg.transtools import locale_choices
from dtg.transtools import idem_gettext as _


# monkeypatch compatible i18n support into WTForms
def __call__(self, text=None, **kwargs):
    from dtg.transtools import _
    kwargs['for'] = self.field_id
    attributes = widgets.html_params(**kwargs)
    return widgets.HTMLString(u'<label %s>%s</label>' % (attributes, unicode(_(text or self.text))))
Label.__call__ = __call__


def make_global(cls):
    globals()[cls.__name__] = cls
    return cls


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

class IfSetRequiresOtherField(object):
    def __init__(self, fieldname, message):
        self.fieldname = fieldname
        self.message = message

    def __call__(self, form, field):
        other_field = form[self.fieldname]
        if field.data and not other_field.data:
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
    from dtg.model import Task
    t = Task("", "")
    t.recur_data = field.data
    try:
        t.rrule
    except RecurInfoException, e:
        raise ValidationError(_(e.message[0], e.message[1]))

def is_recur_proc(form, field):
    from dtg.model import Task
    t = Task("", "")
    t.recur_procedure = field.data
    try:
        t.rrule
    except RecurInfoException, e:
        raise ValidationError(_(e.args[0][0], e.args[0][1]))

class DTGDateField(DateField):

    def process_formdata(self, valuelist):
        if valuelist and valuelist[0]: # Bug in wtforms
            DateField.process_formdata(self, valuelist)


class DTGModelConverter(ModelConverter):

    @converts('Date')
    def conv_Date(self, field_args, **extra):
        return DTGDateField(**field_args)

    @converts('Boolean')
    def conv_Boolean(self, field_args, **extra):
        field_args['validators'] = []  # Bug in wtforms, a boolean might be required!?
        return BooleanField(**field_args)

    @converts('types.Text', 'UnicodeText', 'types.LargeBinary', 'types.Binary', 'sql.sqltypes.Text')
    def conv_Text(self, field_args, **extra):
        field_args['validators'] = []  # Bug in wtforms
        self._string_common(field_args=field_args, **extra)
        return TextAreaField(**field_args)

to_exclude = ["id", "position", "master_task_id", "context_id", "recur_last",
              "created_datetime", "completion_time", "slaves", "master_task"]

def generate_forms(app, db):
    global _
    from dtg.model import Task, Context, Tag, User
    with app.app_context():
        def model_form_type(*args, **kwargs):
            kwargs['db_session'] = db.session
            kwargs['converter'] = DTGModelConverter(None)
            return model_form(*args, **kwargs)
        TaskFormBase = model_form_type(Task, exclude=to_exclude,
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
                        "validators": [is_recur_info, ExclusiveWith("recur_procedure", _("Please enter either the easy or the expert string, but not both.")), IfSetRequiresOtherField("due", _("Please set a due date before setting the recurrence interval!"))],
                        },
                    "recur_procedure": {
                        "label": _("Recurrence procedure"),
                        "description": _("Here you may use your English words to describe the recurrence pattern. Supported examples include 'Every month', 'Every 3 months', 'Every Monday', 'Every 3 years', 'Every 42 weeks'."),
                        "validators": [is_recur_proc, ExclusiveWith("recur_data", _("Please enter either the easy or the expert string, but not both.")), IfSetRequiresOtherField("due", _("Please set a due date before setting the recurrence interval!"))],
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

        @make_global
        class TaskForm(TaskFormBase):
            context = QuerySelectField(get_label="name")

        TaskForm.context.creation_counter = -1

        ContextForm = make_global(model_form_type(Context, exclude=["id", "position", "workspace_id", "created_datetime",
                                                                    "tasks", "workspace"]))
        TagForm = make_global(model_form_type(Tag, exclude=["id", "position", "workspace_id",
                                                            "created_datetime", "tasks", "workspace"]))
        PreferencesBaseForm = make_global(model_form_type(User, exclude=["id", "username", "password", "salt", "created_datetime", "feature_idx", "tutorial_idx", "workspaces"], field_args={
            "do_notify": {
                "label": _("Send nightly mail notifications"),
                "validators": [RequireField("email", _("You need to supply your e-mail address to use this feature!"))],
                },
            "email": {
                "label": _("E-mail"),
            },
        }))
        @make_global
        class PreferencesForm(PreferencesBaseForm):
            locale = SelectField(_("Language"), choices=locale_choices)
            pwd1 = PasswordField(_('New Password'), [EqualTo('pwd2', message=_('Passwords must match'))])
            pwd2  = PasswordField(_('Repeat Password'))

        from dtg.transtools import _
