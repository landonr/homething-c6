"""Board geometry read out of the KiCad exports, so the case follows the PCB.

Nothing here is hand-transcribed except WHEEL_OD, which no KiCad export carries
and which wheel_profile() now cross-checks against the assembly STEP rather than
trusting blind. Run `python board.py` for a keepout report re-derived from it.
"""

import csv
import functools
import math
import re
from collections import defaultdict, namedtuple
from pathlib import Path

from build123d import Axis, Box, Face, Plane, Pos, import_step

ROOT = Path(__file__).resolve().parent.parent
KICAD_PCB = ROOT / "c6remote-kicad" / "c6remote.kicad_pcb"
POS_CSV = ROOT / "c6remote-kicad" / "export" / "c6remote-pos.csv"
BOARD_ONLY_STEP = Path(__file__).resolve().parent / "board" / "c6remote-board-only.step"
ASSEMBLY_STEP = Path(__file__).resolve().parent / "board" / "c6remote-board.step"
LEGACY_BOARD_ONLY_STEP = (
    Path(__file__).resolve().parent / "board" / "c6remote-v2-board-only.step"
)
"""The V2 board, frozen. Release 2026.8.0, commit d0a2c2e, exported with
`kicad-cli pcb export step --board-only` the same way scripts/export-case-refs.sh
exports the live one. It is static reference geometry: that revision is gone from
the working tree, so nothing regenerates this file and nothing should."""

WHEEL_CUTOUT_R = 2.0

WHEEL_OD = 34.0
"""Widest ANO solid in the assembly STEP. ENC1 has no dimension in the board file."""


def _require(path):
    if not path.exists():
        raise FileNotFoundError(f"{path} missing. Run scripts/export-case-refs.sh")
    return path


def _edge_cut_circles():
    src = _require(KICAD_PCB).read_text()
    pattern = re.compile(
        r"\(gr_circle\s*\(center ([-\d.]+) ([-\d.]+)\)\s*"
        r"\(end ([-\d.]+) ([-\d.]+)\).*?\(layer \"([^\"]+)\"",
        re.S,
    )
    out = []
    for cx, cy, ex, ey, layer in pattern.findall(src):
        if layer != "Edge.Cuts":
            continue
        cx, cy, ex, ey = float(cx), float(cy), float(ex), float(ey)
        out.append((cx, -cy, math.hypot(ex - cx, ey - cy)))
    return out


@functools.cache
def _mounting_hole_rows():
    """(ref, x, y, diameter) per case screw hole, in board file order.

    Read off any footprint whose name contains "MountingHole", currently
    the three MountingHole_2.4mm_M2 instances (H1-H3): a dedicated NPTH
    footprint again, not the plain Edge.Cuts circles this briefly was, and
    not the fixed "MountingHole" exact name the original footprint used
    either, since the new one carries the hole size in its own name.
    Substring match rather than an exact one, so a future size or fastener
    change (a new MountingHole_* name) still matches with no code change
    here. Each carries one NPTH pad centred on its own local origin, so the
    footprint's own placement is the hole centre with no further offset.
    """
    src = _require(KICAD_PCB).read_text()
    out = []
    for name, body in re.findall(r'\(footprint "([^"]*)"(.*?)\n\t\)\n', src, re.S):
        if "MountingHole" not in name:
            continue
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+)", body)
        ref = re.search(r'\(property "Reference" "([^"]*)"', body)
        drill = re.search(
            r'\(pad "[^"]*" np_thru_hole \w+\s*\(at [-\d.]+ [-\d.]+\)\s*'
            r"\(size [-\d.]+ [-\d.]+\)\s*\(drill ([-\d.]+)\)",
            body,
        )
        if at and drill:
            out.append(
                (
                    ref.group(1) if ref else "",
                    float(at.group(1)),
                    -float(at.group(2)),
                    float(drill.group(1)),
                )
            )
    return tuple(out)


