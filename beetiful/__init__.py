from typing import TYPE_CHECKING, cast
from flask import Flask, jsonify, request, render_template, send_file
from collections import OrderedDict
import os
import mimetypes
import subprocess
import threading

from . import duplicates
from . import hashscan
from . import artwork


app = Flask(__name__)

beets_config_dir = os.getenv('BEETSDIR', os.path.expanduser('~/.config/beets'))
config_path = os.path.join(beets_config_dir, 'config.yaml')

# Use ASCII Unit Separator between fields and Record Separator between records so embedded
# newlines in fields like $comments don't fracture rows when parsing `beet list` output.
FIELD_SEP = '\x1f'
RECORD_SEP = '\x1e'


@app.route('/api/config', methods=['GET'])
def view_config():
    """Fetch the configuration as raw text."""
    try:
        with open(config_path, 'r') as file:
            config_text = file.read()
        return config_text, 200
    except FileNotFoundError:
        return "Config file not found.", 404
    except Exception as e:
        return f"Error loading config: {str(e)}", 500

@app.route('/api/config', methods=['POST'])
def edit_config():
    """Save the configuration as raw text."""
    try:
        config_text = request.data.decode('utf-8')
        with open(config_path, 'w') as file:
            file.write(config_text)
        return jsonify({'message': 'Configuration updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': f"Failed to save configuration: {str(e)}"}), 500

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/duplicates')
def duplicates_page():
    return render_template('duplicates.html')


DUP_FIELDS = ['id', 'title', 'artist', 'album', 'genre', 'year', 'composer',
              'length', 'bitrate', 'format', 'path', 'acoustid_id']
# Descriptive fields used to break ties toward the more fully-tagged copy.
_RICHNESS_FIELDS = ('album', 'genre', 'year', 'composer')
DUP_FORMAT = FIELD_SEP.join(f'${f}' for f in DUP_FIELDS) + RECORD_SEP

# Codec quality ordering for "which copy to keep". Lossless first, then by codec
# efficiency. Bitrate is NOT comparable across codecs (opus@260 beats mp3@320), so it
# only breaks ties within the same codec class — see _suggest_keep.
_CODEC_RANK = {
    'FLAC': 100, 'ALAC': 100, 'WAV': 100, 'AIFF': 100, 'APE': 100, 'WV': 100,
    'WAVPACK': 100, 'DSF': 100, 'DSD': 100,
    'OPUS': 80,
    'AAC': 70, 'M4A': 70, 'MP4': 70,
    'VORBIS': 68, 'OGG': 68,
    'MPC': 66, 'MUSEPACK': 66,
    'WMA': 50,
    'MP3': 40,
}
_CODEC_RANK_DEFAULT = 30


def _codec_rank(fmt):
    return _CODEC_RANK.get((fmt or '').upper(), _CODEC_RANK_DEFAULT)


def _parse_length(text):
    """Beets renders $length as H:MM:SS / M:SS. Return whole seconds, or None."""
    text = (text or '').strip()
    if not text:
        return None
    try:
        parts = [int(p) for p in text.split(':')]
    except ValueError:
        return None
    seconds = 0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def _parse_bitrate(text):
    """Beets renders $bitrate as e.g. '275kbps'. Return the integer kbps, or None."""
    digits = ''.join(c for c in (text or '') if c.isdigit())
    return int(digits) if digits else None


