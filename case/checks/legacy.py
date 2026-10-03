"""The V2 retention post, the one thing in this case built on the old board.

V2 and V3 share an outline and an origin but no mounting hole, so a V2 board
would otherwise sit in this case loose. The back shell carries one tapped post
under V2's upper-right hole. These passes hold what that post owes the V3
board it shares the cavity with, and what the pilot owes the floor it is
drilled into.

Retention only. Nothing here says a V2 board works in this case: its IR parts
and its upper keys land in the wrong place regardless, and no post moves them.

The V2 top pad is the one part that answers the upper keys. It is the FDM pad's
SW1/SW2 lobe with a nib added over each V2 switch, so its passes hold the nibs'
engagement on a board that clamps on the post, the lobe's fit in the FDM front,
and its clearance to the V2 screw head that the kept V3 SW1 plunger passes close
by.

The V2 one-piece TPU top pad adds a skirt to that lobe. Its passes hold the
skirt to the built plunger bottoms of the V3 pad, off the V2 parts, and the board reader that
carries the V3 part bodies to their V2 placements.
"""

import copy
import math

from build123d import Box, Cylinder, Pos

import board
import case
import params
from model.stack import (
    CAP_TOP,
    FDM_FACE,
    LEGACY_SWITCH_TOP,
    SUPPORT_TOP,
    SWITCH_TOP,
)

from .common import TOLERANCE, Problem, _fill_fraction, _ray_runs, _volume
from .common import PROBE_D
from .keypad import (
    PLUNGER_CONTACT_TOLERANCE,
    _skirt_zones,
    pad_clears_board,
    pad_skirt_depth,
    plunger_bottoms,
)

TOP_PAD = "case-pad-fdm-v2-top"
"""The V2 top pad's export stem, as checks/shells.py and the viewer name parts."""

MOULDED_TOP_PAD = "case-pad-v2-top"
"""The moulded V2 top pad's export stem. It takes the separate caps."""

TPU_TOP_PAD = "case-pad-tpu-v2-top"
"""The V2 one-piece TPU top pad's export stem."""


def legacy_point_in_frame():
    """The V2 hole this is all built on, still where the reader says it is.

    board.legacy_mounting_holes() raises when the two revisions stop sharing an
    outline, so calling it is the pass: it is the guard, and a pass that merely
    restated its result would be the vacuous kind this model has shipped before.
    What is added here is the count and the choice, which the raise does not
    cover: three holes, and the one taken is the one furthest +Y and then +X.
    """
    holes = board.legacy_mounting_holes()
    point = board.legacy_retention_point()
    problems = []
    if len(holes) != 3:
        problems.append(f"V2 has {len(holes)} mounting holes, not three")
    behind = [p for p in holes if p != point and (p[1], p[0]) > (point[1], point[0])]
    if behind:
        problems.append(
            f"{behind} sits past the retention point, so it is not upper-right"
        )
    return problems


def legacy_post_clearance():
    """The built post against everything in the V3 cavity that has a solid.

    The courtyard side of this, which is what sees the switches and D2-D5, is
    feature_clashes() in checks/hardware.py. Here is what has a shape: every
    assembly solid, the board itself at rest, and the cell.
    """
    post = case.legacy_retention_post()
    problems = []

    profile = board.board_profile().bounding_box()
    at_rest = Pos(
        profile.center().X, profile.center().Y, params.BOARD_THICKNESS / 2
    ) * Box(profile.size.X, profile.size.Y, params.BOARD_THICKNESS)
    if _volume(post.intersect(at_rest)) > TOLERANCE:
        problems.append("V2 retention post touches the V3 board at rest")

    gap = -post.bounding_box().max.Z
    if abs(gap - params.SUPPORT_GAP) > TOLERANCE:
        problems.append(
            f"V2 retention post stops {gap:.2f} below the board, not "
            f"{params.SUPPORT_GAP:.2f}"
        )

    for solid in board.assembly_solids():
        overlap = _volume(post.intersect(solid))
        if overlap <= TOLERANCE:
            continue
        box = solid.bounding_box()
        problems.append(
            "V2 retention post hits assembly solid at "
            f"({box.center().X:.2f}, {box.center().Y:.2f}) by {overlap:.2f} mm3"
        )

    if _volume(post.intersect(case.cell_envelope())) > TOLERANCE:
        problems.append("V2 retention post hits the cell envelope")

    # Not against support_obstacles(). Those keepouts are sized for the ledge's
    # own raked underside at the wall and reach several mm below anything the
    # board carries, so a free-standing column in the middle of the cavity fails
    # them on air: the post's root chamfer clips D1's keepout 3 mm under D1's
    # own lowest solid. Courtyards at their real z are feature_clashes()' job.
    for x, y in case.mount_points():
        head_r = params.SCREW_HEAD_D / 2
        head = Pos(x, y, -params.SCREW_HEAD_H / 2) * Cylinder(
            radius=head_r, height=params.SCREW_HEAD_H
        )
        if _volume(post.intersect(head)) > TOLERANCE:
            problems.append(f"V2 retention post hits the V3 screw head at ({x}, {y})")

    return problems