def mounting_holes():
    """(x, y, diameter) for the case's screw holes, in STEP frame."""
    return [(x, y, diameter) for _, x, y, diameter in _mounting_hole_rows()]


def mounting_hole_refs():
    """{(x, y): ref} over the same holes, so a feature built on one can carry
    its refdes. The geometry needs no hole name, but a boss with an id of H2
    is one a reader can find on the board."""
    return {(x, y): ref for ref, x, y, _ in _mounting_hole_rows()}


LEGACY_MOUNT_D = 2.9
"""V2's mounting hole diameter, as its Edge.Cuts circles cut it. V3 went to
2.4 mm NPTH footprints, so no reader shared between the two revisions can
match on one size."""

LEGACY_MOUNT_ROUND = 0.05
"""How far a V2 hole may depart from LEGACY_MOUNT_D and still count. The
STEP rounds a circle to the micron, so this only absorbs that."""

LEGACY_FRAME_TOLERANCE = 0.01
"""How far the two revisions' outlines may disagree before a V2 coordinate is
meaningless in the case frame. The two boards share an outline and an origin,
which is the only reason a V2 hole can be built on at all."""


@functools.cache
def legacy_mounting_holes():
    """[(x, y)] for V2's 2.9 mm mounting holes, in STEP frame.

    Read out of LEGACY_BOARD_ONLY_STEP rather than out of a KiCad file, because
    V2 has no MountingHole footprint and its board file is no longer in the
    working tree. The holes are plain circular voids in the board solid, so they
    arrive as inner wires of its bottom face, told apart from vias and part holes
    by diameter alone.

    Raises if the two revisions no longer share an outline. A V2 coordinate is
    only usable here because both boards sit on the same origin with the same
    edge, and a case feature built on a hole from a board that has moved would
    land somewhere arbitrary.
    """
    solid = import_step(_require(LEGACY_BOARD_ONLY_STEP)).solids()[0]
    legacy_box = solid.bounding_box()
    live_box = board_profile().bounding_box()
    for axis in ("X", "Y"):
        for end in ("min", "max"):
            apart = abs(
                getattr(getattr(legacy_box, end), axis)
                - getattr(getattr(live_box, end), axis)
            )
            if apart > LEGACY_FRAME_TOLERANCE:
                raise ValueError(
                    f"V2 and V3 outlines disagree on {end}.{axis} by {apart:.3f}: "
                    "they no longer share a frame, so no V2 coordinate means "
                    "anything in the case frame"
                )

    bottom = solid.faces().filter_by(Plane.XY).sort_by(Axis.Z)[0]
    out = []
    for wire in bottom.inner_wires():
        box = wire.bounding_box()
        if abs(box.size.X - box.size.Y) > LEGACY_MOUNT_ROUND:
            continue
        if abs(box.size.X - LEGACY_MOUNT_D) > LEGACY_MOUNT_ROUND:
            continue
        out.append((box.center().X, box.center().Y))
    if len(out) != 3:
        raise ValueError(
            f"expected three {LEGACY_MOUNT_D} holes in the V2 board, found {len(out)}"
        )
    return tuple(sorted(out))


def legacy_retention_point():
    """(x, y) of the one V2 hole the case offers a post under: the upper-right
    one, at the IR end.

    V2 put two holes at that end and one at the grip end; V3 does the reverse.
    So no V2 hole lands on a V3 one, and only this one has room under it in the
    V3 cavity for a post that clears every V3 part. Upper before right, so the
    pair at the IR end is picked first and the right of that pair second.
    """
    return max(legacy_mounting_holes(), key=lambda point: (point[1], point[0]))


def wheel_center():
    pts = [
        (x, y)
        for x, y, r in _edge_cut_circles()
        if math.isclose(r, WHEEL_CUTOUT_R, abs_tol=0.01)
    ]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def components():
    """Placement rows in STEP frame: {ref: (x, y, rotation, side)}."""
    out = {}
    with _require(POS_CSV).open() as fh:
        for row in csv.DictReader(fh):
            out[row["Ref"]] = (
                float(row["PosX"]),
                float(row["PosY"]),
                float(row["Rot"]),
                row["Side"],
            )
    return out