def _fetch_dup_items():
    result = subprocess.run(['beet', 'list', '-f', DUP_FORMAT], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    items = []
    for record in result.stdout.split(RECORD_SEP):
        if not record.strip():
            continue
        fields = record.lstrip('\n').split(FIELD_SEP)
        row: dict = {name: (fields[i] if i < len(fields) else '') for i, name in enumerate(DUP_FIELDS)}
        try:
            row['id'] = int(row['id'])
        except (ValueError, TypeError):
            continue
        row['length_s'] = _parse_length(row['length'])
        row['bitrate_kbps'] = _parse_bitrate(row['bitrate'])
        items.append(row)
    return items


# id -> filesystem path, warmed by list/duplicate fetches so the art and audio
# endpoints don't each spawn a `beet` subprocess.
_PATH_CACHE = {}


def _remember_paths(items):
    for it in items:
        if it.get('path'):
            _PATH_CACHE[it['id']] = it['path']


def _path_for(track_id):
    cached = _PATH_CACHE.get(track_id)
    if cached:
        return cached
    result = subprocess.run(['beet', 'list', '-f', '$path', f'id:{int(track_id)}'],
                            capture_output=True, text=True)
    if result.returncode != 0:
        return None
    lines = result.stdout.splitlines()
    if not lines:
        return None
    _PATH_CACHE[track_id] = lines[0]
    return lines[0]


def _raw_art(path):
    """Return (mime, bytes) of full-size art: embedded first, then a cover file."""
    art = artwork.embedded_art(path)
    if art:
        return art
    cover = artwork.cover_file(path)
    if cover and os.path.isfile(cover):
        with open(cover, 'rb') as f:
            data = f.read()
        mime, _ = mimetypes.guess_type(cover)
        return (mime or 'image/jpeg', data)
    return None


# Bounded LRU of downscaled thumbnails keyed by (id, size) so NFS reads + decodes happen
# once, not per render. `False` is a negative cache for tracks with no art.
_ART_CACHE = OrderedDict()
_ART_CACHE_MAX = 1024
_art_lock = threading.Lock()


def _art_cache_get(key):
    with _art_lock:
        if key in _ART_CACHE:
            _ART_CACHE.move_to_end(key)
            return _ART_CACHE[key]
    return None


def _art_cache_put(key, value):
    with _art_lock:
        _ART_CACHE[key] = value
        _ART_CACHE.move_to_end(key)
        while len(_ART_CACHE) > _ART_CACHE_MAX:
            _ART_CACHE.popitem(last=False)


def _metadata_richness(track):
    """Count populated descriptive fields — used to prefer the better-tagged copy."""
    return sum(1 for f in _RICHNESS_FIELDS if str(track.get(f) or '').strip())


def _suggest_keep(member_ids, by_id):
    """Pick the best copy: codec class, then bitrate (within codec), length, richer tags, lowest id."""
    def rank(track):
        return (
            _codec_rank(track.get('format')),
            track.get('bitrate_kbps') or 0,
            track.get('length_s') or 0,
            _metadata_richness(track),
            -track['id'],
        )
    return max(member_ids, key=lambda mid: rank(by_id[mid]))


@app.route('/api/duplicates', methods=['GET'])
def get_duplicates():
    tiers_arg = request.args.get('tiers', 'definite,probable,possible')
    tiers = tuple(t.strip() for t in tiers_arg.split(',') if t.strip())
    try:
        items = _fetch_dup_items()
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 500

    _remember_paths(items)

    # Inject cached file hashes (sidecar) so the definite tier can match identical files.
    hashes = hashscan.cached_hashes()
    for it in items:
        it['content_hash'] = hashes.get(it['id'], '')

    by_id = {it['id']: it for it in items}
    clusters = duplicates.find_duplicates(items, tiers=tiers)

    out_clusters = []
    counts = {}
    for cl in clusters:
        d = cl.as_dict()
        d['keep'] = _suggest_keep(cl.member_ids, by_id)
        out_clusters.append(d)
        counts[cl.tier] = counts.get(cl.tier, 0) + 1

    referenced = {mid for cl in clusters for mid in cl.member_ids}
    tracks = {
        str(mid): {
            'id': by_id[mid]['id'],
            'title': by_id[mid]['title'],
            'artist': by_id[mid]['artist'],
            'album': by_id[mid]['album'],
            'length': by_id[mid]['length'],
            'length_s': by_id[mid]['length_s'],
            'bitrate': by_id[mid]['bitrate_kbps'],
            'format': by_id[mid]['format'],
            'path': by_id[mid]['path'],
        }
        for mid in referenced
    }
    return jsonify({'clusters': out_clusters, 'tracks': tracks, 'counts': counts})


@app.route('/api/duplicates/scan', methods=['POST'])
def start_hash_scan():
    """Kick off the async file-content hashing job for the definite tier."""
    try:
        items = _fetch_dup_items()
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 500
    started = hashscan.start_scan({'id': it['id'], 'path': it['path']} for it in items)
    if not started:
        return jsonify({'error': 'A scan is already running.'}), 409
    return jsonify({'message': 'Scan started.', 'total': len(items)})


@app.route('/api/duplicates/scan/status', methods=['GET'])
def hash_scan_status():
    return jsonify(hashscan.get_status())


@app.route('/api/library/art/<int:track_id>', methods=['GET'])
def get_art(track_id):
    """Serve a downscaled WebP thumbnail of a track's cover art (embedded or cover file)."""
    size = request.args.get('size', default=96, type=int)
    size = max(16, min(size, 512))
    key = (track_id, size)

    cached = _art_cache_get(key)
    if cached is None:
        path = _path_for(track_id)
        raw = _raw_art(path) if path else None
        if not raw:
            _art_cache_put(key, False)  # negative cache: don't re-read missing art
            cached = False
        else:
            # Fall back to the original bytes if Pillow can't decode/encode it.
            cached = artwork.thumbnail(raw[1], size) or raw
            _art_cache_put(key, cached)

    if cached is False:
        return ('', 404)
    mime, data = cached
    resp = app.response_class(data, mimetype=mime)
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Fetch statistics from beets."""
    result = subprocess.run(['beet', 'stats'], capture_output=True, text=True)
    if result.returncode == 0:
        stats = parse_stats(result.stdout)
        return jsonify(stats)
    else:
        return jsonify({'error': result.stderr}), 500


@app.route('/api/run-command', methods=['POST'])
def run_command():
    """Run a command using beets."""
    if not request.is_json:
        return jsonify({'error': 'Expected JSON body.'}), 400
    if TYPE_CHECKING:
        assert isinstance(request.json, dict)
    command = request.json.get('command')
    options = request.json.get('options', [])
    arguments = request.json.get('arguments', [])

    full_command = ['beet', command] + options + arguments

    try:
        result = subprocess.run(full_command, capture_output=True, text=True)
        if result.returncode == 0:
            return jsonify({'output': result.stdout.splitlines()})
        else:
            return jsonify({'error': result.stderr}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

LIBRARY_FIELDS = ['title', 'artist', 'album', 'genre', 'year', 'bpm', 'composer', 'comments', 'id', 'path']
LIBRARY_FORMAT = FIELD_SEP.join(f'${f}' for f in LIBRARY_FIELDS) + RECORD_SEP


@app.route('/api/library', methods=['GET'])
def get_library():
    """Fetch the library items including genre information."""
    result = subprocess.run(['beet', 'list', '-f', LIBRARY_FORMAT], capture_output=True, text=True)
    if result.returncode == 0:
        items = [parse_library_item(r) for r in result.stdout.split(RECORD_SEP) if r.strip()]
        return jsonify({'items': items})
    else:
        return jsonify({'error': result.stderr}), 500

def parse_library_item(record):
    """Parse one record from the list output."""
    fields = record.lstrip('\n').split(FIELD_SEP)
    return {name: (fields[i] if i < len(fields) else '') for i, name in enumerate(LIBRARY_FIELDS)}


@app.route('/api/library/audio/<int:track_id>', methods=['GET'])
def get_audio(track_id):
    """Stream a track's audio file. Lazy: only invoked when the client plays."""
    result = subprocess.run(['beet', 'list', '-f', '$path', f'id:{track_id}'], capture_output=True, text=True)
    if result.returncode != 0:
        return jsonify({'error': result.stderr}), 500
    lines = result.stdout.splitlines()
    if not lines:
        return jsonify({'error': 'Track not found.'}), 404
    file_path = lines[0]
    if not os.path.isfile(file_path):
        return jsonify({'error': 'Audio file missing on disk.'}), 404
    mimetype, _ = mimetypes.guess_type(file_path)
    return send_file(file_path, mimetype=mimetype or 'application/octet-stream', conditional=True)



def _remove_by_id(track_id, delete_from_disk):
    try:
        beet_id = int(track_id)
    except (ValueError, TypeError):
        return jsonify({'error': f'Invalid track id: {track_id!r}'}), 400

    command = ['beet', 'remove', '-f']
    if delete_from_disk:
        command.append('-d')
    command.append(f'id:{beet_id}')

    print(f"Executing: {' '.join(command)}")
    try:
        subprocess.run(command, capture_output=True, text=True, check=True)
        return jsonify({'message': 'Track deleted from disk.' if delete_from_disk else 'Track removed from library.'})
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}")
        return jsonify({'error': e.stderr}), 500


