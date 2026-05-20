"""Resolve cover art for a track.

Priority: embedded art (this library embeds via beets' embedart with remove_art_file),
then a standalone cover file in the track's directory (the common fetchart layout for
users who don't embed). Returns (mimetype, bytes) or None.
"""

import base64
import io
import os

from mutagen import File as MutagenFile
from PIL import Image

# Standalone cover filenames, checked case-insensitively, in preference order.
_COVER_NAMES = ('cover', 'folder', 'front', 'album', 'albumart', 'art', 'thumb')
_COVER_EXTS = ('.jpg', '.jpeg', '.png', '.webp', '.gif')


def embedded_art(path):
    """Extract embedded art via mutagen. Returns (mime, bytes) or None."""
    try:
        f = MutagenFile(path)
    except Exception:
        return None
    if f is None:
        return None

    # FLAC (and some Opus) expose parsed picture blocks directly.
    pics = getattr(f, 'pictures', None)
    if pics:
        return (pics[0].mime or 'image/jpeg', pics[0].data)

    tags = getattr(f, 'tags', None)
    if not tags:
        return None

    # MP4 / M4A / AAC
    if 'covr' in tags:
        try:
            import mutagen.mp4
            cov = tags['covr'][0]
            mime = 'image/png' if cov.imageformat == mutagen.mp4.MP4Cover.FORMAT_PNG else 'image/jpeg'
            return (mime, bytes(cov))
        except Exception:
            pass

    # ID3 APIC (MP3)
    try:
        for key in tags.keys():
            if key.startswith('APIC'):
                apic = tags[key]
                return (apic.mime or 'image/jpeg', apic.data)
    except Exception:
        pass

    # Vorbis/Opus base64 METADATA_BLOCK_PICTURE
    try:
        if 'metadata_block_picture' in tags:
            from mutagen.flac import Picture
            pic = Picture(base64.b64decode(tags['metadata_block_picture'][0]))
            return (pic.mime or 'image/jpeg', pic.data)
    except Exception:
        pass

    return None


def thumbnail(data, size, quality=80):
    """Downscale raw image bytes to fit a size×size box, re-encoded as WebP.

    Returns (mime, bytes), or None if the bytes can't be decoded (caller should then
    fall back to serving the original).
    """
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    if img.mode == 'P':
        img = img.convert('RGBA')
    elif img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')
    img.thumbnail((size, size))
    buf = io.BytesIO()
    try:
        img.save(buf, 'WEBP', quality=quality, method=4)
    except Exception:
        return None
    return ('image/webp', buf.getvalue())


def cover_file(path):
    """Find a standalone cover image alongside the track. Returns a filepath or None."""
    directory = os.path.dirname(path)
    try:
        entries = {e.lower(): e for e in os.listdir(directory)}
    except OSError:
        return None
    for name in _COVER_NAMES:
        for ext in _COVER_EXTS:
            actual = entries.get(name + ext)
            if actual:
                return os.path.join(directory, actual)
    return None
