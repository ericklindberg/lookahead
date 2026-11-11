from types import SimpleNamespace

import pytest


def context():
    class Context:
        def get_config(self,key,default=None):
            return {'operator_platform':'telegram','operator_user_id':'fictional-user','operator_chat_id':'fictional-chat'}.get(key,default)
    return Context()


def source(**overrides):
    data = dict(platform='telegram',user_id='fictional-user',chat_id='fictional-chat',chat_type='dm')
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.parametrize('identity',[None,source(user_id='stranger'),source(chat_type='group'),source(chat_id='other')])
def test_controls_deny_before_storage(module,tmp_path,monkeypatch,identity):
    home = tmp_path/'state'
    monkeypatch.setenv('HERMES_HOME',str(home))
    assert module('commands').handle(context(),'list',source=identity).startswith('Lookahead: controls require')
    assert not home.exists()


def test_controls_list_forget_stop_resume(module,tmp_path,monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path/'state'))
    command = module('commands')
    assert 'Capture is on' in command.handle(context(),'list',source=source())
    assert 'resumed' in command.handle(context(),'resume',source=source())
    assert 'stopped' in command.handle(context(),'stop',source=source())
    assert module('store').Store().status()['stopped']
    assert 'not found' in command.handle(context(),'forget '+'a'*64,source=source())
    assert 'Usage:' in command.handle(context(),'forget ../bad',source=source())


def test_plain_hook_only_exact_bound_dm(module,tmp_path,monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path/'state'))
    command = module('commands')
    assert command.admission(context(),text='Please STOP',source=vars(source())) is None
    assert command.admission(context(),text='STOP',source=vars(source(user_id='stranger'))) is None
    result = command.admission(context(),text='STOP',source=vars(source()))
    assert result['action'] == 'handled'
    assert module('store').Store().status()['stopped']
