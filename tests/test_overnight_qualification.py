import importlib.util
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo


def test_overnight_qualification_uses_product_timing_and_suppresses_notices(module,monkeypatch):
    root=Path(__file__).resolve().parents[1];monkeypatch.syspath_prepend(str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('overnight_config_test',root/'scripts/acceptance_brief.py')
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    now=datetime(2030,6,10,17,tzinfo=ZoneInfo('America/New_York'))
    settings=m.qualification_settings(now,telegram=True,overnight=True)
    defaults=module('contracts').Config(timezone='America/New_York')
    for key in ('offer_lead_minutes','followup_delay_minutes','spacing_minutes','quiet_start','quiet_end'):
        assert settings[key]==getattr(defaults,key)
    cfg=m.qualification_config(settings,{'provider':'minimax','default':'MiniMax-M2.7'},{'provider':'minimax','model':'MiniMax-M2.7'})
    assert cfg['platforms']['telegram']['gateway_restart_notification'] is False
    assert cfg['_config_version']==12
    due=m.qualification_due(now,True)
    assert due.date()>now.date() and due.hour==9 and due.minute==30
