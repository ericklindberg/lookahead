from types import SimpleNamespace
import json


def test_question_about_obligation_is_not_a_commitment(module,now):
    text='Do I need to attend the review tomorrow?'
    llm=SimpleNamespace(complete=lambda **kw:SimpleNamespace(text=json.dumps({'items':[{'subject':'Review','quote':text,'when':'tomorrow','confidence':.95,'help_kind':'prep_brief'}]})))
    assert module('capture').extract(llm,text,session_id='s',now=now,timezone='UTC')==()
