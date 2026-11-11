import importlib.util
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pytest


def test_probe_cannot_pass_on_leftover_acorn_row(monkeypatch):
    root=Path(__file__).resolve().parents[1];monkeypatch.syspath_prepend(str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('capture_probe_identity_test',root/'scripts/probe_capture.py')
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    since=datetime(2030,6,10,12,tzinfo=timezone.utc);due=since+timedelta(days=1)
    text='I will meet Acorn tomorrow at 10:00.'
    row={'id':'a'*64,'quote':text,'due':due.isoformat(),'captured_at':(since-timedelta(seconds=1)).isoformat()}
    with pytest.raises(AssertionError,match='old'):
        m.confirm_capture([row],text,due,since,'Acorn '+row['id'])
    row['captured_at']=(since+timedelta(seconds=1)).isoformat()
    assert m.confirm_capture([row],text,due,since,'Acorn '+row['id'])==row['id']
