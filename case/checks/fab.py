"""Fab walls: the front and back shells keep the PCBWay minimum wall for
FAB_PROCESS. PCBWay holds an order with a thinner wall until the customer
accepts the risk. Other passes hold a few named walls, such as the LED ring
roof and the counterbore lands. No other pass measures every wall the way
PCBWay does.

The pass reads the STL that PCBWay receives, not the solid. It casts a ray
inward from even samples over each surface, and the distance to the next
surface is the wall there. The angle at the far face sorts each thin reading.
A wall has near-parallel faces. A taper is an edge that narrows to a line. A
square corner is not thin, so the pass ignores it.
"""

import contextlib
import logging
import tempfile
from pathlib import Path

import numpy as np
import trimesh

import cache
import params
from model.features import write_features

from .common import Problem

PARTS = ("c6remote-case-front.stl", "c6remote-case-back.stl")
"""The PCBWay SLA or SLS parts, by export name. The FDM front, the pads, the
caps and the IR window are printed elsewhere."""

SAMPLES_PER_MM2 = 10
SEED = 1
RAY_OFFSET = 1e-3
"""How far inside the surface a ray starts, so it cannot hit its own triangle."""

EDGE_ANGLE = 30
"""Degrees between the ray and the outward normal of the face it hits, which is
the inside angle of the material. A thin reading at or below it is a wall."""

CORNER_ANGLE = 80
"""A thin reading at or above this angle is a square corner, not a thin wall: a
sample near the corner reads near zero across it. Between EDGE_ANGLE and this
angle, a thin reading is a taper."""

BOX_MARGIN = 0.05
NO_FEATURE = "(no feature box)"

MAX_MISS = 0.001
"""Largest share of a part's rays that can find no wall."""

FLOOR_TOLERANCE = 0.03
# The thin area moves a few percent when the mesh changes, and much more on a
# small feature.
AREA_TOLERANCE = 0.25
AREA_SLACK = 1.0

# Key (STL name, feature id), value (floor_mm, area_cap_mm2, note) for a feature
# that is under the PCBWay minimum today and is accepted. Set floor_mm near the
# current thinnest wall reading, or None for a feature that is thin only at
# tapered edges. Set area_cap_mm2 at about the current thin area under
# FAB_PROCESS.
FRONT, BACK = PARTS

LAND = (
    "counterbore land under the dish, LAND_FLOOR_MIN in checks/keypad.py. The face hole "
    "lead-in tapers to the hole wall"
)
FACE_HOLE = "the counterbore land, read from the face hole"
POCKET_LIP = "lip under the side catch pocket, SIDE_CATCH_LOWER_LAND"
PILOT = "cap over the end screw pilot tip, END_SCREW_BLOCK_D less END_SCREW_PILOT_DEPTH"
KNOCKOUT = "Qwiic breakaway cover at the SLA minimum, QWIIC_KNOCKOUT_T and QWIIC_KNOCKOUT_TAB_T"
RESET = "reset guide tube, RESET_GUIDE_WALL"
SCREW_CUT = "taper where the end screw cuts meet"

