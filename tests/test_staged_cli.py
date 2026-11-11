import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest


def test_staged_runner_uses_documented_cli_process_not_private_entry(tmp_path,monkeypatch):
    script=Path(__file__).resolve().parents[1]/'scripts/cron_entry.py'
    spec=importlib.util.spec_from_file_location('staged_probe',script)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.RUNTIME_ROOT=str(tmp_path);m.PLUGIN_ROOT=str(tmp_path)
    (tmp_path/'__init__.py').write_text('')
    monkeypatch.setattr('hermes_cli.config.load_config',lambda:{'plugins':{'enabled':['lookahead']}})
    monkeypatch.setattr('hermes_cli.main.main',lambda:pytest.fail('private Python main called instead of native CLI process'))
    calls=[]
    monkeypatch.setattr('subprocess.run',lambda *a,**kw: calls.append((a,kw)) or SimpleNamespace(returncode=0))
    with pytest.raises(SystemExit) as result: m.main()
    assert result.value.code==0
    assert calls[0][0][0][1:]==['-m','hermes_cli.main','lookahead','tick']
    assert calls[0][1]['cwd']==str(tmp_path)
