"""One direct completion through the native stock launcher, not a live capture."""
import hashlib
import json
from pathlib import Path
import sys
from dataclasses import asdict
from importlib.metadata import version

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from eval_capture import context


def main():
    request_path=ROOT/'../lookahead-private-evidence/stock-20261110/paired-request.json'
    if not request_path.is_file():
        print('SKIP: private paired request is not distributed; generate a fictional local request first.')
        return
    request=json.loads(request_path.read_text())
    ctx=context()
    result=ctx.llm.complete(messages=request['messages'],task='lookahead_capture',max_tokens=512,temperature=0,timeout=8)
    try: body=json.loads(result.text);parsed=True;items=len(body['items'])
    except (ValueError,TypeError,KeyError):parsed=False;items=None
    row={'diagnostic_only_not_persisted':True,'native_python':sys.executable,'sdk_versions':{n:version(n) for n in ('openai','anthropic')},
         'system_hash':hashlib.sha256(request['messages'][0]['content'].encode()).hexdigest()[:12],
         'payload_hash':hashlib.sha256(request['messages'][1]['content'].encode()).hexdigest()[:12],
         'parameters':{'max_tokens':512,'temperature':0,'timeout':8,'response_format':None},
         'text_chars':len(result.text),'body_hash':hashlib.sha256(result.text.encode()).hexdigest()[:12],
         'parsed':parsed,'items':items,'usage':asdict(result.usage),'finish_reason':'unavailable_stock_api','model':result.model}
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'../lookahead-private-evidence/stock-20261110/paired-direct-result.json')
    args=parser.parse_args()
    out=args.output
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True)


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)