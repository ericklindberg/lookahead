"""Pre-gated scheduled evaluation. Stdout is a handoff, never a receipt."""
from dataclasses import fields, replace
from datetime import datetime, timezone

from .capture import ConversationSource
from .compose import compose
from .contracts import Config, Snapshot
from .sources import IcsSource
from .store import Store


def _calendar(ctx, store, now, config):
    if ctx.get_config('ics_enabled', False) is not True:
        store.calendar_status({'enabled': False})
        return None
    status = {'enabled': True}
    try:
        adapter = IcsSource(ics_path=ctx.get_config('ics_path'), ics_url=ctx.get_config('ics_url'),
                            timezone=config.timezone, horizon_hours=config.horizon_hours,
                            freshness_hours=ctx.get_config('ics_freshness_hours', 24),
                            timeout=ctx.get_config('ics_timeout_seconds', 5))
        status.update(adapter.status)
        snapshot = adapter.read(now=now)
        status.update(adapter.status)
        store.calendar_status(status)
        store.observe(snapshot)
        return snapshot
    except ValueError:
        store.calendar_status({**status, 'error': 'calendar_unavailable'})
        # Do not resolve pending facts on a failed read; hold all outbound instead.
        return Snapshot((), (), None, source_id='calendar')


def run(ctx, *, now=None, before_output=None):
    if ctx.get_config('enabled', True) is not True:
        return
    now = now or datetime.now(timezone.utc)
    config = Config(**{f.name: ctx.get_config(f.name, f.default) for f in fields(Config)})
    store = Store()
    try:
        snapshot = ConversationSource(store).read(now=now)
        store.observe(snapshot)
        calendar = _calendar(ctx, store, now, config)
        snapshots = (snapshot, calendar) if calendar is not None else (snapshot,)
        decision = store.reserve(snapshot,now,replace(config,batch_size=1),snapshots=snapshots)
        reserved_ids = set()
        message = compose(decision,now)
        if decision.selected:
            captures = store.list_captures()
            ids = {r.event.id for r in decision.selected}
            reserved_ids = ids
            rows = [r for r in captures if r['id'] in ids]
            if rows:
                try:
                    from .brief import generate
                    related = [r for r in captures if r['id'] not in ids and r['subject'].casefold()==rows[0]['subject'].casefold()]
                    message = generate(ctx.llm,rows,related)
                except Exception:
                    pass  # Keep deterministic fallback; reservation prevents a retry loop.
        elif decision.reason not in ('stale_sources', 'meeting'):
            followup = store.reserve_followup(now,config)
            if followup:
                reserved_ids = {followup['id']}
                from .compose import sanitize
                message = f"How did {sanitize(followup['subject'])} go? Any next steps I should keep track of?"
        if before_output:
            before_output()
        # Re-read durable STOP and current config immediately before stdout.
        remaining = {r['id'] for r in (*store.list_captures(), *store.list_calendar())} if message else set()
        if message and reserved_ids <= remaining and not store.status()['stopped'] and ctx.get_config('enabled',True) is True:
            print(message,flush=True)
    finally:
        store.close()
