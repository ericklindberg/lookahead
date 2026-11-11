"""Native PM entry points and explicitly persistent, isolated demo fixtures."""
from datetime import datetime, timezone
import json
import os
import signal
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
STOCK=ROOT.parent/'stock-hermes'
DEMO_ROOT=Path(__import__('os').environ.get('LOOKAHEAD_DEMO_ROOT', str(ROOT.parent/'lookahead-demo-env')))


def quiet_host_config():
    # Stock v0.23.0 uses this one per-platform flag for both restart and shutdown notices.
    return {'platforms':{'telegram':{'gateway_restart_notification':False}}}


def argv(*args):
    entry=STOCK/'.hermes/bin/hermes'
    if entry.is_file(): return [str(entry),*args]
    return [str(STOCK/'.venv/bin/python'),'-m','hermes_cli.main',*args]


def process_stamp(pid):
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return fields[19] if fields[0]!='Z' else None
    except (FileNotFoundError,ProcessLookupError): return None


def make_fixture(label,*,persistent_demo=False,env_root=None):
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    base=(DEMO_ROOT/'runs' if persistent_demo else Path(env_root or ROOT.parent/'env'))/('real-'+label+'-'+stamp)
    base.mkdir(parents=True)
    paths=({'home':str(DEMO_ROOT/'demo-os-home'),'state':str(DEMO_ROOT/'demo-home'),
            'runtime':str(DEMO_ROOT/'demo-runtime'),'tmp':str(DEMO_ROOT/'demo-tmp')}
           if persistent_demo else {k:str(base/v) for k,v in {'home':'home','state':'hermes','runtime':'runtime','tmp':'tmp'}.items()})
    for path in paths.values(): Path(path).mkdir(parents=True,exist_ok=True)
    marker=Path(paths['state'])/'lookahead-demo-gateway.json'
    if persistent_demo and marker.exists():
        current=json.loads(marker.read_text())
        if process_stamp(current['pid'])==current['started']:
            raise RuntimeError('a recorded demo gateway is still running; stop it before reusing this home')
    log=Path(paths['state'])/'logs/agent.log'
    paths['agent_log_offset']=log.stat().st_size if log.exists() else 0
    (base/'fixture.json').write_text(json.dumps(paths,indent=2)+'\n')
    return base,paths


def fixture_paths(base):
    path=base/'fixture.json'
    return json.loads(path.read_text()) if path.exists() else {'home':str(base/'home'),'state':str(base/'hermes'),'runtime':str(base/'runtime'),'tmp':str(base/'tmp'),'agent_log_offset':0}


def fixture_state(base): return Path(fixture_paths(base)['state'])


def agent_text(base):
    settings=fixture_paths(base);path=Path(settings['state'])/'logs/agent.log'
    if not path.exists(): return ''
    with path.open('rb') as f:
        f.seek(settings.get('agent_log_offset',0));return f.read().decode(errors='replace')


def mark_gateway(base,pid):
    (fixture_state(base)/'lookahead-demo-gateway.json').write_text(json.dumps({'pid':pid,'started':process_stamp(pid),'receipt_base':str(base)})+'\n')


def runtime_identity(base):
    state=fixture_state(base)
    if state!=DEMO_ROOT/'demo-home': return None
    path=state/'gateway_state.json'
    if not path.exists(): return None
    data=json.loads(path.read_text());pid=data.get('pid')
    if type(pid) is not int or pid<=0: return None
    birth=process_stamp(pid)
    if birth is None: return None
    if data.get('kind')!='hermes-gateway' or data.get('hermes_home')!=str(state):
        raise RuntimeError('runtime descriptor has an unexpected home or kind')
    if str(data.get('start_time'))!=birth: raise RuntimeError('runtime PID birth differs from descriptor')
    env=Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
    if ('HERMES_HOME='+str(state)).encode() not in env: raise RuntimeError('runtime process home differs from fixture')
    if os.getpgid(pid)!=pid: raise RuntimeError('runtime is not its own recorded process group')
    return {'pid':pid,'started':birth,'state':str(state)}


def _protected_runtime(base,current):
    path=fixture_state(base)/'lookahead-demo-gateway.json'
    if not path.exists(): return False
    record=json.loads(path.read_text())
    return record.get('pid')==current['pid'] and record.get('started')==current['started']


