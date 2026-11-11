from datetime import timedelta
from types import SimpleNamespace

import pytest


@pytest.fixture
def context(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    settings = {'timezone':'UTC','enabled':True}
    return SimpleNamespace(get_config=lambda k,d=None: settings.get(k,d), settings=settings)


def prepare(module, now):
    cap = module('capture')
    store = module('store').Store()
    row = cap.Captured('a'*64,'Boss account meeting',"I've got to meet my boss",'session',now,now+timedelta(hours=2),now,'UTC',.95,'talking_points',False)
    store.save_captures([row])
    store.set_stopped(False)
    return store


def test_runner_only_approved_stdout(module, now, context, capsys):
    store = prepare(module,now)
    module('runner').run(context,now=now)
    assert capsys.readouterr().out.startswith('Lookahead:\n')
    module('runner').run(context,now=now)
    assert capsys.readouterr().out == ''
    assert store.status()['counts'] == {'handoff_unknown':1}
    store.close()


def test_stop_before_stdout_retains_unknown(module,now,context,capsys):
    store = prepare(module,now)
    module('runner').run(context,now=now,before_output=lambda:store.set_stopped(True))
    assert capsys.readouterr().out == ''
    assert store.status()['counts'] == {'handoff_unknown':1}
    store.close()


def test_stop_after_handoff_cannot_recall(module,now,context,capsys):
    store = prepare(module,now)
    module('runner').run(context,now=now)
    store.set_stopped(True)
    assert capsys.readouterr().out.startswith('Lookahead:')
    module('runner').run(context,now=now)
    assert capsys.readouterr().out == ''
    store.close()


def test_disabled_runner_no_state(module,now,context,capsys,tmp_path):
    context.settings['enabled'] = False
    module('runner').run(context,now=now)
    assert capsys.readouterr().out == ''
    assert not (tmp_path/'plugins'/'lookahead'/'data.db').exists()


def test_setup_stages_without_scheduling(module,context,tmp_path,monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    command = module('cli').stage(context,deliver='localproof')
    assert '--no-agent --script' in command
    assert '--deliver localproof' in command
    assert (tmp_path/'scripts'/'lookahead_tick.py').is_file()
    assert not (tmp_path/'cron'/'jobs.json').exists()
