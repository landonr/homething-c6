#!/usr/bin/env python3
"""Draw the c6remote front face plan as one SVG: the shell face, the keypad
recess outline, the wheel, and the keycaps with their legends. Every coordinate
comes from the build123d case model at run time."""

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "case"))

import board  # noqa: E402
import params  # noqa: E402
from model import caps as capmod  # noqa: E402
from model import keypad as kp  # noqa: E402
from model import legends as lg  # noqa: E402
from model import mic as micmod  # noqa: E402
from model import stack  # noqa: E402
from model.shape import _offset_face  # noqa: E402

# Drawing scale and layout, in sheet pixels. Nothing here describes the part.
SCALE = 5.0

OUTLINE_STEPS = 640
CONTOUR_STEPS = 640
LEGEND_PTS_PER_MM = 4.0
CIRCLE_PTS = 48
PLAN_STROKE_PAD = 0.7  # half the shell outline stroke, so the crop does not clip it
# Path simplification tolerance in sheet px. The /buttons page embeds this SVG
# in firmware flash, so its size matters.
SIMPLIFY_TOL = 0.1

# Palette. Every rule states its light value first and then the token, so a
# renderer without CSS custom properties still gets the light theme.
LIGHT = {
    "face": "#ffffff",
    "edge": "#5f584e",
    "rim": "#ddd7cd",
    "void": "#39352e",
    "knob": "#000000",
    "wheel-ink": "#ffffff",
    # Keycaps match the wheel: black face, white legend.
    "cap": "#000000",
    "cap-edge": "#1a1a1a",
    "glyph": "#ffffff",
}

DARK = {
    "face": "#ffffff",
    "edge": "#98a1a9",
    "rim": "#c5ced6",
    "void": "#05070a",
    "knob": "#000000",
    "wheel-ink": "#ffffff",
    "cap": "#000000",
    "cap-edge": "#1a1a1a",
    "glyph": "#ffffff",
}


# --- the model ------------------------------------------------------------


def shell_outline():
    """Plan outline of the shell's outer wall, as points."""
    wire = _offset_face(params.BOARD_FIT + params.WALL).outer_wire()
    return [
        (lambda p: (p.X, p.Y))(wire.position_at(i / OUTLINE_STEPS))
        for i in range(OUTLINE_STEPS)
    ]


def spine_depth(y):
    return kp.recess_spine(y)[1]


def _half_at(y, level):
    """Half width of the level-depth contour at y, zero where the recess never
    reaches that level. Bisected on _cross(), which falls monotonically from
    one on the centreline to zero at the rim."""
    width, depth, shape, n, axis_rounding, edge_width = kp.recess_spine(y)
    if width <= 0.0 or depth <= 0.0:
        return 0.0
    target = level / depth
    if target > 1.0:
        return 0.0
    if target <= 0.0:
        return width
    lo, hi = 0.0, 1.0
    for _ in range(46):
        mid = (lo + hi) / 2
        lo, hi = (
            (mid, hi)
            if kp._cross(mid, shape, n, axis_rounding, edge_width) > target
            else (lo, mid)
        )
    return width * (lo + hi) / 2


def _level_spans(level):
    """[(y0, y1)] the level-depth contour closes over. Shallow levels run the
    whole recess; deep ones break into one span per basin once the necks pinch
    below the level."""
    y0, y1 = kp.recess_span()
    step = (y1 - y0) / CONTOUR_STEPS

    def inside(y):
        return spine_depth(y) >= level

    def edge(lo, hi):
        for _ in range(46):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if inside(mid) else (lo, mid)
        return (lo + hi) / 2

    spans, start = [], None
    prev_y, prev_in = y0, inside(y0)
    if prev_in:
        start = y0
    for i in range(1, CONTOUR_STEPS + 1):
        y = y0 + step * i
        now = inside(y)
        if now and not prev_in:
            start = edge(y, prev_y)
        elif prev_in and not now:
            spans.append((start, edge(prev_y, y)))
            start = None
        prev_y, prev_in = y, now
    if prev_in:
        spans.append((start, y1))
    return [s for s in spans if s[1] - s[0] > step]


