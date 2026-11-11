"""Real-model evaluation via stock PluginContext.llm, never provider SDK/HTTP.

Run with stock Python. Credentials are loaded only in memory from the explicitly approved
key source. Isolated HOME/HERMES_HOME is set BEFORE importing any stock modules.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import time

ROOT=Path(__file__).resolve().parents[1]
STOCK=ROOT.parent/'stock-hermes'
EVIDENCE=ROOT/'../lookahead-private-evidence/eval-20261110'


def isolated_home(label, model, provider='openrouter', env_root=None, persistent_demo=False):
    from native_cli import make_fixture, prepare_logged, quiet_host_config
    from auth_diagnostics import auth_add
    key_name = {'openrouter':'OPENROUTER_API_KEY','kimi-coding':'KIMI_API_KEY','minimax':'MINIMAX_API_KEY'}[provider]
    base,paths=make_fixture(label,persistent_demo=persistent_demo,env_root=env_root)
    state=Path(paths['state'])
    key=dict(__import__('os').environ).get(key_name)
    if not key: raise RuntimeError('approved '+provider+' key absent')
    demo_token=os.environ.get('TELEGRAM_BOT_TOKEN')
    for name in tuple(os.environ):
        if name.endswith(('_API_KEY','_BOT_TOKEN')) or name.startswith(('HERMES_','IRC_','TELEGRAM_')):
            os.environ.pop(name,None)
    os.environ.update(HOME=paths['home'],HERMES_HOME=paths['state'],TMPDIR=paths['tmp'],
                      HERMES_RUNTIME_DIR=paths['runtime'],HERMES_DISABLE_AUTO_UPDATE='1',PYTHONDONTWRITEBYTECODE='1')
    config={}
    if (state/'config.yaml').exists():
        from ruamel.yaml import YAML
        config=YAML(typ='safe').load((state/'config.yaml').read_text()) or {}
    config.update(_config_version=12,model={'default':model,'provider':provider,'context_length':128000},
                  auxiliary={'lookahead_capture':{'provider':provider,'model':model},'lookahead_brief':{'provider':provider,'model':model}},
                  memory={'memory_enabled':False,'user_profile_enabled':False})
    config.update(quiet_host_config())
    plugins=config.setdefault('plugins',{});plugins['enabled']=['lookahead']
    plugins.setdefault('entries',{}).setdefault('lookahead',{}).setdefault('settings',{})['timezone']='America/New_York'
    (state/'config.yaml').write_text(json.dumps(config,indent=2))
    target=state/'plugins/lookahead'
    shutil.copytree(ROOT,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git','__pycache__','.pytest_cache','.ruff_cache'))
    if persistent_demo: prepare_logged(base,dict(os.environ))
    auth_add(base,dict(os.environ),provider,key,STOCK)
    os.environ[key_name]=key
    if demo_token: os.environ['TELEGRAM_BOT_TOKEN']=demo_token
    return base


def context():
    # Qualification-only stock fixtures live beside the unit-test host fixtures,
    # never on the production plugin registration/tick path.
    import runpy
    return runpy.run_path(str(ROOT/'tests/evaluation/stock_context.py'))['context'](ROOT)


def load_capture():
    spec=importlib.util.spec_from_file_location('lookahead',ROOT/'__init__.py',submodule_search_locations=[str(ROOT)])
    package=importlib.util.module_from_spec(spec)
    import sys
    sys.modules['lookahead']=package;spec.loader.exec_module(package)
    from lookahead import capture
    return capture


def metrics(rows):
    tp=sum(min(len(r['predicted']),1) for r in rows if r['positive'])
    fp=sum(len(r['predicted'])-(min(len(r['predicted']),1) if r['positive'] else 0) for r in rows)
    fn=sum(r['positive'] and not r['predicted'] for r in rows)
    correct=sum(bool(r['predicted']) and r['predicted'][0]['due']==r['expected_due'] for r in rows if r['positive'])
    return {'turns':len(rows),'tp':tp,'fp':fp,'fn':fn,'precision':tp/(tp+fp) if tp+fp else 0,
            'recall':tp/(tp+fn) if tp+fn else 0,'date_correct':correct,
            'date_accuracy_on_true_positives':correct/tp if tp else 0,
            'date_recall':correct/(tp+fn) if tp+fn else 0}


def main():
    p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--split',choices=['dev','holdout'])
    p.add_argument('--provider',choices=['kimi-coding','minimax','openrouter'],default='openrouter')
    p.add_argument('--preflight',action='store_true')
    p.add_argument('--label',default='',help='Visible run suffix; preserve previous results.')
    args=p.parse_args()
    if not args.preflight and not (EVIDENCE/'corpus.json').is_file():
        print('SKIP: private evaluation corpus is not distributed; supply a fictional local corpus first.')
        return
    if shutil.disk_usage(ROOT).free<2_000_000_000: raise RuntimeError('disk below 2 GB')
    base=isolated_home('eval',args.model,args.provider)
    import sys
    sys.path.insert(0,str(STOCK))
    cap=load_capture();ctx=context()
    try:
        result=ctx.llm.complete(messages=[{'role':'user','content':'Reply exactly OK.'}],task='lookahead_capture',max_tokens=128,timeout=8)
        print(json.dumps({'preflight':'PASS','provider':result.provider,'model':result.model,'text':result.text,'input_tokens':result.usage.input_tokens,'output_tokens':result.usage.output_tokens}),flush=True)
    except Exception as exc:
        print(json.dumps({'preflight':'FAIL','provider':args.provider,'model':args.model,'error_type':type(exc).__name__,'status':getattr(exc,'status_code',None)}),flush=True)
        raise SystemExit(2) from None
    if args.preflight: return
    if not args.split: raise RuntimeError('--split required for evaluation')
    corpus=json.loads((EVIDENCE/'corpus.json').read_text())
    selected=[r for r in corpus if r['split']==args.split]
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    output=EVIDENCE/(args.model.replace('/','--')+'-'+args.split+('-'+args.label if args.label else '')+'.jsonl')
    if output.exists(): raise RuntimeError('results exist; preserve prior run')
    all_rows=[]
    class Recorder:
        def __init__(self): self.calls=[]
        def complete(self,**kwargs):
            result=ctx.llm.complete(**kwargs)
            self.calls.append({'provider':result.provider,'model':result.model,
                               'usage':{'input_tokens':result.usage.input_tokens,'output_tokens':result.usage.output_tokens},'text':result.text})
            return result
    with output.open('w') as f:
        for item in selected:
            recorder=Recorder();start=time.monotonic();error=None
            try:
                captured=cap.extract(recorder,item['text'],session_id='fictional-eval',now=datetime.fromisoformat(item['now']),timezone=item['timezone'])
            except Exception as exc:
                captured=();error=type(exc).__name__  # No potentially secret exception strings.
            row={**item,'predicted':[r.payload() for r in captured],'calls':recorder.calls,'error':error,'seconds':round(time.monotonic()-start,3)}
            f.write(json.dumps(row)+'\n');f.flush();all_rows.append(row)
            print(item['id'],len(captured),error,flush=True)
    report={'model':args.model,'split':args.split,'at':datetime.now(timezone.utc).isoformat(),
            'prompt_sha256':hashlib.sha256(cap.PROMPT.encode()).hexdigest(),'corpus_sha256':hashlib.sha256((EVIDENCE/'corpus.json').read_bytes()).hexdigest(),
            'metrics':metrics(all_rows),'calls':sum(len(r['calls']) for r in all_rows),
            'input_tokens':sum(c['usage']['input_tokens'] for r in all_rows for c in r['calls']),
            'output_tokens':sum(c['usage']['output_tokens'] for r in all_rows for c in r['calls']),
            'errors':sum(bool(r['error']) for r in all_rows),'isolated_home':str(base)}
    output.with_suffix('.summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__': main()