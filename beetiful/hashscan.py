"""Async file-content hashing for the definite duplicate tier.

Hashes are cached in a sidecar SQLite DB keyed by (item id, size, mtime) so a file is
only re-hashed when it actually changes. We use a sidecar rather than a beets flexattr
because the `beet` CLI is our only beets interface — per-item `beet modify` across
thousands of files would be unusably slow.

The worker runs in a daemon thread; progress is polled via get_status(). This is sized
for a local single-user tool, not concurrent multi-user use.
"""

import hashlib
import os
import sqlite3
import threading
import time

from . import artwork

# Overridable so tests (and containers) can use an isolated cache instead of the repo's.
CACHE_PATH = os.environ.get('BEETIFUL_HASHCACHE') or \
    os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'hashcache.sqlite')

_state_lock = threading.Lock()
_state = {
    'running': False, 'total': 0, 'done': 0,
    'hashed': 0, 'skipped': 0, 'errors': 0,
    'started': None, 'finished': None, 'error': None,
}
_thread = None


def _connect():
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    conn = sqlite3.connect(CACHE_PATH, timeout=10)
    conn.execute('PRAGMA busy_timeout=5000')
    conn.execute(
        'CREATE TABLE IF NOT EXISTS file_hash '
        '(item_id INTEGER PRIMARY KEY, size INTEGER, mtime REAL, sha256 TEXT)'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS art_dims '
        '(item_id INTEGER PRIMARY KEY, width INTEGER, height INTEGER)'
    )
    return conn


def get_status():
    with _state_lock:
        return dict(_state)


def cached_hashes():
    """Return {item_id: sha256} for every cached row."""
    conn = _connect()
    try:
        return {row[0]: row[1] for row in conn.execute('SELECT item_id, sha256 FROM file_hash')}
    finally:
        conn.close()


def art_dims():
    """Return {item_id: (width, height)} for every cached art-dimension row."""
    conn = _connect()
    try:
        return {row[0]: (row[1], row[2]) for row in conn.execute('SELECT item_id, width, height FROM art_dims')}
    finally:
        conn.close()


def record_art_dims(item_id, width, height):
    """Upsert one track's art dimensions (called opportunistically from request threads)."""
    conn = _connect()
    try:
        conn.execute('INSERT OR REPLACE INTO art_dims VALUES (?,?,?)', (item_id, width, height))
        conn.commit()
    finally:
        conn.close()


def _hash_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(chunk), b''):
            h.update(block)
    return h.hexdigest()


def start_scan(items):
    """items: iterable of {'id': int, 'path': str}. Returns False if already running."""
    global _thread
    items = list(items)
    with _state_lock:
        if _state['running']:
            return False
        _state.update(running=True, total=len(items), done=0, hashed=0, skipped=0,
                      errors=0, started=time.time(), finished=None, error=None)
    _thread = threading.Thread(target=_run, args=(items,), daemon=True)
    _thread.start()
    return True


def _bump(key):
    with _state_lock:
        _state[key] += 1


def _run(items):
    try:
        conn = _connect()
        existing = {row[0]: (row[1], row[2])
                    for row in conn.execute('SELECT item_id, size, mtime FROM file_hash')}
        have_dims = {row[0] for row in conn.execute('SELECT item_id FROM art_dims')}
        for it in items:
            iid, path = it.get('id'), it.get('path')
            try:
                if path and os.path.isfile(path):
                    st = os.stat(path)
                    if existing.get(iid) == (st.st_size, st.st_mtime):
                        _bump('skipped')
                    else:
                        digest = _hash_file(path)
                        conn.execute('INSERT OR REPLACE INTO file_hash VALUES (?,?,?,?)',
                                     (iid, st.st_size, st.st_mtime, digest))
                        conn.commit()
                        _bump('hashed')
                    # Backfill art dimensions in the same pass (even for hash-cached files).
                    if iid not in have_dims:
                        dims = artwork.art_dimensions(path)
                        if dims:
                            conn.execute('INSERT OR REPLACE INTO art_dims VALUES (?,?,?)',
                                         (iid, dims[0], dims[1]))
                            conn.commit()
                else:
                    _bump('errors')
            except OSError:
                _bump('errors')
            finally:
                _bump('done')
        conn.close()
    except Exception as e:  # pragma: no cover - defensive; surfaced via status
        with _state_lock:
            _state['error'] = str(e)
    finally:
        with _state_lock:
            _state['running'] = False
            _state['finished'] = time.time()
