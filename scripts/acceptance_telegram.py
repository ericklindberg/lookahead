"""One owner-authorized real Telegram acceptance; at most two outbound demo messages.

Uses real stock CLI chat, the production post-turn hook, unmodified stock cron
and its live Telegram adapter. No clock/ledger deadline editing or forced ticks.
Same-day extraction misses are retained, not tuned away or labeled reliable.
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

LABEL = 'Lookahead demo test — fictional data; accelerated 5/1-minute timing'
CHAT = __import__('os').environ.get('LOOKAHEAD_DEMO_CHAT_ID', '123456789')


def label_output(text):
    return LABEL+'\n'+text if text.strip() else ''


def settings(now):
    return {'timezone':'America/New_York','enabled':True,'capture_enabled':True,
            'operator_platform':'telegram','operator_user_id':__import__('os').environ.get('LOOKAHEAD_DEMO_USER_ID', CHAT),'operator_chat_id':CHAT,
            'capture_cli':True,'ics_enabled':False,'offer_lead_minutes':5,
            'followup_delay_minutes':1,'spacing_minutes':0,'normal_cap':3,
            'quiet_start':(now.hour+3)%24,'quiet_end':(now.hour-3)%24}


def receipts(text):
    rows=[]
    for line in text.splitlines():
        match=re.search(r"Job '[^']+': delivered to telegram:"+re.escape(CHAT)+r" via live adapter.*message_id=(\d+)",line)
        if match: rows.append({'message_id':match[1],'native_log':line})
    return rows


def no_existing_consumer(state,token):
    import os
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid(): continue
        try: env=(p/'environ').read_bytes().split(b'\0')
        except (OSError,PermissionError): continue
        if ('HERMES_HOME='+str(state)).encode() in env or ('TELEGRAM_BOT_TOKEN='+token).encode() in env:
            found.append(int(p.name))
    if found: raise RuntimeError('existing demo-home/token consumer PIDs: '+str(found))
    return found


def verify_bot(token):
    import urllib.request
    try:
        with urllib.request.urlopen('https://api.telegram.org/bot'+token+'/getMe',timeout=15) as r:
            me=json.load(r)
        with urllib.request.urlopen('https://api.telegram.org/bot'+token+'/getWebhookInfo',timeout=15) as r:
            webhook=json.load(r)
    except Exception as exc:
        raise RuntimeError('bot read-only preflight failed: '+type(exc).__name__) from None
    assert me.get('ok') and me['result']['username']==__import__('os').environ['LOOKAHEAD_TEST_BOT_USERNAME']
    assert webhook.get('ok') and not webhook['result']['url']
    return {'username':me['result']['username'],'bot_id':me['result']['id'],'webhook_empty':True}


def captures(state):
    import sqlite3
    with sqlite3.connect(f'file:{state}/plugin-data/lookahead/data.db?mode=ro',uri=True) as db:
        return [json.loads(r[0]) for r in db.execute('SELECT payload FROM captures')]


def capture_plan(command,state,record,due):
    sentence=f'I will meet the Acorn team {due:%Y-%m-%d at %H:%M} to discuss the budget decision.'
    for attempt in range(1,4):
        command('chat','-q',sentence,'-Q')
        rows=captures(state)
        record('capture_attempt',attempt=attempt,text=sentence,captured=len(rows))
        if rows:
            assert len(rows)==1 and datetime.fromisoformat(rows[0]['due'])==due
            assert rows[0]['quote'] in sentence
            return rows[0]
    raise RuntimeError('three native same-day misses; no cron created and no demo message sent')


def await_deliveries(base,gateway,record,timeout=660):
    import time
    from native_cli import agent_text
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        if gateway.poll() is not None: raise RuntimeError('demo gateway exited early')
        rows=receipts(agent_text(base))
        if len(rows)>=2:
            assert len(rows)==2,'unexpected extra delivery'
            record('two_telegram_api_receipts',receipts=rows)
            return rows
        time.sleep(2)
    raise RuntimeError('bounded wait expired before both API send receipts')


def preserve_and_teardown(preserve, teardown):
    # Stock cron remove deletes native output files, so export first.
    try:
        preserve()
    finally:
        teardown()


def execute(base,state,env,command,record):
    import os
    import subprocess
    from zoneinfo import ZoneInfo
    from native_cli import argv,mark_gateway,wait_telegram,reset_lookahead
    from acceptance_stock import STOCK,teardown
    from collect_evidence import collect
    from acceptance_brief import qualification_config
    gateway=None
    destination=Path(__file__).resolve().parents[1]/'../lookahead-private-evidence/final-20261110'/base.name
    try:
        reset_lookahead(base,command)
        now=datetime.now(ZoneInfo('America/New_York'))
        aux={'provider':'minimax','model':'MiniMax-M2.7'}
        config=qualification_config(settings(now),{'default':'MiniMax-M2.7','provider':'minimax','context_length':128000},aux)
        (state/'config.yaml').write_text(json.dumps(config,indent=2)+'\n')
        (state/'SOUL.md').write_text('Fictional Lookahead demo test. Briefly acknowledge normal user statements. Do not call tools, access accounts, prepare work or create reminders. Lookahead handles its own briefs independently.\n')
        command('--version');command('plugins','enable','lookahead')
        command('plugins','doctor',str(state/'plugins/lookahead'),'--ci')
        command('lookahead','setup','--deliver','telegram');command('lookahead','resume')
        # Prefix only nonempty native tick stdout, without touching stock or plugin logic.
        wrapper="import subprocess\nresult=subprocess.run("+repr([*argv('lookahead','tick')])+",capture_output=True,text=True,timeout=90)\nimport sys\nsys.stderr.write(result.stderr)\nif result.returncode: raise SystemExit(result.returncode)\nif result.stdout.strip(): print("+repr(LABEL)+"+'\\n'+result.stdout,end='')\n"
        (state/'scripts/lookahead_telegram_acceptance_tick.py').write_text(wrapper)
        raw=(base/'gateway.private.log').open('w')
        gateway=subprocess.Popen([*argv('gateway','run')],cwd=STOCK,env=env,stdout=raw,stderr=subprocess.STDOUT,start_new_session=True)
        mark_gateway(base,gateway.pid);record('gateway_started',pid=gateway.pid)
        wait_telegram(base,gateway)
        now=datetime.now(ZoneInfo('America/New_York'))
        due=(now+timedelta(minutes=6)).replace(second=0,microsecond=0)
        parent=capture_plan(command,state,record,due)
        listing=command('lookahead','list');assert parent['id'] in listing.stdout
        record('captured_plan_read_back',capture=parent)
        command('cron','create','* * * * *','--name','lookahead','--no-agent','--script','lookahead_telegram_acceptance_tick.py','--deliver','telegram')
        acks=await_deliveries(base,gateway,record)
        jobs=json.loads((state/'cron/jobs.json').read_text())['jobs']
        for job in jobs:
            if job.get('name')=='lookahead':command('cron','pause',job['id'])
        documents=[]
        owned={j['id'] for j in jobs if j.get('name')=='lookahead'}
        for job_id in owned:
            documents.extend(p.read_text() for p in (state/'cron/output'/job_id).glob('*.md'))
        joined='\n'.join(documents)
        assert joined.count('Preparation brief')==1 and joined.count('Any next steps I should keep track of?')==1
        assert joined.count(LABEL)==2
        reply='It went well. I will send the revised Acorn budget tomorrow at 10:00.'
        command('chat','-q',reply,'-Q')
        children=[r for r in captures(state) if r.get('parent_id')==parent['id']]
        assert len(children)==1,'simulated native CLI reply did not capture one linked next step'
        listing=command('lookahead','list');assert children[0]['id'] in listing.stdout
        record('simulated_reply_next_step_read_back',reply=reply,capture=children[0],input_kind='native CLI; NOT owner Telegram DM')
        record('acceptance_pass',telegram_api_receipts=acks,owner_receipt_confirmed=False,clock='real elapsed; no override',outbound_message_count=2)
    finally:
        preserve_and_teardown(lambda:collect(base,destination), lambda:teardown(command,state,gateway,record))
        raw_path=base/'gateway.private.log'
        if raw_path.exists():
            from auth_diagnostics import scrub
            (base/'gateway.log').write_text(scrub(raw_path.read_text(),os.environ.get('MINIMAX_API_KEY','')))
        no_existing_consumer(state,os.environ['TELEGRAM_BOT_TOKEN'])
        jobs=json.loads((state/'cron/jobs.json').read_text()).get('jobs',[])
        assert not [j for j in jobs if j.get('name')=='lookahead']
        record('teardown_verified',gateway_dead=gateway is None or gateway.poll() is not None,no_demo_home_or_token_consumer=True,owned_jobs_remaining=0)
        collect(base,destination)
        print('EVIDENCE_DIR='+str(destination),flush=True)


def main():
    from demo_fixture import require_demo_config
    require_demo_config()
    import os
    from native_cli import DEMO_ROOT,fixture_state
    from eval_capture import isolated_home
    from demo_fixture import child_env
    from acceptance_brief import recorded_command,redactor
    token=dict(__import__('os').environ).get('TELEGRAM_BOT_TOKEN')
    assert token,'dedicated demo token missing'
    no_existing_consumer(DEMO_ROOT/'demo-home',token)
    identity=verify_bot(token)
    base=isolated_home('telegram-final','MiniMax-M2.7','minimax',persistent_demo=True)
    state=fixture_state(base)
    secret_file=state/'.env'
    secret_file.write_text('TELEGRAM_BOT_TOKEN='+token+'\nTELEGRAM_ALLOWED_USERS='+CHAT+'\nTELEGRAM_ALLOWED_CHATS='+CHAT+'\nTELEGRAM_HOME_CHANNEL='+CHAT+'\n')
    secret_file.chmod(0o600)
    os.environ['TELEGRAM_BOT_TOKEN']=token
    env=child_env(base,os.environ['MINIMAX_API_KEY'])
    env['TELEGRAM_BOT_TOKEN']=token
    redact=redactor([token,os.environ['MINIMAX_API_KEY']])
    with (base/'commands.jsonl').open('a') as log, (base/'transport.jsonl').open('a') as transcript:
        def record(kind,**fields):
            row=redact(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'kind':kind,**fields}))
            transcript.write(row+'\n');transcript.flush();print(row,flush=True)
        record('bot_preflight',**identity)
        command=recorded_command(base,env,log,redact)
        execute(base,state,env,command,record)


if __name__=='__main__': main()