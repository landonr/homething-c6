"""Persistent solid cache, so an unchanged model reloads instead of rebuilding.

Every cached builder is a pure function of a fixed set of files: the geometry
under model/, the parameters, the board readers, the legend fonts and glyphs,
and the four KiCad exports board.py reads. Those files are hashed by content
into one key, and the key names a directory under .cache holding a BREP blob
per builder plus the manifest of what was hashed. Any byte change anywhere in
that set gives a new key, so the whole cache is missed at once. One global key
rather than a dependency graph per builder: nothing here is expensive enough to
be worth tracking which module feeds which shape, and a graph that is subtly
wrong caches a stale solid, which makes every check that probes it vacuous.

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
from pathlib import Path

from build123d import export_brep, export_stl, import_brep

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"


def enabled():
    return not os.environ.get("CASE_NO_CACHE")


def _sources():
    """Every file whose bytes can change what a cached builder returns."""
    import board

    paths = [HERE / "params.py", HERE / "board.py"]
    paths += sorted((HERE / "model").glob("*.py"))
    for directory in (HERE / "fonts", HERE / "glyphs"):
        paths += sorted(p for p in directory.rglob("*") if p.is_file())
    paths += [board.KICAD_PCB, board.POS_CSV, board.BOARD_ONLY_STEP, board.ASSEMBLY_STEP]
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


@functools.cache
def _dir():
    return CACHE / key()


@functools.cache
def _open_for_write():
    """The blob directory, created, with its manifest written and every other
    key's directory dropped."""
    target = _dir()
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text(
        json.dumps({"key": key(), "files": manifest()}, indent=2, sort_keys=True) + "\n"
    )
    for stale in CACHE.iterdir():
        if stale.is_dir() and stale != target:
            shutil.rmtree(stale, ignore_errors=True)
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
        partial = _open_for_write() / f"{name}.brep.partial"
        export_brep(shape, partial)
        partial.replace(blob)
        return shape

    return wrapped


def export_stl_cached(shape, dest):
    """Write dest, from the cached bytes if this shape has been meshed before."""
    dest = Path(dest)
    if not enabled():
        export_stl(shape, str(dest))
        return
    blob = _dir() / dest.name
    if blob.exists():
        shutil.copyfile(blob, dest)
        return
    export_stl(shape, str(dest))
    _open_for_write()
    shutil.copyfile(dest, blob)
