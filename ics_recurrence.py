"""Deliberately small RFC 5545 subset; unsupported recurrence fails closed."""
from calendar import monthrange
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# Outlook Windows IDs are mapped explicitly, not inferred from VTIMEZONE rules.
WINDOWS_ZONES = {'Eastern Standard Time': 'America/New_York',
                 'Central Standard Time': 'America/Chicago',
                 'Mountain Standard Time': 'America/Denver',
                 'Pacific Standard Time': 'America/Los_Angeles',
                 'GMT Standard Time': 'Europe/London', 'UTC': 'UTC'}
DAYS = ('MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU')
MAX_STEPS = 100000


def date_value(prop, default_zone):
    params, value = prop
    if set(params)-{'TZID', 'VALUE'} or params.get('VALUE', 'DATE-TIME') not in ('DATE', 'DATE-TIME'):
        raise ValueError('unsupported date parameters')
    if params.get('VALUE') == 'DATE':
        if 'TZID' in params:
            raise ValueError('TZID on DATE')
        dt = datetime.strptime(value, '%Y%m%d')
    else:
        dt = datetime.strptime(value, '%Y%m%dT%H%M%SZ' if value.endswith('Z') else '%Y%m%dT%H%M%S')
    if value.endswith('Z'):
        if 'TZID' in params:
            raise ValueError('TZID on UTC')
        return dt.replace(tzinfo=timezone.utc)
    name = params.get('TZID', default_zone)
    zone = ZoneInfo(WINDOWS_ZONES.get(name, name))
    return localize(dt, zone)


def localize(dt, zone):
    result = dt.replace(tzinfo=zone, fold=0)
    if result.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != dt:
        raise ValueError('nonexistent local time')
    return result


def rule_parts(text, start):
    parts = {}
    for pair in text.split(';'):
        key, value = pair.split('=')
        if key in parts:
            raise ValueError('duplicate recurrence part')
        parts[key] = value
    if set(parts)-{'FREQ', 'INTERVAL', 'COUNT', 'UNTIL', 'BYDAY'}:
        raise ValueError('unsupported recurrence part')
    if parts.get('FREQ') not in ('DAILY', 'WEEKLY', 'MONTHLY'):
        raise ValueError('unsupported frequency')
    interval = int(parts.get('INTERVAL', '1'))
    count = int(parts.get('COUNT', str(MAX_STEPS)))
    if not 1 <= interval <= 10000 or not 1 <= count <= MAX_STEPS or {'COUNT', 'UNTIL'} <= parts.keys():
        raise ValueError('unsupported recurrence bounds')
    weekdays = parts.get('BYDAY', DAYS[start.weekday()]).split(',')
    if 'BYDAY' in parts and (parts['FREQ'] != 'WEEKLY' or not all(v in DAYS for v in weekdays)):
        raise ValueError('unsupported BYDAY')
    until = None
    if 'UNTIL' in parts:
        value = parts['UNTIL']
        params = {'VALUE': 'DATE'} if len(value) == 8 else {}
        until = date_value((params, value), start.tzinfo.key if hasattr(start.tzinfo, 'key') else 'UTC')
    return parts['FREQ'], interval, count, until, weekdays


def _dates(start, freq, interval, weekdays):
    wall = start.replace(tzinfo=None)
    for index in range(MAX_STEPS):
        if freq == 'MONTHLY':
            month = start.year*12+start.month-1+index*interval
            year, month = divmod(month, 12)
            if year > 9999:
                return
            if wall.day > monthrange(year, month+1)[1]:
                continue
            yield wall.replace(year=year, month=month+1)
        elif freq == 'DAILY':
            yield wall+timedelta(days=index*interval)
        else:
            date = wall+timedelta(days=index)
            week = (index+start.weekday())//7
            if week % interval == 0 and DAYS[date.weekday()] in weekdays:
                yield date
    raise ValueError('recurrence expansion limit')


def expand(start, rule, horizon):
    if not rule:
        return (start,)
    freq, interval, count, until, weekdays = rule_parts(rule, start)
    result = []
    for wall in _dates(start, freq, interval, weekdays):
        instance = localize(wall, start.tzinfo)
        if instance > horizon or (until is not None and instance > until):
            break
        result.append(instance)
        if len(result) >= count:
            break
    return tuple(result)
