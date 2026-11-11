"""Credential-free acceptance harness: real stock IRC adapter, local IRC peer/provider.

Not a real model or public IRC service. No core patches or scheduler helper calls.
Run with the stock interpreter; all child environments are allowlisted and isolated.
"""
import argparse
from datetime import datetime, timedelta, timezone
import http.server
import json
import os
from pathlib import Path
import shutil
import signal
import socketserver
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT.parent/'stock-hermes'
PYTHON = STOCK/'.venv/bin/python'


def teardown(command,state,gateway,record):
    command('lookahead','stop',check=False)
    jobs_path = state/'cron'/'jobs.json'
    if jobs_path.exists():
        data = json.loads(jobs_path.read_text())
        jobs = data.get('jobs',[]) if isinstance(data,dict) else data
        for job in jobs:
            if job.get('name') == 'lookahead':
                command('cron','pause',job['id'],check=False)
                command('cron','remove',job['id'],check=False)
    if gateway and gateway.poll() is None:
        os.killpg(gateway.pid,signal.SIGTERM)
        try:
            gateway.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(gateway.pid,signal.SIGKILL);gateway.wait()
    record('teardown',gateway_exit=gateway.returncode if gateway else None,state=str(state))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout',type=int,default=180)
    args = parser.parse_args()
    base = ROOT.parent/'env'/('acceptance-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    home, state = base/'home', base/'hermes'
    for directory in (home,state,base/'tmp'):
        directory.mkdir(parents=True)
    env = {'PATH':str(PYTHON.parent)+':/usr/bin:/bin','HOME':str(home),'HERMES_HOME':str(state),
           'HERMES_RUNTIME_DIR':str(base/'runtime'),'TMPDIR':str(base/'tmp'),'PYTHONDONTWRITEBYTECODE':'1',
           'PYTHONPATH':str(STOCK),'PYTHONUNBUFFERED':'1','NO_COLOR':'1','TERM':'dumb',
           'HERMES_DISABLE_AUTO_UPDATE':'1'}
    log = open(base/'commands.jsonl','a')
    def command(*argv,check=True):
        cmd = ['nice','-n','10',str(PYTHON),'-m','hermes_cli.main',*argv]
        result = subprocess.run(cmd,cwd=STOCK,env=env,text=True,capture_output=True,timeout=90)
        receipt = {'at':datetime.now(timezone.utc).isoformat(),'argv':cmd,'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
        log.write(json.dumps(receipt)+'\n'); log.flush()
        print(json.dumps(receipt),flush=True)
        if check and result.returncode:
            raise RuntimeError('command failed')
        return result
    transcript = open(base/'transport.jsonl','a')
    lock = threading.Lock()
    def record(kind,**fields):
        with lock:
            row = {'at':datetime.now(timezone.utc).isoformat(),'monotonic':time.monotonic(),'kind':kind,**fields}
            transcript.write(json.dumps(row)+'\n');transcript.flush()
            print(json.dumps(row),flush=True)
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo('America/New_York'))
    due = now+timedelta(hours=2)
    when = due.strftime('%Y-%m-%d at %H:%M')
    sentence = "Tough day, I've got to meet with my boss "+when+' to talk about how we save this account.'
    delivered = threading.Event()
    class Model(http.server.BaseHTTPRequestHandler):
        def log_message(self,*a):
            pass
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({'object':'list','data':[{'id':'local-scripted','object':'model','owned_by':'fixture'}]}).encode())
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            extraction = 'Extract only definite future' in json.dumps(data.get('messages',[]))
            record('provider_request',path=self.path,extraction=extraction,stream=bool(data.get('stream')))
            text = json.dumps({'items':[{'subject':'Boss account recovery meeting','quote':sentence,'when':when,'confidence':.95,'help_kind':'talking_points'}]}) if extraction else 'That sounds difficult. We can take it one step at a time.'
            self.send_response(200)
            self.send_header('Content-Type','text/event-stream' if data.get('stream') else 'application/json')
            self.end_headers()
            if data.get('stream'):
                for delta,finish in [({'role':'assistant','content':text},None),({},'stop')]:
                    self.wfile.write(('data: '+json.dumps({'id':'fixture','object':'chat.completion.chunk','created':int(time.time()),'model':'local-scripted','choices':[{'index':0,'delta':delta,'finish_reason':finish}]})+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')
            else:
                self.wfile.write(json.dumps({'id':'fixture','object':'chat.completion','created':int(time.time()),'model':'local-scripted','choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':30,'total_tokens':130}}).encode())
    class IRC(socketserver.StreamRequestHandler):
        def handle(self):
            nick = 'lookahead-test'
            while line := self.rfile.readline():
                text = line.decode().rstrip('\r\n')
                record('irc_client',line=text)
                if text.startswith('NICK '):
                    nick = text.split(' ',1)[1]
                if text.startswith('USER '):
                    self.wfile.write(f':local.test 001 {nick} :Welcome\r\n'.encode());self.wfile.flush()
                if text.startswith('JOIN '):
                    self.wfile.write(f':{nick}!test@localhost JOIN :#lookahead\r\n'.encode());self.wfile.flush()
                    time.sleep(3)
                    # A normal chat sentence, not a remind-me or manual cron command.
                    self.wfile.write(f':operator!test@localhost PRIVMSG {nick} :{sentence}\r\n'.encode());self.wfile.flush()
                    record('offhand_chat_sent',text=sentence)
                if text.startswith('PRIVMSG operator :') and 'Lookahead:' in text:
                    delivered.set()
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True
    provider = http.server.ThreadingHTTPServer(('127.0.0.1',0),Model)
    irc = Server(('127.0.0.1',0),IRC)
    for server in (provider,irc):
        threading.Thread(target=server.serve_forever,daemon=True).start()
    env.update({'IRC_SERVER':'127.0.0.1','IRC_PORT':str(irc.server_address[1]),'IRC_USE_TLS':'false',
                'IRC_NICKNAME':'lookahead-test','IRC_CHANNEL':'#lookahead','IRC_HOME_CHANNEL':'operator',
                'IRC_ALLOWED_USERS':'operator'})
    settings = {'timezone':'America/New_York','enabled':True,'capture_enabled':True,'operator_platform':'irc',
                'operator_user_id':'operator','operator_chat_id':'operator',
                'quiet_start':(now.hour+2)%24,'quiet_end':(now.hour-2)%24}
    config = {'model':{'default':'local-scripted','provider':'custom','base_url':f'http://127.0.0.1:{provider.server_port}/v1','api_key':'local-fixture-not-a-secret','context_length':128000},
              'auxiliary':{'lookahead_capture':{'provider':'custom','model':'local-scripted','base_url':f'http://127.0.0.1:{provider.server_port}/v1','api_key':'local-fixture-not-a-secret'}},
              'plugins':{'entries':{'lookahead':{'enabled':True,'settings':settings}}},
              'memory':{'memory_enabled':False,'user_profile_enabled':False},'compression':{'enabled':False},
              'agent':{'max_turns':2},'onboarding':{'profile_build':'off','seen':{'profile_build_offered':True}}}
    # JSON is valid YAML; no dependency or credentials inherited.
    (state/'config.yaml').write_text(json.dumps(config,indent=2))
    target = state/'plugins'/'lookahead'
    shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.git','__pycache__','.ruff_cache','.pytest_cache'))
    gateway = None
    try:
        command('--version')
        command('plugins','enable','lookahead')
        command('plugins','list','--plain','--no-bundled')
        command('plugins','doctor',str(target),'--ci',check=False)
        command('plugins','validate',str(target),'--install-deps','--json',check=False)
        command('lookahead','setup','--deliver','irc')
        command('lookahead','stop')
        command('cron','create','every 1m','--name','lookahead','--no-agent','--script','lookahead_tick.py','--deliver','irc')
        command('cron','list')
        started = time.monotonic()
        gateway_log = open(base/'gateway.log','w')
        gateway = subprocess.Popen(['nice','-n','10',str(PYTHON),'-m','hermes_cli.main','gateway','run'],cwd=STOCK,env=env,stdout=gateway_log,stderr=subprocess.STDOUT,start_new_session=True)
        record('gateway_started',pid=gateway.pid)
        # Allow actual interval fires; never call cron run or scheduler helpers.
        time.sleep(85)
        stopped_job = json.loads((state/'cron/jobs.json').read_text())['jobs'][0]
        record('stopped_tick',job=stopped_job,delivered=delivered.is_set())
        assert stopped_job['last_run_at'] and not delivered.is_set()
        command('lookahead','list')
        command('lookahead','resume')
        command('plugins','disable','lookahead')
        import sqlite3
        def ledger():
            with sqlite3.connect(f'file:{state}/plugin-data/lookahead/data.db?mode=ro',uri=True) as db:
                return {t:db.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in ('captures','facts','handoffs','meta')}
        disabled_before = ledger()
        time.sleep(145)
        disabled_job = json.loads((state/'cron/jobs.json').read_text())['jobs'][0]
        record('disabled_tick',job=disabled_job,delivered=delivered.is_set(),ledger_unchanged=ledger()==disabled_before)
        assert ledger() == disabled_before
        assert disabled_job['last_run_at'] != stopped_job['last_run_at'] and not delivered.is_set()
        command('plugins','enable','lookahead')
        ok = delivered.wait(args.timeout)
        record('elapsed_tick_result',delivered=ok,elapsed_seconds=time.monotonic()-started,gateway_exit=gateway.poll())
        command('lookahead','list')
        command('lookahead','status')
        if not ok:
            raise RuntimeError('no unsolicited local IRC delivery before timeout')
    finally:
        teardown(command,state,gateway,record)
        provider.shutdown();irc.shutdown()
        log.close();transcript.close()
        print('EVIDENCE_DIR='+str(base),flush=True)


if __name__ == '__main__':
    main()
