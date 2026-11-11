"""Automated demo transport rehearsal: explicitly CLI-seeded, not Telegram-user impersonation.

Requires demo_up first. An actual owner DM reply is preferred; after a bounded
reply window a real stock CLI chat can exercise linkage, clearly labeled as such.
Always tears down the exact recorded demo fixture, even when assertions fail.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import time

from demo_fixture import CONTROL, ROOT, command, child_env, down, birth
from native_cli import agent_text


def captures(state):
    path=state/'plugin-data/lookahead/data.db'
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        return [json.loads(r[0]) for r in db.execute('SELECT payload FROM captures')]


def deliveries(state):
    path=state/'logs/agent.log'
    info=json.loads(CONTROL.read_text())
    return [line for line in agent_text(Path(info['base'])).splitlines() if re.search(r"Job '[^']+': delivered to telegram:"+re.escape(__import__('os').environ['LOOKAHEAD_DEMO_CHAT_ID'])+r" .*message_id=",line)] if path.exists() else []


def outputs(state):
    return [p.read_text() for p in (state/'cron/output').rglob('*.md')]


def main():
    info=json.loads(CONTROL.read_text());base=Path(info['base']);state=Path(info['state'])
    key=dict(__import__('os').environ).get('MINIMAX_API_KEY','')
    env=child_env(base,key)
    transcript=base/'dry-run.jsonl'
    def record(kind,**data):
        row={'at':datetime.now(timezone.utc).isoformat(),'kind':kind,**data}
        with transcript.open('a') as f: f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
    reply_kind=None
    try:
        lines=json.loads((base/'messages.json').read_text())['messages']
        command(base,env,'config','set','plugins.entries.lookahead.settings.capture_cli','true')
        record('cli_seeding_explicit',capture_cli=True,not_telegram_user_impersonation=True)
        for text in lines[:3]:
            command(base,env,'chat','-q',text,'-Q')
            record('native_cli_chat',text=text)
        rows=captures(state)
        assert len(rows)==2,'expected exactly two dated commitments and no workshop'
        assert not any('workshop' in r['subject'].lower() for r in rows)
        record('two_plans_captured',captures=rows)
        start=time.monotonic();followup_seen=None
        while time.monotonic()-start<900:
            if not birth(info['pid']): raise RuntimeError('demo gateway exited')
            rows=captures(state)
            if any(r.get('parent_id') for r in rows) and reply_kind is None:
                reply_kind='owner_telegram_dm'
                record('linked_next_step',kind_detail=reply_kind,captures=rows)
            all_output='\n'.join(outputs(state))
            if 'Any next steps I should keep track of?' in all_output and followup_seen is None:
                followup_seen=time.monotonic()
                record('first_followup_native_output',delivery_acks=deliveries(state))
                print('OWNER_REPLY_WINDOW: send the fictional next-step reply in the demo bot DM now; waiting 90 seconds before explicitly labeled CLI fallback.',flush=True)
            if followup_seen and reply_kind is None and time.monotonic()-followup_seen>=90:
                command(base,env,'chat','-q',lines[3],'-Q')
                reply_kind='native_cli_reply_NOT_telegram_dm'
                rows=captures(state)
                assert any(r.get('parent_id') for r in rows),'CLI reply did not capture linked next step'
                record('linked_next_step',kind_detail=reply_kind,captures=rows)
            if reply_kind and len(deliveries(state))>=4:
                # Observe another real minute fire: no one should nag the silent second event.
                time.sleep(75)
                assert len(deliveries(state))==4,'duplicate/extra proactive delivery'
                break
            time.sleep(3)
        assert len(deliveries(state))==4,'expected two brief and two follow-up API send acknowledgements'
        text='\n'.join(outputs(state))
        assert text.count('Preparation brief')==2,'expected two actual briefs, not fallback offers'
        assert text.count('Any next steps I should keep track of?')==2
        command(base,env,'lookahead','list');command(base,env,'lookahead','status')
        command(base,env,'lookahead','stop')
        record('dry_run_pass',reply_kind=reply_kind,telegram_api_send_acks=deliveries(state),captured_count=len(captures(state)))
    finally:
        command(base,env,'config','set','plugins.entries.lookahead.settings.capture_cli','false',check=False)
        record('teardown_requested',reply_kind=reply_kind)
        down()
        output=ROOT/'../lookahead-private-evidence/demo-20261110'/base.name
        output.mkdir(parents=True,exist_ok=True)
        (output/'dry-run.jsonl').write_text(transcript.read_text())


if __name__=='__main__': main()