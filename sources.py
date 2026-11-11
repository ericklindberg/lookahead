"""Bounded local inputs. Adapters return immutable Snapshot, never paths in event text."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Protocol, runtime_checkable

from .contracts import Candidate, Event, Readiness, Snapshot, aware

MAX_BYTES = 65536
MAX_ROWS = 200


@runtime_checkable
class Source(Protocol):
    def read(self, *, now: datetime) -> Snapshot:
        """Return canonical events, readiness, busy intervals and source freshness."""
        ...


def read_source(source: Source, *, now: datetime) -> Snapshot:
    aware(now)
    snapshot = source.read(now=now)
    if not isinstance(snapshot, Snapshot):
        raise ValueError('source must return Snapshot')
    return snapshot


def _open_regular(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('explicit absolute local path required')
    # Open every component relative to an owned descriptor: no symlink/race escape.
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)


def _read(path, now, freshness_minutes):
    try:
        fd = _open_regular(path)
        with os.fdopen(fd, 'rb') as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
                raise ValueError('bounded regular file required')
            data = handle.read(MAX_BYTES+1)
            after = os.fstat(handle.fileno())
        if len(data) > MAX_BYTES or (before.st_size,before.st_mtime_ns) != (after.st_size,after.st_mtime_ns):
            raise ValueError('source changed during read')
        modified = datetime.fromtimestamp(before.st_mtime, timezone.utc)
        age = (now-modified).total_seconds()
        if age > freshness_minutes*60 or age < -60:
            raise ValueError('stale or future source timestamp')
        return data.decode('utf-8'), modified
    except (OSError, UnicodeError) as exc:
        raise ValueError('source unavailable or invalid') from exc


def _cells(line):
    if not line.startswith('|') or not line.endswith('|'):
        raise ValueError('Markdown table row required')
    return [cell.strip() for cell in line[1:-1].split('|')]


def _table(text, header):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or _cells(lines[0]) != header:
        raise ValueError('exact table header required')
    separators = _cells(lines[1])
    if len(separators) != len(header) or not all(re.fullmatch(r':?-{3,}:?',v) for v in separators):
        raise ValueError('Markdown separator required')
    if len(lines)-2 > MAX_ROWS:
        raise ValueError('too many rows')
    rows = [_cells(line) for line in lines[2:]]
    if any(len(row) != len(header) or not all(row) for row in rows):
        raise ValueError('invalid row width or empty field')
    return rows


@dataclass(frozen=True)
class MarkdownSource:
    agenda_path: Path
    readiness_path: Path
    freshness_minutes: int = 15

    def read(self, *, now):
        now = aware(now)
        agenda, agenda_time = _read(self.agenda_path,now,self.freshness_minutes)
        board, board_time = _read(self.readiness_path,now,self.freshness_minutes)
        events = tuple(Event(id,datetime.fromisoformat(at),title,key) for id,at,title,key in _table(agenda,['id','at','title','readiness_key']))
        readiness = tuple(Readiness(*row) for row in _table(board,['key','status','detail']))
        busy = tuple((e.at,e.at+timedelta(minutes=30)) for e in events)
        return Snapshot(events,readiness,min(agenda_time,board_time),busy)


def load(agenda_path, readiness_path, *, now, freshness_minutes=15):
    return read_source(MarkdownSource(agenda_path,readiness_path,freshness_minutes),now=now)


def candidates(snapshot):
    board = {row.key:row for row in snapshot.readiness}
    risks = []
    for event in snapshot.events:
        row = board.get(event.readiness_key)
        if row is None or row.status != 'not_ready':
            continue
        fields = [snapshot.source_id,event.id,event.at.isoformat(),event.title,event.readiness_key,row.status,row.detail,event.not_before.isoformat() if event.not_before else None]
        if event.end_at is not None:
            fields.append(event.end_at.isoformat())
        revision = hashlib.sha256(json.dumps(fields,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
        risks.append(Candidate(event,row.detail,revision,snapshot.source_id in ('conversation', 'calendar')))
    return tuple(risks)


# Public adapter seam; defer import until local file helpers exist.
from .ics import IcsSource  # noqa: E402,F401
