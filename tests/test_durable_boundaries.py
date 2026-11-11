from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


def test_actual_process_crash_before_commit(module, tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path/'profile'))
    s = module('store').Store()
    s.status()
    s.close()
    import lookahead
    root = str(Path(lookahead.__file__).parent)
    code = '''import importlib.util,sys,os
spec=importlib.util.spec_from_file_location('lookahead',sys.argv[1]+'/__init__.py',submodule_search_locations=[sys.argv[1]])
m=importlib.util.module_from_spec(spec);sys.modules['lookahead']=m;spec.loader.exec_module(m)
from lookahead.store import Store
s=Store()
with s.transaction() as db:
    db.execute("UPDATE meta SET value='false' WHERE key='stopped'")
    os._exit(74)
'''
    result = subprocess.run([sys.executable,'-c',code,root],capture_output=True,text=True)
    assert result.returncode == 74, result.stderr
    reopened = module('store').Store()
    assert reopened.status()['stopped'] is True
    reopened.close()


def test_same_fact_never_retried_seven_days(module,tmp_path,monkeypatch,sample,now):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path/'profile'))
    s = module('store').Store()
    s.observe(sample())
    s.observe(sample(minutes=30))
    s.set_stopped(False)
    cfg = module('contracts').Config(timezone='UTC')
    assert len(s.reserve(sample(minutes=30),now,cfg).selected) == 1
    for day in range(7):
        s.close()
        s = module('store').Store()
        assert s.observe(sample(minutes=30)) == ()
        assert not s.reserve(sample(minutes=30),now+timedelta(days=day),cfg).selected
    assert s.status()['counts']['handoff_unknown'] == 1
    s.close()


def test_stop_after_reservation_does_not_recall_unknown(module,tmp_path,monkeypatch,sample,now):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path/'profile'))
    s = module('store').Store()
    s.observe(sample())
    s.observe(sample(minutes=30))
    s.set_stopped(False)
    d = s.reserve(sample(minutes=30),now,module('contracts').Config(timezone='UTC'))
    s.set_stopped(True)
    assert d.selected  # A decision already returned cannot be retracted by storage.
    assert s.status()['counts']['handoff_unknown'] == 1
    assert not s.reserve(sample(minutes=30),now,module('contracts').Config(timezone='UTC')).selected
    s.close()


@pytest.mark.parametrize('raw',['not json','{"items":[],"unexpected":1}', '{"items":[],"items":[{"subject":"Boss meeting","quote":"I need to meet my boss Monday","when":"Monday","confidence":0.95,"help_kind":"talking_points"}]}'])
def test_strict_capture_response(module,raw):
    class Llm:
        def complete(self,**kwargs): return SimpleNamespace(text=raw)
    assert module('capture').extract(Llm(),'I need to meet my boss Monday',session_id='s',now=datetime.fromisoformat('2030-06-07T16:00:00Z'),timezone='UTC') == ()