ACCEPTED = {
    (FRONT, "keypad_recess"): (
        0.54, 219.8, "dish face over the LED ring roof and the counterbore lands"
    ),
    (FRONT, "led_ring_channel"): (
        0.77, 280.4, "LED ring roof: LED_RING_FACE_ROOF is vertical and the face slopes"
    ),
    (FRONT, "wheel_opening"): (0.79, 89.2, "dish face over the LED ring roof"),
    (FRONT, "key.SW1.counterbore"): (0.60, 9.4, LAND),
    (FRONT, "key.SW2.counterbore"): (0.60, 11.2, LAND),
    (FRONT, "key.SW3.counterbore"): (0.57, 14.4, LAND),
    (FRONT, "key.SW4.counterbore"): (0.55, 22.0, LAND),
    (FRONT, "key.SW5.counterbore"): (0.57, 15.0, LAND),
    (FRONT, "key.SW6.counterbore"): (0.76, 13.2, LAND),
    (FRONT, "key.SW7.counterbore"): (0.72, 24.1, LAND),
    (FRONT, "key.SW8.counterbore"): (0.76, 13.9, LAND),
    (FRONT, "key.SW9.counterbore"): (0.58, 13.1, LAND),
    (FRONT, "key.SW10.counterbore"): (0.55, 23.1, LAND),
    (FRONT, "key.SW11.counterbore"): (0.58, 15.1, LAND),
    (FRONT, "key.SW1.face_hole"): (0.71, 1.7, FACE_HOLE),
    (FRONT, "key.SW2.face_hole"): (0.71, 2.1, FACE_HOLE),
    (FRONT, "key.SW3.face_hole"): (0.68, 4.1, FACE_HOLE),
    (FRONT, "key.SW4.face_hole"): (0.66, 7.7, FACE_HOLE),
    (FRONT, "key.SW5.face_hole"): (0.68, 3.6, FACE_HOLE),
    (FRONT, "key.SW6.face_hole"): (0.76, 3.2, FACE_HOLE),
    (FRONT, "key.SW7.face_hole"): (0.72, 7.9, FACE_HOLE),
    (FRONT, "key.SW8.face_hole"): (0.76, 3.7, FACE_HOLE),
    (FRONT, "key.SW9.face_hole"): (0.68, 3.9, FACE_HOLE),
    (FRONT, "key.SW10.face_hole"): (0.67, 6.2, FACE_HOLE),
    (FRONT, "key.SW11.face_hole"): (0.68, 4.6, FACE_HOLE),
    (FRONT, "support_runs.+x.1"): (0.61, 3.8, POCKET_LIP),
    (FRONT, "support_runs.-x.1"): (0.62, 3.2, POCKET_LIP),
    (FRONT, "side_catch_pockets.+x"): (0.65, 3.4, POCKET_LIP),
    (FRONT, "side_catch_pockets.-x"): (0.64, 3.3, POCKET_LIP),
    (FRONT, "end_screw_pilot"): (0.50, 1.8, PILOT),
    (FRONT, "end_screw_block"): (
        0.50, 7.2, PILOT + ", and a taper where the block ramp runs out"
    ),
    (FRONT, "skirt_lead_in.1"): (None, 0.3, "taper at the skirt lead-in chamfer"),
    (FRONT, "skirt_lead_in.2"): (None, 0.3, "taper at the skirt lead-in chamfer"),
    (FRONT, "skirt_stiffener"): (
        None, 0.2, "taper where the stiffener meets the skirt lead-in"
    ),
    (BACK, "qwiic_knockout_panel"): (0.79, 38.2, KNOCKOUT),
    (BACK, "qwiic_knockout_tab.+y"): (0.79, 1.4, KNOCKOUT),
    (BACK, "qwiic_knockout_tab.-y"): (0.79, 1.7, KNOCKOUT),
    (BACK, "reset_guide"): (0.62, 45.1, RESET),
    (BACK, "reset_bore"): (
        0.61, 24.8, RESET + ", and a taper where the bore leaves the rolled floor"
    ),
    (BACK, "(no feature box)"): (
        None, 0.7, "taper where the reset bore leaves the rolled back floor"
    ),
    (BACK, "catch_detents.+x"): (None, 6.8, "nose of the catch detent wedge"),
    (BACK, "catch_detents.-x"): (None, 7.6, "nose of the catch detent wedge"),
    (BACK, "side_catch_detents.+x"): (None, 0.1, "edge of the side catch detent"),
    (BACK, "end_screw.head"): (None, 0.7, SCREW_CUT),
    (BACK, "end_screw.clearance"): (None, 1.0, SCREW_CUT),
    (BACK, "end_screw.wall_chamfer"): (None, 3.0, SCREW_CUT),
    (BACK, "qwiic_slot"): (None, 0.4, "taper at the Qwiic slot edge"),
    (BACK, "ir_window_opening"): (None, 0.1, "taper at the IR window opening edge"),
}

FIRST_REACH = 4.0
REACH_GROWTH = 4.0
"""Ray length of the first cast, and the factor for each later cast. trimesh's
RayMeshIntersector boxes each ray out to the mesh bounds, so a diagonal ray
takes most of the triangles as candidates: on a 160k-face test shell it took
3800 per ray on average. A short cast keeps the box small, and only the rays
without a hit go on to the next, longer cast."""

