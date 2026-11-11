import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest


def setup(tmp_path,monkeypatch):
    path=Path(__file__).resolve().parents[1]/'scripts/native_cli.py'
    spec=importlib.util.spec_from_file_location('runtime_cleanup_probe',path)
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    monkeypatch.setattr(m,'DEMO_ROOT',tmp_path)
    base,paths=m.make_fixture('cleanup',persistent_demo=True)
    return m,base,Path(paths['state'])


def spawn(state):
    proc = subprocess.Popen([sys.executable,'-c','import time;print("READY",flush=True);time.sleep(30)','fixture-gateway'],env=dict(os.environ,HERMES_HOME=str(state)),start_new_session=True,stdout=subprocess.PIPE,text=True)
    assert proc.stdout.readline() == 'READY\n'  # exec completed; /proc now exposes the child environment.
    return proc


def describe(state,pid):
    (state/'gateway_state.json').write_text(json.dumps({'pid':pid,'start_time':int(Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]),'hermes_home':str(state),'kind':'hermes-gateway'}))


def test_stops_only_new_scoped_cli_owner(tmp_path,monkeypatch):
    m,base,state=setup(tmp_path,monkeypatch)
    proc=spawn(state)
    try:
        describe(state,proc.pid)
        assert m.cleanup_cli_runtime(base,None) is True
        proc.wait(timeout=5)
        assert m.runtime_identity(base) is None
    finally:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)


def test_preserves_explicit_fixture_gateway(tmp_path,monkeypatch):
    m,base,state=setup(tmp_path,monkeypatch)
    proc=spawn(state)
    try:
        describe(state,proc.pid);m.mark_gateway(base,proc.pid)
        assert m.cleanup_cli_runtime(base,None) is False
        assert proc.poll() is None
    finally:proc.terminate();proc.wait(timeout=5)


def test_refuses_owner_with_wrong_home(tmp_path,monkeypatch):
    m,base,state=setup(tmp_path,monkeypatch)
    proc=spawn(tmp_path/'different-home')
    try:
        describe(state,proc.pid)
        with pytest.raises(RuntimeError,match='home'):
            m.cleanup_cli_runtime(base,None)
        assert proc.poll() is None
    finally:proc.terminate();proc.wait(timeout=5)
