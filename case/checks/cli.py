"""Run every pass in order and print one line each.

check.py is the entry point that calls main() here. The order is the report,
so a new pass goes where its subject belongs rather than at the end.

Every pass carries the name of the checks module it lives in, and `--only`
takes a comma list of those names. Scoping is worth having because the solids
are built on demand: an ir-only run never touches the pad or the keycap
legends, so it skips the build a full run pays for. A pass whose subject is the
whole assembly rather than one feature is tagged `assembly` instead, so scoping
one side of it never runs it half blind.

`--jobs N` spreads the passes themselves across N processes rather than the
features. The features are wildly uneven, one of them being better than a third
of the suite on its own, so feature-sized units of work leave most of the pool
idle within seconds and put a floor under the wall clock at whatever the slowest
single feature costs. Pass-sized units have no such floor, which also means a
larger --jobs is worth asking for than it used to be.

Passes then finish in whatever order they finish, and each one says so the
moment it does. The report proper is replayed afterwards in registry order, so
what a run prints as its verdict never depends on how the work happened to land
across the pool; only the progress lines are in completion order, and nothing
reads those back.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import functools
import io
import json
import multiprocessing
import os
import sys
import time
import traceback

import board
import cache
import case
import params

from .apertures import probe_apertures
from .common import Problem
from .caps import (
    cap_fits_around_perimeter,
    caps_fit,
    caps_flush,
    caps_proud_of_pocket,
    legends_present,
)
from .fdm import (
    ceilings_hold,
    edge_round_is_hard,
    face_is_flat,
    outline_is_cut,
    outline_solid_sane,
)
from .hardware import cell_clearance, feature_clashes
from .ir import (
    end_ports_open,
    receiver_clearance,
    receiver_paths,
    window_installation,
)
from .legacy import (
    legacy_pilot_blind,
    legacy_point_in_frame,
    legacy_post_clearance,
    legacy_post_headroom,
    legacy_post_merged,
)
from .keypad import (
    mic_pad_contour,
    neck_blends_smoothly,
    neck_continuity,
    pad_clears_wheel,
    pad_fits,
    plunger_stub_contact,
    recess_edge_clearance,
    recess_land,
    recess_margins,
    recess_solid_sane,
    recesses_open,
    wheel_basin_shape,
)
from .mic import mic_fillet
from .shells import interference, parts_are_sound, shells_mate
from .support import (
    support_board_clearance,
    support_case_containment,
    support_cell_clearance,
    support_flat_bearing,
    support_inner_round,
    support_min_run,
    support_part_clearance,
    support_printable,
    support_wall_merge,
)
from .usb import usb_pocket_clearance
from .wheel_ring import (
    led_ring,
    light_path,
    rotation_clearance,
    wheel_seat_clearance,
)


class Solids:
    """The shapes the passes probe, each built the first time one asks for it.

    Demand-driven rather than built up front so that `--only` is worth using on
    a cache miss, which is the state right after the edit that prompts a scoped
    run.
    """

    @functools.cached_property
    def front(self):
        return case.front_shell()

    @functools.cached_property
    def front_fdm(self):
        return case.front_shell(fdm=True)

    @functools.cached_property
    def back(self):
        return case.back_shell()

    @functools.cached_property
    def shells(self):
        return self.back + self.front

    @functools.cached_property
    def pad(self):
        return case.button_pad()

    @functools.cached_property
    def window(self):
        return case.ir_window()

    @functools.cached_property
    def caps(self):
        return {ref: case.keycap(ref) for ref in case.cap_refs()}


CHECKS = []

CHECKS_JSON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "export", "c6remote-checks.json")

_PENDING = []
"""The problems the pass now running has reported, drained by _run_pass().

A pass says where a failure is by appending a checks.common.Problem rather than
a bare string, and the printed report cannot carry that. This is where the
objects wait to be written to the JSON report, which is what the viewer draws
from. It is filled and drained inside one process, so a --jobs run keeps its own
per worker and only dicts ever cross a fork.
"""


def _check(feature):
    def register(fn):
        CHECKS.append((feature, fn))
        return fn

    return register


def _report(problems, passed):
    """Print a pass's problem lines, or its one-line all-clear, and say which."""
    if problems:
        _PENDING.extend(problems)
        for line in problems:
            print(f"  {line}")
        return False
    print(passed)
    return True


