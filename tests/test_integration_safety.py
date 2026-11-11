import json
from types import SimpleNamespace


def test_capture_rejects_unbound_runtime_session(module, tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    ctx = SimpleNamespace(get_config=lambda k,d=None:{'timezone':'UTC'}.get(k,d),llm=None)
    module('capture').observe_turn(ctx,session_id='untrusted',user_message="I've got to meet my boss tomorrow",platform='irc')
    assert module('store').Store().status()['capture_last_error'] is None
    store = module('store').Store()
    assert store._connect().execute('SELECT COUNT(*) FROM capture_turns').fetchone()[0] == 0
    store.close()


def test_compose_concrete_help(module,now):
    c = module('contracts')
    event = c.Event('a',now,'Boss account meeting','a')
    risk = c.Candidate(event,'I can help prepare talking points','revision',True)
    text = module('compose').compose(c.Decision((risk,),'approved'),now)
    assert 'what changed' in text
    assert 'decision' in text


def test_list_is_bounded_and_paginated(module,tmp_path,monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    settings={'operator_platform':'irc','operator_user_id':'operator','operator_chat_id':'operator'}
    ctx=SimpleNamespace(get_config=lambda k,d=None:settings.get(k,d))
    source={'platform':'irc','user_id':'operator','chat_id':'operator','chat_type':'dm'}
    store=module('store').Store()
    with store.transaction() as db:
        for n in range(25):
            row={'id':f'{n:064x}','subject':'Meeting','due':'2030-01-01','timezone':'UTC','confidence':.95}
            db.execute('INSERT INTO captures VALUES (?,?)',(row['id'],json.dumps(row)))
    text=module('commands').handle(ctx,'list',source=source)
    assert 'Page 1/3' in text
    assert len(text.splitlines()) == 12
    second=module('commands').handle(ctx,'list 2',source=source)
    assert 'Page 2/3' in second
    assert f'{10:064x}' in second
    store.close()
