import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_ics import BASE, EVENT, write
from test_runner import prepare


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path/'home'))
    settings = {'timezone':'UTC', 'enabled':True, 'ics_enabled':True,
                'ics_path':str(write(tmp_path, datetime(2030,6,10,12,tzinfo=timezone.utc))),
                'operator_platform':'test', 'operator_user_id':'owner', 'operator_chat_id':'dm'}
    return SimpleNamespace(get_config=lambda k,d=None:settings.get(k,d), settings=settings)


def test_calendar_runner_baselines_then_offers(module, now, context, capsys):
    store = module('store').Store()
    store.set_stopped(False)
    runner = module('runner')
    runner.run(context, now=now)
    assert capsys.readouterr().out == ''
    path = Path(context.settings['ics_path'])
    path.write_text(BASE.format(events=EVENT.replace('Orbital planning','Revised orbital planning')))
    os.utime(path, (now.timestamp(),now.timestamp()))
    runner.run(context, now=now)
    assert 'Revised orbital planning' in capsys.readouterr().out
    runner.run(context, now=now)
    assert capsys.readouterr().out == ''
    assert store.status()['calendar']['skipped_series'] == 0
    store.close()


def test_calendar_busy_holds_chat(module, now, context, capsys):
    store = prepare(module,now)
    path = Path(context.settings['ics_path'])
    path.write_text(BASE.format(events=EVENT.replace('130000Z','113000Z').replace('140000Z','123000Z')))
    os.utime(path, (now.timestamp(),now.timestamp()))
    module('runner').run(context, now=now)
    assert capsys.readouterr().out == ''
    assert store.status()['last_reason'] == 'meeting'
    store.close()


def test_unavailable_calendar_holds_chat_without_resolving(module, now, context, capsys):
    store = prepare(module,now)
    context.settings['ics_path'] = '/not/a/real/calendar.ics'
    module('runner').run(context, now=now)
    assert capsys.readouterr().out == ''
    assert store.status()['last_reason'] == 'stale_sources'
    assert store.status()['calendar']['error'] == 'calendar_unavailable'
    assert store.status()['counts'] == {'pending':1}
    store.close()


def test_disabled_calendar_does_not_read(module, now, context, capsys):
    context.settings['ics_enabled'] = False
    context.settings['ics_path'] = '/not/a/real/calendar.ics'
    store = prepare(module,now)
    module('runner').run(context, now=now)
    assert capsys.readouterr().out.startswith('Lookahead:')
    store.close()


def test_list_distinguishes_sources(module, now, context):
    store = prepare(module,now)
    module('runner').run(context, now=now)
    reply = module('commands').handle(context,'list',source={'platform':'test','user_id':'owner','chat_id':'dm','chat_type':'dm'})
    assert '| calendar |' in reply
    assert '| chat |' in reply
    assert 'example.invalid' not in reply
    store.close()


def test_calendar_status_never_stores_url(module, now, context, monkeypatch):
    context.settings.pop('ics_path')
    context.settings['ics_url'] = 'https://calendar.example.invalid/private/SECRET?token=HIDDEN'
    monkeypatch.setattr(module('ics'), '_https', lambda *a: BASE.format(events=EVENT).encode())
    module('runner').run(context, now=now)
    store = module('store').Store()
    try:
        status = store.status()['calendar']
        assert status['host'] == 'calendar.example.invalid'
        dump = '\n'.join(store._connect().iterdump())
        assert 'SECRET' not in dump and 'HIDDEN' not in dump
    finally:
        store.close()
