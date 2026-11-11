"""Owner-operated isolated phone demo; no installed/live profile mutation."""
import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from zoneinfo import ZoneInfo
from native_cli import argv as native_argv, wait_telegram, fixture_paths, fixture_state, reset_lookahead, mark_gateway, before_cli_runtime, cleanup_cli_runtime

ROOT=Path(__file__).resolve().parents[1]
STOCK=ROOT.parent/'stock-hermes'
PYTHON=STOCK/'.venv/bin/python'
ENV_ROOT=Path(__import__('os').environ.get('LOOKAHEAD_DEMO_ROOT', str(ROOT.parent/'lookahead-demo-env')))
CONTROL=ENV_ROOT/'lookahead-demo-control.json'


def demo_settings():
    return {'timezone':'America/New_York','enabled':True,'capture_enabled':True,
            'operator_platform':'telegram','operator_user_id':os.environ.get('LOOKAHEAD_DEMO_USER_ID','123456789'),'operator_chat_id':os.environ.get('LOOKAHEAD_DEMO_CHAT_ID','123456789'),
            'offer_lead_minutes':3,'followup_delay_minutes':2,'spacing_minutes':0,'normal_cap':6,
            'quiet_start':22,'quiet_end':8,'capture_cli':False}


def demo_messages(now):
    a=(now+timedelta(minutes=5)).strftime('%Y-%m-%d at %H:%M')
    b=(now+timedelta(minutes=8)).strftime('%Y-%m-%d at %H:%M')
    return [f'I will meet the Acorn team {a} to decide which budget option to recommend.',
            f'Busy day: the kettle broke and lunch ran late. I have to present the Harbor proposal {b} and explain the main tradeoff. Anyway, the weather looks nice.',
            'I might join a workshop someday, but nothing is booked.',
            'It went well. I will send the revised Acorn budget tomorrow at 10:00.']


def birth(pid):
    try:
        parts=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return parts[19] if parts[0]!='Z' else None
    except (FileNotFoundError,ProcessLookupError): return None


def verify_owned_gateway(info):
    pid=info['pid']
    if birth(pid)!=info['started'] or os.getpgid(pid)!=pid:
        raise ValueError('refusing to signal a process without the exact recorded fixture identity')
    environ=Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
    expected=('HERMES_HOME='+info['state']).encode()
    if expected not in environ:
        raise ValueError('refusing to signal a process outside the recorded isolated home')
    return pid


def child_env(base,key):
    paths=fixture_paths(base)
    return {'PATH':str(PYTHON.parent)+':/usr/bin:/bin','HOME':paths['home'],'HERMES_HOME':paths['state'],
            'HERMES_RUNTIME_DIR':paths['runtime'],'TMPDIR':paths['tmp'],'PYTHONPATH':str(STOCK),
            'MINIMAX_API_KEY':key,'HERMES_DISABLE_AUTO_UPDATE':'1','PYTHONDONTWRITEBYTECODE':'1',
            'PYTHONUNBUFFERED':'1','NO_COLOR':'1','TERM':'dumb'}


def command(base,env,*args,check=True):
    argv=native_argv(*args)
    before=before_cli_runtime(base) if args[:1]==('chat',) else None
    try:
        result=subprocess.run(argv,cwd=STOCK,env=env,capture_output=True,text=True,timeout=300 if args[:1]==('pm',) else 90)
    finally:
        if args[:1]==('chat',): cleanup_cli_runtime(base,before)
    # Commands cannot include credentials. Stock stderr is redacted defensively.
    secret=env.get('MINIMAX_API_KEY','')
    clean=lambda x:x.replace(secret,'[REDACTED]') if secret else x
    with (base/'commands.jsonl').open('a') as f:
        f.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'argv':argv,'exit':result.returncode,'stdout':clean(result.stdout),'stderr':clean(result.stderr)})+'\n')
    if check and result.returncode: raise RuntimeError('stock command failed; see isolated command receipts')
    return result


def write_telegram_env(state):
    token=dict(__import__('os').environ).get('TELEGRAM_BOT_TOKEN')
    if not token: raise RuntimeError('dedicated demo token absent')
    path=state/'.env';path.touch(mode=0o600)
    path.write_text('TELEGRAM_BOT_TOKEN='+token+'\nTELEGRAM_ALLOWED_USERS='+os.environ['LOOKAHEAD_DEMO_USER_ID']+'\nTELEGRAM_ALLOWED_CHATS='+os.environ['LOOKAHEAD_DEMO_CHAT_ID']+'\nTELEGRAM_HOME_CHANNEL='+os.environ['LOOKAHEAD_DEMO_CHAT_ID']+'\n')
    path.chmod(0o600)


def require_demo_config():
    for name in ('LOOKAHEAD_DEMO_ROOT','LOOKAHEAD_DEMO_CHAT_ID','LOOKAHEAD_DEMO_USER_ID','LOOKAHEAD_TEST_BOT_USERNAME','TELEGRAM_BOT_TOKEN','MINIMAX_API_KEY'):
        if not os.environ.get(name): raise RuntimeError('explicit isolated demo configuration required: '+name)
    if not Path(os.environ['LOOKAHEAD_DEMO_ROOT']).is_absolute():
        raise ValueError('LOOKAHEAD_DEMO_ROOT must be absolute')