def refs(prefix):
    matches = [r for r in components() if re.fullmatch(rf"{prefix}\d+", r)]
    return sorted(matches, key=lambda r: int(re.search(r"\d+", r).group()))


def board_profile():
    """Outer edge of the board as a Face, cutouts and mounting holes dropped."""
    solid = import_step(_require(BOARD_ONLY_STEP)).solids()[0]
    bottom = solid.faces().filter_by(Plane.XY).sort_by(Axis.Z)[0]
    return Face(bottom.outer_wire())


@functools.cache
def assembly_solids():
    return import_step(_require(ASSEMBLY_STEP)).solids()


@functools.cache
def _assembly_boxes():
    """[(solid, bounding_box)] over assembly_solids(), measured once.

    Shape.bounding_box() is an OCC call every time it is asked, and the lookups
    below sweep all 79 solids per part, so leaving it uncached costs about 0.8s
    per part asked for.
    """
    return [(solid, solid.bounding_box()) for solid in assembly_solids()]


MAX_ENVELOPE_OFFSET = 4.0
"""How far a solid may sit from a placement and still be taken for that part.
Without this, asking for a part that has no 3D model quietly returns its
neighbour: part_envelope("D2") answered with Q2, 3.9 away and 0.4 taller."""


@functools.cache
def part_solid(ref):
    """The assembly solid that is the part's body at that placement, as a solid
    rather than a box: the largest one within MAX_ENVELOPE_OFFSET.

    Largest, not nearest. A footprint anchor is not a part centre, so proximity
    does not tell a body from a lead: each of U2's four leads sits closer to its
    own anchor than its body does, and asking by distance answered with a
    0.5 x 1.6 x 1.5 lead, which the receiver's window was then sized off.
    Volume is what separates them, and it separates them by two orders of
    magnitude here, so it needs no threshold of its own beyond the offset
    guard that already excludes a neighbouring part.

    What part_envelope() measures. Exposed separately because a bounding box
    is not always enough: emitter_envelope() has to clip D1's solid before
    boxing it, and boxing first would already have thrown away the shape it
    needs to clip.
    """
    x, y, _, _ = components()[ref]
    near = [
        solid
        for solid, box in _assembly_boxes()
        if math.hypot(box.center().X - x, box.center().Y - y) <= MAX_ENVELOPE_OFFSET
    ]
    if not near:
        raise ValueError(
            f"nothing within {MAX_ENVELOPE_OFFSET} of {ref}; it has no 3D model, "
            "so its size has to come from a parameter"
        )
    return max(near, key=lambda solid: solid.volume)


@functools.cache
def part_envelope(ref, radius=None):
    """Bounding box of the part's own body at that placement (see part_solid),
    or with a radius, of every solid centred within it, which is what a
    multi-solid part needs measured whole rather than body alone.

    Footprint anchors are not part centres: U2's is 1.2 off its body and
    closer to each of its leads than to it, so an aperture placed on the
    anchor misses and a solid picked by proximity is the wrong solid.
    """
    x, y, _, _ = components()[ref]

    if radius is None:
        return part_solid(ref).bounding_box()

    near = [
        box
        for _, box in _assembly_boxes()
        if math.hypot(box.center().X - x, box.center().Y - y) <= radius
    ]
    if not near:
        raise ValueError(f"no solid within {radius} of {ref}")
    box = near[0]
    for other in near[1:]:
        box = box.add(other)
    return box


WheelProfile = namedtuple("WheelProfile", "top lip_od lip_z0 lip_z1 main_od")

WHEEL_ENVELOPE_OFFSET = 5.0
"""How far a solid's bounding-box centre may sit from wheel_center() and still
count toward wheel_profile(). ENC1's revolved discs land 0.16 off wheel_center(),
the mean of the four ANO cutouts rather than the model's own axis; its leaf-spring
pin and mounting legs sit 1.2 to 1.7 off. Both offsets are well inside 5.0, so it
is WHEEL_SQUARENESS that actually tells the two groups apart."""