RAY_CHUNK = 4096
MIN_RAY_CHUNK = 16
"""Rays per rtree query in the first cast. Later casts take fewer, by the
square of the reach, so each query returns a similar number of candidates."""

GIVE_UP_SHARE = 0.5

PAIR_CHUNK = 500_000
"""Ray and triangle pairs per narrow-phase step, to bound memory."""

BARY_TOL = 1e-7
"""Slack on the barycentric test, so a ray through a shared edge hits one of
the two triangles, not neither."""

LABEL_CHUNK = 4096


@contextlib.contextmanager
def _quiet_trimesh():
    """sample_surface_even logs a warning when it returns fewer points than
    asked, and the rays count already says so."""
    logger = logging.getLogger("trimesh")
    level = logger.level
    logger.setLevel(logging.ERROR)
    try:
        yield
    finally:
        logger.setLevel(level)


def _dot(a, b):
    return np.einsum("ij,ij->i", a, b)


def _intersect(triangles, origins, directions, reach):
    """Moller-Trumbore: the ray length to each paired triangle, inf for none."""
    v0 = triangles[:, 0]
    e1 = triangles[:, 1] - v0
    e2 = triangles[:, 2] - v0
    p = np.cross(directions, e2)
    det = _dot(e1, p)
    # Only a face the ray leaves through can end the wall, so an origin pushed
    # into air by RAY_OFFSET does not read zero.
    ok = det < -1e-12
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    s = origins - v0
    u = _dot(s, p) * inv
    q = np.cross(s, e1)
    v = _dot(directions, q) * inv
    t = _dot(e2, q) * inv
    hit = (
        ok
        & (u >= -BARY_TOL)
        & (v >= -BARY_TOL)
        & (u + v <= 1 + BARY_TOL)
        & (t > 0)
        & (t <= reach)
    )
    return np.where(hit, t, np.inf)


def _cast_chunk(tree, triangles, origins, directions, reach):
    """Nearest hit within `reach` for each ray: distance and triangle."""
    ends = origins + directions * reach
    ids, counts = tree.intersection_v(
        np.minimum(origins, ends) - 1e-5, np.maximum(origins, ends) + 1e-5
    )
    owner = np.repeat(np.arange(len(origins)), counts.astype(np.int64))
    best = np.full(len(origins), np.inf)
    best_tri = np.full(len(origins), -1, dtype=np.int64)
    for start in range(0, len(ids), PAIR_CHUNK):
        ray = owner[start:start + PAIR_CHUNK]
        face = ids[start:start + PAIR_CHUNK]
        t = _intersect(triangles[face], origins[ray], directions[ray], reach)
        np.minimum.at(best, ray, t)
        won = np.isfinite(t) & (t == best[ray])
        best_tri[ray[won]] = face[won]
    return best, best_tri


def _cast(mesh, origins, directions):
    """Distance to the nearest hit and its triangle per ray, inf and -1 for a
    miss. Uses the rtree index, so embree never changes the result."""
    tree = mesh.triangles_tree
    triangles = mesh.triangles
    dist = np.full(len(origins), np.inf)
    tri = np.full(len(origins), -1, dtype=np.int64)
    whole = float(np.linalg.norm(mesh.extents)) + 1.0
    # Most of a sound part's surface faces across its thinnest extent. If most
    # rays still have no hit past that extent, the normals or the cast are
    # broken, and a full-length cast of them would take many minutes.
    give_up = float(mesh.extents.min())
    todo = np.arange(len(origins))
    reach = FIRST_REACH
    while len(todo):
        reach = min(reach, whole)
        size = max(MIN_RAY_CHUNK, int(RAY_CHUNK * (FIRST_REACH / reach) ** 2))
        for start in range(0, len(todo), size):
            rays = todo[start:start + size]
            dist[rays], tri[rays] = _cast_chunk(
                tree, triangles, origins[rays], directions[rays], reach
            )
        todo = todo[tri[todo] < 0]
        if reach >= whole or (reach >= give_up and len(todo) > GIVE_UP_SHARE * len(origins)):
            break
        reach *= REACH_GROWTH
    return dist, tri


