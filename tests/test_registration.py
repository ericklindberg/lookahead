from pathlib import Path

import pytest
import hermes_yaml as yaml


def test_manifest(module):
    c = module('contracts')
    manifest = yaml.safe_load((Path(__file__).parents[1] / 'plugin.yaml').read_text())
    assert manifest['name'] == c.PLUGIN_NAME == 'lookahead'
    assert manifest['requires_hermes'] == '>=0.23.0'
    assert manifest['provides_tools'] == ['lookahead_status']
    assert manifest['provides_hooks'] == ['post_gateway_admission', 'post_llm_call']
    assert 'timezone' in manifest['config_schema']
    from hermes_cli.plugins_manifest import _KNOWN_MANIFEST_FIELDS
    assert set(manifest) <= _KNOWN_MANIFEST_FIELDS


def test_registration_has_no_io(module, monkeypatch):
    module('contracts')
    import lookahead
    calls = []
    class Context:
        def __getattr__(self, key):
            assert key.startswith('register_'), key
            return lambda *a, **kw: calls.append((key, a, kw))
    monkeypatch.setattr('sqlite3.connect', lambda *a, **kw: pytest.fail('registration opened storage'))
    monkeypatch.setattr('subprocess.Popen', lambda *a, **kw: pytest.fail('registration launched child'))
    monkeypatch.setattr('builtins.open', lambda *a, **kw: pytest.fail('registration opened a file'))
    monkeypatch.setattr('os.open', lambda *a, **kw: pytest.fail('registration opened a file descriptor'))
    lookahead.register(Context())
    assert [x[0] for x in calls] == ['register_tool', 'register_command', 'register_cli_command', 'register_hook', 'register_auxiliary_task', 'register_auxiliary_task', 'register_hook']
    assert [x[1][0] for x in calls if x[0]=='register_auxiliary_task']==['lookahead_capture','lookahead_brief']
    tool = calls[0][2]
    assert tool.get('override', False) is False
    assert callable(tool['handler'])
    assert calls[-1][1][1](event=object()) is None


@pytest.mark.parametrize('kwargs', [{'timezone':'Invalid/Zone'}, {'timezone':'UTC','batch_size':4}, {'timezone':'UTC','normal_cap':-1}, {'timezone':'UTC','spacing_minutes':-1}, {'timezone':'UTC','quiet_start':24}, {'timezone':'UTC','freshness_minutes':0}])
def test_invalid_config(module, kwargs):
    with pytest.raises(ValueError):
        module('contracts').Config(**kwargs)


def test_timezone_required(module):
    with pytest.raises(TypeError):
        module('contracts').Config()


def test_stock_plugin_manager(module, tmp_path, monkeypatch):
    module('contracts')
    from hermes_cli.plugins import PluginManager
    import shutil
    home = tmp_path / 'profile'
    directory = home / 'plugins' / 'lookahead'
    shutil.copytree(Path(__file__).parents[1], directory, ignore=shutil.ignore_patterns('.git', '__pycache__', '.pytest_cache'))
    (home / 'config.yaml').write_text('plugins:\n  enabled: [lookahead]\n')
    monkeypatch.setenv('HERMES_HOME', str(home))
    monkeypatch.setenv('HERMES_BUNDLED_PLUGINS', str(tmp_path / 'empty'))
    manager = PluginManager()
    manager.discover_and_load()
    loaded = manager._plugins['lookahead']
    assert loaded.enabled, loaded.error
    assert loaded.tools_registered == ['lookahead_status']
    assert loaded.hooks_registered == ['post_gateway_admission', 'post_llm_call']
    assert loaded.commands_registered == ['lookahead']
    assert 'lookahead' in manager._cli_commands
    assert 'lookahead_capture' in manager._aux_tasks
    assert 'lookahead_brief' in manager._aux_tasks
    assert not (home / 'plugin-data').exists()
    assert not list((home / 'cron').glob('*'))  # Stock initializes an empty directory.
