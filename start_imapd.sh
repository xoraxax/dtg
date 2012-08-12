#!/bin/sh
. env/bin/activate
PYTHONPATH=$PYTHONPATH:. exec python dtgimapd/imapserver.py  -k dtgcert -c dtgcert http://alexanderweb.homeip.net:5005/ alexanderweb.homeip.net

