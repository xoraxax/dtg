#!/bin/sh
. env/bin/activate
PYTHONPATH=. exec python dtg/main.py -D -M
