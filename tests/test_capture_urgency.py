from datetime import datetime, timedelta


def test_conversation_offer_is_not_verified_overnight_readiness(module):
    c = module('contracts')
    now = datetime.fromisoformat('2030-06-10T23:00:00Z')
    s = c.Snapshot((c.Event('demo',now+timedelta(minutes=10),'Boss meeting','prep',now),),
                   (c.Readiness('prep','not_ready','I can help prepare talking points'),),now,source_id='conversation')
    d = module('policy').decide(module('sources').candidates(s),s,now,c.Config(timezone='UTC'))
    assert not d.selected and not d.urgent and d.reason == 'quiet_hours'
