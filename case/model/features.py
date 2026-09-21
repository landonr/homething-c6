"""Names for what the exported meshes are made of, so a click in the viewer can
be answered with an id instead of a description.

An STL is triangle soup. Every feature in this package is built by a named
function, and the name is the first thing the mesh throws away, so the viewer at
../c6remote-explode can show a surface but cannot say what it is. This module
writes the names back out beside the meshes: one entry per feature, carrying the
module and function that builds it, the parameters that source reads, whether it
is material or void, and its bounding box in the case frame.

The boxes overlap, and nothing here tries to stop that. A key's own prism sits
inside the recess it is cut through, and the smaller box is the better answer, so
the viewer ranks by which containing box is smallest. Per-instance ids are what
make that ranking useful, so a feature the model builds eleven or three or two of
gets that many entries, by refdes where the board has one.

`op` is what a box alone cannot say: "add" is a solid the part's builder fuses,
"cut" is a volume it subtracts, and "clear" is a volume both shells keep clear of
the support ledge. The keepout gaps need that third word, because the same break
is a relief cut in the front and absent material in the back, so "add" and "cut"
would invert between the two parts.

Two things are deliberately left out. The keycaps carry no entries, because
each is already one part in the export and its STL is moved to the origin rather
than left where it was built, so a box in the case frame would not describe it.
The skirt and the cavities carry none either: each is a cut over the whole plan
profile, so its box is the part's own box and says nothing that ranking can use.

The FDM front does carry entries, and they are the front shell's own but for the
one cut the face is finished with: the outline groove where the standard shell
has the keypad recess. They are keyed under `c6remote-case-front-fdm.stl`,
because that is the file the viewer loaded and therefore the name it looks a
click up under. The two fronts are never both on screen, so nothing of one ever
ranks against the other.
"""

import inspect
import json
import re
from pathlib import Path

from build123d import Box, Pos

import board
import cache
import params

from . import caps, cell, hardware, ir, keypad, mic, shells, support, usb, wheel_ring
from .shape import _cut, _hole, _slab
from .stack import (
    BOARD_TOP,
    CAVITY_FRONT,
    COUNTERBORE_TOP,
    PAD_WEB_BOTTOM,
    PAD_WEB_TOP,
    SHELL_FRONT,
    SWITCH_TOP,
)

MODULES = {
    "caps": caps,
    "cell": cell,
    "hardware": hardware,
    "ir": ir,
    "keypad": keypad,
    "mic": mic,
    "shells": shells,
    "support": support,
    "usb": usb,
    "wheel_ring": wheel_ring,
}

PARAM = re.compile(r"params\.([A-Z][A-Z0-9_]*)")


def _reads(src):
    """The params.<NAME> identifiers a builder's own source reads.

    Static and direct only. A builder that calls another does not inherit that
    one's parameters, because the entry has to say what to edit to move this
    box, not restate the module's dependency tree. A builder that reads only
    derived constants out of stack.py reads no parameter, and gets an empty
    list rather than a guess.
    """
    module, _, name = src.partition(".")
    return sorted(set(PARAM.findall(inspect.getsource(getattr(MODULES[module], name)))))


def _entry(name, src, op, shapes, reads=None):
    """One feature. `shapes` may be several solids that share an id, in which
    case the box is the union of theirs."""
    if not isinstance(shapes, (list, tuple)):
        shapes = [shapes]
    boxes = [shape.bounding_box() for shape in shapes]
    low = [
        min(b.min.X for b in boxes),
        min(b.min.Y for b in boxes),
        min(b.min.Z for b in boxes),
    ]
    high = [
        max(b.max.X for b in boxes),
        max(b.max.Y for b in boxes),
        max(b.max.Z for b in boxes),
    ]
    return {
        "id": name,
        "src": src,
        "op": op,
        "params": _reads(src) if reads is None else reads,
        "box": [[round(v, 3) for v in low], [round(v, 3) for v in high]],
    }


def _split(name, src, op, shapes, axis="x", reads=None):
    """One entry per solid of a pair, each labelled by which of the two it is.

    Against the pair's own mean rather than the middle of the case, so a pair
    that sits entirely at one end still gets one id each. The cradle's two ribs
    are both well into -Y, and splitting them on the case centre named them
    both cradle.-y.
    """
    centres = []
    for shape in shapes:
        centre = shape.bounding_box().center()
        centres.append(centre.X if axis == "x" else centre.Y)
    middle = sum(centres) / len(centres)
    out = [
        _entry(f"{name}.{'-' if at < middle else '+'}{axis}", src, op, shape, reads)
        for shape, at in zip(shapes, centres)
    ]
    return sorted(out, key=lambda entry: entry["id"])


