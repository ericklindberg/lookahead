import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest


def test_staged_runner_prefers_native_pm_hermes_entry(tmp_path,monkeypatch):
    script=Path(__file__).resolve().parents[1]/'scripts/cron_entry.py'
    spec=importlib.util.spec_from_file_location('staged_pm_probe',script)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.RUNTIME_ROOT=str(tmp_path);m.PLUGIN_ROOT=str(tmp_path)
    (tmp_path/'__init__.py').write_text('')
    entry=tmp_path/'.hermes/bin/hermes';entry.parent.mkdir(parents=True);entry.write_text('# fixture launcher')
    monkeypatch.setattr('hermes_cli.config.load_config',lambda:{'plugins':{'enabled':['lookahead']}})
    calls=[]
    monkeypatch.setattr('subprocess.run',lambda *a,**kw:calls.append((a,kw)) or SimpleNamespace(returncode=0))
    with pytest.raises(SystemExit) as result: m.main()
    assert result.value.code==0
    assert calls[0][0][0]==[str(entry),'lookahead','tick']
