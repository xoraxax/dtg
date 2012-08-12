# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

import random
from datetime import datetime, timedelta, time, date
from urllib2 import HTTPError
from email.parser import Parser
from email.header import decode_header, Header
from cStringIO import StringIO

from twisted.mail import imap4
from twisted.mail.smtp import rfc822date
from zope.interface import implements
from twisted.internet import defer
from twisted.cred import checkers, credentials, error as credError
from urlparse import urlparse

from dtgimapd.dtgbinding import ProxyException


MAILBOXDELIMITER = "."


class DTGUserAccount(imap4.MemoryAccount):
    def __init__(self, proxy):
        self.proxy = proxy
        imap4.MemoryAccount.__init__(self, "DTG")
        self.addMailbox(r"Sent", DTGImapMailboxSent(proxy))
        for item in proxy.contexts()["data"]:
            if proxy.state.first_context is None:
                proxy.state.first_context = item["id"]
            name = item["name"]
            self.addMailbox(name, DTGImapMailbox(name, item["id"], proxy))
        proxy.state.account = self

    def listMailboxes(self, ref, wildcard):
        ref = self._inferiorNames(ref.upper())
        wildcard = imap4.wildcardToRegexp(wildcard, '/')
        return [(self.mailboxes[i].folder, self.mailboxes[i]) for i in ref if wildcard.match(i)]

    def select(self, name, readwrite=1):
        mbox = self.mailboxes.get(name.upper())
        if mbox is not None:
            mbox.refresh()
        return mbox

    def create(self, path):
        return False

    def isSubscribed(self, name):
        return True

    def logout(self):
        pass


class DTGImapMailbox(object):
    implements(imap4.IMailbox)

    def __init__(self, folder, id, proxy):
        self.folder = folder
        self.id = id
        self.proxy = proxy
        self.listeners = []
        self.tasks = None
        self._uidval = None

    def refresh(self):
        self.tasks = self.remote_tasks
        self._uidval = random.randint(0, 2**30)

    @property
    def remote_tasks(self):
        tasks = self.proxy.tasks(selected_context=str(self.id), tagexcl="0", kindfilter="flttodo", timefilter="fltall")["data"]
        today = datetime.combine(date.today(), time(0))
        for i, task in enumerate(tasks, start=1):
            task["position"] = i
            task["sort_time"] = (today + timedelta(minutes=i)).timetuple()
        tasks.sort(key=lambda x: x["id"])
        return tasks

    def getHierarchicalDelimiter(self):
        return MAILBOXDELIMITER

    def getFlags(self):
        flags = ['\Deleted']
        return flags

    def getMessageCount(self):
        return len(self.tasks)

    def getRecentCount(self):
        return len(self.tasks)

    def getUnseenCount(self):
        return self.getRecentCount()

    def isWriteable(self):
        return False

    def getUIDValidity(self):
        return self._uidval

    def getUID(self, messageNum):
        if 0 < messageNum <= len(self.tasks):
            return self.tasks[messageNum - 1]["id"]
        raise imap4.MailboxException("Invalid message number")

    def getUIDNext(self):
        raise imap4.MailboxException("Not implemented")

    def fetch(self, messages, uid):
        retval = []
        for i, task in enumerate(self.tasks, start=1):
            search_for = task["id"] if uid else i
            if messages.last is messages._empty:
                messages.last = 2**31
            if search_for in messages:
                retval.append((i, DTGImapMessage(task, self.proxy)))
        return retval

    def addListener(self, listener):
        self.listeners.append(listener)
        return True

    def removeListener(self, listener):
        self.listeners.remove(listener)
        return True

    def requestStatus(self, names):
        if "UIDNEXT" in names:
            names.remove("UIDNEXT")
        return imap4.statusRequestHelper(self, names)

    def addMessage(self, msg, flags=None, date=None):
        raise imap4.MailboxException("Not implemented")
        headers = Parser().parse(msg)
        try:
            uid, hostname = headers["message-id"].replace("<", "").replace(">", "").split("@")
        except Exception, e:
            return defer.fail(e)
        if hostname != self.proxy.hostname:
            return defer.fail("Invalid hostname in references header line")
        res = self.proxy.contexts(action="move_task", id=str(self.id), task_id=uid)
        self.refresh()
        return defer.succeed(None)

    def store(self, messages, flags, mode, uid):
        res = {}
        for i, task in enumerate(self.tasks, start=1):
            if task["completed"]:
                continue
            search_for = task["id"] if uid else i
            if messages.last is messages._empty:
                messages.last = 2**31
            if search_for in messages:
                if r'\Deleted' in flags:
                    deleted = True
                    if mode == -1:
                        deleted = False
                    if deleted != task["completed"]:
                        self.proxy.tasks(action="togglecompleted", id=str(task["id"]))
                    res[i] = [r"\Deleted" if deleted else ""]
                    task["completed"] = deleted
        return res

    def expunge(self):
        pass

    def destroy(self):
        raise imap4.MailboxException("Not implemented")


