import logging
from types import SimpleNamespace
import pytest


@pytest.mark.parametrize('text,tokens,reason',[
    ('',0,'empty_response'),('{"items":[',512,'output_budget_exhausted'),('{"items":[',20,'invalid_json')])
def test_broken_response_is_error_not_no_commitments(module,now,caplog,text,tokens,reason):
    cap=module('capture');caplog.set_level(logging.INFO)
    result=SimpleNamespace(text=text,usage=SimpleNamespace(output_tokens=tokens,input_tokens=301),audit={})
    llm=SimpleNamespace(complete=lambda **kw:result)
    errors=[]
    assert cap.extract(llm,'I will meet PRIVATE_ZEBRA tomorrow at 10:00.',session_id='s',now=now,timezone='UTC',errors=errors)==()
    assert errors==[reason]
    lines=[r.getMessage() for r in caplog.records]
    assert any('decision=error reason='+reason in x for x in lines)
    assert not any('reason=model_no_commitments' in x for x in lines)
    assert any('parsed=0' in x and 'finish_reason=unavailable_stock_api' in x for x in lines)
    assert not any('PRIVATE_ZEBRA' in x for x in lines)


def test_valid_empty_items_logs_parse_and_count(module,now,caplog):
    cap=module('capture');caplog.set_level(logging.INFO)
    result=SimpleNamespace(text='{"items":[]}',usage=SimpleNamespace(output_tokens=6,input_tokens=301),audit={})
    errors=[]
    assert cap.extract(SimpleNamespace(complete=lambda **kw:result),'I will meet the team tomorrow at 10:00.',session_id='s',now=now,timezone='UTC',errors=errors)==()
    assert errors==[]
    assert any('parsed=1' in r.getMessage() and 'items=0' in r.getMessage() and 'output_tokens=6' in r.getMessage() for r in caplog.records)
