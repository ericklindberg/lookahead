from datetime import timedelta
from types import SimpleNamespace
import json

import pytest


def test_evening_brief_does_not_wait_for_24h_horizon(module,now,tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    stamp=now.replace(hour=18)
    due=stamp+timedelta(hours=28)
    row=module('capture').Captured('a'*64,'Late review','I will attend a review tomorrow at 22:00.','s',now,due,stamp,'UTC',.95,'prep_brief',False)
    store=module('store').Store();store.save_captures([row]);store.set_stopped(False)
    llm=SimpleNamespace(complete=lambda **kw:SimpleNamespace(text=json.dumps({'prep':'Review your notes.','question':'What is the goal?'})))
    ctx=SimpleNamespace(get_config=lambda k,d=None: 'UTC' if k=='timezone' else d,llm=llm)
    module('runner').run(ctx,now=stamp)
    text=capsys.readouterr().out
    assert 'Preparation brief' in text and row.quote in text
    store.close()


def test_quote_final_punctuation_preserved(module,now):
    row={'subject':'Review','quote':'I will attend the review tomorrow.','due':now.isoformat(),'timezone':'UTC','help_kind':'prep_brief','session_id':'missing'}
    llm=SimpleNamespace(complete=lambda **kw:SimpleNamespace(text=json.dumps({'prep':'Review notes.','question':'What is missing?'})))
    assert '"I will attend the review tomorrow."' in module('brief').generate(llm,[row],[])


@pytest.mark.parametrize('value',['\u0000','@<>'])
def test_sanitized_empty_model_text_is_rejected(module,now,value):
    row={'subject':'Review','quote':'I will attend tomorrow.','due':now.isoformat(),'timezone':'UTC','help_kind':'prep_brief','session_id':'missing'}
    llm=SimpleNamespace(complete=lambda **kw:SimpleNamespace(text=json.dumps({'prep':value,'question':'What is missing?'})))
    with pytest.raises(ValueError): module('brief').generate(llm,[row],[])
