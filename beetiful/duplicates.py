"""Duplicate detection for the Beetiful library.

Tiers, weakest-binding first to strongest:
  - possible: fuzzy title+artist (rapidfuzz) and length within a wide tolerance.
  - probable: same normalized title+artist AND (close length OR same album).
  - definite: identical content hash (NOT YET IMPLEMENTED — see note below).

Extensibility: every tier is a `Detector.find(items) -> list[Cluster]`. Items are plain
dicts (already fetched from beets), optionally carrying precomputed signatures such as a
file/stream hash or acoustic fingerprint. Adding the definite tier — including the planned
cross-codec stream-hash / chroma fingerprint matching — means writing a new Detector that
reads `item['<signature>']` plus a scan job that fills that signature; nothing here changes.
"""

import re
import unicodedata

from rapidfuzz import fuzz

# --- tunables -------------------------------------------------------------
PROBABLE_LENGTH_TOL_S = 2              # seconds; "same length" for the probable tier
PROBABLE_ALBUM_LENGTH_TOL_FRAC = 0.15  # album-match still requires lengths within this
POSSIBLE_LENGTH_TOL_FRAC = 0.10        # 10%; length window for the possible tier
POSSIBLE_TITLE_THRESHOLD = 86          # rapidfuzz score (0-100)
POSSIBLE_ARTIST_THRESHOLD = 86
BLOCK_PREFIX_LEN = 4                   # block possible-tier comparisons by this many chars

# Parentheticals / suffixes stripped only by the *loose* normalization used for the
# possible (fuzzy) tier, so "foobar", "foobar (live)", "foobar - remastered" collapse.
# The probable tier deliberately keeps them: "Theme" and "Theme (vocal version)" are
# different tracks and must not be merged.
_PAREN_RE = re.compile(r"[\(\[\{].*?[\)\]\}]")
_FEAT_RE = re.compile(r"\b(feat|ft|featuring|with)\b.*", re.IGNORECASE)
_DASH_SUFFIX_RE = re.compile(r"\s-\s.*$")
_NONALNUM_RE = re.compile(r"[^a-z0-9]+")


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def _normalize_core(s: str) -> str:
    """Strict: lowercase, de-accent, punctuation→space, collapse. Keeps parentheticals."""
    s = _strip_accents((s or "").lower())
    s = _NONALNUM_RE.sub(" ", s)
    return " ".join(s.split())


def _normalize_loose(s: str) -> str:
    """Loose: also drop parentheticals, feat. clauses, and ' - suffix' tails."""
    s = _strip_accents((s or "").lower())
    s = _PAREN_RE.sub(" ", s)
    s = _DASH_SUFFIX_RE.sub(" ", s)
    s = _FEAT_RE.sub(" ", s)
    s = _NONALNUM_RE.sub(" ", s)
    return " ".join(s.split())


# Probable tier (strict).
def normalize_title(s: str) -> str:
    return _normalize_core(s)


def normalize_artist(s: str) -> str:
    return _normalize_core(s)


# Possible tier (loose / fuzzy).
def normalize_title_loose(s: str) -> str:
    return _normalize_loose(s)


def normalize_artist_loose(s: str) -> str:
    return _normalize_loose(s)


def _probable_match(a: dict, b: dict) -> bool:
    """Same (already-equal) strict title+artist; decide using length and album.

    - lengths within PROBABLE_LENGTH_TOL_S  -> yes
    - same album AND lengths within PROBABLE_ALBUM_LENGTH_TOL_FRAC -> yes
    - a length is missing -> fall back to same-album
    """
    la, lb = a.get("length_s"), b.get("length_s")
    same_album = bool(a.get("album")) and a.get("album") == b.get("album")
    if la is not None and lb is not None:
        delta = abs(la - lb)
        if delta <= PROBABLE_LENGTH_TOL_S:
            return True
        longer = max(la, lb) or 1
        return same_album and delta / longer <= PROBABLE_ALBUM_LENGTH_TOL_FRAC
    return same_album


# --- result model ---------------------------------------------------------
class Cluster:
    def __init__(self, tier, reason, member_ids):
        self.tier = tier
        self.reason = reason
        self.member_ids = list(member_ids)

    def as_dict(self):
        return {"tier": self.tier, "reason": self.reason, "members": self.member_ids}


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)

    def groups(self):
        out = {}
        for x in list(self.parent):
            out.setdefault(self.find(x), []).append(x)
        return [v for v in out.values() if len(v) > 1]


# --- detectors ------------------------------------------------------------
class Detector:
    tier = ""

    def find(self, items):
        raise NotImplementedError


