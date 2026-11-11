import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def denied(*args,**kwargs):
        raise AssertionError('Tests must not use network or real model endpoints')
    monkeypatch.setattr('socket.socket.connect',denied)
    monkeypatch.setattr('socket.getaddrinfo',denied)


@pytest.fixture
def module():
    def load(name):
        assert (ROOT / (name + '.py')).exists(), f'Missing feature module: {name}'
        if 'lookahead' not in sys.modules:
            spec = importlib.util.spec_from_file_location('lookahead', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
            package = importlib.util.module_from_spec(spec)
            sys.modules['lookahead'] = package
            spec.loader.exec_module(package)
        return __import__('lookahead.' + name, fromlist=[name])
    return load


@pytest.fixture
def now():
    from datetime import datetime
    return datetime.fromisoformat('2030-06-10T12:00:00+00:00')


@pytest.fixture
def sample(module, now):
    from datetime import timedelta
    c = module('contracts')
    def make(minutes=60, title='Orbital demo', status='not_ready', id='demo', detail='Deck unfinished'):
        event = c.Event(id, now + timedelta(minutes=minutes), title, 'deck')
        return c.Snapshot((event,), (c.Readiness('deck', status, detail),), now)
    return make
