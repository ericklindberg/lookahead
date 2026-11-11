"""Side-effect-free stock registration with lazy runtime handlers."""
import json


def _status(args=None, **kwargs):
    from .store import Store
    store = Store()
    try:
        status = store.status()
        from hermes_constants import get_hermes_home
        status['integration'] = 'runner_staged' if (get_hermes_home()/'scripts'/'lookahead_tick.py').is_file() else 'runner_not_configured'
        return json.dumps(status,sort_keys=True)
    finally:
        store.close()


def _admission(ctx, **kwargs):
    from .commands import admission
    return admission(ctx,**kwargs)


def _dispatch_command(ctx,raw_args='',**kwargs):
    from .commands import handle
    return handle(ctx,raw_args,**kwargs)


def _capture_turn(ctx, **kwargs):
    if not kwargs.get('session_id') or not isinstance(kwargs.get('user_message'),str):
        return None
    from .capture import observe_turn
    return observe_turn(ctx,**kwargs)


def register(ctx):
    ctx.register_tool(name='lookahead_status',override=False,toolset='lookahead',
                      schema={'name':'lookahead_status', 'description':'Show Lookahead integration status.',
                              'parameters':{'type':'object','properties':{},'additionalProperties':False}},
                      handler=_status, check_fn=lambda: True)
    ctx.register_command('lookahead', lambda raw_args='',**kwargs: _dispatch_command(ctx,raw_args,**kwargs), description='Lookahead capture, status and plugin-only controls', args_hint='status|list|forget <id>|stop|resume')
    from .cli import setup_parser, dispatch
    ctx.register_cli_command('lookahead', 'Lookahead readiness radar', setup_parser, lambda args: dispatch(ctx,args))
    ctx.register_hook('post_gateway_admission', lambda **kwargs: _admission(ctx,**kwargs))
    ctx.register_auxiliary_task('lookahead_capture',display_name='Lookahead conversation capture',
                                description='Bounded commitment extraction; sends user text to the configured host model.',
                                defaults={'timeout':8})
    ctx.register_auxiliary_task('lookahead_brief',display_name='Lookahead preparation brief',
                                description='Bounded preparation checklist from captured user quotations only.',
                                defaults={'timeout':8})
    ctx.register_hook('post_llm_call',lambda **kwargs: _capture_turn(ctx,**kwargs))
