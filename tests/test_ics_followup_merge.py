from datetime import timedelta

from test_brief_followup import setup


def test_failed_calendar_holds_due_followup(module, now, monkeypatch, tmp_path, capsys):
    ctx, store, row = setup(module, now, monkeypatch, tmp_path, spacing_minutes=0)
    runner = module('runner')
    runner.run(ctx, now=now)
    capsys.readouterr()
    settings = {'timezone':'UTC', 'enabled':True, 'spacing_minutes':0,
                'ics_enabled':True, 'ics_path':'/not/a/real/calendar.ics'}
    ctx.get_config = lambda k,d=None: settings.get(k,d)
    runner.run(ctx, now=row.due+timedelta(hours=2))
    assert capsys.readouterr().out == ''
    assert store.status()['calendar']['error'] == 'calendar_unavailable'
    settings['ics_enabled'] = False
    runner.run(ctx, now=row.due+timedelta(hours=2))
    assert 'Any next steps' in capsys.readouterr().out
    store.close()
