import importlib.util
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def load():
    path=Path(__file__).resolve().parents[1]/'scripts/acceptance_telegram.py'
    spec=importlib.util.spec_from_file_location('telegram_acceptance',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def test_acceptance_is_two_labeled_messages_without_clock_manipulation():
    mod=load()
    now=datetime(2026,11,10,17,45,tzinfo=ZoneInfo('America/New_York'))
    settings=mod.settings(now)
    assert settings['capture_cli'] is True
    assert settings['operator_chat_id']=='123456789'
    assert settings['normal_cap']==3 and settings['spacing_minutes']==0
    assert settings['offer_lead_minutes']==5 and settings['followup_delay_minutes']==1
    assert mod.label_output('')==''
    assert mod.label_output('Preparation brief\n').startswith('Lookahead demo test')
    assert 'fictional' in mod.label_output('Follow-up\n')


def test_receipts_are_exact_allowlisted_transport_ids():
    mod=load()
    text="2026-11-10 17:50:01 INFO Job 'abc': delivered to telegram:123456789 via live adapter (message_id=123)\n"
    rows=mod.receipts(text)
    assert len(rows)==1 and rows[0]['message_id']=='123'
    assert mod.receipts(text.replace('123456789','1111'))==[]


def test_native_output_is_exported_before_cron_removal():
    mod=load()
    calls=[]
    mod.preserve_and_teardown(lambda:calls.append('export'),lambda:calls.append('remove job'))
    assert calls==['export','remove job']
    def broken_export():
        raise OSError('fictional export failure')
    import pytest
    with pytest.raises(OSError):
        mod.preserve_and_teardown(broken_export,lambda:calls.append('cleanup even on export error'))
    assert calls[-1]=='cleanup even on export error'