@_check("apertures")
def _apertures(s):
    blocked = probe_apertures(s.shells)
    if blocked:
        print(f"{len(blocked)} apertures blocked:")
        for name, volume in blocked:
            print(f"  {name:<6} {volume:8.2f} mm3 of material on the centreline")
        return False
    print("all apertures clear")
    return True


@_check("keypad")
def _pad_fits(s):
    return _report(
        pad_fits(s.front, s.pad), "pad seats in the front shell without fouling it"
    )


@_check("keypad")
def _plunger_stub_contact(s):
    return _report(
        plunger_stub_contact(s.pad),
        "every plunger lands on its switch top within tolerance",
    )


@_check("keypad")
def _mic_pad_contour(s):
    return _report(
        mic_pad_contour(s.pad),
        "mic pad follows both buttons with rounded inner joins and an attached lower bridge",
    )


@_check("caps")
def _caps_fit(s):
    return _report(
        caps_fit(s.front, s.pad, s.caps),
        f"{len(s.caps)} caps clear the shell, grip their stems and stay captive "
        "under the face land",
    )


@_check("caps")
def _cap_fits_around_perimeter(s):
    return _report(
        cap_fits_around_perimeter(),
        "flange overlap, counterbore clearance and guide clearance are all no "
        "tighter around the cap curve than the widths they are stated at",
    )


@_check("caps")
def _caps_flush(s):
    return _report(caps_flush(), "caps land flush with the front face")


@_check("keypad")
def _pad_clears_wheel(s):
    return _report(
        pad_clears_wheel(s.pad),
        f"both pad lobes stop {case.pad_wheel_gap():.2f} short of the wheel's own "
        f"clearance band, so nothing cuts them apart",
    )


@_check("caps")
def _caps_proud_of_pocket(s):
    return _report(
        caps_proud_of_pocket(),
        "every cap stands proud of the recess floor by exactly its local depth",
    )


@_check("caps")
def _legends_present(s):
    return _report(
        legends_present(s.caps),
        f"all {len(s.caps)} legends cut a real deboss out of one solid cap, "
        "every glyph in the font",
    )


@_check("fdm")
def _outline_solid_sane(s):
    return _report(
        outline_solid_sane(),
        f"the FDM outline cut is one band {params.FDM_OUTLINE_W:.2f} wide and "
        f"{params.FDM_OUTLINE_DEPTH:.2f} deep, on the recess's own rim",
    )


@_check("fdm")
def _edge_round_is_hard(s):
    return _report(
        edge_round_is_hard(s.front_fdm),
        f"the FDM front's top edge rounds at {case.front_edge_round(True):.2f} "
        f"rather than {case.front_edge_round():.2f}, leaving the outline "
        f"{params.FDM_OUTLINE_EDGE_CLEAR:.2f} of flat face outboard of it",
    )


@_check("fdm")
def _ceilings_hold(s):
    return _report(
        ceilings_hold(s.front_fdm),
        f"the {params.FDM_FACE_DROP:.2f} the FDM face drops leaves every "
        f"ceiling it thins above the floor the recessed front holds it to",
    )


@_check("fdm")
def _face_is_flat(s):
    return _report(
        face_is_flat(s.front_fdm),
        "the FDM front's face is flat everywhere the recessed one is dished",
    )


@_check("fdm")
def _outline_is_cut(s):
    return _report(
        outline_is_cut(s.front_fdm),
        f"the outline is cut to depth all the way round and leaves material "
        f"under every point of itself",
    )


@_check("shells")
def _shells_mate(s):
    return _report(
        shells_mate(s.front, s.back), "front and back mate with no overlap"
    )


@_check("wheel_ring")
def _light_path(s):
    return _report(
        light_path(s.shells, s.pad),
        "every LED has an open pad below it, open channel above it and a solid "
        "roof over that",
    )


@_check("wheel_ring")
def _led_ring(s):
    return _report(
        led_ring(s.front),
        "ring channel is void all the way around, webbed off the wheel opening, "
        "roofed all the way to the dished face above it",
    )


@_check("wheel_ring")
def _wheel_seat_clearance(s):
    return _report(
        wheel_seat_clearance(s.front),
        "shell's own opening sits flush to the housing and knob at "
        "WHEEL_OPENING_CLEARANCE, lip stays clear of the ceiling",
    )


