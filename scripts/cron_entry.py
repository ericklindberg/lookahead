"""Staged no-agent entry; missing or disabled package is silent."""
from pathlib import Path
import sys

RUNTIME_ROOT = None
PLUGIN_ROOT = None


def main():
    if not RUNTIME_ROOT or not PLUGIN_ROOT or not (Path(PLUGIN_ROOT)/'__init__.py').is_file():
        return
    sys.path.insert(0,RUNTIME_ROOT)
    from hermes_cli.config import load_config
    class Settings:
        def get_config(self,key,default=None):
            plugins = load_config().get('plugins',{})
            entry = plugins.get('entries',{}).get('lookahead',{})
            if key == 'enabled':
                return ('lookahead' in plugins.get('enabled',[]) and 'lookahead' not in plugins.get('disabled',[])
                        and entry.get('enabled',True) is True and entry.get('settings',{}).get('enabled',True) is True)
            return entry.get('settings',entry.get('config',{})).get(key,default)
    ctx = Settings()
    if not ctx.get_config('enabled',True):
        return
    # Use the documented CLI process, not a private Python entry-point import.
    # The registered handler obtains the real PluginContext and host trust gates.
    import subprocess
    entry = Path(RUNTIME_ROOT)/'.hermes/bin/hermes'
    command = [str(entry),'lookahead','tick'] if entry.is_file() else [sys.executable,'-m','hermes_cli.main','lookahead','tick']
    result = subprocess.run(command,cwd=RUNTIME_ROOT,timeout=60)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
