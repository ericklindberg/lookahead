from datetime import datetime, timedelta

import pytest


def decide(module, sample, now, **kwargs):
    c = module('contracts')
    snapshot = kwargs.pop('snapshot', sample())
    cfg = kwargs.pop('config', c.Config(timezone='UTC'))
    risks = kwargs.pop('risks', module('sources').candidates(snapshot))
    return module('policy').decide(risks, snapshot, now, cfg, **kwargs)


def test_normal(module, sample, now):
    d = decide(module, sample, now)
    assert d.reason == 'eligible' and len(d.selected) == 1 and not d.urgent


@pytest.mark.parametrize('flag,reason', [('stopped','stopped'), ('stale','stale_sources'), ('meeting','meeting'), ('spacing','spacing'), ('cap','normal_cap'), ('expired','no_upcoming_risks')])
def test_holds(module, sample, now, flag, reason):
    kw = {}
    if flag == 'stopped': kw['stopped'] = True
    if flag == 'stale': kw['snapshot'] = module('contracts').Snapshot(sample().events, sample().readiness, now-timedelta(minutes=16))
    if flag == 'meeting': kw['snapshot'] = module('contracts').Snapshot(sample().events, sample().readiness, now, ((now-timedelta(minutes=1), now+timedelta(minutes=20)),))
    if flag == 'spacing': kw['history'] = ((now-timedelta(minutes=29), False),)
    if flag == 'cap': kw['history'] = tuple((now-timedelta(hours=i+1),False) for i in range(3))
    if flag == 'expired': kw['snapshot'] = sample(minutes=-1)
    d = decide(module, sample, now, **kw)
    assert d.reason == reason and not d.selected


@pytest.mark.parametrize('clock,minutes,urgent,reason', [('2030-06-10T23:00:00Z',10,True,'eligible'), ('2030-06-10T23:00:00Z',16,False,'quiet_hours'), ('2030-06-10T07:55:00Z',10,False,'quiet_hours'), ('2030-06-10T08:00:00Z',10,False,'eligible')])
def test_verified_urgency(module, clock, minutes, urgent, reason):
    c = module('contracts')
    now = datetime.fromisoformat(clock)
    e = c.Event('demo', now+timedelta(minutes=minutes), 'Demo', 'deck')
    s = c.Snapshot((e,), (c.Readiness('deck','not_ready','Deck unfinished'),), now)
    d = module('policy').decide(module('sources').candidates(s), s, now, c.Config(timezone='UTC'))
    assert d.urgent is urgent and d.reason == reason


def test_overnight_cap(module):
    c = module('contracts')
    now = datetime.fromisoformat('2030-06-11T00:05:00Z')
    e = c.Event('demo', now+timedelta(minutes=10), 'Demo', 'deck')
    s = c.Snapshot((e,), (c.Readiness('deck','not_ready','Deck'),), now)
    d = module('policy').decide(module('sources').candidates(s), s, now, c.Config(timezone='UTC'), history=((now-timedelta(minutes=20), True),))
    assert d.reason == 'urgent_cap' and not d.selected


@pytest.mark.parametrize('instant,expected', [('2030-03-10T06:59:00Z','2030-03-10T12:00:00+00:00'), ('2030-11-03T05:30:00Z','2030-11-03T13:00:00+00:00'), ('2030-11-03T06:30:00Z','2030-11-03T13:00:00+00:00')])
def test_dst_next_window(module, instant, expected):
    c = module('contracts')
    assert module('policy').next_normal_window(datetime.fromisoformat(instant), c.Config(timezone='America/New_York')).isoformat() == expected


def test_bundle_chronological_and_exact_text(module, sample, now):
    c = module('contracts')
    events = tuple(c.Event(str(i),now+timedelta(minutes=i*10),f'Demo {i}','deck') for i in [4,1,3,2])
    s = c.Snapshot(events, sample().readiness, now)
    d = module('policy').decide(module('sources').candidates(s), s, now, c.Config(timezone='UTC'))
    assert [x.event.id for x in d.selected] == ['1','2','3']
    assert module('compose').compose(d, now) == 'Lookahead:\n- Demo 1 starts in 10 minutes; Deck unfinished.\n- Demo 2 starts in 20 minutes; Deck unfinished.\n- Demo 3 starts in 30 minutes; Deck unfinished.'


def test_sanitized_bounded_text(module, sample, now):
    d = decide(module, sample, now, snapshot=sample(title='@everyone\u202e\x00<script>'+ 'x'*1000,detail='@here\nfollow [link](https://example.test)'))
    text = module('compose').compose(d,now)
    assert '@' not in text and '\u202e' not in text and '\x00' not in text and '<script>' not in text
    assert len(text) < 600
    assert module('compose').compose(module('contracts').Decision((), 'stopped'),now) == ''


def test_unknown_freshness(module, sample, now):
    c = module('contracts')
    d = decide(module,sample,now,snapshot=c.Snapshot(sample().events,sample().readiness,None))
    assert d.reason == 'stale_sources'


def test_pure_policy_no_mutation(module, sample, now):
    snapshot = sample()
    before = repr(snapshot)
    assert decide(module,sample,now,snapshot=snapshot) == decide(module,sample,now,snapshot=snapshot)
    assert repr(snapshot) == before
