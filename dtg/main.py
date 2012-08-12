#!/usr/bin/env python
# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

import optparse
import random
import sys
from getpass import getpass

from paste.exceptions.errormiddleware import ErrorMiddleware


def main():
    parser = optparse.OptionParser()
    parser.add_option('-l', '--location', dest='location', action='store', type="string",
            help='path prefix to store the database in', default="dtg_")
    parser.add_option('-i', '--server-ip', dest='server_ip', action='store', type="string",
            help='ip/hostname to run the server on', default="127.0.0.1")
    parser.add_option('-p', '--server-port', dest='server_port', action='store',
            type="int", help='port to run the server on', default=5005)
    parser.add_option('-e', '--email', dest='email', action='store',
            type="string", help='e-mail address of the admin', default=None)
    parser.add_option('-D', '--debug', dest='debug', action='store_true',
            help='Debug mode', default=False)
    parser.add_option('-M', '--allow-migrations', dest='migrate', action='store_true',
            help='Allow DB migrations. Only use it with backups :-)', default=False)
    parser.add_option('--add-user', dest='adduser', action='store',
            type="string", help="Username to add, password will be asked for", default="")
    parser.add_option('--del-user', dest='deluser', action='store',
            type="string", help="Username to delete", default="")
    parser.add_option('--change-pwd', dest='changepwd', action='store',
            type="string", help="Username to change password of", default="")

    options, args = parser.parse_args()
    if args:
        parser.error("don't know what to do with additional arguments")

    # HACK! :)

    sys.dtg_db_path = lambda x: "sqlite:///" + os.path.abspath(options.location + x + ".db")
    sys.dtg_do_upgrade = options.migrate
    sys.dtg_debug = options.debug

    from dtg.webapp import app, add_user, del_user, change_pwd
    if options.debug:
        app.secret_key = "insecure"

    if options.adduser or options.changepwd:
        password, password2 = getpass(), getpass("Password, again: ")
        if password != password2:
            print "Passwords do not match"
            return
    if options.adduser:
        print add_user(options.adduser, password)
        return
    if options.deluser:
        print del_user(options.deluser)
        return
    if options.changepwd:
        print change_pwd(options.changepwd, password)
        return

    #app.wsgi_app = GzipMiddleware(app.wsgi_app)
    if options.email is not None:
        kwargs = dict(error_email=options.email, from_address=options.email, smtp_server="localhost")
    else:
        kwargs = {}
    app.wsgi_app = ErrorMiddleware(app.wsgi_app, **kwargs)
    app.run(host=options.server_ip, port=options.server_port, threaded=True, use_reloader=True, passthrough_errors=True)


if __name__ == '__main__':
    main()

