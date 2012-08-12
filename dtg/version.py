# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################
# the following code is partly copyrighted by the PyPy Team
# License: MIT

import os
import sys
from subprocess import Popen, PIPE


__version__ = "?"

root = os.path.abspath(os.path.join(os.path.dirname(sys.modules[__name__].__file__), ".."))
err = None

if not os.path.isdir(os.path.join(root, '.hg')):
    err = "ENOENT"
else:
    env = dict(os.environ)
    # get Mercurial into scripting mode
    env['HGPLAIN'] = '1'
    # disable user configuration, extensions, etc.
    env['HGRCPATH'] = os.devnull

    try:
        p = Popen(["hg", 'version', '-q'],
                  stdout=PIPE, stderr=PIPE, env=env)
    except OSError, e:
        err = "OsError"
    else:
        if not p.stdout.read().startswith('Mercurial Distributed SCM'):
            err = "WrongCommand"
        else:
            p = Popen(["hg", 'id', '-i', root],
                      stdout=PIPE, stderr=PIPE, env=env)
            __version__ = p.stdout.read().strip()
            err = p.stderr.read()
            if p.wait() != 0:
                __version__ = '?'

if err:
    __version__ = "%s (%s)" % (__version__, err)

