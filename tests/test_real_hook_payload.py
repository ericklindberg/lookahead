import json
from types import SimpleNamespace


def test_real_v023_post_llm_payload_uses_original_user_field(module,now,tmp_path,monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    user='I will meet the Acorn team tomorrow at 09:30 to discuss the budget decision.'
    assistant='Noted. Let me know if you want help.'
    seen=[]
    def complete(**kw):
        seen.append(json.loads(kw['messages'][1]['content'])['text'])
        return SimpleNamespace(text=json.dumps({'items':[{'subject':'Acorn budget meeting','quote':user,'when':'tomorrow at 09:30','confidence':.99,'help_kind':'talking_points'}]}))
    settings={'timezone':'America/New_York','capture_cli':True}
    ctx=SimpleNamespace(enabled=True,llm=SimpleNamespace(complete=complete),get_config=lambda k,d=None:settings.get(k,d))
    module('capture').observe_turn(ctx,session_id='real-payload-session',task_id='real-task',turn_id='real-turn',
        user_message=user,assistant_response=assistant,conversation_history=[{'role':'user','content':user},{'role':'assistant','content':assistant}],
        model='MiniMax-M2.7',platform='cli',side_question_token=None,telemetry_schema_version=1,now=now)
    assert seen==[user]
    store=module('store').Store();rows=store.list_captures()
    assert len(rows)==1 and rows[0]['quote']==user and rows[0]['session_id']=='real-payload-session'
    store.close()
