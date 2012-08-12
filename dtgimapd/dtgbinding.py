# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

import json
from urllib import quote_plus, quote
from urllib2 import urlopen, Request, build_opener, BaseHandler, HTTPCookieProcessor

import html5lib


TIMEOUT = 10

class ProxyException(Exception):
    pass

def urlencstr(s):
    return quote_plus(s.encode("utf-8"))

def urlencstr_noplus(s):
    return quote(s.encode("utf-8"))


def urlencode(query):
    query = query.items()

    l = []
    for k, v in query:
        k = urlencstr(k)
        if isinstance(v, str):
            v = quote_plus(v)
            l.append(k + '=' + v)
        elif isinstance(v, unicode):
            v = urlencstr(v)
            l.append(k + '=' + v)
        else:
            for elt in v:
                l.append(k + '=' + urlencstr(elt))
    return '&'.join(l)


class DTGProxy(object):
    def __init__(self, base_url, hostname, workspace):
        if not base_url.endswith("/"):
            base_url += "/"
        self.base_url = base_url
        self.hostname = hostname

        self._workspace = urlencstr_noplus(workspace)
        self.workspacename = workspace
        self.opener = build_opener(HTTPCookieProcessor)

    def login(self, username, password):
        f = self.opener.open(self.base_url + "login", urlencode({"username": username, "password": password}))
        return "newworkspaceform" in f.read()

    def __getattr__(self, methodname):
        return DTGProxyMethod(self, methodname)


class DTGProxyMethod(object):
    def __init__(self, dtg_proxy, methodname):
        self.dtg_proxy = dtg_proxy
        self.methodname = methodname

    def __call__(self, **kwargs):
        url = "%s%s/%s" % (self.dtg_proxy.base_url, self.dtg_proxy._workspace, urlencstr_noplus(self.methodname))
        if not kwargs:
            data = None
        else:
            data = urlencode(kwargs)
        req = Request(url, data)
        f = self.dtg_proxy.opener.open(req)
        datastr = f.read()
        try:
            data = json.loads(datastr)
        except ValueError:
            p = html5lib.HTMLParser(tree=html5lib.treebuilders.getTreeBuilder("lxml"))
            tree = p.parse(datastr)
            try:
                error = tree.xpath("//html:strong/following-sibling::text()", namespaces={'html': 'http://www.w3.org/1999/xhtml'})[0].strip()
            except (ValueError, IndexError):
                raise ProxyException("Unknown error")
            raise ProxyException(error)
        return data

