"""Remember what each pass decided, so an unchanged pass is not run twice.

A verdict is a pure function of two things: the solids the pass probes, which
cache.key() already hashes out of params.py, model/, board.py and the board
files, and the code that does the probing, which nothing hashed before. Hash
that second half too and the pair names the verdict. A run that moves neither
replays the last answer instead of spending the CPU again, which matters here
because the suite is a little over two hours of CPU and the common reason to
start it is an edit somewhere else entirely.

One key over the whole checks package, not a dependency graph per pass, for the
reason cache.py keeps one key over the whole model: a graph that is subtly wrong
serves a stale verdict, and a stale verdict is worse than a stale solid. The
next pass to probe a stale solid usually trips over it. A stale verdict is the
answer itself, and it reads green while describing the case the model used to
be. So an edit anywhere under checks/, or to check.py or case.py, misses every
entry at once. That bluntness is the point: being wrong here buys a pass that
has quietly stopped testing anything.

A pass that raised is never stored. A crash is as often the environment as the
geometry, a missing trimesh or an unlinked 3D model, and freezing one would
outlive the fix. Only a pass that ran to a verdict has decided anything.

`CASE_NO_CACHE=1` bypasses this with the solids. `--recheck` is the narrower
tool: it keeps the solids warm and runs every pass again, which is what to reach
for when a pass is wrong about something neither key covers.
"""

import functools
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

import cache

HERE = Path(__file__).resolve().parent
CASE = HERE.parent

STORED = ("feature", "name", "passed", "output", "elapsed", "problems")
"""The fields of a record that survive the trip. `crashed` is deliberately not
among them, because a record that carries it is never written."""

_FORCE = False


def force():
    """Run every pass again this run, and still store what they decide."""
    global _FORCE
    _FORCE = True


def reading():
    """True when a stored verdict may stand in for running the pass."""
    return cache.enabled() and not _FORCE


def _sources():
    """Every file whose bytes can change a verdict without moving a solid."""
    paths = sorted(HERE.glob("*.py"))
    paths += [CASE / "check.py", CASE / "case.py"]
    return [path for path in paths if path.exists()]


@functools.cache
def key():
    digest = hashlib.sha256()
    for path in _sources():
        digest.update(f"{path.relative_to(CASE)}\0".encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()[:16]


@functools.cache
def _dir():
    return cache.CACHE / cache.key() / "verdicts" / key()


@functools.cache
def _open_for_write():
    """The verdict directory, created, and clear of the keys it replaces.

    Nested under the solid key so that cache.py evicting a stale solid key takes
    the verdicts measured against it along. Within one solid key the checks can
    still move, so the sibling sweep here is the other half of the same job.
    Concurrent workers keep their siblings for the reason cache.py does: another
    process can still be reading or writing one.
    """
    target = _dir()
    target.mkdir(parents=True, exist_ok=True)
    if not os.environ.get("CASE_CACHE_PARALLEL"):
        for stale in target.parent.iterdir():
            if stale.is_dir() and stale != target:
                shutil.rmtree(stale, ignore_errors=True)
    return target


def _path(feature, name):
    return _dir() / f"{feature}.{name}.json"


def load(feature, name):
    """The stored record for this pass, or None if there is not a sound one."""
    if not reading():
        return None
    try:
        record = json.loads(_path(feature, name).read_bytes())
    except (OSError, ValueError):
        return None
    if not all(field in record for field in STORED):
        return None
    record["cached"] = True
    return record


def store(record):
    """Keep a verdict, unless the pass crashed rather than decided."""
    if not cache.enabled() or record.get("crashed"):
        return
    path = _open_for_write() / f"{record['feature']}.{record['name']}.json"
    payload = json.dumps({field: record[field] for field in STORED}, indent=1)
    partial = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.partial")
    partial.write_bytes((payload + "\n").encode())
    partial.replace(path)


def provenance(hits, total):
    """One line saying how much of this run the stored verdicts answered."""
    if not cache.enabled():
        return "verdicts: disabled by CASE_NO_CACHE, running every pass"
    if _FORCE:
        return f"verdicts: --recheck, running all {total} passes again"
    if not hits:
        return f"verdicts: miss {key()}, running all {total} passes"
    return f"verdicts: hit {key()}, {hits} of {total} passes replayed"
