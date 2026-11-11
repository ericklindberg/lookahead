"""One fictional normal-chat capture probe; no cron or delivery gateway."""
import argparse
from datetime import datetime,timedelta
import json
import os
import sqlite3
from zoneinfo import ZoneInfo
from eval_capture import isolated_home
from native_cli import fixture_state,agent_text,reset_lookahead
from demo_fixture import child_env,command


def confirm_capture(rows,text,due,since,listing):
    assert len(rows)==1,'expected exactly one fresh plan'
    row=rows[0]
    assert datetime.fromisoformat(row['captured_at'])>=since,'old capture cannot qualify this probe'
    assert datetime.fromisoformat(row['due'])==due,'captured due differs from this plan'
    assert row['quote'] in text,'quotation differs from this plan'
    assert row['id'] in listing,'native list did not read back the exact captured plan'
    return row['id']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--tomorrow-morning',action='store_true',help='use tomorrow 09:30 local instead of a near-term event')
    parser.add_argument('--event-lead-minutes',type=int,default=4)
    args=parser.parse_args()
    if not 1<=args.event_lead_minutes<=10080:raise ValueError('event lead outside supported probe bounds')
    base=isolated_home('capture-only','MiniMax-M2.7','minimax',persistent_demo=True)
    state=fixture_state(base)
    cfg=json.loads((state/'config.yaml').read_text())
    cfg['plugins']['entries']['lookahead']['settings']['capture_cli']=True
    (state/'config.yaml').write_text(json.dumps(cfg,indent=2))
    env=child_env(base,os.environ['MINIMAX_API_KEY'])
    reset_lookahead(base,lambda *a:command(base,env,*a))
    ready=datetime.now(ZoneInfo('America/New_York'))
    due=((ready+timedelta(days=1)).replace(hour=9,minute=30,second=0,microsecond=0) if args.tomorrow_morning
         else (ready+timedelta(minutes=args.event_lead_minutes)).replace(second=0,microsecond=0))
    text=f'I will meet the Acorn team {due:%Y-%m-%d at %H:%M} to discuss the budget decision.'
    print(json.dumps({'probe':'one normal CLI capture only','text':text,'state':str(state),'started_local':ready.isoformat(),
                      'due_local':due.isoformat(),'notification_flag':cfg['platforms']['telegram']['gateway_restart_notification']}),flush=True)
    result=command(base,env,'chat','-q',text,'-Q',check=False)
    listing=command(base,env,'lookahead','list')
    print(listing.stdout,flush=True)
    decisions=[line for line in agent_text(base).splitlines() if 'lookahead_capture_' in line]
    print('\n'.join(decisions),flush=True)
    with sqlite3.connect('file:'+str(state/'plugin-data/lookahead/data.db')+'?mode=ro',uri=True) as db:
        rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM captures')]
    receipt={'text':text,'list':listing.stdout,'native_chat_exit':result.returncode,'decisions':decisions,'rows':rows}
    (base/'capture-only.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert result.returncode==0,'native chat failed; do not score model capture'
    captured=confirm_capture(rows,text,due,ready,listing.stdout)
    print(json.dumps({'capture_only':'PASS','id':captured,'receipt':str(base)}),flush=True)


if __name__=='__main__': main()
