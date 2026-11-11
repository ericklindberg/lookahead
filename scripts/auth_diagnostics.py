"""Key-safe native auth-add diagnostics for explicitly isolated operator fixtures."""
import json
import re
import subprocess
from datetime import datetime, timezone


def scrub(text,key):
    if key: text=text.replace(key,'[REDACTED]')
    text=re.sub(r'\bsk-[A-Za-z0-9_-]{8,}\b','[REDACTED_KEY]',text)
    text=re.sub(r'\b[0-9]{6,12}:[A-Za-z0-9_-]{20,}\b','[REDACTED_TOKEN]',text)
    text=re.sub(r'\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b','[REDACTED_TOKEN]',text)
    return text


def auth_add(base,env,provider,key,stock):
    from native_cli import argv
    command=argv('auth','add',provider,'--type','api-key','--label','isolated-lookahead-proof')
    safe_env={k:v for k,v in env.items() if k not in ('OPENROUTER_API_KEY','KIMI_API_KEY','MINIMAX_API_KEY')}
    result=subprocess.run(command,input=key+'\n',text=True,capture_output=True,cwd=stock,env=safe_env,timeout=60)
    row={'at':datetime.now(timezone.utc).isoformat(),'argv':command,'exit':result.returncode,
         'stdout':scrub(result.stdout,key),'stderr':scrub(result.stderr,key)}
    (base/'auth-add.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({'auth_add_exit':result.returncode,'scrubbed_stderr':row['stderr'],'receipt':str(base/'auth-add.json')}),flush=True)
    if result.returncode: raise RuntimeError('native isolated auth-add failed; see scrubbed diagnostic receipt')
    return row