def legacy_post_merged(back):
    """The post is part of the back shell, not a second solid beside it.

    A solid count alone is not enough: the shell would be one solid with no post
    at all. So this asks the built shell for material in the ring the post's
    wall occupies just under its top, which is only there if the post survived
    the fuse and the pilot did not eat it.
    """
    problems = []
    if len(back.solids()) != 1:
        problems.append(
            f"back shell has {len(back.solids())} solids with the post fused"
        )

    x, y = board.legacy_retention_point()
    mid_r = (params.BOSS_PILOT_D / 2 + params.LEGACY_RETENTION_OD / 2) / 2
    # Top and bottom of the thread, not the top alone. This is also what stops
    # legacy_pilot_blind()'s open half reading as open on bare cavity air: the
    # bore is only meaningfully open if there is post wall around it, and that
    # wall has to be there over the whole engagement rather than at one height.
    depths = {
        "under its top": SUPPORT_TOP - 0.2,
        "at the pilot's bottom": SUPPORT_TOP - params.BOSS_PILOT_DEPTH + 0.2,
    }
    for label, z in depths.items():
        for dx, dy, where in (
            (mid_r, 0, "+x"),
            (-mid_r, 0, "-x"),
            (0, mid_r, "+y"),
            (0, -mid_r, "-y"),
        ):
            probe = Pos(x + dx, y + dy, z) * Cylinder(radius=0.15, height=0.2)
            filled = _fill_fraction(back, probe)
            if filled < 1 - TOLERANCE:
                problems.append(
                    f"post wall on {where} is only {filled:.0%} material {label}"
                )
    return problems


def legacy_pilot_blind(back):
    """The pilot is open its full depth, and stops inside the post.

    Both halves matter and neither implies the other. A pilot that never got
    cut takes no screw; one that ran through the floor is a hole in the
    outside of the case.
    """
    x, y = board.legacy_retention_point()
    outer, _ = case.legacy_retention_floors()
    depth = params.BOSS_PILOT_DEPTH
    problems = []

    bore = Pos(x, y, SUPPORT_TOP - depth / 2) * Cylinder(
        radius=params.BOSS_PILOT_D / 2 - 0.1, height=depth
    )
    filled = _fill_fraction(back, bore)
    if filled > TOLERANCE:
        problems.append(f"pilot is {filled:.0%} blocked over its {depth:.1f} of depth")

    # Measured, not assumed: the pilot's own bottom against the back's own
    # exterior surface. Taken before the probe because a pilot that has already
    # passed the surface leaves no column under it to probe, and asking for one
    # is a negative height rather than a failure message.
    floor_top = SUPPORT_TOP - depth
    if floor_top <= outer:
        problems.append(
            f"pilot bottom is at {floor_top:.2f}, at or past the exterior floor "
            f"at {outer:.2f}, so it is a hole through the outside of the case"
        )
        return problems

    plug = Pos(x, y, (floor_top + outer) / 2) * Cylinder(
        radius=params.BOSS_PILOT_D / 2 + 0.1, height=floor_top - outer
    )
    solid = _fill_fraction(back, plug)
    if solid < 1 - TOLERANCE:
        problems.append(
            f"only {solid:.0%} of the {floor_top - outer:.2f} under the pilot is "
            "material, so it is not blind"
        )
    return problems


def legacy_post_headroom():
    """The V2 screw head has somewhere to sit, and the post has thread to take it.

    The head lands on the V2 board's own top face, so what it needs is bare
    board around the hole, which the V2 outline cannot answer for on its own.
    What this holds instead is the two numbers the case does set: the engagement
    the pilot offers, and the wall left around it.
    """
    problems = []
    wall = (params.LEGACY_RETENTION_OD - params.BOSS_PILOT_D) / 2
    if wall < params.WALL / 3:
        problems.append(f"only {wall:.2f} of wall around the pilot")
    post = case.legacy_retention_post().bounding_box()
    height = post.max.Z - post.min.Z
    if height < params.BOSS_PILOT_DEPTH + params.FLOOR:
        problems.append(
            f"post is {height:.2f} tall, too short to hold "
            f"{params.BOSS_PILOT_DEPTH:.1f} of pilot clear of a "
            f"{params.FLOOR:.1f} floor"
        )
    return problems