@_check("wheel_ring")
def _rotation_clearance(s):
    return _report(
        rotation_clearance(s.front, s.pad),
        "nothing intrudes inside the wheel's rotation clearance",
    )


@_check("keypad")
def _recess_solid_sane(s):
    return _report(
        recess_solid_sane(),
        "the built recess is one solid of positive volume filling exactly the box "
        "its own field spans",
    )


@_check("keypad")
def _recesses_open(s):
    return _report(
        recesses_open(s.front),
        "the face is dished to its predicted depth beside every key, beside the "
        "mic, on the wheel seat on four bearings and at each join's narrowest "
        "open point",
    )


@_check("mic")
def _mic_fillet(s):
    return _report(
        mic_fillet(s.front),
        f"mic inlet is one funnel: {case.mic_throat_d():.2f} throat on the board's "
        f"own {case.mic_port_drill():.2f} port, tapering out to "
        f"{2 * case.mic_taper_r():.2f} and then {2 * case.mic_mouth_r():.2f} at the "
        f"recess floor on a {case.mic_fillet_r():.2f} concave fillet",
    )


@_check("keypad")
def _recess_land(s):
    thinnest = min(case.counterbore_land(ref) for ref in case.cap_refs())
    return _report(
        recess_land(s.front),
        f"every counterbore keeps a solid face land under its recess, "
        f"{thinnest:.2f} at the thinnest",
    )


@_check("usb")
def _usb_pocket_clearance(s):
    return _report(
        usb_pocket_clearance(s.front),
        f"USB pocket clears the connector by USB_CLEARANCE and is flush with "
        f"the slot at {case.usb_roof():.2f}, leaving "
        f"{case.SHELL_FRONT - case.usb_roof():.2f} of ceiling above it",
    )


@_check("keypad")
def _recess_margins(s):
    return _report(
        recess_margins(),
        "every counterbore sits inside the recess rim, the rim clears the "
        "exterior wall by KEYPAD_EDGE_MARGIN, and the dish centres share one x",
    )


@_check("keypad")
def _wheel_basin_shape(s):
    return _report(
        wheel_basin_shape(),
        "wheel basin has circular cardinal curvature and exact "
        f"exponent {params.WHEEL_SQUIRCLE_N:.1f} diagonals",
    )


@_check("keypad")
def _neck_continuity(s):
    return _report(
        neck_continuity(),
        "the recess runs unbroken along its centreline from one island's keys to "
        "the other's, both joins inside their reach bounds and round enough",
    )


@_check("keypad")
def _neck_blends_smoothly(s):
    return _report(
        neck_blends_smoothly(),
        "floor and outline are tangent-continuous across every join junction and "
        "waist, so the merged recess has no crease and no cusp",
    )


@_check("keypad")
def _recess_edge_clearance(s):
    return _report(
        recess_edge_clearance(s.front),
        "the built recess clears the side wall by KEYPAD_EDGE_MARGIN",
    )


@_check("hardware")
def _cell_clearance(s):
    fouled = cell_clearance()
    if fouled:
        print(f"{len(fouled)} things the cell runs into:")
        for what, volume in fouled:
            print(f"  {what:<28} {volume:8.2f} mm3")
        return False
    print("cell clears the board, the bosses and the shells")
    return True


@_check("support")
def _support_board_clearance(s):
    return _report(
        support_board_clearance(case.support_ledges()),
        f"support ledges stop {params.SUPPORT_GAP:.2f} below the board",
    )


@_check("support")
def _support_part_clearance(s):
    return _report(
        support_part_clearance(case.support_ledges()),
        "support ledges clear every bottom courtyard and screw head",
    )


@_check("support")
def _support_cell_clearance(s):
    return _report(
        support_cell_clearance(case.support_ledges()),
        "support ledges clear the cell envelope",
    )


@_check("support")
def _support_flat_bearing(s):
    ledge = case.support_ledges()
    widths = case.support_bearing_widths(ledge)
    return _report(
        support_flat_bearing(ledge),
        "support flat bearing remains: "
        + ", ".join(f"{side} {width:.2f} mm" for side, width in widths.items()),
    )


@_check("support")
def _support_min_run(s):
    return _report(
        support_min_run(),
        f"all {len(case.support_runs())} support runs meet SUPPORT_MIN_RUN",
    )