def contour_loops(level):
    """Closed plan loops for one depth contour without bridging a neck gap."""
    cx = kp.centerline_x()
    y0, y1 = kp.recess_span()
    loops = []
    for ya, yb in _level_spans(level):
        # Cosine spacing packs points at both ends so round tips stay round
        # under the reduced mid-span step count.
        steps = max(48, int(CONTOUR_STEPS * (yb - ya) / (y1 - y0)))
        right, left = [], []
        for i in range(steps + 1):
            t = i / steps
            y = ya + (yb - ya) * (1 - math.cos(math.pi * t)) / 2
            half = _half_at(y, level)
            right.append((cx + half, y))
            left.append((cx - half, y))
        loops.append(right + left[::-1])
    return loops


def circle_pts(cx, cy, r):
    return [
        (
            cx + r * math.cos(2 * math.pi * i / CIRCLE_PTS),
            cy + r * math.sin(2 * math.pi * i / CIRCLE_PTS),
        )
        for i in range(CIRCLE_PTS)
    ]


def legend_loops(ref):
    """One cap legend's ink as closed loops in the case frame, outer wires and
    counters alike, ready for an even-odd fill."""
    spec, size = lg.legend_entry(ref)
    x, y = board.components()[ref][:2]
    loops = []
    for face in lg._legend_faces(spec, size):
        for wire in [face.outer_wire()] + list(face.inner_wires()):
            n = max(48, int(wire.length * LEGEND_PTS_PER_MM))
            pts = [wire.position_at(i / n) for i in range(n)]
            loops.append([(x + p.X, y + p.Y) for p in pts])
    return loops


# --- SVG helpers ----------------------------------------------------------


def fmt(v, places=2):
    return f"{v:.{places}f}".rstrip("0").rstrip(".")


def simplify(pts, tol):
    """Ramer-Douglas-Peucker on an open polyline. Both end points stay."""
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    todo = [(0, len(pts) - 1)]
    while todo:
        i, j = todo.pop()
        (ax, ay), (bx, by) = pts[i], pts[j]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        worst, at = tol, None
        for k in range(i + 1, j):
            px, py = pts[k]
            if norm:
                dist = abs(dx * (ay - py) - dy * (ax - px)) / norm
            else:
                dist = math.hypot(px - ax, py - ay)
            if dist > worst:
                worst, at = dist, k
        if at is not None:
            keep[at] = True
            todo += [(i, at), (at, j)]
    return [p for p, k in zip(pts, keep) if k]


def path_d(loops, project):
    out = []
    for loop in loops:
        pts = [project(*p) for p in loop]
        # Close the ring for the simplifier so the closing edge also holds tol.
        pts = simplify(pts + pts[:1], SIMPLIFY_TOL)[:-1]
        coords = []
        for a, b in pts:
            c = f"{fmt(a, 1)} {fmt(b, 1)}"
            if not coords or coords[-1] != c:
                coords.append(c)
        out.append("M" + " L".join(coords) + "Z")
    return "".join(out)


def wheel_controls(P, cx, cy):
    """TSWB-3N-CB222 direction ring, rotary dial, and centre select."""
    direction_r = 32.0 / 2
    dial_r = 22.9 / 2
    select_r = 8.1 / 2
    arrows = [
        [(cx, cy + 15.0), (cx - 1.25, cy + 13.2), (cx + 1.25, cy + 13.2)],
        [(cx, cy - 15.0), (cx - 1.25, cy - 13.2), (cx + 1.25, cy - 13.2)],
        [(cx - 15.0, cy), (cx - 13.2, cy - 1.25), (cx - 13.2, cy + 1.25)],
        [(cx + 15.0, cy), (cx + 13.2, cy - 1.25), (cx + 13.2, cy + 1.25)],
    ]
    out = [
        f'<path class="wheelmark directionring" d="'
        f'{path_d([circle_pts(cx, cy, direction_r)], P)}"/>',
        f'<path class="wheelmark scrolldial" d="'
        f'{path_d([circle_pts(cx, cy, dial_r)], P)}"/>',
        f'<path class="wheelglyph" d="{path_d(arrows, P)}"/>',
    ]
    out.append(
        f'<path class="wheelmark" d="'
        f'{path_d([circle_pts(cx, cy, select_r)], P)}"/>'
    )
    for i in range(24):
        angle = 2 * math.pi * i / 24
        x = cx + 9.4 * math.cos(angle)
        y = cy + 9.4 * math.sin(angle)
        out.append(
            f'<path class="detent" d="{path_d([circle_pts(x, y, 0.22)], P)}"/>'
        )
    return "".join(out)


# --- the sheet ------------------------------------------------------------