# Runs that merely touch across a rounding leave no break worth a name.
GAP_MIN = 0.01


def _support_sides(runs):
    """[(side, [run])], each side's runs in order along y.

    The runs are scattered down both walls, so a side and a rank along that
    wall is what tells one from another. Both the runs and the breaks between
    them are named off this one ordering.
    """
    middle = board.board_profile().bounding_box().center().X
    sides = {}
    for run in runs:
        side = "-x" if run.bounding_box().center().X < middle else "+x"
        sides.setdefault(side, []).append(run)
    for group in sides.values():
        group.sort(key=lambda run: run.bounding_box().center().Y)
    return sorted(sides.items())


def _support_entries(runs, op):
    """The board support runs, one entry each. Per instance because one box
    around all of them would cover the whole cavity."""
    out = []
    for side, group in _support_sides(runs):
        for index, run in enumerate(group, 1):
            out.append(
                _entry(f"support_runs.{side}.{index}", "support.support_runs", op, run)
            )
    return out


def _obstacle_ref(name):
    """The board name inside an obstacle's own label.

    A bottom courtyard is already a bare refdes. The other two labels are
    sentences, and an id has to stay one token.
    """
    if name.startswith("mount "):
        return name.split(" ")[-1]
    if name.startswith("through-board solid "):
        return f"solid.{name.split(' ')[-1]}"
    return name