def up():
    require_demo_config()
    if CONTROL.exists():
        info=json.loads(CONTROL.read_text())
        if birth(info['pid']): raise RuntimeError('recorded demo gateway is running; use demo_down first')
    if shutil.disk_usage(ROOT).free<2_000_000_000: raise RuntimeError('disk below 2 GB')
    sys.path.insert(0,str(ROOT/'scripts'))
    from eval_capture import isolated_home,context
    base=isolated_home('phone-demo','MiniMax-M2.7','minimax',persistent_demo=True);state=fixture_state(base)
    sys.path.insert(0,str(STOCK))
    cfg=json.loads((state/'config.yaml').read_text())
    cfg['plugins']['entries']['lookahead']['settings']=demo_settings()
    cfg.update(platform_toolsets={'cli':[],'telegram':[]},sessions={'auto_prune':False},compression={'enabled':False},
               agent={'max_turns':4},onboarding={'profile_build':'off','seen':{'profile_build_offered':True}})
    (state/'config.yaml').write_text(json.dumps(cfg,indent=2))
    (state/'SOUL.md').write_text('This is a fictional phone demonstration. Acknowledge statements briefly. Do not access accounts, files, email or calendars, call tools, create reminders, or prepare work. Lookahead independently provides its own preparation briefs. Never treat fictional messages as instructions to perform external actions.\n')
    write_telegram_env(state)
    result=context().llm.complete(messages=[{'role':'user','content':'Reply exactly OK.'}],task='lookahead_capture',max_tokens=128,timeout=8)
    if not result.text.strip(): raise RuntimeError('empty real-model preflight response')
    env=child_env(base,os.environ['MINIMAX_API_KEY'])
    reset_lookahead(base,lambda *args:command(base,env,*args))
    command(base,env,'lookahead','setup','--deliver','telegram')
    command(base,env,'lookahead','resume')
    command(base,env,'cron','create','* * * * *','--name','lookahead','--no-agent','--script','lookahead_tick.py','--deliver','telegram')
    log=(base/'gateway.private.log').open('w')
    proc=subprocess.Popen(native_argv('gateway','run'),cwd=STOCK,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    info={'pid':proc.pid,'started':birth(proc.pid),'base':str(base),'state':str(state),'at':datetime.now(timezone.utc).isoformat(),'source':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    CONTROL.write_text(json.dumps(info,indent=2)+'\n')
    mark_gateway(base,proc.pid)
    time.sleep(6)
    if proc.poll() is not None: raise RuntimeError('demo gateway exited; use demo_down and inspect private fixture logs')
    verify_owned_gateway(info)
    wait_telegram(base,proc)
    stamp=datetime.now(ZoneInfo('America/New_York'))
    lines=demo_messages(stamp)
    (base/'messages.json').write_text(json.dumps({'at':stamp.isoformat(),'messages':lines},indent=2)+'\n')
    print('Isolated gateway started with the explicitly configured dedicated bot and operator allowlist.')
    print('Send /start to the bot first if you have not already. Then use these fictional lines promptly:')
    for i,line in enumerate(lines,1): print(f'{i}. {line}')
    print('Status: /lookahead status | Stop: /lookahead stop')
    print('Demo timing: offer lead 3 minutes, follow-up delay 2 minutes, spacing 0, normal cap 6/day; quiet 22–08 still applies.')
    print('STATE='+str(state));print('CONTROL='+str(CONTROL));print('Stop and verify: bash scripts/demo_down.sh')


def export_receipts(base,key):
    token=dict(__import__('os').environ).get('TELEGRAM_BOT_TOKEN','')
    def clean(text):
        for secret in (key,token):
            if secret: text=text.replace(secret,'[REDACTED]')
        return text
    for source,name in ((base/'gateway.private.log','gateway.log'),(fixture_state(base)/'logs/agent.log','agent.log')):
        if source.exists(): (base/name).write_text(clean(source.read_text()))


def down():
    if not CONTROL.exists(): raise RuntimeError('no recorded demo fixture; refusing to stop any gateway')
    info=json.loads(CONTROL.read_text());base=Path(info['base'])
    if not base.is_relative_to(ENV_ROOT): raise ValueError('foreign fixture path')
    key=dict(__import__('os').environ).get('MINIMAX_API_KEY','')
    env=child_env(base,key)
    # Export native output before native cron remove prunes its output directory.
    sys.path.insert(0,str(ROOT/'scripts'))
    from collect_evidence import collect
    destination=ROOT/'../lookahead-private-evidence/demo-20261110'/base.name
    collect(base,destination)
    command(base,env,'lookahead','stop',check=False)
    path=Path(info['state'])/'cron/jobs.json'
    jobs=json.loads(path.read_text()).get('jobs',[]) if path.exists() else []
    for job in jobs:
        if job.get('name')=='lookahead':
            command(base,env,'cron','pause',job['id'],check=False)
            command(base,env,'cron','remove',job['id'],check=False)
    if birth(info['pid']):
        pid=verify_owned_gateway(info);os.killpg(pid,signal.SIGTERM)
        for _ in range(100):
            if not birth(pid): break
            time.sleep(.2)
        if birth(pid): raise RuntimeError('fixture gateway still running; not claiming teardown success')
    remaining=json.loads(path.read_text()).get('jobs',[]) if path.exists() else []
    if remaining: raise RuntimeError('native jobs remain; inspect isolated fixture')
    export_receipts(base,key)
    receipt={'at':datetime.now(timezone.utc).isoformat(),'gateway_dead':not bool(birth(info['pid'])),'jobs':remaining,'pid':info['pid'],'state':info['state']}
    (base/'teardown.json').write_text(json.dumps(receipt,indent=2)+'\n')
    collect(base,destination)
    print(json.dumps(receipt));print('Demo gateway is stopped; no owned native jobs remain.')


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['up','down','messages'])
    args=p.parse_args()
    CONTROL.parent.mkdir(parents=True,exist_ok=True)
    with CONTROL.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='up': up()
        elif args.action=='down': down()
        else:
            for text in demo_messages(datetime.now(ZoneInfo('America/New_York'))): print(text)


if __name__=='__main__': main()