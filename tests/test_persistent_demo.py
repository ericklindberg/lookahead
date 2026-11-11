import importlib.util
from pathlib import Path


def load(name):
    path=Path(__file__).resolve().parents[1]/'scripts'/f'{name}.py'
    spec=importlib.util.spec_from_file_location('probe_'+name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def test_persistent_demo_reuses_one_home_but_new_receipts(tmp_path,monkeypatch):
    m=load('native_cli')
    monkeypatch.setattr(m,'DEMO_ROOT',tmp_path)
    first,paths=m.make_fixture('one',persistent_demo=True)
    marker=Path(paths['state'])/'do-not-reset-core';marker.write_text('keep')
    second,other=m.make_fixture('two',persistent_demo=True)
    assert first!=second
    assert paths['state']==other['state']==str(tmp_path/'demo-home')
    assert paths['runtime']==other['runtime']==str(tmp_path/'demo-runtime')
    assert marker.read_text()=='keep'
    assert m.fixture_state(second)==tmp_path/'demo-home'


def test_auth_diagnostics_scrub_key_and_token_shapes():
    m=load('auth_diagnostics')
    text='key=sk-privateExampleKey123456 and token=123456789:abcdefghijklmnopqrstuvwxy plus exact-sensitive-value'
    safe=m.scrub(text,'exact-sensitive-value')
    assert 'privateExample' not in safe and 'abcdefghijklmnopqrstuvwxy' not in safe and 'exact-sensitive' not in safe
