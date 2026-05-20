"""Build an isolated mock beets library for tests.

Generates tiny silent audio files (various codecs) with real tags and embedded art,
imports them into a throwaway beets library, and sets up deliberate duplicate scenarios
covering every tier and feature the app exercises:

  - probable      : same title/artist/album, near-equal length (mp3 + flac)
  - possible      : fuzzy title ("Beta Song" / "Beta Song (Live)"), length within 10%
  - definite/aid  : same acoustid_id across codecs (mp3 + flac) -> keep should be flac
  - titles_diverge: same acoustid_id, genuinely different titles (rename target)
  - missing field : same acoustid_id, one has album/genre/etc, one doesn't (copy-fields)
  - definite/hash : byte-identical copies (after a content-hash scan)
  - solo          : a unique track with no art (negative art test)

Run standalone to materialize a library and print its BEETSDIR:
    python -m tests.seed /tmp/mocklib
"""

import base64
import io
import os
import shutil
import subprocess
import sys

from PIL import Image

_ENC = {
    'mp3': ['-c:a', 'libmp3lame', '-b:a', '128k'],
    'flac': ['-c:a', 'flac'],
    'opus': ['-c:a', 'libopus', '-b:a', '96k'],
    'm4a': ['-c:a', 'aac', '-b:a', '128k'],
}


def _png(w, h, color):
    buf = io.BytesIO()
    Image.new('RGB', (w, h), color).save(buf, 'PNG')
    return buf.getvalue()


def _make_audio(path, fmt, dur, meta):
    args = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', str(dur)]
    args += _ENC[fmt]
    for key, val in meta.items():
        if val:
            args += ['-metadata', f'{key}={val}']
    args.append(path)
    subprocess.run(args, capture_output=True, text=True, check=True)


def _embed_art(path, fmt, img):
    if fmt == 'mp3':
        from mutagen.id3 import ID3, APIC, ID3NoHeaderError
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()
        tags.add(APIC(encoding=3, mime='image/png', type=3, desc='Cover', data=img))
        tags.save(path)
    elif fmt == 'flac':
        from mutagen.flac import FLAC, Picture
        f = FLAC(path)
        pic = Picture()
        pic.type, pic.mime, pic.data = 3, 'image/png', img
        f.add_picture(pic)
        f.save()
    elif fmt == 'opus':
        from mutagen.oggopus import OggOpus
        from mutagen.flac import Picture
        f = OggOpus(path)
        pic = Picture()
        pic.type, pic.mime, pic.data = 3, 'image/png', img
        f['metadata_block_picture'] = [base64.b64encode(pic.write()).decode('ascii')]
        f.save()
    elif fmt == 'm4a':
        from mutagen.mp4 import MP4, MP4Cover
        f = MP4(path)
        f['covr'] = [MP4Cover(img, imageformat=MP4Cover.FORMAT_PNG)]
        f.save()