def _support_gaps(runs, obstacles):
    """The breaks between the runs, named for the obstacle that opens each.

    A run's box answers a click on the ledge, but the wall between two runs is
    bare, and a click there used to land in no box at all. The break is a
    keepout rather than anything built, so it carries the obstacle's own source
    and the "clear" op.

    A break can be wider than the obstacle that opens it: where SUPPORT_MIN_RUN
    drops a short fragment between two obstacles, one break spans both. So the
    widest y overlap wins the name rather than the first or the nearest.
    """
    out = []
    for side, group in _support_sides(runs):
        for lower, upper in zip(group, group[1:]):
            low = lower.bounding_box()
            high = upper.bounding_box()
            y0, y1 = low.max.Y, high.min.Y
            if y1 - y0 < GAP_MIN:
                continue
            # x and z off both runs, so the front's SKIRT_OUT reach and the
            # back's LAP_IN reach each stay the part's own.
            x0, x1 = min(low.min.X, high.min.X), max(low.max.X, high.max.X)
            z0, z1 = min(low.min.Z, high.min.Z), max(low.max.Z, high.max.Z)
            gap = Pos((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2) * Box(
                x1 - x0, y1 - y0, z1 - z0
            )
            overlaps = []
            for name, solid in obstacles:
                box = solid.bounding_box()
                if box.max.X <= x0 or box.min.X >= x1:
                    continue
                overlaps.append(
                    (min(box.max.Y, y1) - max(box.min.Y, y0), _obstacle_ref(name))
                )
            widest = max(overlaps, default=None)
            if widest is None or widest[0] <= 0:
                raise ValueError(
                    f"support gap on {side} at y {y0:.2f} to {y1:.2f} has no obstacle"
                )
            out.append(
                _entry(
                    f"support_gap.{side}.{widest[1]}",
                    "support.support_obstacles",
                    "clear",
                    gap,
                )
            )
    return out


def _front(runs, obstacles, fdm=False):
    """The front shell, in the order front_shell() builds and cuts it.

    `fdm` swaps the one entry the two fronts differ by, the outline groove the
    filament build cuts where the standard shell cuts the keypad recess.
    """
    refs = board.mounting_hole_refs()
    placements = board.components()
    out = [
        _entry("mic_duct", "mic.mic_duct", "add", mic.mic_duct()),
        _entry("deep_skirt", "shells.deep_skirt", "add", shells.deep_skirt()),
        *[
            _entry(f"skirt_lead_in.{index}", "shells.skirt_lead_in_cuts", "cut", solid)
            for index, solid in enumerate(shells.skirt_lead_in_cuts().solids(), 1)
        ],
    ]
    # The bosses and their pilots have no builder of their own: front_shell()
    # holes them straight out of mount_points(), so the parameters are named
    # here rather than read out of that whole function's source.
    for x, y in hardware.mount_points():
        out.append(
            _entry(
                f"boss.{refs[(x, y)]}",
                "shells.front_shell",
                "add",
                _hole(x, y, params.BOSS_OD, BOARD_TOP, SHELL_FRONT),
                ["BOSS_OD"],
            )
        )
    out.append(
        _entry(
            "end_screw_block",
            "hardware.end_screw_block",
            "add",
            hardware.end_screw_block(),
        )
    )
    out.append(_entry("usb_pocket", "usb.usb_pocket", "cut", usb.usb_pocket()))
    out += _support_entries(runs, "cut")
    out += _support_gaps(runs, obstacles)
    for x, y in hardware.mount_points():
        out.append(
            _entry(
                f"pilot.{refs[(x, y)]}",
                "shells.front_shell",
                "cut",
                _hole(
                    x,
                    y,
                    params.BOSS_PILOT_D,
                    BOARD_TOP - 0.1,
                    BOARD_TOP + params.BOSS_PILOT_DEPTH,
                ),
                ["BOSS_PILOT_D", "BOSS_PILOT_DEPTH"],
            )
        )
    out.append(
        _entry(
            "end_screw_pilot",
            "hardware.end_screw_pilot",
            "cut",
            hardware.end_screw_pilot(),
        )
    )
    out += _split(
        "catch_windows", "shells.catch_windows", "cut", shells.catch_windows()
    )
    out += [
        _entry(
            "wheel_opening",
            "wheel_ring.wheel_opening",
            "cut",
            wheel_ring.wheel_opening(CAVITY_FRONT - 1, SHELL_FRONT + 1),
        ),
        _entry(
            "led_ring_channel",
            "wheel_ring.led_ring_channel",
            "cut",
            wheel_ring.led_ring_channel(),
        ),
        _entry("mic_bore", "mic.mic_bore", "cut", mic.mic_bore()),
    ]
    # Both holes per key, at the depths front_shell() cuts them, so a box is the
    # cut rather than the ceiling it opens in.
    for ref in board.refs("SW"):
        x, y = placements[ref][:2]
        out.append(
            _entry(
                f"key.{ref}.counterbore",
                "caps._key_prism",
                "cut",
                caps._key_prism(
                    x, y, caps.cap_counterbore(ref), CAVITY_FRONT - 1, COUNTERBORE_TOP
                ),
            )
        )
        out.append(
            _entry(
                f"key.{ref}.face_hole",
                "caps._key_prism",
                "cut",
                caps._key_prism(
                    x, y, caps.cap_face_hole(ref), CAVITY_FRONT - 1, SHELL_FRONT + 1
                ),
            )
        )
    out += [
        _entry(
            "keypad_outline_groove",
            "keypad.keypad_outline_groove",
            "cut",
            keypad.keypad_outline_groove(),
        )
        if fdm
        else _entry(
            "keypad_recess", "keypad.keypad_recess", "cut", keypad.keypad_recess()
        ),
        _entry("usb_slot", "usb.usb_slot", "cut", usb.usb_slot()),
        _entry("emitter_bore", "ir.emitter_bore", "cut", ir.emitter_bore()),
    ]
    return out


def _back(runs, obstacles):
    """The back shell, in the order back_shell() builds and cuts it."""
    out = [
        _entry("skirt_relief", "shells.skirt_relief", "cut", shells.skirt_relief()),
        _entry("catch_relief", "shells.catch_relief", "cut", shells.catch_relief()),
        _entry(
            "legacy_retention.post",
            "hardware.legacy_retention_post",
            "add",
            hardware.legacy_retention_post(),
        ),
    ]
    out += _support_entries(runs, "add")
    out += _support_gaps(runs, obstacles)
    out += _split(
        "catch_detents", "shells.catch_detents", "add", shells.catch_detents()
    )
    # The two end-screw cuts share one hole, so the shank and the head
    # counterbore are told apart by what each does rather than by where it is.
    # No refdes: this screw goes into a case feature, not a board hole.
    for name, shape in zip(("clearance", "head"), hardware.end_screw_cuts()):
        out.append(
            _entry(f"end_screw.{name}", "hardware.end_screw_cuts", "cut", shape)
        )
    out += [
        _entry("usb_slot", "usb.usb_slot", "cut", usb.usb_slot()),
        _entry("emitter_bore", "ir.emitter_bore", "cut", ir.emitter_bore()),
        _entry(
            "ir_window_opening", "ir.ir_window_opening", "cut", ir.ir_window_opening()
        ),
        _entry("ir_window_rebate", "ir.ir_window_rebate", "cut", ir.ir_window_rebate()),
        _entry(
            "legacy_retention.pilot",
            "hardware.legacy_retention_pilot",
            "cut",
            hardware.legacy_retention_pilot(),
        ),
    ]
    return out


def _pad():
    """The button pad, one group per lobe."""
    refs = board.mounting_hole_refs()
    placements = board.components()
    mounts = hardware.mount_points()
    out = []
    for name, x0, y0, x1, y1 in keypad.pad_lobes():
        out.append(
            _entry(
                f"lobe.{name}",
                "keypad.pad_lobe_face",
                "add",
                _slab(keypad.pad_lobe_face(name), PAD_WEB_BOTTOM, PAD_WEB_TOP),
            )
        )
        for ref in keypad.island_refs(name):
            x, y = placements[ref][:2]
            out.append(_entry(f"stem.{ref}", "keypad._stem", "add", keypad._stem(x, y)))
            out.append(
                _entry(
                    f"plunger.{ref}",
                    "keypad.plunger",
                    "add",
                    keypad.plunger(x, y),
                )
            )
        # A clearance cut can be an open U rather than a circle, so its box is
        # off centre from the hole it clears. The three holes are far enough
        # apart that the nearest one is still the right name.
        for cut in keypad._boss_clearances(x0, y0, x1, y1):
            centre = cut.bounding_box().center()
            near = min(
                mounts,
                key=lambda p: (p[0] - centre.X) ** 2 + (p[1] - centre.Y) ** 2,
            )
            out.append(
                _entry(
                    f"boss_clearance.{refs[near]}",
                    "keypad._boss_clearances",
                    "cut",
                    cut,
                )
            )
        if name == "grid":
            for index, cut in enumerate(keypad._pad_grooves()):
                face = "top" if index % 2 == 0 else "bottom"
                out.append(
                    _entry(
                        f"isolation_groove.{index // 2}.{face}",
                        "keypad._pad_grooves",
                        "cut",
                        cut,
                    )
                )
    return out


def _fdm_pad():
    """The FDM pad, with printed keytops flush with its lobe webs."""
    out = _pad()
    for ref in board.refs("SW"):
        out.append(
            _entry(
                f"keytop.{ref}",
                "keypad.fdm_keycap",
                "add",
                keypad.fdm_keycap(ref),
                ["FDM_CAP_GUIDE_CLEARANCE", "KEY_SQUIRCLE_N", "LEGEND_DEPTH"],
            )
        )
    return out


def _window():
    """The IR window insert: the pane in the beam and the flange behind it.

    The two layers are rebuilt here the way ir_window() fuses them, since the
    part is the fusion and carries no separate handle on either half.
    """
    pane = ir._surface_layer(params.IR_WINDOW_PRESS, 0, params.IR_WINDOW_T)
    flange = ir._surface_layer(
        params.IR_WINDOW_FLANGE,
        params.IR_WINDOW_T,
        params.IR_WINDOW_T + params.IR_WINDOW_FLANGE_T,
    )
    flange = _cut(flange, ir._bottom_prism(-0.5))
    return [
        _entry(
            "pane",
            "ir.ir_window",
            "add",
            pane,
            ["IR_WINDOW_PRESS", "IR_WINDOW_T"],
        ),
        _entry(
            "flange",
            "ir.ir_window",
            "add",
            flange,
            ["IR_WINDOW_FLANGE", "IR_WINDOW_FLANGE_T", "IR_WINDOW_T"],
        ),
    ]


def features():
    """{stl name: [entry]}, keyed by the file the viewer loads.

    The back supports and front clearance cuts use separate wall extensions so
    each finishes flush with its shell surface.
    """
    back_runs = support.support_runs()
    front_runs = support.front_support_cuts()
    obstacles = support.support_obstacles()
    out = {
        "c6remote-case-front.stl": _front(front_runs, obstacles),
        "c6remote-case-front-fdm.stl": _front(front_runs, obstacles, fdm=True),
        "c6remote-case-back.stl": _back(back_runs, obstacles),
        "c6remote-case-pad.stl": _pad(),
        "c6remote-case-pad-fdm.stl": _fdm_pad(),
        "c6remote-ir-window.stl": _window(),
    }
    # An id is what a viewer hands back to be acted on, so two features holding
    # the same one is worse than either being unnamed. This is the guard the
    # per-instance labelling needs: a pair or a group that grows a third member,
    # or one labelled off the wrong axis, collides here rather than quietly
    # exporting two boxes under one name.
    for part, entries in out.items():
        ids = [entry["id"] for entry in entries]
        clashes = sorted({name for name in ids if ids.count(name) > 1})
        if clashes:
            raise ValueError(
                f"{part} has {len(clashes)} repeated feature ids: {clashes}"
            )
    return out


def _payload():
    body = json.dumps({"frame": "case", "parts": features()}, indent=2)
    return (body + "\n").encode()


def write_features(dest):
    """Write the features JSON, from the cache when this key already has it.

    Cached as finished bytes, the way the STLs are. Only the two shells, the
    recess, the caps and the window insert are cached solids, so measuring every
    feature means building the rest of the model from scratch: on a warm run
    that would cost more than the shells it was meant to save.
    """
    dest = Path(dest)
    data = cache.bytes_cached(dest.name, _payload)
    dest.write_bytes(data)
    # Read back rather than returned from features(): on a warm run nothing was
    # built, and the caller's own count has to come off the bytes that were
    # written for that to stay true.
    return json.loads(data)