def _column_bottom(pad, x, y):
    """Lowest Z of the built pad inside a thin column at (x, y)."""
    column = Pos(x, y, 0) * Box(PROBE_D, PROBE_D, 100)
    hit = pad.intersect(column).solids()
    return min((s.bounding_box().min.Z for s in hit), default=None)


def _plunger_over_nib(top, refs, parts, legacy, part=TOP_PAD):
    """Each kept V3 plunger's built bottom stands SWITCH_TRAVEL above the lowest
    built nib bottom, read off the pad and not off the parameters."""
    problems = []
    nib = [_column_bottom(top, *legacy[ref][:2]) for ref in refs]
    if None in nib:
        return [Problem("a V2 nib has no material at its point", part=part)]
    low = min(nib)
    for ref in refs:
        x, y = parts[ref][:2]
        bottom = _column_bottom(top, x, y)
        if bottom is None:
            continue
        gap = bottom - low
        if gap < params.SWITCH_TRAVEL - PLUNGER_CONTACT_TOLERANCE:
            problems.append(
                Problem(
                    f"{ref}'s kept V3 plunger bottom at {bottom:.3f} is only "
                    f"{gap:.3f} above the V2 nib at {low:.3f}, less than "
                    "SWITCH_TRAVEL, so it can bottom on the V2 switch body "
                    "before the switch makes",
                    at=(x, y, bottom),
                    part=part,
                )
            )
    return problems


def legacy_nib_contact(top, part=TOP_PAD, label="the V2 top pad"):
    """Each V2 switch gets a nib LEGACY_NIB_EXTENSION below its top, and the V3
    plungers the lobe keeps reach the V3 switch tops by the same extension.
    Each kept plunger must also stand at least SWITCH_TRAVEL above the lowest
    nib, so it cannot land on a V2 switch body before the switch makes.

    Probed on the built part at both sets of points, because the nibs are the
    only thing that differs from the FDM pad's own lobe: a nib built to the V3
    switch top would stand SUPPORT_GAP short of a V2 switch and read as present.
    """
    legacy = board.legacy_components()
    parts = board.components()
    refs = case.island_refs("second")
    problems = plunger_bottoms(
        top,
        {ref: legacy[ref][:2] for ref in refs},
        LEGACY_SWITCH_TOP,
        what="V2 nib",
        part=part,
        extension=params.LEGACY_NIB_EXTENSION,
    )
    problems += plunger_bottoms(
        top,
        {ref: parts[ref][:2] for ref in refs},
        SWITCH_TOP,
        what="V3 plunger",
        part=part,
        extension=params.LEGACY_NIB_EXTENSION,
    )
    problems += _plunger_over_nib(top, refs, parts, legacy, part)
    if len(top.solids()) != 1:
        problems.append(
            Problem(
                f"{label} is {len(top.solids())} solids, so a nib is "
                "not fused into the lobe",
                part=part,
            )
        )
    return problems


LEGEND_RAYS = 6
"""Points per glyph the legend probe casts a ray down through."""

LEGEND_START_ABOVE = 0.5
"""How far above CAP_TOP each legend ray starts."""


