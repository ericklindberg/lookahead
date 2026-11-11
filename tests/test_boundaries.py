"""Additional boundary regressions written before extending the implementation."""
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

import pytest


def test_source_identity_separates_revision(module,sample):
    c = module('contracts')
    s = sample()
    other = c.Snapshot(s.events,s.readiness,s.observed_at,source_id='second')
    assert module('sources').candidates(s)[0].revision != module('sources').candidates(other)[0].revision


def test_generator(tmp_path, module, now):
    root = Path(__file__).parents[1]
    script = root/'scripts'/'make_demo.py'
    assert script.exists(), 'Missing demo generator'
    result = subprocess.run([sys.executable,str(script),'--output',str(tmp_path),'--now',now.isoformat()],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    s = module('sources').load(tmp_path/'agenda.md',tmp_path/'readiness.md',now=now)
    assert s.events[0].at == now+timedelta(minutes=12)
    assert s.readiness[0].status == 'not_ready'


def test_source_id_and_snapshot_immutability(module,sample):
    c = module('contracts')
    s = sample()
    with pytest.raises(ValueError):
        c.Snapshot(s.events,s.readiness,s.observed_at,source_id='../escape')
    source_events = list(s.events)
    snap = c.Snapshot(source_events,list(s.readiness),s.observed_at)
    source_events.clear()
    assert len(snap.events) == 1 and isinstance(snap.events,tuple)


def test_policy_rejects_naive_now(module,sample,now):
    with pytest.raises(ValueError):
        module('policy').decide((),sample(),now.replace(tzinfo=None),module('contracts').Config(timezone='UTC'))


@pytest.mark.parametrize('hour', [21,22,7,8])
def test_quiet_endpoints(module,sample,now,hour):
    c = module('contracts')
    clock = now.replace(hour=hour)
    s = c.Snapshot((c.Event('demo',clock+timedelta(hours=1),'Demo','deck'),),sample().readiness,clock)
    d = module('policy').decide(module('sources').candidates(s),s,clock,c.Config(timezone='UTC'))
    assert d.reason == ('quiet_hours' if hour in (22,7) else 'eligible')


def test_dst_gap_and_fold_configured_end(module):
    c = module('contracts')
    p = module('policy')
    cfg = c.Config(timezone='America/New_York',quiet_end=2)
    assert p.next_normal_window(datetime.fromisoformat('2030-03-10T06:50:00Z'),cfg).isoformat() == '2030-03-10T07:00:00+00:00'
    cfg = c.Config(timezone='America/New_York',quiet_end=1)
    assert p.next_normal_window(datetime.fromisoformat('2030-11-03T04:50:00Z'),cfg).isoformat() == '2030-11-03T05:00:00+00:00'


def test_unknown_snapshot_future_holds(module,sample,now):
    c = module('contracts')
    s = c.Snapshot(sample().events,sample().readiness,now+timedelta(minutes=2))
    assert module('policy').decide(module('sources').candidates(s),s,now,c.Config(timezone='UTC')).reason == 'stale_sources'


def test_alternate_adapter_cannot_return_arbitrary_object(module,now):
    class BadSource:
        def read(self,*,now): return {'events':[]}
    with pytest.raises(ValueError):
        module('sources').read_source(BadSource(),now=now)
