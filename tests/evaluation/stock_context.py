"""Qualification-only real stock context, analogous to test_registration.py.

Never imported by plugin registration, capture hooks or scheduled production code.
No provider facade is hand-built and no caller/policy/credential lookup is replaced.
"""

def context(root):
    from hermes_cli.plugins import PluginManager, PluginContext
    from hermes_cli.plugins_manifest import parse_manifest_file
    manager=PluginManager()
    manager.discover_and_load()
    manifest=parse_manifest_file(root/'plugin.yaml',root,'user','')
    if manifest is None:
        raise RuntimeError('invalid qualification manifest')
    return PluginContext(manifest,manager)
