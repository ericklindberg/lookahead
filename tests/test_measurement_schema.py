import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone


def test_live_measurement_reads_real_claim_schema_and_request_clock(module,tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[1];monkeypatch.syspath_prepend(str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('measurement_schema_probe',root/'scripts/measure_capture_leads.py')
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    base=tmp_path/'receipts';base.mkdir();state=tmp_path/'state';state.mkdir()
    monkeypatch.setenv('HERMES_HOME',str(state))
    store=module('store').Store();store.status()
    log=state/'logs/agent.log';log.parent.mkdir(exist_ok=True);log.write_text('')
    out=tmp_path/'results.jsonl';monkeypatch.setattr(m,'OUT',out)
    reset={'lookahead_rows_after':{'capture_turns':0},'explicit_demo_only_reset':True}
    monkeypatch.setattr(m,'reset_lookahead',lambda *a:(base/'lookahead-reset.json').write_text(json.dumps(reset)))
    def command(_base,_env,*args,**kw):
        if args[0]=='chat':
            assert args[3:]==('-Q',)  # only verified stock flags
            text=args[2];store.claim_capture('fixture-session','fixture-turn')
            at=datetime.now(timezone.utc).isoformat()
            log.write_text('lookahead_capture_request text_hash='+hashlib.sha256(text.encode()).hexdigest()[:12]+' captured_at='+at+'\n')
        return SimpleNamespace(returncode=0,stdout='fixture-only',stderr='')
    monkeypatch.setattr(m,'command',command)
    m.trial(base,{},state,'fresh_4_minutes',1)
    row=json.loads(out.read_text())
    assert row['hook_captured_at'] and row['lead_at_hook_minutes']>0
    assert row['live_text_hash_matches'] is True and row['capture'] is False
    assert json.loads(out.with_suffix('.attempts.jsonl').read_text())['computed_lead_minutes']>0
    store.close()