def before_cli_runtime(base):
    current=runtime_identity(base)
    if current and not _protected_runtime(base,current):
        raise RuntimeError('unclaimed persistent CLI owner exists; verify and stop that fixture before proceeding')
    return current


def cleanup_cli_runtime(base,before):
    current=runtime_identity(base)
    if not current or _protected_runtime(base,current): return False
    if before is not None: raise RuntimeError('refusing to stop an owner that pre-existed this CLI command')
    pid=current['pid']
    if process_stamp(pid)!=current['started']: raise RuntimeError('runtime identity changed before cleanup')
    os.kill(pid,signal.SIGTERM)
    deadline=time.monotonic()+20
    while process_stamp(pid)==current['started'] and time.monotonic()<deadline: time.sleep(.1)
    if process_stamp(pid)==current['started']: raise RuntimeError('owned CLI gateway did not exit')
    row={**current,'terminated':True,'origin':'stock CLI auto-start','at':datetime.now(timezone.utc).isoformat()}
    with (base/'cli-runtime-cleanup.jsonl').open('a') as f: f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
    return True


def prepare_telegram(command,enabled=True):
    if not enabled: return
    command('pm','install','--tools-only')
    command('pm','install','--extra','telegram')


def prepare_logged(base,env):
    from auth_diagnostics import scrub
    def command(*args):
        if shutil.disk_usage(ROOT).free<2_000_000_000: raise RuntimeError('fixture disk below 2 GB')
        cmd=argv(*args)
        result=subprocess.run(cmd,cwd=STOCK,env=env,text=True,capture_output=True,timeout=600)
        row={'at':datetime.now(timezone.utc).isoformat(),'argv':cmd,'exit':result.returncode,
             'stdout':scrub(result.stdout,''),'stderr':scrub(result.stderr,'')}
        with (base/'commands.jsonl').open('a') as f: f.write(json.dumps(row)+'\n')
        print(json.dumps(row),flush=True)
        if result.returncode: raise RuntimeError('stock PM preparation refused; see exact scrubbed stderr above')
    prepare_telegram(command)


def reset_lookahead(base,command,enabled=True):
    """Explicit owner-approved fictional-demo reset; never run by plugin ticks."""
    if not enabled: return
    state=fixture_state(base)
    if state!=DEMO_ROOT/'demo-home': raise ValueError('reset is restricted to the dedicated persistent demo home')
    marker=state/'lookahead-demo-gateway.json'
    if marker.exists():
        prior=json.loads(marker.read_text())
        if process_stamp(prior['pid'])==prior['started']: raise RuntimeError('refusing to reset a running demo gateway')
    command('lookahead','stop')
    path=state/'cron/jobs.json'
    jobs=json.loads(path.read_text()).get('jobs',[]) if path.exists() else []
    owned=[j for j in jobs if j.get('name')=='lookahead']
    for job in owned:
        command('cron','pause',job['id']);command('cron','remove',job['id'])
    tables=('facts','handoffs','captures','forgotten','capture_turns','followups','meta')
    dbpath=state/'plugin-data/lookahead/data.db'
    with sqlite3.connect(dbpath) as db:
        if db.execute('PRAGMA user_version').fetchone()[0]!=1: raise RuntimeError('unknown demo Lookahead schema; reset refused')
        before={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables}
        for table in tables: db.execute('DELETE FROM '+table)
        db.execute("INSERT INTO meta VALUES ('stopped','true')")
        after={t:db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables}
    receipt={'at':datetime.now(timezone.utc).isoformat(),'explicit_demo_only_reset':True,'state':str(state),
             'owned_jobs_removed':[j['id'] for j in owned],'lookahead_rows_before':before,'lookahead_rows_after':after,
             'core_sessions_credentials_dependencies_untouched':True}
    (base/'lookahead-reset.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt),flush=True)


def wait_telegram(base,process,timeout=75):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        private=base/'gateway.private.log'
        logs=(private.read_text() if private.exists() else '')+'\n'+agent_text(base)
        if 'Connected to Telegram' in logs: return
        if process.poll() is not None: raise RuntimeError('fixture gateway exited before Telegram connected')
        if "Platform 'Telegram' requirements not met" in logs:
            raise RuntimeError('stock Telegram dependency preflight failed; no test plan sent')
        time.sleep(.5)
    raise RuntimeError('Telegram adapter did not report connected; no test plan sent')