def _inside_points(glyph, count):
    """Up to `count` (x, y) points truly inside a glyph solid, off a grid over
    its box, so a concave glyph cannot hand back a centroid that lies outside."""
    box = glyph.bounding_box()
    zmid = (box.min.Z + box.max.Z) / 2
    found = []
    steps = 12
    for i in range(1, steps):
        for j in range(1, steps):
            x = box.min.X + (box.max.X - box.min.X) * i / steps
            y = box.min.Y + (box.max.Y - box.min.Y) * j / steps
            if glyph.is_inside((x, y, zmid)):
                found.append((x, y))
    stride = max(1, len(found) // count)
    return found[::stride][:count]


def _column_top(pad, x, y, side):
    """Highest point of `pad` over a keytop column at (x, y), read off the built pad."""
    column = Pos(x, y, CAP_TOP) * Box(side, side, 2.0)
    hit = pad.intersect(column).solids()
    return max((v.bounding_box().max.Z for v in hit), default=float("-inf"))


def legacy_keytops_level(top, main, part=TOP_PAD):
    """Each SW1/SW2 keytop of the V2 top pad stands level with a grid keytop of
    the main pad `main`, with its legend cut open at that top.

    Both tops are read off the built pads, the grid reference being SW7 on
    `main`. The copies are deep because a boolean against the shared cached
    pad leaves it unusable for the next pass (fits, below). The legend is read
    by rays cast down through points inside each glyph: the first material
    along each must start LEGEND_DEPTH below the keytop top.
    """
    pad = copy.deepcopy(top)
    grid = copy.deepcopy(main)
    gx, gy = board.components()["SW7"][:2]
    level = _column_top(grid, gx, gy, case.fdm_cap_body("SW7"))
    problems = []
    for ref in case.island_refs("second"):
        x, y = board.components()[ref][:2]
        column_top = _column_top(pad, x, y, case.fdm_cap_body(ref))
        if abs(column_top - level) > TOLERANCE:
            problems.append(
                Problem(
                    f"{ref}'s V2 keytop tops out at {column_top:.3f} against "
                    f"SW7's {level:.3f} on the main pad, so it is not level",
                    at=(x, y, column_top),
                    part=part,
                )
            )
        want = LEGEND_START_ABOVE + params.LEGEND_DEPTH
        sites = 0
        for glyph in case.legend_solids(ref, x, y):
            for px, py in _inside_points(glyph, LEGEND_RAYS):
                sites += 1
                z0 = column_top + LEGEND_START_ABOVE
                runs = _ray_runs(
                    pad, (px, py, z0), (px, py, column_top - 2 * params.LEGEND_DEPTH - 1)
                )
                start = runs[0][0] if runs else None
                if start is None or abs(start - want) > TOLERANCE:
                    got = "no material" if start is None else f"{z0 - start:.3f}"
                    problems.append(
                        Problem(
                            f"{ref}'s V2 legend floor is at {got} against "
                            f"{want:.3f}, so it is not cut open at the keytop top",
                            at=(px, py, column_top),
                            part=part,
                        )
                    )
                    break
        if sites == 0:
            problems.append(
                Problem(
                    f"{ref}'s legend has no interior point to probe",
                    at=(x, y, column_top),
                    part=part,
                )
            )
    return problems


PRESS_STATES = (("released", 0), ("pressed", -params.SWITCH_TRAVEL))
"""The two pad positions each V2 top pad fit is probed at."""


def legacy_top_pad_fits(
    front_fdm, top, part=TOP_PAD, label="the V2 top pad", front="the FDM front"
):
    """The V2 top pad clears the FDM front released and through switch travel.

    `label` and `front` name the pad and the front in the messages."""
    problems = []
    for state, offset in PRESS_STATES:
        fouled = _volume(front_fdm.intersect(Pos(0, 0, offset) * top))
        if fouled > TOLERANCE:
            problems.append(
                Problem(
                    f"{label} fouls {front} by {fouled:.2f} mm3 "
                    f"when {state}",
                    part=part,
                )
            )
    return problems


def legacy_screw_head():
    """The V2 retention screw's head envelope, on the V2 board's top face."""
    return case.legacy_screw_head()


def legacy_top_pad_clears_screw(top, part=TOP_PAD, label="the V2 top pad"):
    """The V2 top pad stays off the V2 screw head, released and pressed.

    The kept V3 SW1 plunger passes the head closest, in plan, and the press
    takes the whole lobe down towards the head's top.
    """
    head = legacy_screw_head()
    problems = []
    for state, offset in PRESS_STATES:
        fouled = _volume(head.intersect(Pos(0, 0, offset) * top))
        if fouled > TOLERANCE:
            problems.append(
                Problem(
                    f"{label} hits the V2 screw head by {fouled:.2f} mm3 "
                    f"when {state}",
                    box=head,
                    part=part,
                )
            )
    return problems


def legacy_screw_gaps(top):
    """{state: the built pad's closest approach to the V2 screw head}, for the
    pass line. Released it is the kept V3 SW1 plunger in plan, and pressed it is
    the web over the head's top."""
    head = legacy_screw_head()
    return {state: head.distance_to(Pos(0, 0, offset) * top) for state, offset in PRESS_STATES}


def legacy_skirt_nibs():
    """(x, y) of each V2 nib, where the skirt clearance columns are cut."""
    legacy = board.legacy_components()
    return [legacy[ref][:2] for ref in case.island_refs("second")]


def legacy_skirt_depth(pad, reference, fdm=True):
    """(problems, lines): the V2 pad's skirt walks the second lobe down to the
    `reference` V1 pad's built plunger bottoms, the plane the V1 skirt ends on,
    flush with the web and PAD_SKIRT_T thick, and is open only where a moved V2
    part or the V2 screw head stands up to it. `fdm` false reads a moulded pad,
    whose web has no groove chamfer."""
    solids = [solid for _, solid in case.legacy_skirt_obstacles()]
    return pad_skirt_depth(
        pad,
        fdm,
        False,
        lobes=("second",),
        zones=_skirt_zones(solids, case.PAD_SKIRT_BOTTOM),
        reference=reference,
    )


def legacy_skirt_clears_board(pad):
    """(problems, line): the built V2 TPU pad keeps PAD_SKIRT_CLEARANCE off the
    moved V2 parts and the V2 screw head, with columns cut round the V2 and V3
    switch centres, which are the nibs and the kept plungers."""
    parts = board.components()
    columns = legacy_skirt_nibs() + [parts[ref][:2] for ref in case.island_refs("second")]
    return pad_clears_board(
        pad,
        obstacles=case.legacy_skirt_obstacles(),
        columns=columns,
        floor=case.PAD_SKIRT_BOTTOM - 1.0,
    )


def _round_quarter(angle):
    """`angle` in degrees as a whole number of quarter turns, or None."""
    turns = angle / 90
    return round(turns) if abs(turns - round(turns)) < 1e-6 else None


def legacy_part_moves():
    """(problems, moved): each V2 top-side part's moved V3 body sits where the V2
    placement says.

    Read off the built solids. For every V2 top-side ref with a V3 body, the
    moved solid's bounding-box centre must sit at the V2 placement, offset by
    the V3 solid's own offset from the V3 placement turned by the V2 rotation
    less the V3 one. A part on the other board side in V2 is turned over, so its
    Y offset and its height about the board mid plane flip first. Every angle is
    a quarter turn, which keeps a box centre exact under the turn.
    """
    v3, v2 = board.components(), board.legacy_components()
    z_mid = sum(board.board_z_span()) / 2
    problems, moved = [], []
    for ref in sorted(board.placement_groups()):
        if ref not in v2 or v2[ref][3] != "top":
            continue
        x3, y3, r3, side3 = v3[ref]
        x2, y2, r2, side2 = v2[ref]
        quarters = _round_quarter(r2 - r3)
        if quarters is None:
            problems.append(f"{ref} turns {r2 - r3} degrees, not a quarter turn")
            continue
        before, after = board.placement_groups()[ref], board.legacy_part_solids(ref)
        if len(before) != len(after):
            problems.append(f"{ref} has {len(before)} V3 solids but {len(after)} moved")
            continue
        for old, new in zip(before, after):
            c0, c1 = old.bounding_box().center(), new.bounding_box().center()
            dx, dy, dz = c0.X - x3, c0.Y - y3, c0.Z
            # Undo V3's own turn, flip if the side changed, then turn to V2's.
            a = math.radians(-r3)
            dx, dy = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
            if side3 != side2:
                dy, dz = -dy, 2 * z_mid - dz
            a = math.radians(r2)
            dx, dy = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
            want = (x2 + dx, y2 + dy, dz)
            got = (c1.X, c1.Y, c1.Z)
            # A body symmetric about its anchor keeps its centre under any turn,
            # so the box size is read too: it swaps X and Y on an odd quarter.
            size0, size1 = old.bounding_box().size, new.bounding_box().size
            odd = quarters % 2
            want_size = (size0.Y, size0.X) if odd else (size0.X, size0.Y)
            if max(abs(w - g) for w, g in zip(want_size, (size1.X, size1.Y))) > TOLERANCE:
                problems.append(
                    f"{ref}'s moved body measures {size1.X:.3f} x {size1.Y:.3f} "
                    f"but a {quarters * 90:g} degree turn of its V3 body gives "
                    f"{want_size[0]:.3f} x {want_size[1]:.3f}"
                )
            if max(abs(w - g) for w, g in zip(want, got)) > TOLERANCE:
                problems.append(
                    f"{ref}'s moved body centres at ({got[0]:.3f}, {got[1]:.3f}, {got[2]:.3f}) "
                    f"but its V2 placement puts it at ({want[0]:.3f}, {want[1]:.3f}, {want[2]:.3f})"
                )
        if (x2, y2, r2, side2) != (x3, y3, r3, side3):
            moved.append(ref)
    return problems, moved


def moulded_top_pad_caps_rest(pad, caps):
    """The standard SW1 and SW2 caps rest on the moulded V2 top pad's web.

    The caps are the same parts the moulded pad takes. The pad keeps the V3 stems
    at the V3 positions, so each cap must stand on its web and must not overlap
    the pad while STEM_GRIP is zero or less.
    """
    from .caps import caps_rest_on_pad

    refs = case.island_refs("second")
    return caps_rest_on_pad(
        pad, {ref: caps[ref] for ref in refs}, label="moulded V2 top pad"
    )
