import sqlite3


def test_stock_open_lock_retried(module, monkeypatch, tmp_path):
    monkeypatch.setenv('HERMES_HOME',str(tmp_path/'state'))
    import plugins.plugin_storage as native
    original = native.plugin_db
    calls = []
    def initially_locked(*a,**kw):
        calls.append(1)
        if len(calls) == 1:
            raise sqlite3.OperationalError('database is locked')
        return original(*a,**kw)
    monkeypatch.setattr(native,'plugin_db',initially_locked)
    s = module('store').Store()
    try:
        assert s.status()['stopped']
        assert len(calls) == 2
    finally:
        s.close()