def _measure(mesh):
    """Even surface samples, the wall under each, and the angle at its far side."""
    with _quiet_trimesh():
        points, faces = trimesh.sample.sample_surface_even(
            mesh, int(mesh.area * SAMPLES_PER_MM2), seed=SEED
        )
    normals = mesh.face_normals[faces]
    dist, tri = _cast(mesh, points - normals * RAY_OFFSET, -normals)
    hit = tri >= 0
    cos = np.full(len(points), np.nan)
    cos[hit] = _dot(-normals[hit], mesh.face_normals[tri[hit]])
    angle = np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))
    return points, dist, angle


def _label(points, entries):
    """The id of the smallest feature box that holds each point."""
    ids = np.array([entry["id"] for entry in entries] + [NO_FEATURE])
    if not entries:
        return np.full(len(points), NO_FEATURE)
    boxes = np.array([entry["box"] for entry in entries], dtype=float)
    lo = boxes[:, 0] - BOX_MARGIN
    hi = boxes[:, 1] + BOX_MARGIN
    volume = np.prod(hi - lo, axis=1)
    index = np.empty(len(points), dtype=np.int64)
    for start in range(0, len(points), LABEL_CHUNK):
        chunk = points[start:start + LABEL_CHUNK, None, :]
        inside = ((chunk >= lo) & (chunk <= hi)).all(axis=2)
        best = np.where(inside, volume, np.inf).argmin(axis=1)
        index[start:start + LABEL_CHUNK] = np.where(
            inside.any(axis=1), best, len(entries)
        )
    return ids[index]


def _corner(angle):
    """Square-corner readings. A miss has a NaN angle and is not a corner."""
    return np.nan_to_num(angle) >= CORNER_ANGLE


def _thinnest(dist, mask):
    """Index of the smallest masked reading, or None for an empty mask."""
    if not mask.any():
        return None
    return int(np.argmin(np.where(mask, dist, np.inf)))


def _features(points, dist, angle, minimum, entries, share):
    """One row per feature with wall or taper samples under the minimum,
    thinnest wall first, then thinnest taper."""
    thin = (dist < minimum) & ~_corner(angle)
    if not thin.any():
        return []
    points, dist, wall = points[thin], dist[thin], angle[thin] <= EDGE_ANGLE
    labels = _label(points, entries)
    rows = []
    for fid in np.unique(labels):
        mine = labels == fid
        sheet = _thinnest(dist, mine & wall)
        taper = _thinnest(dist, mine & ~wall)
        rows.append({
            "id": str(fid),
            "wall": None if sheet is None else float(dist[sheet]),
            "taper": None if taper is None else float(dist[taper]),
            "area": float(np.count_nonzero(mine) * share),
            "taper_pct": float(100 * (~wall[mine]).mean()),
            "at": points[taper if sheet is None else sheet],
        })
    return sorted(rows, key=lambda row: (
        row["wall"] if row["wall"] is not None else row["taper"], row["id"]
    ))


def _cell(value):
    return "-" if value is None else f"{value:.2f}"


def _mm(value):
    return "-" if value is None else f"{value:.2f} mm"


def _judge(name, row, process, minimum):
    """Status, WARN line or None, and failures for one feature under the minimum."""
    stem = Path(name).stem
    fid, wall, area = row["id"], row["wall"], row["area"]
    where = (
        f"{stem} {fid}: wall {_mm(wall)}, taper {_mm(row['taper'])}, "
        f"{area:.1f} mm2 thin ({row['taper_pct']:.0f}% taper)"
    )
    held = (
        f"under the {process} minimum {minimum:.2f} mm, so PCBWay holds the "
        "order unless the risk is accepted"
    )
    if (name, fid) not in ACCEPTED:
        return "NOT ACCEPTED", None, [Problem(
            f"{where}, {held}. Make it thicker, or add it to ACCEPTED in "
            "checks/fab.py",
            at=row["at"], part=stem,
        )]
    floor, cap, note = ACCEPTED[(name, fid)]
    bound = "no floor" if floor is None else f"floor {floor:.2f} mm"
    warn = (
        f"WARN {where}, {held}. Accepted with {bound} and area cap "
        f"{cap:.1f} mm2: {note}"
    )
    flags, problems = [], []
    # The taper minimum is never floored: it depends on how near the luckiest
    # sample falls to the edge.
    if wall is not None and floor is not None and wall < floor - FLOOR_TOLERANCE:
        flags.append("UNDER FLOOR")
        problems.append(Problem(
            f"{where}, thinner than its accepted floor {floor:.2f} mm less "
            f"FLOOR_TOLERANCE {FLOOR_TOLERANCE:.2f}, and {held}",
            at=row["at"], part=stem,
        ))
    if wall is not None and floor is None:
        flags.append("NEW WALL")
        problems.append(Problem(
            f"{where}, a thin wall in a feature accepted for tapered edges "
            f"only, and {held}",
            at=row["at"], part=stem,
        ))
    if area > cap * (1 + AREA_TOLERANCE) + AREA_SLACK:
        flags.append("OVER AREA CAP")
        problems.append(Problem(
            f"{where}, more than its accepted area cap {cap:.1f} mm2 plus "
            f"AREA_TOLERANCE {100 * AREA_TOLERANCE:.0f}% and AREA_SLACK "
            f"{AREA_SLACK:.1f} mm2, and {held}",
            at=row["at"], part=stem,
        ))
    return ", ".join(flags) or "accepted", warn, problems