@_check("support")
def _support_printable(s):
    return _report(
        support_printable(),
        f"support undersides rise at {params.SUPPORT_UNDER_ANGLE:.1f} degrees",
    )


@_check("support")
def _support_inner_round(s):
    return _report(
        support_inner_round(case.support_ledges()),
        f"support inboard edges have a {params.SUPPORT_INNER_R:.2f} radius",
    )


@_check("support")
def _support_wall_merge(s):
    return _report(
        support_wall_merge(s.back),
        "support ledges overlap the back shell cavity wall",
    )


@_check("support")
def _support_case_containment(s):
    return _report(
        support_case_containment(s.back),
        "back shell stays inside the case envelope",
    )


@_check("legacy")
def _legacy_point_in_frame(s):
    return _report(
        legacy_point_in_frame(),
        f"V2's three mounting holes read off its own STEP in the shared frame; "
        f"the post takes the upper-right one at {board.legacy_retention_point()}",
    )


@_check("legacy")
def _legacy_post_clearance(s):
    return _report(
        legacy_post_clearance(),
        f"V2 retention post stops {params.SUPPORT_GAP:.2f} below the V3 board and "
        "clears every assembly solid, the cell, both V3 screw heads and the "
        "closure standoff",
    )


@_check("legacy")
def _legacy_post_merged(s):
    return _report(
        legacy_post_merged(s.back),
        "V2 retention post is fused into one back-shell solid, walled all the "
        "way round its pilot",
    )


@_check("legacy")
def _legacy_pilot_blind(s):
    return _report(
        legacy_pilot_blind(s.back),
        f"V2 pilot is open its full {params.BOSS_PILOT_DEPTH:.1f} and blind, on "
        "solid floor below",
    )


@_check("legacy")
def _legacy_post_headroom(s):
    return _report(
        legacy_post_headroom(),
        f"V2 post takes an M2 x {case.legacy_screw_length():.0f}: "
        f"{params.BOSS_PILOT_DEPTH:.1f} of engagement in "
        f"{(params.LEGACY_RETENTION_OD - params.BOSS_PILOT_D) / 2:.2f} of wall",
    )


@_check("assembly")
def _feature_clashes(s):
    clashes = feature_clashes()
    if clashes:
        print(f"\n{len(clashes)} case features overlap a courtyard:")
        for name, ref, depth in sorted(clashes, key=lambda c: -c[2]):
            print(f"  {name:<12} into {ref:<6} by {depth:5.2f} mm")
        return False
    print("all bosses, ribs and the battery clear every courtyard")
    return True


@_check("ir")
def _end_ports_open(s):
    return _report(
        end_ports_open(s.shells),
        "D1's bore and the USB shell remain open at their end-wall centrelines",
    )


@_check("ir")
def _receiver_paths(s):
    return _report(
        receiver_paths(s.shells, s.back),
        "U2 has a clear -Z sightline and its obsolete +Y end-wall path is closed",
    )


@_check("ir")
def _receiver_clearance(s):
    return _report(
        receiver_clearance(s.back, s.window),
        "built back shell and installed insert clear U2's complete envelope",
    )


@_check("ir")
def _window_installation(s):
    return _report(
        window_installation(s.back, s.window),
        f"IR insert is exterior-flush, press-held, closes the sightline, and "
        f"retains on {case.ir_window_retention():.2f} of flanged adhesive land",
    )


@_check("assembly")
def _parts_are_sound(s):
    parts = {
        "front shell": s.front,
        "FDM front shell": s.front_fdm,
        "back shell": s.back,
        "button pad": s.pad,
        "IR window": s.window,
        **{f"{ref} cap": cap for ref, cap in s.caps.items()},
    }
    return _report(
        parts_are_sound(parts),
        f"all {len(parts)} exported parts are valid solids and mesh to closed "
        "manifolds",
    )


@_check("assembly")
def _interference(s):
    hits = interference(s.shells + s.window)
    if not hits:
        print("no interference")
        return True
    print(f"\n{len(hits)} colliding solids (ref is the nearest placement, approximate")
    print("for multi-solid models):")
    for ref, volume, lo, hi in sorted(hits, key=lambda h: -h[1]):
        print(f"  {ref:<6} {volume:8.2f} mm3   solid z {lo:6.2f} .. {hi:6.2f}")
    return False


