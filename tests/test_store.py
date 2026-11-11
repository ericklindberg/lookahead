from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import os
import subprocess
import sys

import pytest


@pytest.fixture
def store(module, tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path/'state'))
    s = module('store').Store()
    yield s
    s.close()


def test_lazy_store(module, tmp_path, monkeypatch):
    home = tmp_path/'lazy'
    monkeypatch.setenv('HERMES_HOME',str(home))
    s = module('store').Store()
    assert not home.exists()
    assert s.status()['stopped'] is True
    assert (home/'plugin-data'/'lookahead'/'data.db').exists()
    s.close()


def test_baseline_pending_resolved(store, sample):
    assert store.observe(sample()) == ()
    assert store.observe(sample()) == ()
    assert len(store.observe(sample(minutes=30))) == 1
    assert store.observe(sample(status='ready')) == ()
    assert store.status()['counts'] == {'resolved':2}


def test_dedup_reopen(module, store, sample, now):
    cfg = module('contracts').Config(timezone='UTC')
    store.observe(sample())
    store.observe(sample(minutes=30))
    store.set_stopped(False)
    d = store.reserve(sample(minutes=30),now,cfg)
    assert len(d.selected) == 1
    assert store.status()['counts']['handoff_unknown'] == 1
    store.close()
    reopened = module('store').Store()
    assert not reopened.status()['stopped']
    assert reopened.observe(sample(minutes=30)) == ()
    assert not reopened.reserve(sample(minutes=30),now+timedelta(minutes=31),cfg).selected
    reopened.close()


def test_stopped_reservation(store, sample, now, module):
    store.observe(sample())
    store.observe(sample(minutes=30))
    d = store.reserve(sample(minutes=30),now,module('contracts').Config(timezone='UTC'))
    assert d.reason == 'stopped' and not d.selected
    assert store.status()['counts']['pending'] == 1


def test_concurrent_reservation(store, sample, now, module):
    store.observe(sample())
    store.observe(sample(minutes=30))
    store.set_stopped(False)
    def scan(_):
        s = module('store').Store()
        try:
            return len(s.reserve(sample(minutes=30),now,module('contracts').Config(timezone='UTC')).selected)
        finally: s.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(scan,range(8))) == 1


def test_concurrent_baseline(store, sample, module):
    def scan(_):
        s = module('store').Store()
        try: return len(s.observe(sample()))
        finally: s.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sum(pool.map(scan,range(8))) == 0
    assert store.status()['counts'] == {'baseline':1}


def test_schema_version(store):
    store.status()
    assert store._db.execute('PRAGMA user_version').fetchone()[0] == 1
    store._db.execute('PRAGMA user_version=99')
    store.close()
    with pytest.raises(ValueError,match='schema'):
        store.status()


def test_crash_after_reservation(module, store, sample, now):
    store.observe(sample())
    store.observe(sample(minutes=30))
    store.set_stopped(False)
    import lookahead
    root = str(__import__('pathlib').Path(lookahead.__file__).parent)
    code = '''import importlib.util,sys,os
from datetime import datetime
spec=importlib.util.spec_from_file_location('lookahead',sys.argv[1]+'/__init__.py',submodule_search_locations=[sys.argv[1]])
m=importlib.util.module_from_spec(spec);sys.modules['lookahead']=m;spec.loader.exec_module(m)
from lookahead.contracts import Config,Snapshot
from lookahead.store import Store
s=Store(); now=datetime.fromisoformat('2030-06-10T12:00:00Z')
from lookahead.contracts import Event,Readiness
snap=Snapshot((Event('demo',datetime.fromisoformat('2030-06-10T12:30:00Z'),'Orbital demo','deck'),),(Readiness('deck','not_ready','Deck unfinished'),),now)
assert s.reserve(snap,now,Config(timezone='UTC')).selected
os._exit(73)
'''
    result = subprocess.run([sys.executable,'-c',code,root],env=os.environ.copy(),capture_output=True,text=True)
    assert result.returncode == 73, result.stderr
    assert store.status()['counts']['handoff_unknown'] == 1
    assert store.observe(sample(minutes=30)) == ()


def test_rollback_before_commit(store, sample):
    store.observe(sample())
    with pytest.raises(RuntimeError):
        with store.transaction() as db:
            db.execute("UPDATE meta SET value='false' WHERE key='stopped'")
            raise RuntimeError('simulated crash')
    assert store.status()['stopped'] is True
