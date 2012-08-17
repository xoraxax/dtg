# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

import os
import sys
import optparse

from twisted.mail import imap4
from twisted.internet import reactor, defer, protocol
from twisted.cred import portal
from zope.interface import implements
from OpenSSL import SSL
from twisted.internet import ssl

from dtgimapd.dtg2imap import DTGUserAccount, DTGCredentialsChecker
from dtgimapd.dtgbinding import DTGProxy


class ReactorSSLContext(ssl.ContextFactory):
    def __init__(self, certfile, privkeyfile, certpass):
        self.keyfile = privkeyfile
        self.certfile = certfile
        self.privkey_pass = certpass
        if not os.path.exists(self.keyfile) or not os.path.exists(self.certfile):
            raise ValueError('Missing Certificate, please generate valid certs')

    def getContext(self):
        myContext = SSL.Context(SSL.TLSv1_METHOD)
        myContext.set_passwd_cb(lambda x, y, z: self.privkey_pass)
        myContext.use_privatekey_file(self.keyfile)
        myContext.use_certificate_file(self.certfile)
        return myContext


class MailUserRealm(object):
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if imap4.IAccount in interfaces:
            avatar = DTGUserAccount(avatarId)
            logout = avatar.logout
            return defer.succeed((imap4.IAccount, avatar, logout))
        raise KeyError("None of the requested interfaces is supported")


class IMAPServerProtocol(imap4.IMAP4Server):
    debug = False
    instrumented = False

    def capabilities(self):
        cap = imap4.IMAP4Server.capabilities(self)
        del cap["IDLE"]
        return cap

    def lineReceived(self, line):
        if self.debug and not self.instrumented:
            self.instrumented = True
            foo = self.transport.write
            foo2 = self.transport.writeSequence
            self.transport.write = lambda *args, **kwargs: [sys.stdout.write('SERVER: ' + args[0]), foo(*args, **kwargs)][1]
            self.transport.writeSequence = lambda *args, **kwargs: [sys.stdout.write('SERVER: ' + repr(args[0]) + "\n"), foo2(*args, **kwargs)][1]
        if self.debug:
            print "CLIENT:", line
        imap4.IMAP4Server.lineReceived(self, line)

    def sendLine(self, line):
        imap4.IMAP4Server.sendLine(self, line)


class IMAPFactory(protocol.Factory):
    protocol = IMAPServerProtocol
    portal = None # placeholder
    context_factory = None # placeholder

    def buildProtocol(self, address):
        p = self.protocol(contextFactory=self.context_factory)
        p.portal = self.portal
        p.factory = self
        return p


if __name__ == "__main__":
    parser = optparse.OptionParser(usage="usage: %prog [options] DTGURL HOSTNAME")
    parser.add_option('-i', '--server-ip', dest='server_ip', action='store', type="string",
            help='ip/hostname to run the server on', default="::")
    parser.add_option('-p', '--server-port', dest='server_port', action='store',
            type="int", help='port to run the server on', default=1143)

    parser.add_option('-c', '--cert-file', dest='certfile', action='store',
            type="string", help='The file name of the certificate', default=None)
    parser.add_option('-k', '--priv-key-file', dest='privkeyfile', action='store',
            type="string", help='The file name of the private key', default=None)
    parser.add_option('-s', '--cert-pass', dest='certpass', action='store',
            type="string", help='The secret password for the key file', default="")

    options, args = parser.parse_args()
    if len(args) != 2:
        parser.error("Please supply exactly two arguments.")
    if options.certfile is None or options.privkeyfile is None:
        parser.error("Please supply two TLS options: -c and -k")
    url, hostname = args

    portal = portal.Portal(MailUserRealm())
    portal.registerChecker(DTGCredentialsChecker(lambda workspace: DTGProxy(url, hostname, workspace)))

    ssl_context = ReactorSSLContext(options.certfile, options.privkeyfile, options.certpass)
    factory = IMAPFactory()
    factory.context_factory = ssl_context
    factory.portal = portal

    reactor.listenTCP(options.server_port, factory, interface=options.server_ip)
    print "RUNNING"
    reactor.run()

