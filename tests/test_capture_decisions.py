import json
from types import SimpleNamespace
import logging
import pytest


def fake(text): return SimpleNamespace(complete=lambda **kw:SimpleNamespace(text=text))


@pytest.mark.parametrize('kind,expected',[
    ('empty','model_no_commitments'),('json','invalid_json'),('confidence','low_confidence'),
    ('quote','quote_not_exact'),('when','date_phrase_not_exact'),('past','not_future_or_outside_horizon')])
def test_content_safe_capture_decisions(module,now,caplog,kind,expected):
    cap=module('capture');caplog.set_level(logging.INFO)
    text='I will review PRIVATE_CAPTURE_TEXT_ZEBRA tomorrow at 10:00.'
    item={'subject':'Private review','quote':text,'when':'tomorrow at 10:00','confidence':.95,'help_kind':'talking_points'}
    if kind=='confidence': item['confidence']=.1
    if kind=='quote': item['quote']=text+' changed'
    if kind=='when': item['when']='2030-06-11 at 10:00'
    if kind=='past':
        text='I will review PRIVATE_CAPTURE_TEXT_ZEBRA 2030-06-01 at 10:00.'
        item.update(quote=text,when='2030-06-01 at 10:00')
    response='not JSON' if kind=='json' else json.dumps({'items':[] if kind=='empty' else [item]})
    assert cap.extract(fake(response),text,session_id='s',now=now,timezone='UTC')==()
    lines=[r.getMessage() for r in caplog.records if 'lookahead_capture_decision' in r.getMessage()]
    assert any('reason='+expected in line and ('decision=error' if kind=='json' else 'decision=ignored') in line for line in lines)
    assert all('PRIVATE_CAPTURE_TEXT' not in line and 'Private review' not in line for line in lines)


def test_store_decision_logs_dedupe_and_scope(module,now,tmp_path,monkeypatch,caplog):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path));caplog.set_level(logging.INFO)
    cap=module('capture')
    text='I will review PRIVATE_CAPTURE_TEXT_ZEBRA tomorrow at 10:00.'
    item={'subject':'Private review','quote':text,'when':'tomorrow at 10:00','confidence':.95,'help_kind':'talking_points'}
    row=cap.extract(fake(json.dumps({'items':[item]})),text,session_id='s',now=now,timezone='UTC')[0]
    store=module('store').Store()
    assert store.save_captures([row])==1
    assert store.save_captures([row])==0
    lines=[r.getMessage() for r in caplog.records if 'lookahead_capture_decision' in r.getMessage()]
    assert any('reason=stored' in x and 'scope=' in x for x in lines)
    assert any('reason=dedupe_hit' in x for x in lines)
    assert not any('PRIVATE_CAPTURE_TEXT' in x or str(tmp_path) in x for x in lines)
    store.close()


def test_demo_host_notifications_disabled():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'scripts/native_cli.py'
    spec=importlib.util.spec_from_file_location('native_config_probe',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    assert m.quiet_host_config()['platforms']['telegram']['gateway_restart_notification'] is False
