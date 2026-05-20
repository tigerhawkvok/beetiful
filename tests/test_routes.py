"""Exercise every app route against the isolated mock beets library.

Read-only / detection tests come first; mutation tests (each on its own track) come last,
since the seeded library is shared across the session.
"""

import os
import time


def _items(client):
    return client.get('/api/library').get_json()['items']


def _by_title(client, title):
    return [it for it in _items(client) if it['title'] == title]


def _find_cluster(payload, title):
    for c in payload['clusters']:
        if any(payload['tracks'][str(m)]['title'] == title for m in c['members']):
            return c
    raise AssertionError(f'no cluster containing a track titled {title!r}')


# --- pages & basic reads -------------------------------------------------

def test_home(client):
    r = client.get('/')
    assert r.status_code == 200
    assert b'Beetiful' in r.data


def test_duplicates_page(client):
    r = client.get('/duplicates')
    assert r.status_code == 200
    assert b'Duplicate Finder' in r.data


def test_stats(client):
    j = client.get('/api/stats').get_json()
    assert int(j['total_tracks']) >= 13


def test_library_list(client):
    titles = {it['title'] for it in _items(client)}
    assert {'Alpha', 'Beta Song', 'Gamma', 'Solo Unique'} <= titles


def test_run_command_list(client):
    r = client.post('/api/run-command', json={'command': 'list', 'options': [], 'arguments': []})
    assert r.status_code == 200
    assert isinstance(r.get_json()['output'], list)


def test_config_round_trip(client):
    r = client.get('/api/config')
    assert r.status_code == 200
    original = r.get_data(as_text=True)
    assert 'directory:' in original
    w = client.post('/api/config', data=original, content_type='text/plain')
    assert w.status_code == 200


# --- duplicate detection -------------------------------------------------

def test_duplicate_tiers_present(client):
    j = client.get('/api/duplicates?tiers=definite,probable,possible').get_json()
    tiers = {c['tier'] for c in j['clusters']}
    assert {'definite', 'probable', 'possible'} <= tiers


def test_acoustid_definite_keeps_flac(client):
    j = client.get('/api/duplicates?tiers=definite').get_json()
    gamma = _find_cluster(j, 'Gamma')
    assert gamma['tier'] == 'definite'
    assert 'AcoustID' in gamma['reason']
    assert j['tracks'][str(gamma['keep'])]['format'] == 'FLAC'  # codec rank tiebreak


def test_probable_cluster(client):
    j = client.get('/api/duplicates?tiers=probable').get_json()
    alpha = _find_cluster(j, 'Alpha')
    assert alpha['tier'] == 'probable'
    assert len(alpha['members']) == 2


def test_possible_cluster(client):
    j = client.get('/api/duplicates?tiers=possible').get_json()
    beta = _find_cluster(j, 'Beta Song')
    assert beta['tier'] == 'possible'


def test_titles_diverge_flag(client):
    j = client.get('/api/duplicates?tiers=definite').get_json()
    assert _find_cluster(j, 'Divergent Title A')['titles_diverge'] is True
    assert _find_cluster(j, 'Gamma')['titles_diverge'] is False


def test_hash_scan_then_definite(client):
    assert client.post('/api/duplicates/scan').status_code in (200, 409)
    status = {'running': True}
    for _ in range(150):
        status = client.get('/api/duplicates/scan/status').get_json()
        if not status['running']:
            break
        time.sleep(0.3)
    assert status['running'] is False
    j = client.get('/api/duplicates?tiers=definite').get_json()
    twin = _find_cluster(j, 'Hash Twin')
    assert twin['tier'] == 'definite'
    assert 'identical file' in twin['reason']


# --- art & audio ---------------------------------------------------------

def test_art_thumbnail_and_full(client):
    gamma = _by_title(client, 'Gamma')[0]
    thumb = client.get(f"/api/library/art/{gamma['id']}")
    assert thumb.status_code == 200
    assert thumb.headers['Content-Type'] == 'image/webp'
    full = client.get(f"/api/library/art/{gamma['id']}?full=1")
    assert full.status_code == 200
    assert full.headers['Content-Type'] in ('image/png', 'image/jpeg')


def test_art_missing_returns_404(client):
    solo = _by_title(client, 'Solo Unique')[0]
    assert client.get(f"/api/library/art/{solo['id']}").status_code == 404


def test_audio_stream(client):
    solo = _by_title(client, 'Solo Unique')[0]
    r = client.get(f"/api/library/audio/{solo['id']}")
    assert r.status_code == 200
    assert r.headers['Content-Type'].startswith('audio')


# --- mutations (each isolated to its own track) --------------------------

def test_rename(client):
    track = _by_title(client, 'Completely Other Name')[0]
    r = client.post('/api/library/rename', json={'id': track['id'], 'title': 'Fixed Title'})
    assert r.status_code == 200
    assert _by_title(client, 'Fixed Title')


def test_copy_fields_fills_missing(client):
    members = _by_title(client, 'Missing Album Test')
    has = next(t for t in members if t['album'])
    miss = next(t for t in members if not t['album'])
    r = client.post('/api/library/copy-fields',
                    json={'source_id': has['id'], 'target_ids': [miss['id']]})
    assert r.status_code == 200
    after = next(t for t in _by_title(client, 'Missing Album Test') if t['id'] == miss['id'])
    assert after['album'] == has['album']


def test_batch_update(client):
    track = _by_title(client, 'Solo Unique')[0]
    r = client.post('/api/library/batch-update',
                    json={'ids': [track['id']], 'updates': {'genre': 'TestGenre'}})
    assert r.status_code == 200
    after = next(t for t in _items(client) if t['id'] == track['id'])
    assert after['genre'] == 'TestGenre'


def test_remove_from_library(client):
    beta = _by_title(client, 'Beta Song')[0]
    before = len(_items(client))
    assert client.post('/api/library/remove', json={'id': beta['id']}).status_code == 200
    assert len(_items(client)) == before - 1


def test_delete_from_disk(client):
    live = _by_title(client, 'Beta Song (Live)')[0]
    path = live['path']
    assert os.path.isfile(path)
    assert client.post('/api/library/delete', json={'id': live['id']}).status_code == 200
    assert not os.path.isfile(path)