@app.route('/api/library/remove', methods=['POST'])
def remove_track():
    data = request.json or {}
    track_id = data.get('id')
    if track_id in (None, ''):
        return jsonify({'error': 'Missing track id.'}), 400
    return _remove_by_id(track_id, delete_from_disk=False)


@app.route('/api/library/delete', methods=['POST'])
def delete_track():
    data = request.json or {}
    print(f"Delete request received with data: {data}")
    track_id = data.get('id')
    if track_id in (None, ''):
        return jsonify({'error': 'Missing track id.'}), 400
    return _remove_by_id(track_id, delete_from_disk=True)




@app.route('/api/library/batch-update', methods=['POST'])
def batch_update():
    data = request.json or {}
    ids = data.get('ids', [])
    updates = data.get('updates', {})

    if not ids:
        return jsonify({'error': 'No tracks selected.'}), 400

    cleaned = {k: v.strip() for k, v in updates.items() if isinstance(v, str) and v.strip()}
    if not cleaned:
        return jsonify({'error': 'No fields to update.'}), 400

    # Beets query: `id:1 , id:2 , id:3` (comma as a separate arg = OR).
    query = []
    for i, track_id in enumerate(ids):
        if i > 0:
            query.append(',')
        try:
            query.append(f'id:{int(track_id)}')
        except (ValueError, TypeError):
            return jsonify({'error': f'Invalid track id: {track_id!r}'}), 400

    field_args = [f'{field}={value}' for field, value in cleaned.items()]
    command = ['beet', 'modify', '-y'] + query + field_args

    print(f'Executing batch modify: {command}')
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        return jsonify({'error': result.stderr}), 500
    return jsonify({'message': f'Updated {len(ids)} track(s).'})