FEATURES = sorted({feature for feature, _ in CHECKS})


def _selection(argv):
    """The features to run, or None for all of them."""
    parser = argparse.ArgumentParser(
        prog="check.py", description="Verify the case against the board."
    )
    parser.add_argument(
        "--only",
        metavar="FEATURE[,FEATURE...]",
        help="run only these features' passes: " + ", ".join(FEATURES),
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        metavar="N",
        help="run passes in N independent processes (default: 1)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="show failures, provenance, counts, and scoped-run warnings only",
    )
    parser.add_argument(
        "--json",
        metavar="PATH",
        default=CHECKS_JSON,
        help=f"where to write the machine-readable report (default: {CHECKS_JSON})",
    )
    parser.add_argument(
        "--timings",
        action="store_true",
        help="show per-pass elapsed times after the report",
    )
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    if args.only is None:
        return None, args
    wanted = [name.strip() for name in args.only.split(",") if name.strip()]
    unknown = [name for name in wanted if name not in FEATURES]
    if unknown or not wanted:
        parser.error(
            f"unknown feature: {', '.join(unknown) or '(none given)'}. "
            f"Valid names: {', '.join(FEATURES)}"
        )
    return wanted, args


def _run_pass(feature, run, solids):
    """Run one pass and retain its output for deterministic parent reporting."""
    output = io.StringIO()
    _PENDING.clear()
    started = time.perf_counter()
    try:
        previous = sys.stdout
        sys.stdout = output
        try:
            passed = bool(run(solids))
        finally:
            sys.stdout = previous
    except Exception:
        passed = False
        output.write(traceback.format_exc())
    return {
        "feature": feature,
        "name": run.__name__.lstrip("_"),
        "passed": passed,
        "output": output.getvalue(),
        "elapsed": time.perf_counter() - started,
        "problems": [
            p.as_dict() if isinstance(p, Problem) else {"text": str(p)}
            for p in _PENDING
        ],
    }


_WORKER_SOLIDS = None
"""The one Solids() this worker process owns, made by the pool initializer.

Work is handed out a pass at a time, so a worker runs many passes and they come
from whichever features happen to still be pending. Solids is a lazy holder
whose properties cost minutes to fill the first time and nothing every time
after, so it has to outlive the task that first asked for a shape: building a
fresh one per task would throw away everything the previous task built and pay
for it again, which is strictly worse than owning a whole feature was. The pool
is spawned rather than forked, so nothing can be inherited from the parent and
the initializer is the only place this can be made.
"""


def _run_indexed(index):
    """Run CHECKS[index] against this worker's solids.

    A task is an index into CHECKS rather than the pass's own function because
    the task has to cross a spawn. An int is an int on both sides; a function
    survives the trip only by being importable under the qualified name it was
    defined at, which silently couples the schedule to where a pass happens to
    live. CHECKS is built at import time in one fixed order in the parent and in
    every worker, so an index names the same pass everywhere.
    """
    feature, run = CHECKS[index]
    return _run_pass(feature, run, _WORKER_SOLIDS)


def _parallel_initializer():
    """Set a worker up: off its neighbours' cache directory, and with solids.

    CASE_CACHE_PARALLEL keeps concurrent writers from deleting another worker's
    cache directory. The Solids() is this process's only one, for the reason in
    _WORKER_SOLIDS.
    """
    global _WORKER_SOLIDS
    os.environ["CASE_CACHE_PARALLEL"] = "1"
    _WORKER_SOLIDS = Solids()


_FEATURE_SOLIDS = {
    "apertures": ("front", "back"),
    "assembly": ("front", "front_fdm", "back", "pad", "window", "caps"),
    "caps": ("front", "pad", "caps"),
    "fdm": ("front_fdm",),
    "hardware": (),
    "ir": ("front", "back", "window"),
    "keypad": ("front", "pad"),
    "legacy": ("back",),
    "mic": ("front",),
    "shells": ("front", "back"),
    "support": ("back",),
    "usb": ("front",),
    "wheel_ring": ("front", "back", "pad"),
}
"""Which of the cached solids each feature's passes reach for.

Written in terms of the six properties that have a blob of their own rather
than the seven Solids exposes: `shells` is `back` fused to `front` in memory
and is not cached itself, so a feature that reads it wants those two.

The table only ever decides what to prewarm. It never gates what a pass can
reach, because the properties stay lazy and a pass touches whatever it touches
whether or not this expected it. A feature listed short, or left out of the
table entirely, costs a worker one build it would have done anyway; a feature
listed long costs one solid nobody reads. Neither can move a verdict, and that
is the whole reason a hand-maintained list is acceptable here when it would not
be if it stood between a pass and its geometry.
"""

