"""Pytest fixtures: build an isolated mock beets library and a Flask test client.

The app reads BEETSDIR at import and shells out to `beet` for everything else, so we set
BEETSDIR (and an isolated hash-cache path) before importing the app. The cache path is set
at module load — before any test imports the app — so the real repo cache is never touched.
"""

import importlib
import os
import shutil
import tempfile

import pytest

# Must be set before `beetiful`/`hashscan` import so the scan writes to a throwaway cache.
_CACHE_DIR = tempfile.mkdtemp(prefix='beetiful-cache-')
os.environ['BEETIFUL_HASHCACHE'] = os.path.join(_CACHE_DIR, 'hashcache.sqlite')

from tests import seed  # noqa: E402


@pytest.fixture(scope='session')
def beetsdir():
    base = tempfile.mkdtemp(prefix='beetiful-test-')
    bd = seed.build(base)
    os.environ['BEETSDIR'] = bd
    yield bd
    shutil.rmtree(base, ignore_errors=True)
    shutil.rmtree(_CACHE_DIR, ignore_errors=True)


@pytest.fixture(scope='session')
def app(beetsdir):
    import beetiful
    importlib.reload(beetiful)  # rebind config_path now that BEETSDIR is set
    beetiful.app.config.update(TESTING=True)
    return beetiful.app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(scope='session')
def library(app):
    """Map of title -> track dict, from /api/library, for looking up ids in tests."""
    resp = app.test_client().get('/api/library')
    return {item['title']: item for item in resp.get_json()['items']}