WHEEL_SQUARENESS = 0.5
"""Max difference between a candidate solid's X and Y bounding-box size, for
wheel_profile(). ENC1's revolved discs come out exactly square in plan; the pin
and legs do not, so this is what excludes them from the profile."""


@functools.cache
def wheel_profile():
    """ENC1's revolved shape, measured off the assembly STEP rather than
    hand-entered: WheelProfile(top, lip_od, lip_z0, lip_z1, main_od).

    ENC1 carries no row in c6remote-pos.csv, so it never reaches
    part_envelope(), which needs a placement to anchor on. Its solids are
    found the same way keepouts() finds it instead: nearest wheel_center(),
    filtered to WHEEL_ENVELOPE_OFFSET and to a square bounding box
    (WHEEL_SQUARENESS), which is what separates the revolved discs from the
    part's own pin and mounting legs.

    `top` is the highest point of anything in that set: the knob. `lip` is
    the widest disc, the flange a panel would normally clamp against; the
    case's wheel opening has to clear it for the shell to drop over the wheel
    from the front. `main` is the widest disc entirely at or above the lip's
    top face: the encoder's own body, the part that actually rotates and
    that a panel-mount bushing normally passes through rather than under.
    Five solids make up the assembly: a 32.00 barrel from z 0.545 to 3.545
    that passes through the board, the 34.00 lip from 3.545 to 4.145, a
    31.70 housing from 4.145 to 7.145 (this is `main`), a narrower 23.00
    knob riding inside that same span up to the 7.345 top, and an 8.00
    shaft or bushing alongside it; nothing above the lip is ever wider than
    the housing, so one radius covers the whole span up to the top.
    """
    wx, wy = wheel_center()
    near = []
    for solid in assembly_solids():
        box = solid.bounding_box()
        center = box.center()
        if math.hypot(center.X - wx, center.Y - wy) > WHEEL_ENVELOPE_OFFSET:
            continue
        if abs(box.size.X - box.size.Y) > WHEEL_SQUARENESS:
            continue
        near.append(box)
    if not near:
        raise ValueError(f"no wheel solids within {WHEEL_ENVELOPE_OFFSET} of wheel_center()")

    top = max(box.max.Z for box in near)
    lip = max(near, key=lambda box: box.size.X)
    above = [box for box in near if box.min.Z >= lip.max.Z - 0.01]
    if not above:
        raise ValueError("no solid sits above the wheel's lip")
    main = max(above, key=lambda box: box.size.X)

    return WheelProfile(
        top=top, lip_od=lip.size.X, lip_z0=lip.min.Z, lip_z1=lip.max.Z, main_od=main.size.X
    )


def _graphic_items(body):
    """Each fp_line, fp_rect, fp_poly and fp_circle as its own balanced substring.

    Regex alone cannot do this: a pattern spanning from one item's coordinates to
    the next item's layer tag matches happily and yields a mix of the two.
    """
    for match in re.finditer(r"\(fp_(?:line|rect|poly|circle)\b", body):
        depth = 0
        for i in range(match.start(), len(body)):
            if body[i] == "(":
                depth += 1
            elif body[i] == ")":
                depth -= 1
                if depth == 0:
                    yield body[match.start() : i + 1]
                    break