def plan_view(P):
    out = ['<g id="plan">']
    out.append(f'<path class="face" d="{path_d([shell_outline()], P)}"/>')
    out.append(f'<path class="rim" d="{path_d(contour_loops(0.0), P)}"/>')

    wx, wy = board.wheel_center()
    out.append(
        f'<path class="bore" d="'
        f'{path_d([circle_pts(wx, wy, stack.WHEEL_OPENING_R)], P)}"/>'
    )
    out.append(
        f'<path class="knob" d="'
        f'{path_d([circle_pts(wx, wy, stack.WHEEL_MAIN_OD / 2)], P)}"/>'
    )
    out.append(wheel_controls(P, wx, wy))

    for ref in capmod.cap_refs():
        x, y = board.components()[ref][:2]
        out.append(
            f'<path class="seat" d="'
            f'{path_d([capmod.cap_outline(kp.key_size(ref), x, y)], P)}"/>'
        )
    for ref in capmod.cap_refs():
        x, y = board.components()[ref][:2]
        cap = capmod.cap_outline(capmod.cap_body(ref), x, y)
        out.append(f'<path class="cap" d="{path_d([cap], P)}"/>')
        out.append(
            f'<path class="glyph" fill-rule="evenodd" '
            f'd="{path_d(legend_loops(ref), P)}"/>'
        )

    mx, my = micmod.mic_port()
    out.append(
        f'<path class="bore" d="'
        f'{path_d([circle_pts(mx, my, micmod.mic_mouth_r())], P)}"/>'
    )
    out.append("</g>")
    return "".join(out)


def build_plan():
    ex0, ex1 = kp.exterior_x_bounds()
    ey0, ey1 = kp.exterior_y_bounds()
    plan_w, plan_h = (ex1 - ex0) * SCALE, (ey1 - ey0) * SCALE
    plan_x = plan_y = PLAN_STROKE_PAD

    def P(x, y):
        """Case plan to sheet. y is flipped so the IR end reads at the top."""
        return plan_x + (x - ex0) * SCALE, plan_y + (ey1 - y) * SCALE

    sheet_w = plan_w + 2 * PLAN_STROKE_PAD
    sheet_h = plan_h + 2 * PLAN_STROKE_PAD
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(sheet_w)} '
        f'{fmt(sheet_h)}" width="{fmt(sheet_w)}" height="{fmt(sheet_h)}" role="img" '
        f'aria-label="Plan of the c6remote front face">'
        + _style()
        + plan_view(P)
        + "</svg>\n"
    )
    return svg, sheet_w, sheet_h


def _style():
    def tok(prop, key):
        return f"{prop}:{LIGHT[key]};{prop}:var(--{key})"

    rules = [
        ":root{" + ";".join(f"--{k}:{v}" for k, v in LIGHT.items()) + "}",
        "@media (prefers-color-scheme: dark){:root{"
        + ";".join(f"--{k}:{v}" for k, v in DARK.items())
        + "}}",
        "path{fill:none}",
        f".face{{{tok('fill', 'face')};{tok('stroke', 'edge')};stroke-width:1.4}}",
        f".rim{{{tok('stroke', 'rim')};stroke-width:1.1}}",
        f".bore{{{tok('fill', 'void')};{tok('stroke', 'edge')};stroke-width:.9}}",
        f".knob{{{tok('fill', 'knob')};{tok('stroke', 'void')};stroke-width:.9}}",
        f".wheelglyph{{{tok('fill', 'wheel-ink')}}}",
        f".wheelmark{{{tok('stroke', 'wheel-ink')};stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}}",
        ".directionring{stroke-width:1;stroke-opacity:.55}",
        ".scrolldial{stroke-width:1.2}",
        f".detent{{{tok('fill', 'wheel-ink')};fill-opacity:.8}}",
        f".seat{{{tok('stroke', 'rim')};stroke-width:.5;stroke-opacity:.5}}",
        f".cap{{{tok('fill', 'cap')};{tok('stroke', 'cap-edge')};stroke-width:1}}",
        f".glyph{{{tok('fill', 'glyph')}}}",
    ]
    return "<style>" + "".join(rules) + "</style>"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "-o",
        "--out",
        default=str(ROOT / "docs" / "readme-assets" / "case-front-face.svg"),
        help="where to write the SVG",
    )
    args = ap.parse_args()
    svg, w, h = build_plan()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    print(f"wrote {out}, {fmt(w)} by {fmt(h)} px, {len(svg) / 1024:.0f} kB")


if __name__ == "__main__":
    main()
