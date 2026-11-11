import json


def test_status_tool_real_state(module,tmp_path,monkeypatch):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path/'profile'))
    module('contracts')
    import lookahead
    response = json.loads(lookahead._status({}))
    assert response['stopped'] is True
    assert response['capture_enabled_default'] is True
    assert response['integration'] == 'runner_not_configured'
    assert response['counts'] == {}
