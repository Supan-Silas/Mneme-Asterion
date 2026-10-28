"""Raw input journal in AMI's SQLite database; committed requests alone are visible."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from app import config


@contextmanager
def connect():
    db = sqlite3.connect(config.DB_PATH, timeout=30)
    db.execute('PRAGMA synchronous=FULL')
    try:
        with db:
            yield db
    finally:
        db.close()


def init():
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS e_raw_requests (
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL, request_id TEXT NOT NULL, payload TEXT NOT NULL,
            UNIQUE(user_id, request_id))''')
        missing = db.execute('''SELECT COUNT(*) FROM requests q LEFT JOIN e_raw_requests r
            ON q.user_id=r.user_id AND q.request_id=r.request_id WHERE r.seq IS NULL''').fetchone()[0]
        if missing:
            raise RuntimeError('Existing AMI database lacks E raw history. Use a new database and replay Add; do not silently migrate.')


def stage(request):
    payload = json.dumps(request.model_dump(mode='json'), ensure_ascii=False, sort_keys=True)
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload FROM e_raw_requests WHERE user_id=? AND request_id=?',
                         (request.user_id, request.request_id)).fetchone()
        if row and row[0] != payload:
            raise ValueError('request_id already has a different payload for this user')
        if not row:
            db.execute('INSERT INTO e_raw_requests(user_id,request_id,payload) VALUES(?,?,?)',
                       (request.user_id, request.request_id, payload))


def history(user_id):
    # Raw payload is persisted BEFORE native Add. Its visibility is tied to the
    # native requests commit, so a failed/crashed Add never becomes E evidence.
    with connect() as db:
        rows = db.execute('''SELECT r.payload FROM e_raw_requests r JOIN requests q
            ON q.user_id=r.user_id AND q.request_id=r.request_id
            WHERE r.user_id=? ORDER BY r.seq''', (user_id,)).fetchall()
    # Preserve successful ingestion order, including interleaved session IDs.
    # Globally grouping a repeated session moves later controls before earlier
    # controls from another session. Only coalesce adjacent matching segments.
    sessions = []; previous_key = None
    for (payload,) in rows:
        r = json.loads(payload)
        for i, m in enumerate(r['messages']):
            stamp = m.get('timestamp')
            stamp = datetime.fromtimestamp(stamp / 1000, tz=timezone.utc).isoformat() if stamp is not None else None
            key = (r['session_id'], stamp)
            if not sessions or key != previous_key:
                sessions.append({'timestamp': stamp, 'messages': []})
            previous_key = key
            sessions[-1]['messages'].append({
                'text': m['content'], 'role': m['role'], 'speaker': m.get('speaker') or m['role'],
                'source_id': m.get('source_id') or f"{r['request_id']}:{i}",
            })
    return {'sessions': sessions}
