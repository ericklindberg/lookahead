"""Repeated real native-hook measurements; fictional data, fresh plugin state.

All groups use future absolute local dates computed for each trial. Starts are
persisted before any model call, and nonzero native chat exits are excluded.
"""
from auth_diagnostics import scrub
from collections import Counter
from datetime import datetime,timedelta
import hashlib
import json
import os
import re
import sqlite3
from zoneinfo import ZoneInfo
from eval_capture import ROOT,isolated_home
from native_cli import fixture_state,reset_lookahead
from demo_fixture import child_env,command

OUT=ROOT/'../lookahead-private-evidence/stock-20261110/leadtime-live-v4-20261110.jsonl'


def input_text(group,now):
    due=((now+timedelta(days=1)).replace(hour=9,minute=30,second=0,microsecond=0) if group=='tomorrow_09_30'
         else (now+timedelta(minutes=4 if group=='fresh_4_minutes' else 30)).replace(second=0,microsecond=0))
    return f'I will meet the Acorn team {due:%Y-%m-%d at %H:%M} to discuss the budget decision.',due


def trial(base,env,state,group,index):
    reset_lookahead(base,lambda *args:command(base,env,*args))
    reset=json.loads((base/'lookahead-reset.json').read_text())
    log=state/'logs/agent.log';offset=log.stat().st_size if log.exists() else 0
    started=datetime.now(ZoneInfo('America/New_York'));text,due=input_text(group,started)
    attempt={'group':group,'trial':index,'started_local':started.isoformat(),'due_local':due.isoformat(),'text':text,
             'computed_lead_minutes':(due-started).total_seconds()/60,'log_path':str(log),'log_byte_offset':offset}
    with OUT.with_suffix('.attempts.jsonl').open('a') as f:f.write(json.dumps(attempt)+'\n')
    result=command(base,env,'chat','-q',text,'-Q',check=False)
    listing=command(base,env,'lookahead','list')
    with log.open('rb') as f:
        f.seek(offset);lines=f.read().decode(errors='replace').splitlines()
    decisions=[x for x in lines if 'lookahead_capture_' in x]
    dbpath=state/'plugin-data/lookahead/data.db'
    with sqlite3.connect('file:'+str(dbpath)+'?mode=ro',uri=True) as db:
        captures=[json.loads(r[0]) for r in db.execute('SELECT payload FROM captures')]
        errors=db.execute("SELECT value FROM meta WHERE key='capture_last_error'").fetchone()
    expected=hashlib.sha256(text.encode()).hexdigest()[:12]
    request=next((x for x in decisions if 'lookahead_capture_request ' in x),'')
    found=re.search(r'text_hash=([a-f0-9]+)',request)
    clock=re.search(r'captured_at=([^ ]+)',request)
    at=clock[1] if clock else None
    row={'group':group,'trial':index,'started_local':started.isoformat(),'finished_local':datetime.now(ZoneInfo('America/New_York')).isoformat(),
         'text':text,'due_local':due.isoformat(),'computed_lead_minutes':(due-started).total_seconds()/60,
         'hook_captured_at':at,'lead_at_hook_minutes':(due-datetime.fromisoformat(at)).total_seconds()/60 if at else None,
         'native_chat_exit':result.returncode,'native_chat_stdout':scrub(result.stdout,env.get('MINIMAX_API_KEY','')),'native_chat_stderr':scrub(result.stderr,env.get('MINIMAX_API_KEY','')),
         'capture':bool(captures) if result.returncode==0 else None,'excluded_error':result.returncode!=0,'capture_count':len(captures),
         'captures':captures,'list':listing.stdout,'capture_last_error':json.loads(errors[0]) if errors else None,
         'fresh_state':reset,'decision_lines':decisions,'expected_text_hash':expected,
         'live_request_metadata_present':bool(found),'live_text_hash_matches':bool(found and found[1]==expected) if found else None,
         'expected_state_scope':hashlib.sha256(str(dbpath).encode()).hexdigest()[:12]}
    with OUT.open('a') as f: f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
    if result.returncode: return  # excluded, neither a model success nor failure
    if not found: raise AssertionError('native request metadata absent; runtime qualification failed, not a proven text mismatch')
    if not clock: raise AssertionError('native request clock absent; no guessed claim-table timestamp')
    if not row['live_text_hash_matches']: raise AssertionError('native hook input differs; measurement aborted with evidence')
    # An agent/transport exit is retained but is neither capture nor no-capture.


def main():
    if OUT.exists(): raise FileExistsError('preserve existing measurement; choose a new evidence filename deliberately')
    OUT.parent.mkdir(parents=True,exist_ok=True)
    base=isolated_home('leadtime-measurement','MiniMax-M2.7','minimax',persistent_demo=True)
    state=fixture_state(base);env=child_env(base,os.environ['MINIMAX_API_KEY'])
    cfg=json.loads((state/'config.yaml').read_text());cfg['plugins']['entries']['lookahead']['settings']['capture_cli']=True
    (state/'config.yaml').write_text(json.dumps(cfg,indent=2))
    for group in ('fresh_4_minutes','fresh_30_minutes','tomorrow_09_30'):
        for index in range(1,6): trial(base,env,state,group,index)
    rows=[json.loads(x) for x in OUT.read_text().splitlines()]
    counts=Counter(r['group'] for r in rows)
    assert len(rows)==15 and all(v==5 for v in counts.values())
    summary={g:{'attempts':5,'valid':sum(not r['excluded_error'] for r in rows if r['group']==g),
                'excluded_errors':sum(r['excluded_error'] for r in rows if r['group']==g),
                'captured':sum(r['capture'] is True for r in rows if r['group']==g),
                'no_capture':sum(r['capture'] is False for r in rows if r['group']==g)} for g in counts}
    (OUT.parent/'leadtime-live-v4-20261110.summary.json').write_text(json.dumps({'native_hook':True,'state':str(state),'results':summary},indent=2)+'\n')
    print(json.dumps(summary),flush=True)


if __name__=='__main__': main()