_SOLID_BLOBS = {
    "front": (case.front_shell, {}),
    "front_fdm": (case.front_shell, {"fdm": True}),
    "back": (case.back_shell, {}),
    "pad": (case.button_pad, {}),
    "window": (case.ir_window, {}),
}
"""The cached builder and arguments behind each Solids property, for asking the
cache whether that property would import or build. `caps` is not here because it
is one blob per keycap rather than one blob, so _is_warm handles it on its own.
"""


def _is_warm(name):
    """Whether the blob a Solids property would import is already written.

    Per blob rather than per cache directory. cache.provenance() calls a key
    directory a hit as soon as it holds any blob at all, which is the right
    answer for the line it prints and the wrong one here: an interrupted run or
    an evicted blob leaves a directory that reads as a hit and is still most of
    a cold build, and prewarming exists for exactly that state.
    """
    if name == "caps":
        return all(cache.cached(case.keycap, ref) for ref in case.cap_refs())
    builder, kwargs = _SOLID_BLOBS[name]
    return cache.cached(builder, **kwargs)


def _prewarm(features):
    """Build whatever this selection needs and does not have, once, here.

    Each worker builds its own Solids() and every one of those goes through the
    disk cache in case/cache.py. Warm, that is a BREP import per worker and
    costs nothing worth avoiding. Cold, which is exactly the state right after
    the geometry edit that prompted the run, every worker independently builds
    the same shells from scratch, so the expensive half of the suite is paid for
    once per worker instead of once. Building them here, before the pool exists,
    turns those N cold builds into one cold build and N imports.

    Scoped runs get this too, and only for what they use: a one feature run can
    still fan out across that feature's passes, so it can still pay for the same
    shell N times, while prewarming the full set for --only ir would cost far
    more than the fan-out could ever save. That is what _FEATURE_SOLIDS is for.

    A fully warm selection returns having built nothing and said nothing, which
    is the common case and must stay free: this runs in the parent, serially,
    so anything it does is time the pool is not running.
    """
    wanted = {name for feature in features for name in _FEATURE_SOLIDS.get(feature, ())}
    cold = [name for name in sorted(wanted) if not _is_warm(name)]
    if not cold:
        return
    print(f"prewarming {', '.join(cold)} before fanning out", flush=True)
    solids = Solids()
    for name in cold:
        getattr(solids, name)


def _progress(record, suite_started, done, total, quiet):
    """Say that a pass finished, the moment it finishes.

    The report is replayed in registry order once everything is home, which is
    what makes a --jobs run comparable to a serial one, but it also means not a
    line of it can be printed until the last pass lands. A full run is a quarter
    of an hour, and a quarter of an hour of silence is indistinguishable from a
    hang. So completion gets a channel of its own: unordered, one flushed line
    per pass, carrying enough to place the run in time (suite clock, which pass,
    what it cost, how it went, how many of how many are home).

    None of this reaches the JSON report or the pass's own buffered output, so
    the interleaving these lines inevitably have between workers cannot make the
    report itself depend on scheduling. --quiet suppresses the passes that
    passed, the same passes it already suppresses from the report.
    """
    if quiet and record["passed"]:
        return
    print(
        f"[{time.perf_counter() - suite_started:8.2f}s] "
        f"{'ok  ' if record['passed'] else 'FAIL'} "
        f"{record['feature']}.{record['name']} "
        f"({record['elapsed']:.2f}s) [{done}/{total}]",
        flush=True,
    )


def _report_record(record, suite_started, quiet):
    """Render buffered output in registry order, regardless of worker completion."""
    if not quiet or not record["passed"]:
        output = record["output"]
        if not output and not record["passed"]:
            output = f"{record['feature']}.{record['name']}: failed without diagnostic\n"
        print(output, end="")
    if not quiet:
        print(
            f"[{time.perf_counter() - suite_started:8.2f}s] "
            f"done  {record['feature']}.{record['name']} "
            f"({record['elapsed']:.2f}s)",
            flush=True,
        )


