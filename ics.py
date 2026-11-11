"""Opt-in read-only calendar: no cookies, redirects, proxy inheritance or URL persistence."""
from dataclasses import dataclass, field
from datetime import timedelta
import hashlib
import os
import re
import ssl
import stat
import time
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, HTTPRedirectHandler, ProxyHandler, Request, build_opener
from zoneinfo import ZoneInfo

from .compose import sanitize
from .contracts import Event, Readiness, Snapshot, aware
from .ics_recurrence import date_value, expand

MAX_BYTES = 1048576
MAX_EVENTS = 200
EMAIL = re.compile(r'[^\s<>;,]+@[^\s<>;,]+')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('calendar redirect refused')


def _file(path, now, freshness_hours):
    from .sources import _open_regular
    fd = _open_regular(path)
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
            raise ValueError('bounded calendar file required')
        data = handle.read(MAX_BYTES+1)
        after = os.fstat(handle.fileno())
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('calendar changed during read')
    age = now.timestamp()-before.st_mtime
    if not -60 <= age <= freshness_hours*3600:
        raise ValueError('calendar file stale or future')
    return data


def _https(url, timeout):
    # Explicit handlers: no netrc, cookies, Authorization, Referer or env proxies.
    opener = build_opener(ProxyHandler({}), NoRedirect(), HTTPSHandler(context=ssl.create_default_context()))
    request = Request(url, headers={'Accept': 'text/calendar', 'Accept-Encoding': 'identity', 'User-Agent': 'Lookahead/0.1'})
    deadline = time.monotonic()+timeout
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200 or response.headers.get('Content-Encoding', 'identity') != 'identity':
            raise ValueError('calendar HTTP response refused')
        length = response.headers.get('Content-Length')
        if length is not None and int(length) > MAX_BYTES:
            raise ValueError('calendar too large')
        chunks, size = [], 0
        while size <= MAX_BYTES:
            # read1 returns available bytes instead of hiding slow trickles in read(n).
            chunk = response.read1(min(65536, MAX_BYTES+1-size))
            if time.monotonic() > deadline:
                raise ValueError('calendar request deadline')
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    return b''.join(chunks)


def _properties(text):
    lines = re.sub(r'\r?\n[ \t]', '', text).splitlines()
    if not lines or lines[0] != 'BEGIN:VCALENDAR' or lines[-1] != 'END:VCALENDAR':
        raise ValueError('calendar envelope required')
    records, current, stack = [], None, []
    for line in lines:
        if line.startswith('BEGIN:'):
            stack.append(line[6:])
            if stack == ['VCALENDAR', 'VEVENT']:
                current = {}
            continue
        if line.startswith('END:'):
            if not stack or stack.pop() != line[4:]:
                raise ValueError('unbalanced calendar component')
            if line == 'END:VEVENT':
                records.append(current)
                current = None
            continue
        if current is not None and stack == ['VCALENDAR', 'VEVENT']:
            _property(current, line)
        if len(records) > MAX_EVENTS:
            raise ValueError('calendar event limit')
    if stack or len(records) > MAX_EVENTS:
        raise ValueError('calendar event limit or incomplete calendar')
    return records


def _property(current, line):
    head, value = line.split(':', 1)
    name, *options = head.split(';')
    if name not in {'UID', 'SUMMARY', 'DESCRIPTION', 'DTSTART', 'DTEND', 'STATUS', 'RRULE', 'RECURRENCE-ID', 'EXDATE', 'RDATE', 'DURATION', 'EXRULE'}:
        return
    params = dict(option.split('=', 1) for option in options)
    params = {key: value.strip('"') for key, value in params.items()}
    if name in current and name != 'EXDATE':
        raise ValueError('duplicate calendar property')
    current.setdefault(name, []).append((params, value))


def _one(record, key, default=''):
    return record.get(key, [({}, default)])[0][1]


def _text(value, fallback):
    value = re.sub(r'\\([nN,;\\])', lambda m: '\n' if m[1] in 'nN' else m[1], value)
    value = re.sub(r'https?://\S+', '[link omitted]', value, flags=re.IGNORECASE)
    return sanitize(EMAIL.sub('[redacted]', value), 160) or fallback


def _instant(record, key, zone):
    return date_value(record[key][0], zone)


def _exclusions(record, zone):
    return {aware(date_value((params, value), zone)) for params, values in record.get('EXDATE', []) for value in values.split(',')}


