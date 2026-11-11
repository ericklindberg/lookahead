"""One native live/direct pair with exactly replayed model messages."""
from datetime import datetime,timedelta
import hashlib
import json
import os
import re
import subprocess
import sqlite3
from auth_diagnostics import scrub
from zoneinfo import ZoneInfo
from eval_capture import ROOT,isolated_home,load_capture
from native_cli import fixture_state,reset_lookahead,argv
from demo_fixture import child_env,command


def request_line(facts,*,log_path,offset,native_exit,stderr,reset_turns,after_turns):
    found=next((x for x in facts if 'lookahead_capture_request ' in x),None)
    if found:return found
    diagnostic={'reason':'harness_chat_rejected' if native_exit==2 else 'missing_capture_request',
                'log_path':str(log_path),'byte_offset':offset,'native_chat_exit':native_exit,'scrubbed_stderr':stderr,
                'hook_ran':False if native_exit==2 else (True if facts or after_turns else 'no_evidence'),
                'reset_capture_turns':reset_turns,'after_capture_turns':after_turns,
                'model_result':None,'excluded_harness_error':True}
    raise RuntimeError(json.dumps(diagnostic))


def main():
    base=isolated_home('paired-capture','MiniMax-M2.7','minimax',persistent_demo=True)
    state=fixture_state(base);env=child_env(base,os.environ['MINIMAX_API_KEY'])
    reset_lookahead(base,lambda *a:command(base,env,*a))
    log=state/'logs/agent.log';offset=log.stat().st_size
    started=datetime.now(ZoneInfo('America/New_York'));due=(started+timedelta(minutes=30)).replace(second=0,microsecond=0)
    text=f'I will meet the Acorn team {due:%Y-%m-%d at %H:%M} to discuss the budget decision.'
    result=command(base,env,'chat','-q',text,'-Q',check=False)
    with log.open('rb') as f:f.seek(offset);lines=f.read().decode(errors='replace').splitlines()
    facts=[x for x in lines if 'lookahead_capture_' in x]
    reset=json.loads((base/'lookahead-reset.json').read_text())
    with sqlite3.connect('file:'+str(state/'plugin-data/lookahead/data.db')+'?mode=ro',uri=True) as db:
        after_turns=db.execute('SELECT COUNT(*) FROM capture_turns').fetchone()[0]
    request=request_line(facts,log_path=log,offset=offset,native_exit=result.returncode,
                         stderr=scrub(result.stderr,os.environ['MINIMAX_API_KEY']),
                         reset_turns=reset['lookahead_rows_after']['capture_turns'],after_turns=after_turns)
    at=re.search(r'captured_at=([^ ]+)',request)[1]
    payload=json.dumps({'captured_at':at,'timezone':'America/New_York','text':text})
    cap=load_capture()
    assert hashlib.sha256(payload.encode()).hexdigest()[:12]==re.search(r'payload_hash=([a-f0-9]+)',request)[1]
    out=ROOT/'../lookahead-private-evidence/stock-20261110'
    out.mkdir(parents=True,exist_ok=True)
    row={'text':text,'computed_lead_minutes':(due-started).total_seconds()/60,'hook_captured_at':at,
         'native_chat_exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'live_decision_lines':facts,
         'messages':[{'role':'system','content':cap.PROMPT},{'role':'user','content':payload}]}
    (out/'paired-request.json').write_text(json.dumps(row,indent=2)+'\n')
    # Supported minted-launcher module mode retains the exact PM-selected interpreter/environment.
    code=f'import runpy; runpy.run_path({str(ROOT/"scripts/probe_paired_direct.py")!r},run_name="__main__")\n'
    direct=subprocess.run(argv('--run-module','code'),input=code,text=True,capture_output=True,env=env,timeout=90)
    (out/'paired-native-console.log').write_text(direct.stdout+'\n'+direct.stderr)
    if direct.returncode or not (out/'paired-direct-result.json').exists():raise RuntimeError('native direct probe failed; receipt retained')
    direct_row=json.loads((out/'paired-direct-result.json').read_text())
    print(json.dumps({'live':row,'direct':direct_row,'same_payload_hash':direct_row['payload_hash']==re.search(r'payload_hash=([a-f0-9]+)',request)[1]}),flush=True)


if __name__=='__main__':main()