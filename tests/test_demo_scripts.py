import importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest

ROOT=Path(__file__).resolve().parents[1]


def demo():
    path=ROOT/'scripts/demo_fixture.py'
    assert path.exists(),'demo fixture missing'
    spec=importlib.util.spec_from_file_location('demo_fixture',path)
    m=importlib.util.module_from_spec(spec)
    import sys
    from unittest.mock import patch as mock_patch
    with mock_patch.object(sys,'path',[str(ROOT/'scripts'),*sys.path]):
        spec.loader.exec_module(m)
    return m


def test_visible_demo_config_and_messages():
    m=demo()
    values=m.demo_settings()
    assert values['operator_platform']=='telegram'
    assert values['operator_user_id']==values['operator_chat_id']=='123456789'
    assert values['offer_lead_minutes']==3 and values['followup_delay_minutes']==2
    assert values['spacing_minutes']==0 and values['normal_cap']>=4
    now=datetime(2030,6,10,12,tzinfo=timezone.utc)
    lines=m.demo_messages(now)
    assert len(lines)==4
    assert 'I will' in lines[0] and 'I have to' in lines[1]
    assert (now+timedelta(minutes=5)).strftime('%Y-%m-%d at %H:%M') in lines[0]
    assert 'might' in lines[2] and 'tomorrow at 10:00' in lines[3]


def test_demo_down_refuses_foreign_pid(tmp_path):
    m=demo()
    import os
    # This test's own process is emphatically not a fixture gateway.
    with pytest.raises(ValueError): m.verify_owned_gateway({'pid':os.getpid(),'started':'not-this-process','state':str(tmp_path)})


def test_demo_shell_scripts_use_stock_interpreter():
    for name in ('demo_up.sh','demo_down.sh'):
        path=ROOT/'scripts'/name
        assert path.is_file()
        text=path.read_text()
        assert 'stock-hermes/.venv/bin/python' in text and 'demo_fixture.py' in text
        assert 'TELEGRAM_BOT_TOKEN=' not in text