def _instances(master, overrides, now, zone, horizon):
    if _one(master, 'STATUS') == 'CANCELLED':
        return []
    start = _instant(master, 'DTSTART', zone)
    duration = _instant(master, 'DTEND', zone)-start if 'DTEND' in master else timedelta(days=1) if master['DTSTART'][0][0].get('VALUE') == 'DATE' else timedelta(minutes=30)
    if duration <= timedelta(0) or duration > timedelta(days=31):
        raise ValueError('calendar duration bounds')
    excluded = _exclusions(master, zone)
    result = []
    expansion_end = max((horizon, *overrides.keys()))
    for instance in expand(start, _one(master, 'RRULE'), expansion_end):
        original = aware(instance)
        record = overrides.get(original, master)
        if original in excluded or _one(record, 'STATUS') == 'CANCELLED':
            continue
        actual = _instant(record, 'DTSTART', zone) if record is not master else instance
        end = _instant(record, 'DTEND', zone) if record is not master and 'DTEND' in record else actual+duration
        if aware(end) <= aware(actual):
            raise ValueError('calendar end before start')
        if aware(end) > now-timedelta(hours=24) and aware(actual) <= horizon:
            result.append((record, actual, end, original))
    return result


def _snapshot(records, now, zone, horizon):
    groups = {}
    for record in records:
        uid = _one(record, 'UID')
        if not uid or len(uid) > 2048:
            raise ValueError('calendar UID required')
        groups.setdefault(uid, []).append(record)
    events, readiness, busy, skipped = [], [], [], 0
    for uid, group in groups.items():
        try:
            if any(set(row) & {'RDATE', 'DURATION', 'EXRULE'} or row.get('RRULE', [({}, '')])[0][0] for row in group):
                raise ValueError('unsupported timing property')
            masters = [row for row in group if 'RECURRENCE-ID' not in row]
            if len(masters) != 1:
                raise ValueError('one series master required')
            overrides = {}
            for row in group:
                if 'RECURRENCE-ID' in row:
                    if 'RRULE' in row:
                        raise ValueError('recurrence rule on override')
                    if row['RECURRENCE-ID'][0][0].keys()-{'TZID','VALUE'}:
                        raise ValueError('unsupported recurrence range')
                    key = aware(_instant(row, 'RECURRENCE-ID', zone))
                    if key in overrides:
                        raise ValueError('duplicate instance')
                    overrides[key] = row
            instances = _instances(masters[0], overrides, now, zone, horizon)
        except (ValueError, KeyError, OverflowError):
            skipped += 1
            continue
        for record, actual, end, original in instances:
            id = hashlib.sha256((uid+'\0'+original.isoformat()).encode()).hexdigest()
            title = _text(_one(record, 'SUMMARY'), 'Calendar meeting')
            excerpt = _text(_one(record, 'DESCRIPTION'), 'Review the meeting goal and one question')
            events.append(Event(id, actual, title, id, aware(actual)-timedelta(hours=18), end_at=end))
            readiness.append(Readiness(id, 'not_ready', 'Prepare a meeting brief: '+excerpt))
            busy.append((actual, end))
            if len(events) > MAX_EVENTS:
                raise ValueError('calendar occurrence limit')
    pairs = sorted(zip(events, readiness, busy), key=lambda pair: pair[0].at)
    return Snapshot(tuple(p[0] for p in pairs), tuple(p[1] for p in pairs), now,
                    tuple(p[2] for p in pairs), 'calendar'), skipped


@dataclass
class IcsSource:
    ics_path: object = field(default=None, repr=False)
    ics_url: str | None = field(default=None, repr=False)
    timezone: str = 'UTC'
    horizon_hours: int = 24
    freshness_hours: int = 24
    timeout: float = 5
    status: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        try:
            ZoneInfo(self.timezone)
            if bool(self.ics_path) == bool(self.ics_url):
                raise ValueError('choose exactly one source')
            if not 1 <= self.horizon_hours <= 2160 or not 1 <= self.freshness_hours <= 168 or not 0 < self.timeout <= 30:
                raise ValueError('calendar limits')
            self.status = {'kind': 'file', 'skipped_series': 0}
            if self.ics_url:
                url = urlsplit(self.ics_url)
                if url.scheme != 'https' or not url.hostname or url.username is not None or url.password is not None or url.fragment or any(ord(c) <= 32 or ord(c) == 127 for c in self.ics_url):
                    raise ValueError('invalid private URL')
                _ = url.port
                self.status = {'kind': 'https', 'host': url.hostname, 'skipped_series': 0}
        except (ValueError, TypeError, KeyError):
            raise ValueError('invalid calendar configuration') from None

    def read(self, *, now):
        now = aware(now)
        try:
            data = _https(self.ics_url, self.timeout) if self.ics_url else _file(self.ics_path, now, self.freshness_hours)
            if len(data) > MAX_BYTES:
                raise ValueError('calendar too large')
            records = _properties(data.decode('utf-8-sig'))
            snapshot, skipped = _snapshot(records, now, self.timezone, now+timedelta(hours=self.horizon_hours))
            self.status['skipped_series'] = skipped
            self.status.pop('error', None)
            return snapshot
        except Exception:
            self.status['error'] = 'calendar_unavailable'
            # Never chain urllib errors: they can contain the entire private URL.
            raise ValueError('calendar unavailable or invalid') from None
