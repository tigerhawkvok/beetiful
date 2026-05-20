# Tests

Route/integration tests that run the Flask app against an **isolated, generated mock beets
library** — no contact with your real library (a throwaway `BEETSDIR` and hash-cache are
used).

## What's covered

[`seed.py`](seed.py) generates tiny silent audio files (MP3/FLAC/Opus/M4A) with real tags
and embedded cover art, imports them into a temp beets library, and stages every duplicate
scenario:

| Scenario | Tracks | Exercises |
| --- | --- | --- |
| probable | Alpha (mp3 + flac) | same title/artist/album, near length; codec-rank keep |
| possible | Beta Song / Beta Song (Live) | fuzzy title + length window |
| definite (AcoustID) | Gamma (mp3 + flac) | cross-codec match; keep = FLAC |
| titles diverge | Divergent Title A / Completely Other Name | rename affordance |
| missing fields | Missing Album Test (tagged + bare) | copy-to-missing |
| definite (hash) | Hash Twin (byte-identical opus) | content-hash scan |
| solo | Solo Unique (no art) | negative art (404) |

[`test_routes.py`](test_routes.py) hits every endpoint: pages, `stats`, `library`,
`run-command`, `config` (round-trip), `duplicates` (all tiers + `titles_diverge`),
the hash `scan` + status, `art` (thumbnail / full / 404), `audio`, and the mutating
routes `rename`, `copy-fields`, `batch-update`, `remove`, `delete`.

## Running

**Locally** (needs `ffmpeg`, `beet`, and `fpcalc` on PATH):

```bash
uv run pytest tests/ -q
```

**In Docker** (self-contained — installs ffmpeg/beets, seeds, runs):

```bash
./tests/run-tests.sh
# or directly:
docker compose -f docker-compose.test.yml run --rm test
```

`run-tests.sh` uses Docker when available and otherwise falls back to a local run.
