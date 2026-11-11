from datetime import timedelta
from types import SimpleNamespace
import json


def test_each_due_commitment_gets_its_own_brief(module,now,tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    store=module('store').Store();store.set_stopped(False)
    cap=module('capture')
    rows=[cap.Captured(c*64,'Review '+c,'I will review '+c+' tomorrow','s',now,now+timedelta(hours=1),now,'UTC',.95,'prep_brief',False) for c in 'abc']
    store.save_captures(rows)
    calls=[]
    def complete(**kw):
        calls.append(kw);return SimpleNamespace(text=json.dumps({'prep':'Review your notes.','question':'What decision is needed?'}))
    ctx=SimpleNamespace(get_config=lambda k,d=None: {'timezone':'UTC','spacing_minutes':0}.get(k,d),llm=SimpleNamespace(complete=complete))
    for row in rows:
        module('runner').run(ctx,now=now)
        assert row.quote in capsys.readouterr().out
    assert len(calls)==3 and store.status()['counts']=={'handoff_unknown':3}
    store.close()


def test_forget_during_generation_suppresses_output(module,now,tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    store=module('store').Store();store.set_stopped(False)
    row=module('capture').Captured('a'*64,'Review','I will review tomorrow','s',now,now+timedelta(hours=1),now,'UTC',.95,'prep_brief',False)
    store.save_captures([row])
    ctx=SimpleNamespace(get_config=lambda k,d=None: 'UTC' if k=='timezone' else d)
    module('runner').run(ctx,now=now,before_output=lambda:store.forget_capture(row.id))
    assert capsys.readouterr().out==''
    store.close()


def test_followup_reservation_persists_unknown_without_retry(module,now,tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    store=module('store').Store();store.set_stopped(False)
    row=module('capture').Captured('a'*64,'Review','I will review tomorrow','s',now,now+timedelta(hours=1),now,'UTC',.95,'prep_brief',False)
    store.save_captures([row])
    c=module('contracts').Config(timezone='UTC')
    assert store.reserve_followup(now+timedelta(hours=3),c)['id']==row.id
    store.close()
    reopened=module('store').Store()
    assert reopened.reserve_followup(now+timedelta(hours=4),c) is None
    reopened.close()


def test_quote_ellipsis_is_explicit_and_question_preserved(module,now):
    row={'subject':'Review','quote':'I will review tomorrow '+('details '*60),'due':now.isoformat(),'timezone':'UTC','help_kind':'prep_brief','session_id':'missing'}
    llm=SimpleNamespace(complete=lambda **kw: SimpleNamespace(text=json.dumps({'prep':'Review notes.','question':'What is missing?'})))
    text=module('brief').generate(llm,[row],[])
    assert 'excerpt' in text and '…' in text
    assert '- Open question: What is missing?' in text
    assert len(text)<900
