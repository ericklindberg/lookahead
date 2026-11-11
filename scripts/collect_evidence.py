"""Export allowlisted fictional fixture receipts, never auth/config/credential files."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
from native_cli import fixture_state, agent_text

ROOT=Path(__file__).resolve().parents[1]


def collect(base, output):
    base=Path(base).resolve();output=Path(output).resolve()
    permitted = (ROOT.parent/'env',Path(__import__('os').environ.get('LOOKAHEAD_DEMO_ROOT', str(ROOT.parent/'lookahead-demo-env'))))
    if not any(base.is_relative_to(p) for p in permitted) or not output.is_relative_to(ROOT.parent/'lookahead-private-evidence'):
        raise ValueError('fixture/evidence path outside approved roots')
    approved=dict(__import__('os').environ)
    bot=dict(__import__('os').environ)
    secrets=[approved.get(k,'') for k in ('OPENROUTER_API_KEY','KIMI_API_KEY','MINIMAX_API_KEY')]+[bot.get('TELEGRAM_BOT_TOKEN','')]
    def clean(text):
        for key in secrets:
            if key: text=text.replace(key,'[REDACTED]')
        return text
    output.mkdir(parents=True,exist_ok=True)
    state=fixture_state(base)
    mapping={'commands.jsonl':base/'commands.jsonl','transport.jsonl':base/'transport.jsonl',
             'gateway.log':base/'gateway.private.log','agent.log':state/'logs/agent.log',
             'fixture.json':base/'fixture.json','auth-add.json':base/'auth-add.json','lookahead-reset.json':base/'lookahead-reset.json',
             'captures.json':base/'captures.json','teardown.json':base/'teardown.json','messages.json':base/'messages.json'}
    for name,path in mapping.items():
        if path.is_file(): (output/name).write_text(clean(agent_text(base) if name=='agent.log' else path.read_text()))
    executions=state/'cron/executions.db'
    if executions.exists():
        with sqlite3.connect(f'file:{executions}?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            rows=[dict(r) for r in db.execute('SELECT * FROM executions ORDER BY claimed_at')]
        commands=base/'commands.jsonl'
        created=[]
        if commands.exists():
            for line in commands.read_text().splitlines():
                match=re.search(r'Created job: ([a-f0-9]+)',json.loads(line).get('stdout',''))
                if match: created.append(match[1])
        if created: rows=[r for r in rows if r['job_id'] in created]
        (output/'executions.json').write_text(clean(json.dumps(rows,indent=2))+'\n')
    ledger=state/'plugin-data/lookahead/data.db'
    if ledger.exists():
        with sqlite3.connect(f'file:{ledger}?mode=ro',uri=True) as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM captures ORDER BY id')]
            handoffs=[dict(zip(('id','at','urgent'),r)) for r in db.execute('SELECT id,at,urgent FROM handoffs ORDER BY at')]
            followups=[dict(zip(('parent','at','state'),r)) for r in db.execute('SELECT parent,at,state FROM followups ORDER BY at')]
        (output/'captures.json').write_text(json.dumps(rows,indent=2)+'\n')
        (output/'reservations.json').write_text(json.dumps({'handoffs':handoffs,'followups':followups},indent=2)+'\n')
    for path in (state/'cron/output').rglob('*.md'):
        target=output/'native-output'/path.relative_to(state/'cron/output')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(clean(path.read_text()))
    agent=state/'logs/agent.log'
    receipts=[]
    if agent.exists():
        for line in agent_text(base).splitlines():
            match=re.search(r"Job '([^']+)': delivered to ([^ ]+) via live adapter thread=([^ ]+) message_id=([^ ]+)",line)
            if match: receipts.append({'kind':'stock_native_send_ack','at_log_local':line[:23],'job_id':match[1],'target':match[2],'thread':match[3],'message_id':match[4]})
    (output/'delivery-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
    plugin=state/'plugins/lookahead'
    names=['__init__.py','capture.py','brief.py','cli.py','commands.py','compose.py','contracts.py','policy.py','runner.py','sources.py','store.py','plugin.yaml','scripts/cron_entry.py']
    identity={'at':datetime.now(timezone.utc).isoformat(),'fixture':str(base),
              'stock_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT.parent/'stock-hermes',text=True).strip(),
              'stock_status':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT.parent/'stock-hermes',text=True),
              'installed_plugin_sha256':{n:hashlib.sha256((plugin/n).read_bytes()).hexdigest() for n in names if (plugin/n).exists()}}
    (output/'identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    # Verify exact keys never made it into any exported artifact. Print only counts.
    files=[p for p in output.rglob('*') if p.is_file()]
    for path in files:
        text=path.read_text()
        if any(key and key in text for key in secrets): raise RuntimeError('secret in exported artifact')
    print(json.dumps({'exported_files':len(files),'native_send_acks':len(receipts),'output':str(output),'secret_scan':'PASS'}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fixture',required=True);p.add_argument('--output',required=True)
    args=p.parse_args();collect(args.fixture,args.output)