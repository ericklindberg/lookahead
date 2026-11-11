"""Lazy profile-scoped ledger. A reservation is an UNKNOWN handoff, not delivery."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta
import json
import logging
import hashlib
import sqlite3
import time
import uuid

from .contracts import Candidate, Event, PLUGIN_NAME, aware
from .policy import decide
from .sources import candidates


LOGGER = logging.getLogger(__name__)


class Store:
    def __init__(self):
        self._db = None

    @staticmethod
    def _open_native() -> sqlite3.Connection:
        from plugins.plugin_storage import plugin_db
        # Stock WAL setup can race before the caller can set busy_timeout.
        for attempt in range(6):
            try:
                return plugin_db(PLUGIN_NAME)
            except sqlite3.OperationalError as exc:
                if 'locked' not in str(exc).lower() or attempt == 5:
                    raise
                time.sleep(0.05 * (attempt+1))

    def _connect(self) -> sqlite3.Connection:
        if self._db is not None:
            return self._db
        db = self._open_native()
        db.isolation_level = None
        db.execute('PRAGMA busy_timeout=5000')
        try:
            db.execute('BEGIN IMMEDIATE')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0,1):
                raise ValueError('unsupported ledger schema')
            db.execute('CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS facts (revision TEXT PRIMARY KEY,event_id TEXT NOT NULL,payload TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN (\'baseline\',\'pending\',\'resolved\',\'handoff_unknown\')),handoff_id TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS handoffs (id TEXT PRIMARY KEY,at TEXT NOT NULL,urgent INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS captures (id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS followups (parent TEXT PRIMARY KEY,at TEXT NOT NULL,state TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS forgotten (id TEXT PRIMARY KEY)')
            db.execute('CREATE TABLE IF NOT EXISTS capture_turns (session TEXT,turn TEXT,PRIMARY KEY(session,turn))')
            db.execute("INSERT OR IGNORE INTO meta VALUES ('stopped','true')")
            db.execute('PRAGMA user_version=1')
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            db.close()
            raise
        self._db = db
        return db

    @contextmanager
    def transaction(self):
        db = self._connect()
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.execute('COMMIT')
        except BaseException:
            db.execute('ROLLBACK')
            raise

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    @staticmethod
    def _get(db,key,default=None):
        row = db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
        return json.loads(row[0]) if row else default

    @staticmethod
    def _set(db,key,value):
        db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(key,json.dumps(value)))

    def set_stopped(self,stopped):
        if type(stopped) is not bool:
            raise ValueError('boolean stop state required')
        with self.transaction() as db:
            self._set(db,'stopped',stopped)

    def admit_capture(self,session_key,text,now):
        import hashlib
        if not session_key or not isinstance(text,str) or len(text)>4000:
            return
        with self.transaction() as db:
            rows = db.execute("SELECT key FROM meta WHERE key LIKE 'admitted:%'").fetchall()
            key = 'admitted:'+session_key
            if len(rows)>=200 and not any(row[0] == key for row in rows):
                return
            self._set(db,key,{'digest':hashlib.sha256(text.encode()).hexdigest(),'at':now.timestamp()})

    def consume_admission(self,session_key,text,now):
        import hashlib
        with self.transaction() as db:
            key = 'admitted:'+session_key
            ticket = self._get(db,key)
            if not ticket or ticket['digest'] != hashlib.sha256(text.encode()).hexdigest():
                return False
            db.execute('DELETE FROM meta WHERE key=?',(key,))
            return 0 <= now.timestamp()-ticket['at'] <= 600

    def claim_capture(self,session,turn):
        with self.transaction() as db:
            return db.execute('INSERT OR IGNORE INTO capture_turns VALUES (?,?)',(session,turn)).rowcount == 1

    def capture_error(self,reason):
        with self.transaction() as db:
            self._set(db,'capture_last_error',reason)

    def save_captures(self,rows):
        inserted = 0
        with self.transaction() as db:
            count = db.execute('SELECT COUNT(*) FROM captures').fetchone()[0]
            for row in rows:
                if count >= 200:
                    self._set(db,'capture_last_error','capacity_reached')
                    self._capture_decision(db,'capacity_reached',0)
                    break
                if db.execute('SELECT 1 FROM forgotten WHERE id=?',(row.id,)).fetchone():
                    self._capture_decision(db,'forgotten',0)
                    continue
                changed = db.execute('INSERT OR IGNORE INTO captures VALUES (?,?)',(row.id,json.dumps(row.payload()))).rowcount
                self._capture_decision(db,'stored' if changed else 'dedupe_hit',changed)
                count += changed
                inserted += changed
        return inserted

    def capture_scope(self):
        with self.transaction() as db:
            path=db.execute('PRAGMA database_list').fetchone()[2]
            return hashlib.sha256(path.encode()).hexdigest()[:12]

    @staticmethod
    def _capture_decision(db,reason,count):
        path=db.execute('PRAGMA database_list').fetchone()[2]
        scope=hashlib.sha256(path.encode()).hexdigest()[:12]
        LOGGER.info('lookahead_capture_decision stage=store decision=%s reason=%s count=%d scope=%s',
                    'stored' if count else 'ignored',reason,count,scope)

    def list_captures(self):
        with self.transaction() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT payload FROM captures ORDER BY id')]

    def calendar_status(self, status):
        # Accept only fixed adapter diagnostics; never paths, URLs or exceptions.
        allowed = {'kind', 'host', 'skipped_series', 'error', 'enabled'}
        with self.transaction() as db:
            self._set(db, 'calendar_status', {key: value for key, value in status.items() if key in allowed})

    def list_calendar(self):
        with self.transaction() as db:
            return self._get(db, 'calendar_items', [])

    def forget_capture(self,id):
        with self.transaction() as db:
            deleted = db.execute('DELETE FROM captures WHERE id=?',(id,)).rowcount == 1
            if deleted:
                db.execute('INSERT OR IGNORE INTO forgotten VALUES (?)',(id,))
                db.execute('DELETE FROM facts WHERE event_id=?',(id,))
                db.execute('DELETE FROM followups WHERE parent=?',(id,))
                if self._get(db,'reply_parent',{}).get('id') == id:
                    db.execute("DELETE FROM meta WHERE key='reply_parent'")
            return deleted

    def observe(self,snapshot):
        risks = candidates(snapshot)
        revisions = {r.revision for r in risks}
        with self.transaction() as db:
            if snapshot.source_id == 'calendar':
                self._set(db, 'calendar_items', [{'id':e.id, 'subject':e.title, 'due':e.at.isoformat(), 'source':'calendar'} for e in snapshot.events])
            baseline_key = 'baselined:'+snapshot.source_id
            baseline = snapshot.source_id != 'conversation' and not self._get(db,baseline_key,False)
            for revision,state,payload in db.execute('SELECT revision,state,payload FROM facts').fetchall():
                same_source = json.loads(payload)['source_id'] == snapshot.source_id
                if same_source and revision not in revisions and state in ('baseline','pending'):
                    db.execute("UPDATE facts SET state='resolved' WHERE revision=?",(revision,))
            for risk in risks:
                payload = json.dumps({'id':risk.event.id,'at':risk.event.at.isoformat(),'title':risk.event.title,
                                      'key':risk.event.readiness_key,'detail':risk.detail,'source_id':snapshot.source_id,
                                      'not_before':risk.event.not_before.isoformat() if risk.event.not_before else None,
                                      'end_at':risk.event.end_at.isoformat() if risk.event.end_at else None,
                                      'help_offer':risk.help_offer})
                db.execute('INSERT OR IGNORE INTO facts VALUES (?,?,?,?,NULL)',
                           (risk.revision,risk.event.id,payload,'baseline' if baseline else 'pending'))
            self._set(db,baseline_key,True)
            self._set(db,'source_observed_at',snapshot.observed_at.isoformat() if snapshot.observed_at else None)
            return self._pending(db)

    @staticmethod
    def _pending(db):
        result = []
        for revision,payload in db.execute("SELECT revision,payload FROM facts WHERE state='pending' ORDER BY revision"):
            data = json.loads(payload)
            not_before = datetime.fromisoformat(data['not_before']) if data['not_before'] else None
            end_at = datetime.fromisoformat(data['end_at']) if data.get('end_at') else None
            event = Event(data['id'],datetime.fromisoformat(data['at']),data['title'],data['key'],not_before,end_at)
            result.append(Candidate(event,data['detail'],revision,data['help_offer']))
        return tuple(result)

    def reserve(self,snapshot,now,config, *, snapshots=None):
        now = aware(now)
        inputs = tuple(snapshots) if snapshots is not None else (snapshot,)
        current = {r.revision for item in inputs for r in candidates(item)}
        if snapshots is not None:
            times = [item.observed_at for item in inputs]
            fresh = min(times) if times and all(t is not None for t in times) else None
            snapshot = replace(snapshot, observed_at=fresh, busy=tuple(interval for item in inputs for interval in item.busy))
        with self.transaction() as db:
            risks = tuple(r for r in self._pending(db) if r.revision in current)
            history = tuple((datetime.fromisoformat(at),bool(urgent)) for at,urgent in db.execute('SELECT at,urgent FROM handoffs'))
            decision = decide(risks,snapshot,now,config,stopped=self._get(db,'stopped',True),history=history)
            self._set(db,'last_reason',decision.reason)
            self._set(db,'next_window',decision.next_window.isoformat() if decision.next_window else None)
            if decision.selected:
                handoff = uuid.uuid4().hex
                db.execute('INSERT INTO handoffs VALUES (?,?,?)',(handoff,now.isoformat(),int(decision.urgent)))
                for risk in decision.selected:
                    db.execute("UPDATE facts SET state='handoff_unknown',handoff_id=? WHERE revision=? AND state='pending'",(handoff,risk.revision))
            return decision

    def reserve_followup(self,now,config):
        """Shared caps/spacing and durable unknown reservations, one per parent forever."""
        from .policy import next_normal_window, _normal_hold
        now = aware(now)
        with self.transaction() as db:
            if self._get(db,'stopped',True) or next_normal_window(now,config)>now:
                return None
            history = tuple((datetime.fromisoformat(at),bool(u)) for at,u in db.execute('SELECT at,urgent FROM handoffs'))
            if _normal_hold(now,config,history):
                return None
            rows = [json.loads(r[0]) for r in db.execute('SELECT payload FROM captures WHERE id NOT IN (SELECT parent FROM followups)')]
            rows.sort(key=lambda r:(r['due'],r['id']))
            for row in rows:
                eligible = next_normal_window(datetime.fromisoformat(row['due'])+timedelta(minutes=config.followup_delay_minutes),config)
                if now < eligible:
                    continue
                db.execute("INSERT INTO followups VALUES (?,?,'handoff_unknown')",(row['id'],now.isoformat()))
                db.execute('INSERT INTO handoffs VALUES (?,?,0)',(uuid.uuid4().hex,now.isoformat()))
                self._set(db,'reply_parent',{'id':row['id'],'at':now.isoformat()})
                return row
        return None

    def consume_followup_parent(self,now):
        with self.transaction() as db:
            row = self._get(db,'reply_parent')
            db.execute("DELETE FROM meta WHERE key='reply_parent'")
            if row and timedelta(0)<=now-datetime.fromisoformat(row['at'])<=timedelta(hours=24):
                return row['id']
        return None

    def status(self):
        with self.transaction() as db:
            last = db.execute('SELECT at FROM handoffs ORDER BY at DESC LIMIT 1').fetchone()
            return {'stopped':self._get(db,'stopped',True),
                    'capture_enabled_default':True,
                    'calendar':self._get(db,'calendar_status',{'enabled':False}),
                    'capture_last_error':self._get(db,'capture_last_error'),
                    'counts':dict(db.execute('SELECT state,COUNT(*) FROM facts GROUP BY state')),
                    'last_reason':self._get(db,'last_reason','not_scanned'),
                    'next_window':self._get(db,'next_window'),
                    'source_observed_at':self._get(db,'source_observed_at'),
                    'last_handoff':last[0] if last else None,
                    'delivery':'unknown; stdout is not a receipt'}
