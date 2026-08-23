"""Run every pass in order and print one line each.

check.py is the entry point that calls main() here. The order is the report,
so a new pass goes where its subject belongs rather than at the end.

Every pass carries the name of the checks module it lives in, and `--only`
takes a comma list of those names. Scoping is worth having because the solids
are built on demand: an ir-only run never touches the pad or the keycap
legends, so it skips the build a full run pays for. A pass whose subject is the
whole assembly rather than one feature is tagged `assembly` instead, so scoping
one side of it never runs it half blind.
"""

import argparse
import functools
import sys

import cache
import case

from .apertures import probe_apertures
from .caps import (
    cap_fits_around_perimeter,
    caps_fit,
    caps_flush,
    caps_proud_of_pocket,
    legends_present,
)
from .hardware import cell_clearance, feature_clashes
from .ir import (
    end_ports_open,
    receiver_clearance,
    receiver_paths,
    window_installation,
)
from .keypad import (
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
)
from .mic import mic_fillet
from .shells import interference, parts_are_sound, shells_mate
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


def _check(feature):
    def register(fn):
        CHECKS.append((feature, fn))
        return fn

    return register


def _report(problems, passed):
    """Print a pass's problem lines, or its one-line all-clear, and say which."""
    if problems:
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
        f"USB pocket clears the connector by USB_CLEARANCE, leaving "
        f"{case.SHELL_FRONT - case.CAVITY_FRONT_USB:.2f} of ceiling above it",
    )


@_check("keypad")
def _recess_margins(s):
    return _report(
        recess_margins(),
        "every counterbore sits inside the recess rim, the rim clears the "
        "exterior wall by KEYPAD_EDGE_MARGIN, and the dish centres share one x",
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
    args = parser.parse_args(argv)
    if args.only is None:
        return None
    wanted = [name.strip() for name in args.only.split(",") if name.strip()]
    unknown = [name for name in wanted if name not in FEATURES]
    if unknown or not wanted:
        parser.error(
            f"unknown feature: {', '.join(unknown) or '(none given)'}. "
            f"Valid names: {', '.join(FEATURES)}"
        )
    return wanted


def main(argv=None):
    selected = _selection(sys.argv[1:] if argv is None else argv)
    print(cache.provenance())
    solids = Solids()
    passed = True
    for feature, run in CHECKS:
        if selected is None or feature in selected:
            passed = run(solids) and passed
    if selected is not None:
        skipped = [name for name in FEATURES if name not in selected]
        print(
            f"SCOPED RUN, NOT A FULL PASS: skipped {', '.join(skipped)}"
            if skipped
            else "SCOPED RUN, NOT A FULL PASS: nothing skipped"
        )
    sys.exit(0 if passed else 1)