def _write_report(path, records, features, scoped):
    """The machine-readable half of the report: what ran, what failed, and where.

    Written on every run rather than behind a flag, because the viewer reads it
    beside the geometry and a report older than the case it is drawn on is worse
    than none. A scoped run writes only the features it ran and says so, so the
    ones it skipped are never mistaken for clean.

    The location comes from the problems, which is why a pass that prints its own
    table rather than going through _report() carries none: its lines are in
    `output` and the viewer lists them without a marker.
    """
    payload = {
        "provenance": cache.provenance(),
        "features": features,
        "scoped": scoped,
        "passes": [
            {
                "feature": record["feature"],
                "name": record["name"],
                "passed": record["passed"],
                "elapsed": round(record["elapsed"], 3),
                "problems": record.get("problems", []),
                **({} if record["passed"] else {"output": record["output"].strip()}),
            }
            for record in records
        ],
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=1)
        handle.write("\n")


def _timing_report(records):
    print("timings:")
    for record in records:
        print(f"  {record['feature']}.{record['name']}: {record['elapsed']:.2f}s")


def main(argv=None):
    selected, args = _selection(sys.argv[1:] if argv is None else argv)
    print(cache.provenance())
    suite_started = time.perf_counter()
    selected_indices = [
        index
        for index, (feature, _) in enumerate(CHECKS)
        if selected is None or feature in selected
    ]
    selected_checks = [CHECKS[index] for index in selected_indices]
    selected_features = list(dict.fromkeys(feature for feature, _ in selected_checks))
    if args.jobs == 1 or len(selected_checks) < 2:
        solids = Solids()
        records = []
        for feature, run in selected_checks:
            if not args.quiet:
                print(
                    f"[{time.perf_counter() - suite_started:8.2f}s] "
                    f"start {feature}.{run.__name__.lstrip('_')}",
                    flush=True,
                )
            record = _run_pass(feature, run, solids)
            records.append(record)
            _report_record(record, suite_started, args.quiet)
    else:
        # Nothing to prewarm into when the cache is off: the workers would
        # rebuild regardless, so the parent's build would be pure added time.
        if cache.enabled():
            _prewarm(selected_features)
        total = len(selected_indices)
        workers = min(args.jobs, total)
        if not args.quiet:
            print(
                f"running {len(selected_checks)} checks with {workers} workers",
                flush=True,
            )
        by_index = {}
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_parallel_initializer,
            mp_context=multiprocessing.get_context("spawn"),
        ) as executor:
            futures = {
                executor.submit(_run_indexed, index): index
                for index in selected_indices
            }
            for future in as_completed(futures):
                index = futures[future]
                feature, run = CHECKS[index]
                try:
                    record = future.result()
                except Exception:
                    # A worker that dies takes its task with it, and the pool
                    # fails every task still outstanding. Each of those is one
                    # pass now rather than a whole feature, so each gets its own
                    # failed record and the traceback that explains it; the
                    # alternative is a pass that silently drops out of a report
                    # that still says it ran.
                    record = {
                        "feature": feature,
                        "name": run.__name__.lstrip("_"),
                        "passed": False,
                        "output": f"{feature} worker failed:\n{traceback.format_exc()}",
                        "elapsed": 0.0,
                        "problems": [],
                    }
                by_index[index] = record
                _progress(record, suite_started, len(by_index), total, args.quiet)
        # Back into registry order for the report. The printed body and
        # _write_report both read this list, and both have to see the same order
        # whatever order the pool happened to finish in.
        records = [by_index[index] for index in selected_indices]
        for record in records:
            _report_record(record, suite_started, args.quiet)
    passed = all(record["passed"] for record in records)
    _write_report(args.json, records, selected_features, selected is not None)
    print(f"checks: {sum(record['passed'] for record in records)}/{len(records)} passed")
    if args.timings:
        _timing_report(records)
    if selected is not None:
        skipped = [name for name in FEATURES if name not in selected]
        print(
            f"SCOPED RUN, NOT A FULL PASS: skipped {', '.join(skipped)}"
            if skipped
            else "SCOPED RUN, NOT A FULL PASS: nothing skipped"
        )
    sys.exit(0 if passed else 1)
