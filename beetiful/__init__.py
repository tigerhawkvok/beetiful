from flask import Flask, jsonify, request, render_template, send_file
import os
import mimetypes
import subprocess


app = Flask(__name__)

beets_config_dir = os.getenv('BEETSDIR', os.path.expanduser('~/.config/beets'))
config_path = os.path.join(beets_config_dir, 'config.yaml')


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
# Use ASCII Unit Separator between fields and Record Separator between records so embedded
# newlines in fields like $comments don't fracture rows.
FIELD_SEP = '\x1f'
RECORD_SEP = '\x1e'
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
    original_title = data.get('originalTitle', '')
    original_artist = data.get('originalArtist', '')
    original_album = data.get('originalAlbum', '')
    updated_track = data.get('updatedTrack', {})

    
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

