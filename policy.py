"""Pure, timezone-aware selection. No I/O, clock reads or side effects."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from .contracts import Decision, aware


def _quiet(now, config):
    hour = now.astimezone(ZoneInfo(config.timezone)).hour
    start,end = config.quiet_start,config.quiet_end
    return start <= hour < end if start < end else hour >= start or hour < end


def next_normal_window(now, config):
    now = aware(now)
    if not _quiet(now,config):
        return now
    # Walk instants, not ambiguous/nonexistent local wall times, including DST gaps.
    probe = now.replace(second=0,microsecond=0)+timedelta(minutes=1)
    for _ in range(26*60):
        if not _quiet(probe,config):
            return probe
        probe += timedelta(minutes=1)
    raise ValueError('normal window unavailable')


def _overnight_key(instant, config):
    local = instant.astimezone(ZoneInfo(config.timezone))
    if config.quiet_start > config.quiet_end and local.hour < config.quiet_end:
        local -= timedelta(days=1)
    return local.date()


def _fresh(snapshot, now, config):
    if snapshot.observed_at is None:
        return False
    age = (now-aware(snapshot.observed_at)).total_seconds()
    return -60 <= age <= config.freshness_minutes*60


def _normal_hold(now, config, history):
    local_day = now.astimezone(ZoneInfo(config.timezone)).date()
    normal = [aware(at) for at,urgent in history if not urgent]
    count = sum(at.astimezone(ZoneInfo(config.timezone)).date() == local_day for at in normal)
    if count >= config.normal_cap:
        return 'normal_cap'
    if normal and now-max(normal) < timedelta(minutes=config.spacing_minutes):
        return 'spacing'
    return None


def decide(risks, snapshot, now, config, *, stopped=False, history=()):
    now = aware(now)
    window = next_normal_window(now,config)
    if stopped:
        return Decision((), 'stopped', next_window=window)
    if not _fresh(snapshot,now,config):
        return Decision((), 'stale_sources', next_window=window)
    if any(aware(start) <= now < aware(end) for start,end in snapshot.busy):
        return Decision((), 'meeting', next_window=window)
    upcoming = sorted((r for r in risks if now < r.event.at and (r.event.at <= now+timedelta(hours=config.horizon_hours) or (r.help_offer and r.event.not_before is not None)) and (r.event.not_before is None or now >= r.event.not_before)), key=lambda r:(r.event.at,r.event.id))
    if not upcoming:
        return Decision((), 'no_upcoming_risks', next_window=window)
    if not _quiet(now,config):
        hold = _normal_hold(now,config,history)
        return Decision(() if hold else tuple(upcoming[:config.batch_size]),hold or 'eligible',next_window=window)
    urgent = [r for r in upcoming if not r.help_offer and r.event.at <= now+timedelta(minutes=15) and r.event.at < window]
    if not urgent:
        return Decision((), 'quiet_hours', next_window=window)
    count = sum(is_urgent and _overnight_key(aware(at),config) == _overnight_key(now,config) for at,is_urgent in history)
    if count >= config.urgent_cap:
        return Decision((), 'urgent_cap', next_window=window)
    return Decision(tuple(urgent[:config.batch_size]),'eligible',True,window)
