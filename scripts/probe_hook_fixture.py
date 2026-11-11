"""Temporary stock-API observer for fictional native payload/source diagnostics."""
import json
import os
import subprocess
from native_cli import DEMO_ROOT,argv

CODE=r'''import hashlib,importlib,json,marshal,os,sys,re
from pathlib import Path
from importlib.metadata import version

def txt(value):
    if isinstance(value,str):return value
    if isinstance(value,list):return ''.join(x.get('text','') for x in value if isinstance(x,dict) and isinstance(x.get('text'),str))
    return ''

def observe(**kw):
    user=txt(kw.get('user_message'));history=kw.get('conversation_history',[])
    users=[txt(x.get('content')) for x in history if isinstance(x,dict) and x.get('role')=='user']
    assistants=[txt(x.get('content')) for x in history if isinstance(x,dict) and x.get('role')=='assistant']
    h=lambda s:hashlib.sha256(s.encode()).hexdigest()[:12]
    head=user[:80] if user.startswith('I will meet the Acorn team ') else '[HEAD OMITTED: not controlled fixture text]'
    head=re.sub(r'\bsk-[A-Za-z0-9_-]+|\b\d{6,12}:[A-Za-z0-9_-]{20,}','[REDACTED]',head)
    row={'hook':'post_llm_call','field':'user_message','keys':sorted(kw),'chars':len(user),'hash':h(user),
         'head':head,'equals_last_user':bool(users and user==users[-1]),'equals_previous_user':bool(len(users)>1 and user==users[-2]),
         'equals_assistant_response':user==txt(kw.get('assistant_response')),
         'equals_last_assistant':bool(assistants and user==assistants[-1]),'history_roles':[x.get('role') for x in history if isinstance(x,dict)],
         'home':os.environ.get('HERMES_HOME'),'task':kw.get('task_id')}
    p=Path(os.environ['HERMES_HOME'])/'logs/lookahead-hook-probe.private.jsonl'
    with p.open('a') as f:f.write(json.dumps(row)+'\n')

def provenance(args):
    m=importlib.import_module('hermes_plugins.lookahead.capture')
    p=Path(m.__file__)
    result={'home':os.environ.get('HERMES_HOME'),'python':sys.executable,'module_file':str(p),
            'module_file_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'has_response_facts':hasattr(m,'_response_facts'),
            'extract_code_file':m.extract.__code__.co_filename,'extract_code_line':m.extract.__code__.co_firstlineno,
            'extract_code_sha256':hashlib.sha256(marshal.dumps(m.extract.__code__)).hexdigest(),
            'cache':getattr(m,'__cached__',None),'pycache_prefix':sys.pycache_prefix,'sdk_versions':{n:version(n) for n in ('openai','anthropic')},
            'system_hash':hashlib.sha256(m.PROMPT.encode()).hexdigest()[:12]}
    print(json.dumps(result));return 0

def register(ctx):
    ctx.register_cli_command('lookahead-provenance','Fictional fixture provenance',lambda p:None,provenance)
    ctx.register_hook('post_llm_call',observe)
'''


def install():
    state=DEMO_ROOT/'demo-home';target=state/'plugins/lookahead-probe';target.mkdir(parents=True,exist_ok=True)
    (target/'plugin.yaml').write_text('name: lookahead-probe\nversion: "0.0.1"\ndescription: Temporary fictional capture observer\nauthor: Lookahead qualification\nlicense: MIT\nprovides_hooks: [post_llm_call]\n')
    (target/'__init__.py').write_text(CODE)
    from ruamel.yaml import YAML
    cfg=YAML(typ='safe').load((state/'config.yaml').read_text())
    cfg['plugins']['enabled']=['lookahead','lookahead-probe']
    (state/'config.yaml').write_text(json.dumps(cfg,indent=2))
    env=dict(os.environ,HOME=str(DEMO_ROOT/'demo-os-home'),HERMES_HOME=str(state),HERMES_RUNTIME_DIR=str(DEMO_ROOT/'demo-runtime'),HERMES_DISABLE_AUTO_UPDATE='1')
    result=subprocess.run(argv('lookahead-provenance'),env=env,capture_output=True,text=True)
    print(result.stdout,flush=True);print(result.stderr,flush=True)
    if result.returncode:raise RuntimeError('native provenance command failed')


if __name__=='__main__':install()