@functools.cache
def courtyards():
    """{ref: (x0, y0, x1, y1, side)} in STEP frame, from the board's courtyards.

    The only keepout that covers every part. Both 3D assemblies are blind to the
    eleven switches, whose model is VRML and so absent from the STEP, and to
    D2-D5 and J1, which have no model at all. Courtyards are 2D, so this bounds
    where a part sits, never how tall it is.
    """
    src = _require(KICAD_PCB).read_text()
    out = {}
    for block in re.finditer(r'\(footprint "[^"]+"(.*?)\n\t\)\n', src, re.S):
        body = block.group(1)
        ref = re.search(r'\(property "Reference" "([^"]+)"', body)
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", body)
        if not ref or not at:
            continue
        side = "bottom" if '(layer "B.Cu")' in body else "top"
        ox, oy = float(at.group(1)), float(at.group(2))
        angle = math.radians(float(at.group(3) or 0))

        pts = []
        for item in _graphic_items(body):
            if "CrtYd" not in item:
                continue
            pts += [
                (float(x), float(y))
                for x, y in re.findall(r"(?:xy|start|end) ([-\d.]+) ([-\d.]+)", item)
            ]
        if not pts:
            continue

        cos, sin = math.cos(angle), math.sin(angle)
        placed = [(x * cos - y * sin + ox, x * sin + y * cos + oy) for x, y in pts]
        xs = [p[0] for p in placed]
        ys = [p[1] for p in placed]
        out[ref.group(1)] = (min(xs), -max(ys), max(xs), -min(ys), side)
    return out


@functools.cache
def npth_pads(ref):
    """[(x, y, drill)] in STEP frame for a footprint's unplated holes.

    MK1's is its acoustic port: a 0.5 drill at (53.350, -31.582). The mic is on
    the board's bottom side and bottom-ported, so it hears through the board, and
    that hole is why the audio inlet belongs on the front of the case.
    """
    src = _require(KICAD_PCB).read_text()
    for block in re.finditer(r'\(footprint "[^"]+"(.*?)\n\t\)\n', src, re.S):
        body = block.group(1)
        found = re.search(r'\(property "Reference" "([^"]+)"', body)
        if not found or found.group(1) != ref:
            continue
        at = re.search(r"\(at ([-\d.]+) ([-\d.]+)(?: ([-\d.]+))?\)", body)
        ox, oy = float(at.group(1)), float(at.group(2))
        angle = math.radians(float(at.group(3) or 0))
        cos, sin = math.cos(angle), math.sin(angle)

        out = []
        for pad in re.finditer(
            r"\(pad \"[^\"]*\" np_thru_hole \w+\s*\(at ([-\d.]+) ([-\d.]+)"
            r"(?: [-\d.]+)?\)\s*\(size [-\d.]+ [-\d.]+\)\s*\(drill ([-\d.]+)\)",
            body,
        ):
            px, py, drill = (float(v) for v in pad.groups())
            out.append(
                (px * cos - py * sin + ox, -(px * sin + py * cos + oy), drill)
            )
        return out
    raise KeyError(f"no footprint {ref}")


def usb_envelope():
    """Full bounding box of the XIAO's USB-C shell, the solid overhanging
    the board's -Y edge: the U1 footprint anchor is a module corner and
    lands nowhere near the connector, so this is found by shape, not by
    ref. Every case feature near the connector, the local ceiling pocket
    over it and the blind relief in the end wall alike, needs the full
    plan footprint now that neither punches through to daylight, not just
    where it used to cross the board edge for a through-slot."""
    edge_y = board_profile().bounding_box().min.Y
    overhang = min(assembly_solids(), key=lambda s: s.bounding_box().min.Y)
    box = overhang.bounding_box()
    if box.min.Y >= edge_y:
        raise RuntimeError("no solid overhangs the board edge; USB not located")
    return box


