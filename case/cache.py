"""Persistent solid cache, so an unchanged model reloads instead of rebuilding.

Every cached builder is a pure function of a fixed set of files: the geometry
under model/, the parameters, the board readers, the legend fonts and glyphs,
and the board files board.py reads, frozen V2 ones included. Those files are
hashed by content into one key, and the key names a directory under .cache
holding a BREP blob per builder plus the manifest of what was hashed. Any byte
change anywhere in that set gives a new key, so the whole cache is missed at
once. One global key rather than a dependency graph per builder: nothing here
is expensive enough to be worth tracking which module feeds which shape, and a
graph that is subtly wrong caches a stale solid, which makes every check that
probes it vacuous.

A key directory outlives the run that wrote it. The key is a content hash of
every input, so an old directory cannot hold a stale solid: the bytes that built
it are the bytes that name it. Keeping a few therefore costs disk and nothing
else, and it buys back the loop this model is actually edited in. A parameter
that is tried and then reverted used to cost two full rebuilds, because the run
that tried it deleted the directory the revert needed.

STL bytes are cached beside the BREPs because a BREP round trip does not
reproduce them: the geometry is identical to the last digit but the tessellation
is not, so a warm run copies the STL it wrote cold rather than re-meshing.

`CASE_NO_CACHE=1` bypasses both read and write.
"""

import functools
import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path

from build123d import export_brep, export_stl, import_brep

import params

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"

STL_TOLERANCE = 0.01
STL_ANGULAR_TOLERANCE = 0.05
"""Mesh settings for every exported STL. The build123d default linear tolerance
of 0.001 scatters points across the long ruled faces of the back's loft. Their
normals then tilt enough to show as a row of bright facets."""

CACHE_KEEP = 4
"""How many key directories to keep, the live one included.

A key holds every solid for one state of the model, so the budget is disk, not
risk. CASE_CACHE_KEEP overrides it. Set it to 1 to keep only the live key.
"""

USED = "last-used"
"""Marker whose mtime is when a run last opened this key directory.

Recency must follow reads and not only writes. The directory a revert wants is
one that nothing has written to for a while, so a ranking by write time would
evict the very key the next revert asks for.
"""


def enabled():
    return not os.environ.get("CASE_NO_CACHE")


def _parallel():
    """True when independent check workers can write this cache key."""
    return bool(os.environ.get("CASE_CACHE_PARALLEL"))


def _partial(path):
    """A process-unique adjacent temporary path for an atomic cache write."""
    return path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.partial")


def _write_bytes(path, data):
    partial = _partial(path)
    partial.write_bytes(data)
    partial.replace(path)


def _sources():
    """Every file whose bytes can change what a cached builder returns."""
    import board

    paths = [HERE / "params.py", HERE / "board.py", HERE / "cache.py"]
    paths += sorted((HERE / "model").glob("*.py"))
    for directory in (HERE / "fonts", HERE / "glyphs"):
        paths += sorted(p for p in directory.rglob("*") if p.is_file())
    paths += [
        board.KICAD_PCB,
        board.POS_CSV,
        board.BOARD_ONLY_STEP,
        board.ASSEMBLY_STEP,
        board.LEGACY_BOARD_ONLY_STEP,
        board.LEGACY_POS_CSV,
    ]
    return paths


