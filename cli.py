"""Explicit operator setup: stage only; schedule creation is a separate approval."""
from pathlib import Path
import re
import shlex

from .contracts import Config


def stage(ctx, *, deliver):
    from hermes_constants import get_hermes_home
    Config(timezone=ctx.get_config('timezone'))
    if not re.fullmatch(r'[a-z][a-z0-9_]*',deliver):
        raise ValueError('one platform name required')
    import hermes_constants
    runtime = str(Path(hermes_constants.__file__).resolve().parent)
    plugin = str(Path(__file__).resolve().parent)
    target = get_hermes_home()/'scripts'/'lookahead_tick.py'
    target.parent.mkdir(parents=True,exist_ok=True)
    template = (Path(__file__).parent/'scripts'/'cron_entry.py').read_text()
    target.write_text(template.replace('RUNTIME_ROOT = None',f'RUNTIME_ROOT = {runtime!r}').replace('PLUGIN_ROOT = None',f'PLUGIN_ROOT = {plugin!r}'))
    return f"hermes cron create 'every 1m' --name lookahead --no-agent --script {shlex.quote(target.name)} --deliver {deliver}"


def setup_parser(parser):
    parser.add_argument('action', choices=['setup','status','list','forget','stop','resume','tick'])
    parser.add_argument('id',nargs='?')
    parser.add_argument('--deliver',default='telegram')


class TickContext:
    """Retain the registered host LLM; re-read native enablement at final handoff."""
    def __init__(self,ctx):
        self.ctx = ctx

    @property
    def llm(self):
        return self.ctx.llm

    def get_config(self,key,default=None):
        if key == 'enabled':
            from hermes_cli.config import load_config
            plugins = load_config().get('plugins',{})
            entry = plugins.get('entries',{}).get('lookahead',{})
            return ('lookahead' in plugins.get('enabled',[]) and 'lookahead' not in plugins.get('disabled',[])
                    and entry.get('enabled',True) is True and self.ctx.get_config(key,True) is True)
        return self.ctx.get_config(key,default)


def dispatch(ctx,args):
    if args.action == 'tick':
        from .runner import run
        run(TickContext(ctx))
        return
    if args.action == 'setup':
        print('Capture default: ON; bounded normal-chat text goes to your configured Hermes model. capture_enabled=false disables it. Outbound starts STOPPED. No schedule created.')
        print(stage(ctx,deliver=args.deliver))
        return
    # Local CLI is the authenticated OS operator, never reachable from model tools.
    from .commands import handle
    source = {k:ctx.get_config('operator_'+k) for k in ('platform','user_id','chat_id')}
    source['chat_type'] = 'dm'
    print(handle(ctx,args.action+(' '+args.id if args.id else ''),source=source))