class DefiniteDetector(Detector):
    """Identical content: same file hash (sha256) or same AcoustID recording id.

    Items may carry `content_hash` (from the sidecar scan cache) and/or `acoustid_id`
    (read from beets). Either is sufficient to call a pair a definite duplicate; the two
    relations are merged so a file-identical pair and an AcoustID-identical pair that
    share a member land in one cluster.
    """

    tier = "definite"

    def find(self, items):
        by_id = {it["id"]: it for it in items}
        uf = _UnionFind()
        for key_field in ("content_hash", "acoustid_id"):
            groups = {}
            for it in items:
                val = it.get(key_field)
                if val:
                    groups.setdefault(val, []).append(it["id"])
            for ids in groups.values():
                for other in ids[1:]:
                    uf.union(ids[0], other)

        clusters = []
        for member_ids in uf.groups():
            hashes = {by_id[m].get("content_hash") for m in member_ids if by_id[m].get("content_hash")}
            aids = {by_id[m].get("acoustid_id") for m in member_ids if by_id[m].get("acoustid_id")}
            if len(hashes) == 1 and all(by_id[m].get("content_hash") for m in member_ids):
                reason = "identical file (sha256)"
            elif len(aids) == 1 and all(by_id[m].get("acoustid_id") for m in member_ids):
                reason = "same recording (AcoustID)"
            else:
                reason = "identical content (file / recording)"
            clusters.append(Cluster(self.tier, reason, member_ids))
        return clusters


class ProbableDetector(Detector):
    """Same normalized title+artist, and either near-equal length or same album."""

    tier = "probable"

    def __init__(self, suppress_pairs=None):
        self.suppress_pairs = suppress_pairs or set()

    def find(self, items):
        buckets = {}
        for it in items:
            key = (normalize_title(it.get("title", "")), normalize_artist(it.get("artist", "")))
            if not key[0] or not key[1]:
                continue
            buckets.setdefault(key, []).append(it)

        clusters = []
        for (ntitle, _nartist), group in buckets.items():
            if len(group) < 2:
                continue
            uf = _UnionFind()
            for i in range(len(group)):
                uf.find(group[i]["id"])
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if frozenset((a["id"], b["id"])) in self.suppress_pairs:
                        continue
                    if _probable_match(a, b):
                        uf.union(a["id"], b["id"])
            for member_ids in uf.groups():
                clusters.append(Cluster(self.tier, f'title/artist match: "{ntitle}"', member_ids))
        return clusters


class PossibleDetector(Detector):
    """Fuzzy title+artist with a wide length window. Blocked to stay sub-quadratic."""

    tier = "possible"

    def __init__(self, suppress_pairs=None):
        # Pairs (frozenset of two ids) already explained by a stronger tier.
        self.suppress_pairs = suppress_pairs or set()

    def find(self, items):
        blocks = {}
        for it in items:
            nartist = normalize_artist_loose(it.get("artist", ""))
            ntitle = normalize_title_loose(it.get("title", ""))
            if not nartist or not ntitle:
                continue
            it["_nartist"], it["_ntitle"] = nartist, ntitle
            blocks.setdefault(nartist[:BLOCK_PREFIX_LEN], []).append(it)

        uf = _UnionFind()
        reasons = {}
        for group in blocks.values():
            for i in range(len(group)):
                uf.find(group[i]["id"])
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    if frozenset((a["id"], b["id"])) in self.suppress_pairs:
                        continue
                    if not self._length_ok(a, b):
                        continue
                    t = fuzz.token_sort_ratio(a["_ntitle"], b["_ntitle"])
                    ar = fuzz.token_sort_ratio(a["_nartist"], b["_nartist"])
                    if t >= POSSIBLE_TITLE_THRESHOLD and ar >= POSSIBLE_ARTIST_THRESHOLD:
                        uf.union(a["id"], b["id"])
                        reasons[uf.find(a["id"])] = f"~{int(min(t, ar))}% title/artist similarity"

        clusters = []
        for member_ids in uf.groups():
            root = uf.find(member_ids[0])
            clusters.append(Cluster(self.tier, reasons.get(root, "fuzzy match"), member_ids))
        return clusters

    @staticmethod
    def _length_ok(a, b):
        la, lb = a.get("length_s"), b.get("length_s")
        if la is None or lb is None:
            return True  # don't reject on missing length; metadata still gates it
        longer = max(la, lb)
        return longer == 0 or abs(la - lb) / longer <= POSSIBLE_LENGTH_TOL_FRAC


def titles_diverge(titles, threshold=POSSIBLE_TITLE_THRESHOLD):
    """True if the cluster's titles aren't all close — e.g. an AcoustID match whose
    members are tagged with genuinely different titles (one is likely mistagged)."""
    norm = [normalize_title_loose(t) for t in titles]
    norm = [n for n in norm if n]
    for i in range(len(norm)):
        for j in range(i + 1, len(norm)):
            if fuzz.token_sort_ratio(norm[i], norm[j]) < threshold:
                return True
    return False


def find_duplicates(items, tiers=("definite", "probable", "possible")):
    """Run the requested tiers and return clusters, strongest tier first.

    A pair already grouped by a stronger tier is suppressed from weaker ones so the
    same two tracks aren't reported twice.
    """
    results = []
    claimed_pairs = set()

    def claim(cluster):
        ids = cluster.member_ids
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                claimed_pairs.add(frozenset((ids[i], ids[j])))

    if "definite" in tiers:
        for cl in DefiniteDetector().find(items):
            results.append(cl)
            claim(cl)

    if "probable" in tiers:
        for cl in ProbableDetector(suppress_pairs=claimed_pairs).find(items):
            results.append(cl)
            claim(cl)

    if "possible" in tiers:
        results.extend(PossibleDetector(suppress_pairs=claimed_pairs).find(items))

    return results