def fab_walls(front, back):
    """Measure both shells against FAB_MIN_WALL[FAB_PROCESS].

    Returns the lines to print, the failures, and how many accepted features
    are under the minimum.
    """
    process = params.FAB_PROCESS
    minimum = params.FAB_MIN_WALL[process]
    lines, warns, problems, seen = [], [], [], set()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        named = write_features(tmp / "c6remote-features.json")["parts"]
        for name, shape in zip(PARTS, (front, back)):
            # The real export name, because the cached STL blob and the back's
            # angular tolerance are keyed on it.
            cache.export_stl_cached(shape, tmp / name)
            mesh = trimesh.load(str(tmp / name), force="mesh")
            stem = Path(name).stem
            points, dist, angle = _measure(mesh)
            share = mesh.area / len(points)
            missed = ~np.isfinite(dist)
            corner = _corner(angle)
            under = ", ".join(
                f"under {p} {wall:.2f}: "
                f"{np.count_nonzero((dist < wall) & ~corner) * share:.1f} mm2"
                for p, wall in params.FAB_MIN_WALL.items()
            )
            ignored = np.count_nonzero((dist < minimum) & corner) * share
            lines.append(
                f"{stem}: {mesh.area:.1f} mm2, {len(points)} rays, "
                f"{100 * (1 - missed.mean()):.2f}% hit, {under}, "
                f"{ignored:.1f} mm2 of square corners ignored"
            )
            if missed.mean() > MAX_MISS:
                problems.append(Problem(
                    f"{stem}: {np.count_nonzero(missed)} of {len(points)} inward "
                    f"rays ({100 * missed.mean():.2f}%) found no wall, more than "
                    f"the {100 * MAX_MISS:.1f}% allowed. An inward ray from a "
                    "closed mesh must hit, so the mesh or the ray cast is broken "
                    "and no wall reading here is valid",
                    at=points[missed][0], part=stem,
                ))
            rows = _features(points, dist, angle, minimum, named.get(name, []), share)
            if not rows:
                lines.append(f"  no feature under {process} {minimum:.2f} mm")
                continue
            width = max(len("feature"), *(len(row["id"]) for row in rows))
            lines.append(
                f"  {'feature':<{width}}  {'wall':>5}  {'taper':>5}  thin mm2  "
                f"taper %  {'thinnest at':<24}  status"
            )
            for row in rows:
                status, warn, failed = _judge(name, row, process, minimum)
                if warn:
                    warns.append(warn)
                    seen.add((name, row["id"]))
                problems.extend(failed)
                x, y, z = row["at"]
                at = f"({x:.1f}, {y:.1f}, {z:.1f})"
                lines.append(
                    f"  {row['id']:<{width}}  {_cell(row['wall']):>5}  "
                    f"{_cell(row['taper']):>5}  {row['area']:8.1f}  "
                    f"{row['taper_pct']:7.0f}  {at:<24}  {status}"
                )
    lines.extend(warns)
    for name, fid in ACCEPTED:
        if (name, fid) not in seen:
            lines.append(
                f"NOTE {Path(name).stem} {fid} is no longer under the {process} "
                f"minimum {minimum:.2f} mm, so its ACCEPTED entry can be removed"
            )
    return lines, problems, len(seen)
