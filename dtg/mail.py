# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText


SMTPException = smtplib.SMTPException
SMTPRecipientsRefused = smtplib.SMTPRecipientsRefused


class MailAttachment(object):
    def __init__(self, cid, blob, subtype):
        self.cid = cid
        self.blob = blob
        self.subtype = subtype


def construct_html_message(subject, from_addr, to_addr, body_html, attachments):
    msg_root = MIMEMultipart('related')
    msg_root['Subject'] = subject
    msg_root['From'] = from_addr
    msg_root['To'] = to_addr
    msg_root.preamble = 'This is a multi-part message in MIME format.'
    
    msg_alternative = MIMEMultipart('alternative')
    msg_root.attach(msg_alternative)
    msg_alternative.attach(MIMEText('You need an HTML compliant MUA to read this mail.'))
    msg_alternative.attach(MIMEText(body_html, 'html'))
    
    for att in attachments:
        mime_att = MIMEText(att.blob, att.subtype)
        mime_att.add_header('Content-ID', '<%s>' % att.cid)
        msg_root.attach(mime_att)
    
    return msg_root


def send_html_message(subject, from_addr, to_addr, body_html, atts, server):
    msg = construct_html_message(subject, from_addr, to_addr, body_html, atts)

    smtp = smtplib.SMTP()
    smtp.connect(server)
    smtp.sendmail(from_addr, to_addr, msg.as_string())
    smtp.quit()

