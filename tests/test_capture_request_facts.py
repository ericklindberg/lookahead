import hashlib
import logging
from types import SimpleNamespace


def test_logs_response_hash_and_cache_counts_not_body(module,now,caplog):
    cap=module('capture');caplog.set_level(logging.INFO)
    text='{"items":[]}'
    result=SimpleNamespace(text=text,usage=SimpleNamespace(input_tokens=233,output_tokens=105,cache_read_tokens=186,cache_write_tokens=0),audit={})
    cap.extract(SimpleNamespace(complete=lambda **kw:result),'I will meet the team tomorrow at 10:00.',session_id='s',now=now,timezone='UTC')
    lines=[r.getMessage() for r in caplog.records]
    assert any('body_hash='+hashlib.sha256(text.encode()).hexdigest()[:12] in x and 'cache_read_tokens=186' in x for x in lines)
    assert any('messages=2 roles=system,user' in x and 'payload_chars=' in x and 'payload_hash=' in x for x in lines)
    assert not any(text in x for x in lines)
