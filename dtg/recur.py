# -*- coding: utf-8 -*-
################################################################################
# DTG.  The task management web application.
#
# Copyright (c) 2012 Alexander Schremmer <alex@alexanderweb.de>
# Licensed under AGPL Version 3 or later. See LICENSE for details.
################################################################################

"""
Iterators for datetime objects.

This work, including the source code, documentation
and related data, is placed into the public domain.

The original author is Robert Brewer, Amor Ministries.
See http://projects.amor.org/misc/wiki/Recur for more docs.

THIS SOFTWARE IS PROVIDED AS-IS, WITHOUT WARRANTY
OF ANY KIND, NOT EVEN THE IMPLIED WARRANTY OF
MERCHANTABILITY. THE AUTHOR OF THIS SOFTWARE
ASSUMES _NO_ RESPONSIBILITY FOR ANY CONSEQUENCE
RESULTING FROM THE USE, MODIFICATION, OR
REDISTRIBUTION OF THIS SOFTWARE.
"""

import datetime
import re
import dateutil.rrule as dateutil


def eachday():
    return (dateutil.DAILY, {})

def days(frequency=1):
    return (dateutil.DAILY, {"interval": frequency})

def eachweek(weekday=0):
    return (dateutil.WEEKLY, {"byweekday": weekday})

def weeks(frequency=1):
    return (dateutil.WEEKLY, {"interval": frequency})

def eachmonth(day=1):
    return (dateutil.MONTHLY, {"bymonthday": day})

def months(frequency=1):
    return (dateutil.MONTHLY, {"interval": frequency})

def eachyear(month=1, day=1):
    return (dateutil.YEARLY, {"bymonth": month, "bymonthday": day})

def years(frequency=1):
    return (dateutil.YEARLY, {"interval": frequency})

def byunits(whichUnit, frequency=1):
    """Dispatch to the appropriate unit handler.
    """
    frequency = int(frequency)
    unithandler = (days, weeks, months, years)
    return unithandler[whichUnit](frequency)


class Locale(object):
    """Language-specific expression matching.
    
    To use a language other than English with Recurrence objects,
    either subclass Locale and override the "patterns" dictionary,
    or write some other callable that takes a description string
    and returns a recurrence function and its "inner" args.
    """
    
    patterns = {byunits: [
                          r"(?:every|each) ([0-9]+) days",
                          r"(?:every|each) ([0-9]+) weeks",
                          r"(?:every|each) ([0-9]+) months",
                          r"(?:every|each) ([0-9]+) years",
                          ],
                eachday: r"(?:every|each) day",
                eachweek: [
                    r"(?:every|each) mon(?!th)", 
                    r"(?:every|each) tue", 
                    r"(?:every|each) wed", 
                    r"(?:every|each) thu", 
                    r"(?:every|each) fri", 
                    r"(?:every|each) sat", 
                    r"(?:every|each) sun", 
                    ],
                eachmonth: r"(-?\d+) (?:every|each) month",
                # Lookbehind for a digit and separator so we don't
                # screw up singledate, below.
                eachyear: [r"^(dummy entry to line up indexing)$",
                           r"(?<!\d\d[/ \-])(?:jan(?:uary)?|0?1)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:febr?(?:uary)?|0?2)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:mar(?:ch)?|0?3)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:apr(?:il)?|0?4)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:may|0?5)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:june?|0?6)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:july?|0?7)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:aug(?:ust)?|0?8)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:sept?(?:ember)?|0?9)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:oct(?:ober)?|10)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:nov(?:ember)?|11)[/ \-]([0-9]+)",
                           r"(?<!\d\d[/ \-])(?:dec(?:ember)?|12)[/ \-]([0-9]+)",
                           ],
                #singledate: r"(\d\d\d\d)[/ \-]([01]?\d)[/ \-]([0123]?\d)",
                }
    regexes = {}

    def __init__(self):
        for key, regSet in self.patterns.items():
            if isinstance(regSet, list):
                self.regexes[key] = [re.compile(x, re.IGNORECASE)
                                     for x in regSet]
            else:
                self.regexes[key] = re.compile(regSet, re.IGNORECASE)

    def __call__(self, description):
        for rule, regSet in self.regexes.items():
            if isinstance(regSet, list):
                for index, regex in enumerate(regSet):
                    matches = regex.match(description)
                    if matches:
                        return rule, (index,) + matches.groups()
            else:
                matches = regSet.match(description)
                if matches:
                    return rule, matches.groups()

        raise ValueError(u"The supplied description ('%s') "
                         u"could not be parsed." % description)

localeEnglish = Locale()

def get_rrule_args(locale, description):
    function, args = locale(description)
    return function(*args)

