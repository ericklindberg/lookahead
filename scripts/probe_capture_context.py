"""Fictional, non-persisting counterfactuals; not a live capture or holdout."""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from eval_capture import STOCK,context,load_capture
from native_cli import DEMO_ROOT


def main():
    os.environ.update(HOME=str(DEMO_ROOT/'demo-os-home'),HERMES_HOME=str(DEMO_ROOT/'demo-home'),
                      HERMES_RUNTIME_DIR=str(DEMO_ROOT/'demo-runtime'),HERMES_DISABLE_AUTO_UPDATE='1')
    sys.path.insert(0,str(STOCK))
    cap=load_capture();ctx=context()
    now=datetime.fromisoformat('2026-11-10T20:24:46+00:00')
    text='I will meet the Acorn team 2026-11-10 at 15:28 to discuss the budget decision.'
    cases=[('original_utc_anchor',now.isoformat(),'America/New_York',text),
           ('equivalent_local_anchor',now.astimezone(ZoneInfo('America/New_York')).isoformat(),'America/New_York',text),
           ('relative_tomorrow',now.isoformat(),'America/New_York',text.replace('2026-11-10','tomorrow')),
           ('equivalent_utc_event',now.isoformat(),'UTC',text.replace('15:28','20:28'))]
    for label,at,zone,sentence in cases:
        response=ctx.llm.complete(task=cap.TASK,messages=[{'role':'system','content':cap.PROMPT},
            {'role':'user','content':json.dumps({'captured_at':at,'timezone':zone,'text':sentence})}],max_tokens=512,timeout=8,temperature=0)
        print(json.dumps({'diagnostic_only':True,'case':label,'captured_at':at,'timezone':zone,'text':sentence,
                          'raw_model_text':response.text,'model':response.model}),flush=True)


if __name__=='__main__': main()
