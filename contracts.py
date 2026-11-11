"""Immutable, adapter-neutral input and decision contracts."""
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PLUGIN_NAME = 'lookahead'
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')


def aware(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware datetime required')
    return value.astimezone(timezone.utc)


def identifier(value: str) -> None:
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError('invalid identifier')


@dataclass(frozen=True)
class Config:
    timezone: str
    quiet_start: int = 22
    quiet_end: int = 8
    normal_cap: int = 3
    urgent_cap: int = 1
    spacing_minutes: int = 30
    batch_size: int = 3
    freshness_minutes: int = 15
    horizon_hours: int = 24
    offer_lead_minutes: int = 0  # 0 keeps previous-day 18:00 eligibility
    followup_delay_minutes: int = 120

    def __post_init__(self):
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, TypeError) as exc:
            raise ValueError('valid IANA timezone required') from exc
        bounds = {'quiet_start':(0,23), 'quiet_end':(0,23), 'normal_cap':(0,100),
                  'urgent_cap':(0,1), 'spacing_minutes':(0,1440), 'batch_size':(1,3),
                  'freshness_minutes':(1,60), 'horizon_hours':(1,168),
                  'offer_lead_minutes':(0,10080), 'followup_delay_minutes':(0,10080)}
        for key, (low, high) in bounds.items():
            value = getattr(self,key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f'invalid {key}')
        if self.quiet_start == self.quiet_end:
            raise ValueError('quiet window must not be empty')


@dataclass(frozen=True)
class Event:
    id: str
    at: datetime
    title: str
    readiness_key: str
    not_before: datetime | None = None
    end_at: datetime | None = None

    def __post_init__(self):
        identifier(self.id)
        identifier(self.readiness_key)
        object.__setattr__(self,'at',aware(self.at))
        if self.not_before is not None:
            object.__setattr__(self,'not_before',aware(self.not_before))
            if self.not_before > self.at:
                raise ValueError('offer cannot follow due time')
        if self.end_at is not None:
            object.__setattr__(self,'end_at',aware(self.end_at))
            if self.end_at <= self.at:
                raise ValueError('event end must follow start')
        if not isinstance(self.title,str) or not 1 <= len(self.title) <= 2048:
            raise ValueError('invalid title')


@dataclass(frozen=True)
class Readiness:
    key: str
    status: str
    detail: str

    def __post_init__(self):
        identifier(self.key)
        if self.status not in ('ready','not_ready'):
            raise ValueError('invalid readiness status')
        if not isinstance(self.detail,str) or not 1 <= len(self.detail) <= 2048:
            raise ValueError('invalid readiness detail')


@dataclass(frozen=True)
class Snapshot:
    events: tuple[Event, ...]
    readiness: tuple[Readiness, ...]
    observed_at: datetime | None
    busy: tuple[tuple[datetime, datetime], ...] = ()
    source_id: str = 'local'

    def __post_init__(self):
        identifier(self.source_id)
        object.__setattr__(self,'events',tuple(self.events))
        object.__setattr__(self,'readiness',tuple(self.readiness))
        object.__setattr__(self,'busy',tuple((aware(a),aware(b)) for a,b in self.busy))
        if len(self.events) > 200 or len(self.readiness) > 200 or len(self.busy) > 200:
            raise ValueError('too many rows')
        if len({e.id for e in self.events}) != len(self.events):
            raise ValueError('duplicate event id')
        if len({r.key for r in self.readiness}) != len(self.readiness):
            raise ValueError('duplicate readiness key')
        if self.observed_at is not None:
            object.__setattr__(self,'observed_at',aware(self.observed_at))
        for start,end in self.busy:
            if aware(start) >= aware(end):
                raise ValueError('invalid busy interval')


@dataclass(frozen=True)
class Candidate:
    event: Event
    detail: str
    revision: str
    help_offer: bool = False


@dataclass(frozen=True)
class Decision:
    selected: tuple[Candidate, ...]
    reason: str
    urgent: bool = False
    next_window: datetime | None = None
