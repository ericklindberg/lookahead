import importlib.util
from pathlib import Path
import pytest


def test_missing_request_has_actionable_non_model_diagnostic(monkeypatch):
    root=Path(__file__).resolve().parents[1]
    monkeypatch.syspath_prepend(str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('paired_diagnostic_probe',root/'scripts/probe_paired_capture.py')
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    with pytest.raises(RuntimeError) as exc:
        m.request_line([],log_path=Path('/fictional/agent.log'),offset=42,native_exit=2,
                       stderr='unrecognized arguments',reset_turns=0,after_turns=0)
    text=str(exc.value)
    assert '/fictional/agent.log' in text and '42' in text and 'native_chat_exit' in text
    assert 'hook_ran' in text and 'reset_capture_turns' in text and 'harness_chat_rejected' in text