@functools.cache
def manifest():
    """{path: sha256} over _sources(), paths relative to the repo root.

    Content hashes, not mtimes: a checkout, a stash pop or a regenerated export
    all move an mtime without moving the geometry, and the reverse (a rewritten
    file keeping its mtime) is what makes an mtime cache silently stale.
    """
    root = HERE.parent
    out = {}
    for path in _sources():
        name = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        out[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""
    return out


@functools.cache
def key():
    digest = hashlib.sha256()
    for name, file_hash in sorted(manifest().items()):
        digest.update(f"{name}\0{file_hash}\0".encode())
    return digest.hexdigest()[:16]


def _keep():
    raw = os.environ.get("CASE_CACHE_KEEP")
    if raw is None:
        return CACHE_KEEP
    try:
        return max(1, int(raw))
    except ValueError:
        return CACHE_KEEP


def _touch(target):
    """Stamp a key directory as used by this run.

    Best effort: a cache that cannot record its recency must still serve blobs.
    """
    try:
        (target / USED).touch()
    except OSError:
        pass


def _last_used(directory):
    marker = directory / USED
    try:
        return (marker if marker.exists() else directory).stat().st_mtime
    except OSError:
        return 0.0


def _evict(target):
    """Remove all but the _keep() most recently used directories.

    `target` is always kept and always counts, so the budget is the number of
    directories on disk and not the number of spare ones.
    """
    others = sorted(
        (d for d in CACHE.iterdir() if d.is_dir() and d != target),
        key=_last_used,
        reverse=True,
    )
    for stale in others[_keep() - 1:]:
        shutil.rmtree(stale, ignore_errors=True)


@functools.cache
def _dir():
    target = CACHE / key()
    if target.is_dir():
        _touch(target)
    return target


@functools.cache
def _open_for_write():
    """The blob directory, created, with its manifest written.

    Serial callers evict down to the budget. Concurrent workers evict nothing,
    because another process can still read or write a directory they would take.
    """
    target = _dir()
    target.mkdir(parents=True, exist_ok=True)
    _write_bytes(
        target / "manifest.json",
        (json.dumps({"key": key(), "files": manifest()}, indent=2, sort_keys=True) + "\n").encode(),
    )
    _touch(target)
    if not _parallel():
        _evict(target)
    return target


def provenance():
    """One line saying where this run's geometry came from."""
    if not enabled():
        return "cache: disabled by CASE_NO_CACHE, building everything"
    blobs = sorted(_dir().glob("*.brep")) if _dir().is_dir() else []
    if not blobs:
        return f"cache: miss {key()}, building everything"
    return f"cache: hit {key()}, {len(blobs)} solids on disk"


def _blob_name(name, args, kwargs):
    fields = [name, *(str(a) for a in args), *(f"{k}{v}" for k, v in sorted(kwargs.items()))]
    return re.sub(r"[^A-Za-z0-9_.-]", "_", "-".join(fields))


def cached(builder, *args, **kwargs):
    """True when this builder's blob for these arguments is already on disk.

    provenance() answers "did this run find a cache at all", for a human to
    read at the top of a report. This answers "is this one shape already built",
    for a caller deciding whether building it itself is worth the wait. They are
    not the same question, and confusing them is expensive: a key directory
    holding one blob of thirty reads as a hit and is still very nearly a cold
    build.

    Read only. It hashes nothing, writes nothing and evicts nothing, it just
    asks after the blob `solid` would have looked for.
    """
    if not enabled():
        return False
    return (_dir() / f"{_blob_name(builder.__name__, args, kwargs)}.brep").exists()


def solid(builder):
    """Decorator: back a no-side-effect shape builder with a BREP blob.

    On a miss the freshly built shape is returned, not the blob just written, so
    a cold run never depends on the round trip.
    """

    @functools.wraps(builder)
    def wrapped(*args, **kwargs):
        if not enabled():
            return builder(*args, **kwargs)
        name = _blob_name(builder.__name__, args, kwargs)
        blob = _dir() / f"{name}.brep"
        if blob.exists():
            return import_brep(blob)
        shape = builder(*args, **kwargs)
        partial = _partial(_open_for_write() / f"{name}.brep")
        export_brep(shape, partial)
        partial.replace(blob)
        return shape

    return wrapped


def bytes_cached(name, build):
    """Return the bytes for `name`, calling `build()` only on a miss.

    For a file that is derived from the geometry but is not itself a solid, so
    the BREP blobs cannot stand in for it. The features export needs this: the
    builders it measures are almost all uncached, so a warm run that rebuilt
    them for their bounding boxes would cost as much as a cold one.
    """
    if not enabled():
        return build()
    blob = _dir() / name
    if blob.exists():
        return blob.read_bytes()
    data = build()
    _open_for_write()
    _write_bytes(blob, data)
    return data


def export_stl_cached(shape, dest):
    """Write dest, from the cached bytes if this shape has been meshed before."""
    dest = Path(dest)
    angular_tolerance = (
        params.BACK_STL_ANGULAR_TOLERANCE
        if dest.name in ("c6remote-case-back.stl", "c6remote-case-back-one-piece.stl")
        else STL_ANGULAR_TOLERANCE
    )
    if not enabled():
        export_stl(
            shape,
            str(dest),
            tolerance=STL_TOLERANCE,
            angular_tolerance=angular_tolerance,
        )
        return
    blob = _dir() / dest.name
    if blob.exists():
        shutil.copyfile(blob, dest)
        return
    export_stl(
        shape,
        str(dest),
        tolerance=STL_TOLERANCE,
        angular_tolerance=angular_tolerance,
    )
    _open_for_write()
    partial = _partial(blob)
    shutil.copyfile(dest, partial)
    partial.replace(blob)