def emitter_envelope():
    """Bounding box of D1's lens where it crosses the board's +Y edge.

    D1 is a horizontal through-hole emitter on the board's bottom side, so
    its body hangs under the board and fires along the board, out the +Y
    end: the same end U2 listens through, lower down. Only the part past
    the board's own edge ever has to pass through a case wall, so that is
    what this measures.

    Clipped rather than taken whole because the whole solid is 5.9 tall:
    it carries the leads bent up through the board and a rim wider than
    the lens, neither of which reaches the wall, and a window sized to
    that box would notch the front shell's skirt for parts that never
    arrive there. Same reasoning as usb_envelope() being found by shape
    rather than by ref: what the case needs is the part in the wall's way.
    """
    solid = part_solid("D1")
    box = solid.bounding_box()
    edge_y = board_profile().bounding_box().max.Y
    if box.max.Y <= edge_y:
        raise RuntimeError(
            "D1 does not reach the board's +Y edge, so nothing of it passes "
            "through the end wall; its window has to come from somewhere else"
        )

    y0, y1 = edge_y, box.max.Y + 1
    clip = Pos(box.center().X, (y0 + y1) / 2, box.center().Z) * Box(
        box.size.X + 2, y1 - y0, box.size.Z + 2
    )
    hit = solid.intersect(clip)
    solids = hit.solids() if hit else []
    if not solids:
        raise RuntimeError("D1's overhang clipped to nothing")
    out = solids[0].bounding_box()
    for extra in solids[1:]:
        out = out.add(extra.bounding_box())
    return out


def keepouts():
    """{ref: (min_z, max_z)} derived by matching assembly solids to placements."""
    placements = [(r, x, y) for r, (x, y, _, _) in components().items()]
    placements.append(("ENC1", *wheel_center()))
    agg = defaultdict(lambda: [math.inf, -math.inf])
    for solid in assembly_solids():
        box = solid.bounding_box()
        center = box.center()
        ref = min(
            placements, key=lambda p: math.hypot(p[1] - center.X, p[2] - center.Y)
        )[0]
        agg[ref][0] = min(agg[ref][0], box.min.Z)
        agg[ref][1] = max(agg[ref][1], box.max.Z)
    return {ref: tuple(z) for ref, z in agg.items()}


if __name__ == "__main__":
    import params

    box = board_profile().bounding_box()
    print(f"board {box.size.X:.2f} x {box.size.Y:.2f}")
    print(f"wheel centre {wheel_center()[0]:.3f}, {wheel_center()[1]:.3f}")
    for x, y, d in mounting_holes():
        print(f"hole {x:.3f}, {y:.3f} dia {d:.2f}")

    z = keepouts()
    top = max(hi for _, hi in z.values()) - params.BOARD_THICKNESS
    bottom = -min(lo for lo, _ in z.values())
    print(f"\nfront keepout {top:.2f} (param {params.FRONT_KEEPOUT})")
    print(f"back keepout {bottom:.2f} (param {params.BACK_KEEPOUT})")
    print("\ntallest above board face:")
    for ref, (_, hi) in sorted(z.items(), key=lambda kv: -kv[1][1])[:5]:
        print(f"  {ref:<6} {hi - params.BOARD_THICKNESS:5.2f}")
    print("deepest below board:")
    for ref, (lo, _) in sorted(z.items(), key=lambda kv: kv[1][0])[:5]:
        print(f"  {ref:<6} {-lo:5.2f}")

    lens = emitter_envelope()
    print(
        f"\nD1 lens at the +Y edge {lens.size.X:.2f} x {lens.size.Z:.2f}, "
        f"z {lens.min.Z:.2f} .. {lens.max.Z:.2f}, overhanging "
        f"{lens.size.Y:.2f} past it"
    )

    ir = part_envelope("U2", radius=3.0)
    print(
        f"U2 complete envelope {ir.size.X:.2f} x {ir.size.Y:.2f}, z "
        f"{ir.min.Z:.2f} .. {ir.max.Z:.2f}, receiving through the back along -Z"
    )

    profile = wheel_profile()
    print(f"\nwheel top {profile.top:.3f}")
    print(f"wheel lip {profile.lip_od:.2f} OD, z {profile.lip_z0:.3f} .. {profile.lip_z1:.3f}")
    print(f"wheel main body {profile.main_od:.2f} OD above it")
    disagreement = profile.lip_od - WHEEL_OD
    if abs(disagreement) > 0.1:
        print(f"WHEEL_OD param {WHEEL_OD:.2f} disagrees with the measured lip by {disagreement:+.2f}")
    else:
        print(f"WHEEL_OD param {WHEEL_OD:.2f} agrees with the measured lip")