@app.route('/api/library/update', methods=['POST'])
def update_track():
    data = request.json
    if not data:
        return jsonify({'error': 'Missing JSON body.'}), 400
    if TYPE_CHECKING:
        assert isinstance(data, dict)
    original_title = data.get('originalTitle', '')
    original_artist = data.get('originalArtist', '')
    original_album = data.get('originalAlbum', '')
    updated_track = cast(dict, data.get('updatedTrack', {}))


    command = ['beet', 'modify', '-y', f'title:{original_title}', f'artist:{original_artist}', f'album:{original_album}']


    for field, value in updated_track.items():
        if value:
            command.append(f'{field}={value}')


    print(f"Executing command: {' '.join(command)}")


    result = subprocess.run(command, capture_output=True, text=True)


    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return jsonify({'error': result.stderr}), 500

    return jsonify({'message': 'Track updated successfully.'})


def parse_stats(output):
    """Parse the stats output from beets."""
    lines = output.splitlines()
    stats = {}
    for line in lines:
        if 'Tracks:' in line:
            stats['total_tracks'] = line.split(': ')[1]
        elif 'Albums:' in line:
            stats['total_albums'] = line.split(': ')[1]
        elif 'Artists:' in line:
            stats['total_artists'] = line.split(': ')[1]
        elif 'Total size:' in line:
            stats['total_size'] = line.split(': ')[1].split(' ')[0]
    return stats

# Read port from environment variable, defaulting to 3000 if not set
port = int(os.getenv("FLASK_PORT", 3000))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=port)
