"""Plugin-only controls: trust host source coordinates, never text-supplied identity."""
import json
import re

from .compose import sanitize

DENIED = 'Lookahead: controls require a configured, operator-bound DM source.'
USAGE = 'Usage: /lookahead status|list|forget <id>|stop|resume'


def bound(ctx,source):
    if source is None:
        return False
    def value(key):
        result = source.get(key) if isinstance(source,dict) else getattr(source,key,None)
        return getattr(result,'value',result)
    if value('chat_type') != 'dm':
        return False
    for key in ('platform','user_id','chat_id'):
        expected = ctx.get_config('operator_'+key)
        if not isinstance(expected,str) or not expected or value(key) != expected:
            return False
    return True


def handle(ctx,raw_args='',*,source=None,**kwargs):
    if not bound(ctx,source):
        return DENIED
    args = raw_args.strip().split()
    command = args[0] if args else 'status'
    if command not in ('status','list','forget','stop','resume'):
        return USAGE
    if command == 'forget':
        if len(args) != 2 or not re.fullmatch(r'[a-f0-9]{64}',args[1]):
            return USAGE
    elif command == 'list':
        if len(args)>2 or (len(args)==2 and not re.fullmatch(r'[1-9][0-9]?',args[1])):
            return USAGE
    elif len(args) > 1:
        return USAGE
    from .store import Store
    store = Store()
    try:
        if command in ('stop','resume'):
            store.set_stopped(command == 'stop')
            return 'Lookahead stopped; queued output cannot be recalled.' if command == 'stop' else 'Lookahead resumed (only this plugin).'
        if command == 'forget':
            return 'Lookahead: forgotten.' if store.forget_capture(args[1]) else 'Lookahead: item not found.'
        enabled = ctx.get_config('capture_enabled',True)
        header = 'Capture is on (default; configured host model).' if enabled else 'Capture is off.'
        if command == 'list':
            rows = [{**row, 'source':'chat'} for row in store.list_captures()] + store.list_calendar()
            rows.sort(key=lambda row: (row['due'], row['id']))
            page = int(args[1]) if len(args)==2 else 1
            pages = max(1,(len(rows)+9)//10)
            if page>pages:
                return 'Lookahead: page out of range.'
            lines = [header,f'Page {page}/{pages}; use /lookahead list <page>.']
            for row in rows[(page-1)*10:page*10]:
                lines.append(f"{row['id']} | {row['source']} | {sanitize(row['subject'])} | {row['due']} | {row.get('timezone','UTC')} | confidence {row.get('confidence','calendar data')} | parent->next-step {row.get('parent_id') or '-'}->{row['id']}")
            return '\n'.join(lines) if len(lines)>1 else header+' No captured items.'
        status = store.status()
        status['demo_timing'] = bool(ctx.get_config('offer_lead_minutes',0) or ctx.get_config('followup_delay_minutes',120)!=120)
        status['offer_lead_minutes'] = ctx.get_config('offer_lead_minutes',0)
        status['followup_delay_minutes'] = ctx.get_config('followup_delay_minutes',120)
        return header+'\n'+json.dumps(status,sort_keys=True)
    finally:
        store.close()


def admission(ctx,*,text=None,source=None,session_key=None,**kwargs):
    if not bound(ctx,source):
        return None
    if text in ('STOP','RESUME'):
        return {'action':'handled','reply':handle(ctx,'stop' if text == 'STOP' else 'resume',source=source)}
    if ctx.get_config('capture_enabled',True) and session_key and isinstance(text,str):
        from datetime import datetime, timezone
        from .store import Store
        store = Store()
        try:
            store.admit_capture(session_key,text,datetime.now(timezone.utc))
        finally:
            store.close()
    return None