class DTGImapMailboxSent(object):
    implements(imap4.IMailbox)

    def __init__(self, proxy):
        self.proxy = proxy
        self.listeners = []
        self.folder = "Sent"

    def refresh(self):
        pass

    def getHierarchicalDelimiter(self):
        return MAILBOXDELIMITER

    def getFlags(self):
        return []

    def getMessageCount(self):
        return 0

    def getRecentCount(self):
        return 0

    def getUnseenCount(self):
        return 0

    def isWriteable(self):
        return True

    def getUIDValidity(self):
        return 0

    def getUID(self, messageNum):
        raise imap4.MailboxException("Not implemented")

    def getUIDNext(self):
        raise imap4.MailboxException("Not implemented")

    def fetch(self, messages, uid):
        raise StopIteration

    def addListener(self, listener):
        self.listeners.append(listener)
        return True

    def removeListener(self, listener):
        self.listeners.remove(listener)
        return True

    def requestStatus(self, names):
        return imap4.statusRequestHelper(self, names.replace("UIDNEXT", ""))

    def addMessage(self, msg, flags=None, date=None):
        headers = Parser().parse(msg)
        context_id = None
        parts = decode_header(headers["subject"])
        new_parts = []
        for msg, enc in parts:
            new_parts.append(msg.decode(enc or "latin1"))
        subject = "".join(new_parts)
        if ":" in subject:
            contextname, summary = subject.split(":", 1)
            contextname = contextname.strip()
            for item in self.proxy.contexts()["data"]:
                if item["name"] == contextname:
                    context_id = item["id"]
                    break
        else:
            summary = subject
        if context_id is None:
            context_id = self.proxy.state.first_context
        res = self.proxy.tasks(action="create", summary=summary, selected_context=str(context_id))
        return defer.succeed(None)

    def store(self, messageSet, flags, mode, uid):
        pass

    def expunge(self):
        pass

    def destroy(self):
        raise imap4.MailboxException("Not implemented")


class DTGImapMessage(object):
    implements(imap4.IMessage)

    def __init__(self, task, proxy):
        self.proxy = proxy
        self.task = task
        self.compute_body()
        self.internal_date = rfc822date(self.task['sort_time'])

    def compute_body(self):
        body_tmpl = """SUMMARY: %(summary)s
   Tags: %(tags)s

"""
        self.body = body_tmpl % {"summary": self.task["name"], "tags": ", ".join(x["name"] for x in self.task["tags"])}
        if self.task["due_marker"]:
            self.body += self.task["due_marker"][1] + "\n"
        if self.task["completed"]:
            self.body += "Completed" + "\n"
        self.body = self.body.encode("utf-8")

    def getUID(self):
        return self.task['id']

    def getFlags(self):
        flags = []
        if self.task.get('completed', False):
            flags.append("\Seen")
        return flags

    def getInternalDate(self):
        return self.internal_date

    def getHeaders(self, negate, *names):
        def make_header(t):
            return Header(t).encode()

        headers = {
            "to": "DTG User <>",
            "from": make_header("DTG: %s" % (self.task["due_marker"][1] if self.task["due_marker"] else "No due date", )) + " <>",
            "date": "%s" % self.internal_date,
            "subject": make_header("%s" % self.task['name']),
            "message-id": "<%s@%s>" % (self.task["id"], self.proxy.hostname),
            "content-type": 'text/plain; charset="UTF-8"',
            "mime-version": "1.0",
        }
        if self.task["master_task_id"]:
            headers["references"] = "<%s@%s>" % (self.task["master_task_id"], self.proxy.hostname)

        return headers

    def getBodyFile(self):
        return StringIO(self.body)

    def getSize(self):
        return len(self.body)

    def isMultipart(self):
        return False

    def getSubPart(self, part):
        raise imap4.MailboxException("getSubPart not implemented")



class DTGCredentialsChecker(object):
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword, )

    def __init__(self, proxy_factory):
        self.proxy_factory = proxy_factory

    def requestAvatarId(self, credentials):
        try:
            username, workspace = credentials.username.rsplit("#", 1)
        except ValueError:
            return defer.fail(credError.UnauthorizedLogin("Invalid workspace name in username"))

        proxy = self.proxy_factory(workspace)
        if not proxy.login(username, credentials.password):
            return defer.fail(credError.UnauthorizedLogin("Bad password"))
        try:
            proxy.contexts()
        except ProxyException, e:
            return defer.fail(e)

        self.init_proxy(proxy)
        return defer.succeed(proxy)

    def init_proxy(self, proxy):
        class StateStore(object):
            def __repr__(self):
                return repr(self.__dict__)
        proxy.state = StateStore()
        proxy.state.first_context = None
        proxy.state.account = None

