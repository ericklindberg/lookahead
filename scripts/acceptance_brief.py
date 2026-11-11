"""Elapsed stock cron proof. Scripted mode is plumbing-only, never real-model evidence.

--real-model uses the approved key via eval_capture.isolated_home; --telegram is an
explicitly approved dedicated-bot transport (never production tokens). All fixtures
are fictional. Does not invoke cron run, manipulate deadlines or patch stock core.
"""
import argparse
from datetime import datetime, timedelta, timezone
import http.server
import json
import os
from pathlib import Path
import shutil
import socketserver
import sqlite3
import subprocess
import threading
import time

from acceptance_stock import ROOT, STOCK, PYTHON, teardown
from native_cli import argv as native_argv, wait_telegram, fixture_paths, agent_text, mark_gateway, reset_lookahead, quiet_host_config, before_cli_runtime, cleanup_cli_runtime



def model_handler(record,when):
    class Model(http.server.BaseHTTPRequestHandler):
        def log_message(self,*a): pass
        def do_GET(self):
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
            self.wfile.write(json.dumps({'data':[{'id':'local-scripted','object':'model'}]}).encode())
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            messages=body.get('messages',[])
            system=' '.join(m.get('content','') for m in messages if m.get('role')=='system')
            kind='capture' if 'Extract only definite future' in system else 'brief' if 'Create suggested preparation' in system else 'chat'
            record('scripted_provider_request',kind_detail=kind,stream=bool(body.get('stream')))
            if kind=='capture':
                data=json.loads(messages[-1]['content']);text=data['text'];child='revised Acorn' in text
                content=json.dumps({'items':[{'subject':'Send revised Acorn budget' if child else 'Acorn budget decision meeting','quote':text,'when':'tomorrow at 10:00' if child else when,'confidence':.95,'help_kind':'email_review' if child else 'talking_points'}]})
            elif kind=='brief': content=json.dumps({'prep':'List the budget decision and options you want to discuss.','question':'What decision do you need from the Acorn team?'})
            else: content='Noted. I hope the discussion goes well.'
            self.send_response(200);self.send_header('Content-Type','text/event-stream' if body.get('stream') else 'application/json');self.end_headers()
            if body.get('stream'):
                for delta,finish in [({'role':'assistant','content':content},None),({},'stop')]:
                    self.wfile.write(('data: '+json.dumps({'id':'fixture','object':'chat.completion.chunk','created':int(time.time()),'model':'local-scripted','choices':[{'index':0,'delta':delta,'finish_reason':finish}]})+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')
            else:
                self.wfile.write(json.dumps({'id':'fixture','object':'chat.completion','created':int(time.time()),'model':'local-scripted','choices':[{'index':0,'message':{'role':'assistant','content':content},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':40,'total_tokens':140}}).encode())
    return Model


def irc_server(record,sentence,reply,received,brief_received,followup_received,reply_sent):
    class IRC(socketserver.StreamRequestHandler):
        def handle(self):
            nick='lookahead-test'
            while line:=self.rfile.readline():
                text=line.decode().rstrip('\r\n');record('irc_client',line=text)
                if text.startswith('NICK '): nick=text.split(' ',1)[1]
                if text.startswith('USER '): self.wfile.write(f':local.test 001 {nick} :Welcome\r\n'.encode());self.wfile.flush()
                if text.startswith('JOIN '):
                    self.wfile.write(f':{nick}!test@localhost JOIN :#lookahead\r\n'.encode());self.wfile.flush();time.sleep(3)
                    self.wfile.write(f':operator!test@localhost PRIVMSG {nick} :{sentence}\r\n'.encode());self.wfile.flush();record('offhand_chat_sent',text=sentence)
                if text.startswith('PRIVMSG operator :'):
                    received.append(text)
                    if 'Preparation brief' in text: brief_received.set()
                    if 'Any next steps I should keep track of?' in text:
                        followup_received.set();time.sleep(2)
                        self.wfile.write(f':operator!test@localhost PRIVMSG {nick} :{reply}\r\n'.encode());self.wfile.flush();reply_sent.set();record('followup_reply_sent',text=reply)
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address=True;daemon_threads=True
    return Server,IRC



def await_result(args,gateway,ledger,base,command,brief_received,followup_received,reply_sent,received):
    start=time.monotonic()
    while time.monotonic()-start<args.timeout:
        if shutil.disk_usage(ROOT).free<2_000_000_000: raise RuntimeError('disk below 2 GB')
        rows=ledger()
        if any(r.get('parent_id') for r in rows): break
        if args.telegram:
            agent=agent_text(base)
            if agent.count('delivered to telegram:'+os.environ['LOOKAHEAD_DEMO_CHAT_ID']+' via live adapter')>=2:
                break
        if gateway.poll() is not None: raise RuntimeError('fixture gateway exited')
        time.sleep(3)
    (base/'captures.json').write_text(json.dumps(ledger(),indent=2))
    command('lookahead','list');command('lookahead','status')
    if not args.telegram:
        assert brief_received.is_set() and followup_received.is_set() and reply_sent.is_set()
        assert any(r.get('parent_id') for r in ledger()),'no linked next step'
        assert sum('Any next steps I should keep track of?' in x for x in received)==1
    else:
        # This phase proves outbound Telegram only. The bot token cannot impersonate
        # the user; IRC separately proves a normal inbound linked next-step reply.
        agent=agent_text(base)
        assert agent.count('delivered to telegram:'+os.environ['LOOKAHEAD_DEMO_CHAT_ID']+' via live adapter')==2
        docs='\n'.join(p.read_text() for p in (Path(fixture_paths(base)['state'])/'cron/output').rglob('*.md'))
        assert docs.count('Preparation brief')==1 and docs.count('Any next steps I should keep track of?')==1
        assert 'Low disk space' not in agent and 'Auto-prune is off' not in agent
        assert not any('sending response' in line.lower() and '[telegram]' in line.lower() for line in agent.splitlines()),'unexpected non-cron Telegram response'



def real_preflight(args,record):
    if not args.real_model: return
    import sys
    sys.path.insert(0,str(STOCK))
    from eval_capture import context
    try:
        result=context().llm.complete(messages=[{'role':'user','content':'Reply exactly OK'}],task='lookahead_capture',max_tokens=128,timeout=8)
        record('real_model_preflight',model=result.model,text=result.text)
    except Exception as exc:
        record('real_model_blocked',error_type=type(exc).__name__,status=getattr(exc,'status_code',None))
        raise RuntimeError('real-model preflight failed; no schedule or gateway started') from None



def redactor(secrets):
    def redact(text):
        for secret in secrets:
            if secret: text=text.replace(secret,'[REDACTED]')
        return text
    return redact


def qualification_due(now,overnight=False):
    if overnight:return (now+timedelta(days=1)).replace(hour=9,minute=30,second=0,microsecond=0)
    return (now+timedelta(minutes=4)).replace(second=0,microsecond=0)


def qualification_settings(now,*,telegram,overnight=False):
    return {'timezone':'America/New_York','enabled':True,'capture_enabled':True,
            'operator_platform':'telegram' if telegram else 'irc',
            'operator_user_id':os.environ.get('LOOKAHEAD_DEMO_USER_ID','123456789') if telegram else 'operator',
            'operator_chat_id':os.environ.get('LOOKAHEAD_DEMO_CHAT_ID','123456789') if telegram else 'operator','capture_cli':telegram,
            'offer_lead_minutes':0 if overnight else 5,'followup_delay_minutes':120 if overnight else 1,
            'spacing_minutes':30 if overnight else 0,'quiet_start':22 if overnight else (now.hour+3)%24,
            'quiet_end':8 if overnight else (now.hour-3)%24}


def qualification_config(settings,model_config,aux):
    return {'_config_version':12,'model':model_config,'auxiliary':{'lookahead_capture':aux,'lookahead_brief':aux},
            'plugins':{'enabled':['lookahead'],'entries':{'lookahead':{'settings':settings}}},
            'memory':{'memory_enabled':False,'user_profile_enabled':False},'compression':{'enabled':False},
            'agent':{'max_turns':4},'onboarding':{'profile_build':'off','seen':{'profile_build_offered':True}},
            'platform_toolsets':{'cli':[],'irc':[],'telegram':[]},'sessions':{'auto_prune':False},**quiet_host_config()}


def recorded_command(base,env,log,redact):
    def command(*argv,check=True):
        cmd=['nice','-n','10',*native_argv(*argv)]
        before=before_cli_runtime(base) if argv[:1]==('chat',) else None
        try:
            result=subprocess.run(cmd,cwd=STOCK,env=env,text=True,capture_output=True,timeout=300 if argv[:1]==('pm',) else 90)
        finally:
            if argv[:1]==('chat',):cleanup_cli_runtime(base,before)
        row={'at':datetime.now(timezone.utc).isoformat(),'argv':cmd,'exit':result.returncode,'stdout':redact(result.stdout),'stderr':redact(result.stderr)}
        log.write(json.dumps(row)+'\n');log.flush();print(json.dumps(row),flush=True)
        if check and result.returncode: raise RuntimeError('stock command failed')
        return result
    return command


def require_transport_config(args):
    if args.telegram:
        from demo_fixture import require_demo_config
        require_demo_config()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--real-model',default=None)
    p.add_argument('--provider',choices=['kimi-coding','minimax','openrouter'],default='kimi-coding')
    p.add_argument('--skip-validator',action='store_true',help='Reuse separately recorded stock validator proof; avoid another runtime tree.')
    p.add_argument('--telegram',action='store_true')
    p.add_argument('--tomorrow-morning',action='store_true',help='Tomorrow 09:30 local, real default evening-before / 120-minute follow-up; reserves the dedicated bot overnight.')
    p.add_argument('--timeout',type=int,default=None,help='Hard elapsed bound: defaults to 480s, or 72000s for overnight mode.')
    args=p.parse_args()
    require_transport_config(args)
    if args.tomorrow_morning and not (args.telegram and args.real_model):p.error('overnight mode requires a real-model dedicated Telegram run')
    if args.timeout is None:args.timeout=72000 if args.tomorrow_morning else 480
    if shutil.disk_usage(ROOT).free<2_000_000_000: raise RuntimeError('disk below 2 GB')
    if args.real_model:
        from eval_capture import isolated_home
        base=isolated_home('acceptance',args.real_model,args.provider,persistent_demo=args.telegram)
    else:
        base=ROOT.parent/'env'/('brief-scripted-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        for path in (base/'home',base/'hermes',base/'tmp'): path.mkdir(parents=True)
    paths=fixture_paths(base)
    home,state=Path(paths['home']),Path(paths['state'])
    env={'PATH':str(PYTHON.parent)+':/usr/bin:/bin','HOME':str(home),'HERMES_HOME':str(state),
         'HERMES_RUNTIME_DIR':paths['runtime'],'TMPDIR':paths['tmp'],'PYTHONDONTWRITEBYTECODE':'1',
         'PYTHONPATH':str(STOCK),'PYTHONUNBUFFERED':'1','NO_COLOR':'1','TERM':'dumb','HERMES_DISABLE_AUTO_UPDATE':'1'}
    key_name={'openrouter':'OPENROUTER_API_KEY','kimi-coding':'KIMI_API_KEY','minimax':'MINIMAX_API_KEY'}[args.provider]
    if args.real_model: env[key_name]=os.environ[key_name]
    secrets=[env.get(key_name,'')]
    redact=redactor(secrets)
    log=(base/'commands.jsonl').open('a')
    transcript=(base/'transport.jsonl').open('a')
    lock=threading.Lock()
    def record(kind,**fields):
        text=redact(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'kind':kind,**fields}))
        with lock: transcript.write(text+'\n');transcript.flush()
        print(text,flush=True)
    command=recorded_command(base,env,log,redact)
    from zoneinfo import ZoneInfo
    now=datetime.now(ZoneInfo('America/New_York')); due=qualification_due(now,args.tomorrow_morning)
    when=due.strftime('%Y-%m-%d at %H:%M')
    sentence=f"I will meet the Acorn team {when} to discuss the budget decision."
    reply='It went well. I will send the revised Acorn budget tomorrow at 10:00.'
    brief_received=threading.Event();followup_received=threading.Event();reply_sent=threading.Event()
    received=[]
    Model=model_handler(record,when)
    Server,IRC=irc_server(record,sentence,reply,received,brief_received,followup_received,reply_sent)
    irc=None;provider=None;gateway=None
    model=args.real_model or 'local-scripted'
    if not args.real_model:
        provider=http.server.ThreadingHTTPServer(('127.0.0.1',0),Model)
        threading.Thread(target=provider.serve_forever,daemon=True).start()
    settings=qualification_settings(now,telegram=args.telegram,overnight=args.tomorrow_morning)
    model_config={'default':model,'provider':args.provider,'context_length':128000}
    aux={'provider':args.provider,'model':model}
    if provider:
        aux={'provider':'custom','model':model,'base_url':f'http://127.0.0.1:{provider.server_port}/v1','api_key':'local-fixture-not-a-secret'}
        model_config={'default':model,'context_length':128000,**{k:v for k,v in aux.items() if k!='model'}}
    config=qualification_config(settings,model_config,aux)
    if args.telegram:
        token=dict(__import__('os').environ).get('TELEGRAM_BOT_TOKEN')
        if not token: raise RuntimeError('dedicated test bot token absent')
        secrets.append(token)
        secret_file=state/'.env';secret_file.touch(mode=0o600)
        secret_file.write_text('TELEGRAM_BOT_TOKEN='+token+'\nTELEGRAM_ALLOWED_USERS='+os.environ['LOOKAHEAD_DEMO_USER_ID']+'\nTELEGRAM_ALLOWED_CHATS='+os.environ['LOOKAHEAD_DEMO_CHAT_ID']+'\nTELEGRAM_HOME_CHANNEL='+os.environ['LOOKAHEAD_DEMO_CHAT_ID']+'\n')
        secret_file.chmod(0o600)
    else:
        irc=Server(('127.0.0.1',0),IRC);threading.Thread(target=irc.serve_forever,daemon=True).start()
        env.update(IRC_SERVER='127.0.0.1',IRC_PORT=str(irc.server_address[1]),IRC_USE_TLS='false',IRC_NICKNAME='lookahead-test',IRC_CHANNEL='#lookahead',IRC_HOME_CHANNEL='operator',IRC_ALLOWED_USERS='operator')
    (state/'SOUL.md').write_text('This is an isolated fictional conversation demonstration. Acknowledge normal user statements briefly. Do not access email, calendars, files or accounts. Do not prepare work, create reminders, or call tools; Lookahead independently handles its own preparation briefs. All fixture subjects are fictional.\n')
    config['platform_toolsets'] = {'cli':[], 'irc':[], 'telegram':[]}
    config['sessions'] = {'auto_prune':False}
    config['agent']['max_turns'] = 4
    (state/'config.yaml').write_text(json.dumps(config,indent=2))
    target=state/'plugins/lookahead'
    if not target.exists(): shutil.copytree(ROOT,target,ignore=shutil.ignore_patterns('.git','__pycache__','.ruff_cache','.pytest_cache'))
    def ledger():
        dbpath=state/'plugin-data/lookahead/data.db'
        if not dbpath.exists(): return []
        with sqlite3.connect(f'file:{dbpath}?mode=ro',uri=True) as db: return [json.loads(r[0]) for r in db.execute('SELECT payload FROM captures')]
    try:
        reset_lookahead(base,command,enabled=args.telegram)
        command('--version');command('plugins','enable','lookahead')
        command('plugins','doctor',str(target),'--ci')
        if not args.skip_validator:
            command('plugins','validate',str(target),'--install-deps','--json')
        else:
            record('validator_skipped',reason='separate stock validator receipts; disk conservation')
        command('lookahead','setup','--deliver','telegram' if args.telegram else 'irc')
        command('lookahead','resume')
        real_preflight(args,record)
        command('cron','create','* * * * *','--name','lookahead','--no-agent','--script','lookahead_tick.py','--deliver','telegram' if args.telegram else 'irc')
        raw_log=(base/'gateway.private.log').open('w')
        gateway=subprocess.Popen(['nice','-n','10',*native_argv('gateway','run')],cwd=STOCK,env=env,stdout=raw_log,stderr=subprocess.STDOUT,start_new_session=True)
        record('gateway_started',pid=gateway.pid,real_model=bool(args.real_model),settings=settings)
        if args.telegram:
            mark_gateway(base,gateway.pid)
            wait_telegram(base,gateway)
            record('telegram_connected_before_plan')
            ready=datetime.now(ZoneInfo('America/New_York'))
            due=qualification_due(ready,args.tomorrow_morning)
            when=due.strftime('%Y-%m-%d at %H:%M')
            sentence=f'I will meet the Acorn team {when} to discuss the budget decision.'
            record('planned_event',due_local=due.isoformat(),followup_delay_minutes=settings['followup_delay_minutes'],elapsed_bound_seconds=args.timeout,overnight=args.tomorrow_morning)
            command('chat','-q',sentence,'-Q')
            rows=ledger()
            assert len(rows)==1 and datetime.fromisoformat(rows[0]['due'])==due and rows[0]['quote'] in sentence,'new plan not captured; abort before waiting for nonexistent due output'
            listing=command('lookahead','list')
            assert rows[0]['id'] in listing.stdout,'native list did not read back this exact plan'
            record('captured_plan_verified',id=rows[0]['id'],due=rows[0]['due'])
        await_result(args,gateway,ledger,base,command,brief_received,followup_received,reply_sent,received)
        record('acceptance_pass',transport='telegram' if args.telegram else 'loopback_irc',real_model=bool(args.real_model),received=received)
    finally:
        from collect_evidence import collect
        destination=ROOT/'../lookahead-private-evidence/stock-20261110'/base.name
        try:
            collect(base,destination)
        finally:
            teardown(command,state,gateway,record)
        if provider: provider.shutdown()
        if irc: irc.shutdown()
        private=base/'gateway.private.log'
        if private.exists(): (base/'gateway.log').write_text(redact(private.read_text()))
        jobs=state/'cron/jobs.json'
        record('teardown_verified',gateway_dead=gateway is None or gateway.poll() is not None,jobs=json.loads(jobs.read_text()) if jobs.exists() else [])
        log.close();transcript.close()
        collect(base,destination)
        final_log=agent_text(base)
        assert 'Sent gateway shutdown notification to home channel telegram:' not in final_log,'unexpected stock shutdown message'
        assert 'Sent gateway restart notification to home channel telegram:' not in final_log,'unexpected stock restart message'
        print('EVIDENCE_DIR='+str(base),flush=True)


if __name__=='__main__': main()