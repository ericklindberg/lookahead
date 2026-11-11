from datetime import timedelta
from types import SimpleNamespace
import json


def test_native_tick_rechecks_plugin_disabled_during_generation(module,now,tmp_path,monkeypatch,capsys):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path))
    store=module('store').Store();store.set_stopped(False)
    row=module('capture').Captured('a'*64,'Review','I will attend the review tomorrow.','s',now,now+timedelta(days=1),now,'UTC',.95,'prep_brief',False)
    # Runtime uses actual clock; keep this fictional record eligible around that clock.
    from datetime import datetime,timezone
    stamp=datetime.now(timezone.utc)
    from dataclasses import replace
    row=replace(row,due=stamp+timedelta(hours=1),offer_at=stamp)
    store.save_captures([row])
    raw={'plugins':{'enabled':['lookahead'],'entries':{'lookahead':{'settings':{'enabled':True}}}}}
    monkeypatch.setattr('hermes_cli.config.load_config',lambda:raw)
    def complete(**kw):
        raw['plugins']['disabled']=['lookahead']
        return SimpleNamespace(text=json.dumps({'prep':'Review notes.','question':'What is missing?'}))
    ctx=SimpleNamespace(get_config=lambda k,d=None:{'timezone':'UTC','quiet_start':(stamp.hour+3)%24,'quiet_end':(stamp.hour-3)%24}.get(k,d),llm=SimpleNamespace(complete=complete))
    module('cli').dispatch(ctx,SimpleNamespace(action='tick'))
    assert capsys.readouterr().out==''
    assert store.status()['counts']=={'handoff_unknown':1}
    store.close()