# Each spec: filename, format, duration, metadata, optional art (w, h, color),
# optional acoustid id, optional hash-twin filename to byte-copy.
_RED, _BLUE = (200, 30, 30), (30, 90, 200)
SPECS = [
    # probable (mp3 + flac, same tags) -> keep = flac
    dict(f='alpha_1.mp3', fmt='mp3', dur=3.0, art=(300, 300, _RED),
         m=dict(title='Alpha', artist='Artist One', album='Album One', genre='Rock', date='2001', composer='Composer A')),
    dict(f='alpha_2.flac', fmt='flac', dur=3.0, art=(300, 300, _RED),
         m=dict(title='Alpha', artist='Artist One', album='Album One', genre='Rock', date='2001', composer='Composer A')),

    # possible (fuzzy title, similar length, no art)
    dict(f='beta_1.mp3', fmt='mp3', dur=3.0,
         m=dict(title='Beta Song', artist='Artist Two', album='Album Two')),
    dict(f='beta_2.mp3', fmt='mp3', dur=3.2,
         m=dict(title='Beta Song (Live)', artist='Artist Two', album='Live Album')),

    # definite via acoustid, cross-codec -> keep = flac
    dict(f='gamma.mp3', fmt='mp3', dur=4.0, art=(512, 512, _BLUE), acoust='gamma-uuid',
         m=dict(title='Gamma', artist='Artist Three', album='Album Three')),
    dict(f='gamma.flac', fmt='flac', dur=4.0, art=(512, 512, _BLUE), acoust='gamma-uuid',
         m=dict(title='Gamma', artist='Artist Three', album='Album Three')),

    # titles diverge (same acoustid, different titles)
    dict(f='div_a.mp3', fmt='mp3', dur=5.0, acoust='div-uuid',
         m=dict(title='Divergent Title A', artist='Artist Four', album='Album Four')),
    dict(f='div_b.mp3', fmt='mp3', dur=5.0, acoust='div-uuid',
         m=dict(title='Completely Other Name', artist='Artist Four', album='Album Four')),

    # missing fields (same acoustid; one fully tagged, one bare) -> copy-fields
    dict(f='miss_has.mp3', fmt='mp3', dur=2.5, acoust='miss-uuid',
         m=dict(title='Missing Album Test', artist='Artist Five', album='Soundtrack Five', genre='Score', date='2010', composer='Composer E')),
    dict(f='miss_no.m4a', fmt='m4a', dur=2.5, acoust='miss-uuid',
         m=dict(title='Missing Album Test', artist='Artist Five')),

    # definite via byte-identical hash twin (after a content scan)
    dict(f='hash_a.opus', fmt='opus', dur=3.5, art=(256, 256, _RED), hashtwin='hash_b.opus',
         m=dict(title='Hash Twin', artist='Artist Six', album='Album Six')),

    # solo unique, no art (negative art test)
    dict(f='solo.mp3', fmt='mp3', dur=6.0,
         m=dict(title='Solo Unique', artist='Artist Seven', album='Album Seven')),
]


def build(base):
    """Materialize the mock library under `base`. Returns the BEETSDIR path."""
    beetsdir = os.path.join(base, 'beets')
    music = os.path.join(base, 'music')
    os.makedirs(beetsdir, exist_ok=True)
    os.makedirs(music, exist_ok=True)

    with open(os.path.join(beetsdir, 'config.yaml'), 'w') as fh:
        fh.write(
            f"directory: {music}\n"
            f"library: {os.path.join(beetsdir, 'library.db')}\n"
            "import:\n"
            "  copy: no\n"
            "  move: no\n"
            "  write: no\n"
            "  autotag: no\n"
            "  quiet: yes\n"
            "  singletons: yes\n"
            "plugins: []\n"
        )

    env = dict(os.environ, BEETSDIR=beetsdir)

    for spec in SPECS:
        path = os.path.join(music, spec['f'])
        _make_audio(path, spec['fmt'], spec['dur'], spec['m'])
        if spec.get('art'):
            _embed_art(path, spec['fmt'], _png(*spec['art']))
        if spec.get('hashtwin'):
            shutil.copyfile(path, os.path.join(music, spec['hashtwin']))

    subprocess.run(['beet', 'import', music], capture_output=True, text=True, env=env, check=True)

    # Apply acoustid ids (flexattr) by title.
    for spec in SPECS:
        if spec.get('acoust'):
            subprocess.run(
                ['beet', 'modify', '-y', f"title:{spec['m']['title']}", f"acoustid_id={spec['acoust']}"],
                capture_output=True, text=True, env=env, check=True,
            )

    return beetsdir


def _main():
    base = sys.argv[1] if len(sys.argv) > 1 else '/tmp/beetiful-mocklib'
    if os.path.exists(base):
        shutil.rmtree(base)
    beetsdir = build(base)
    print(beetsdir)


if __name__ == '__main__':
    _main()
