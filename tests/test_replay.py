from datetime import timedelta


def test_seven_day_replay(module, sample, now, tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path/'profile'))
    c = module('contracts')
    s = module('store').Store()
    s.set_stopped(False)
    s.observe(sample())
    revisions = []
    for day in range(7):
        clock = now+timedelta(days=day)
        event = c.Event('demo',clock+timedelta(minutes=12),'Orbital demo','deck')
        snap = c.Snapshot((event,),sample().readiness,clock)
        s.observe(snap)
        for _ in range(5):
            d = s.reserve(snap,clock,c.Config(timezone='UTC'))
            if d.selected:
                revisions.extend(x.revision for x in d.selected)
                assert module('compose').compose(d,clock) == 'Lookahead:\n- Orbital demo starts in 12 minutes; Deck unfinished.'
        s.close()
        s = module('store').Store()
    assert len(revisions) == len(set(revisions)) == 7
    assert s.status()['counts']['handoff_unknown'] == 7
    s.close()


def test_pluggable_source(module, sample, now):
    sources = module('sources')
    class FictionalSource:
        def read(self, *, now):
            return sample()
    assert sources.read_source(FictionalSource(),now=now) == sample()
    assert isinstance(FictionalSource(), sources.Source)
