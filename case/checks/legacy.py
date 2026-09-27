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
"""

from build123d import Box, Cylinder, Pos

import board
import case
import params
from model.stack import LEGACY_BOARD_TOP, LEGACY_SWITCH_TOP, SUPPORT_TOP, SWITCH_TOP

from .common import TOLERANCE, Problem, _fill_fraction, _volume
from .keypad import plunger_bottoms

TOP_PAD = "case-pad-fdm-v2-top"
"""The V2 top pad's export stem, as checks/shells.py and the viewer name parts."""


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


def legacy_nib_contact(top):
    """Each V2 switch gets a nib at the V3 plungers' engagement, and the V3
    plungers the lobe keeps still reach theirs.

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
        part=TOP_PAD,
    )
    problems += plunger_bottoms(
        top,
        {ref: parts[ref][:2] for ref in refs},
        SWITCH_TOP,
        what="V3 plunger",
        part=TOP_PAD,
    )
    if len(top.solids()) != 1:
        problems.append(
            Problem(
                f"the V2 top pad is {len(top.solids())} solids, so a nib is "
                "not fused into the lobe",
                part=TOP_PAD,
            )
        )
    return problems


PRESS_STATES = (("released", 0), ("pressed", -params.SWITCH_TRAVEL))
"""The two pad positions each V2 top pad fit is probed at."""


def legacy_top_pad_fits(front_fdm, top):
    """The V2 top pad clears the FDM front released and through switch travel."""
    problems = []
    for state, offset in PRESS_STATES:
        fouled = _volume(front_fdm.intersect(Pos(0, 0, offset) * top))
        if fouled > TOLERANCE:
            problems.append(
                Problem(
                    f"the V2 top pad fouls the FDM front by {fouled:.2f} mm3 "
                    f"when {state}",
                    part=TOP_PAD,
                )
            )
    return problems


def legacy_screw_head():
    """The V2 retention screw's head envelope, on the V2 board's top face."""
    x, y = board.legacy_retention_point()
    return Pos(x, y, LEGACY_BOARD_TOP + params.SCREW_HEAD_H / 2) * Cylinder(
        radius=params.SCREW_HEAD_D / 2, height=params.SCREW_HEAD_H
    )


def legacy_top_pad_clears_screw(top):
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
                    f"the V2 top pad hits the V2 screw head by {fouled:.2f} mm3 "
                    f"when {state}",
                    box=head,
                    part=TOP_PAD,
                )
            )
    return problems


def legacy_screw_gaps(top):
    """{state: the built pad's closest approach to the V2 screw head}, for the
    pass line. Released it is the kept V3 SW1 plunger in plan, and pressed it is
    the web over the head's top."""
    head = legacy_screw_head()
    return {state: head.distance_to(Pos(0, 0, offset) * top) for state, offset in PRESS_STATES}
