#!/usr/bin/env python3
"""Draw the c6remote front face as one SVG: a plan of the shell face with the
keypad recess as iso-depth contours, and a section of that recess on the keypad
centreline. Every coordinate comes from the build123d case model at run time."""

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
from model import wheel_ring as wr  # noqa: E402
from model.shape import _offset_face  # noqa: E402

# Drawing scale and layout, in sheet pixels. Nothing here describes the part.
SCALE = 5.0
EXAG = 10.0
MARGIN = 44.0
GUTTER = 132.0
TITLE_H = 74.0
TABLE_H = 128.0
BAND_KEY_H = 44.0

OUTLINE_STEPS = 640
CONTOUR_STEPS = 640
BAND_LEVELS = 8
LEGEND_PTS_PER_MM = 4.0
CIRCLE_PTS = 48
PLAN_STROKE_PAD = 0.7  # half the shell outline stroke, so the crop does not clip it

# Palette. Every rule states its light value first and then the token, so a
# renderer without CSS custom properties still gets the light theme.
LIGHT = {
    "bg": "#ffffff",
    "ink": "#20242a",
    "mute": "#6d6659",
    "rule": "#b6ae9f",
    "face": "#ffffff",
    "edge": "#5f584e",
    "dish-lo": "#ffffff",
    "dish-hi": "#c5bfb4",
    "contour": "#ebe8e2",
    "rim": "#b9b1a4",
    "void": "#39352e",
    "knob": "#000000",
    "wheel-ink": "#ffffff",
    "ring": "#f7e9b8",
    "cap": "#fdfcf9",
    "cap-edge": "#453f37",
    "glyph": "#221e19",
    "hatch": "#b3ab9c",
    "accent": "#a8552c",
}

DARK = {
    "bg": "#ffffff",
    "ink": "#e8e5df",
    "mute": "#98a0a8",
    "rule": "#3d454d",
    "face": "#ffffff",
    "edge": "#98a1a9",
    "dish-lo": "#ffffff",
    "dish-hi": "#c5bfb4",
    "contour": "#ebe8e2",
    "rim": "#9daab4",
    "void": "#05070a",
    "knob": "#000000",
    "wheel-ink": "#ffffff",
    "ring": "#5c5326",
    "cap": "#c6ced5",
    "cap-edge": "#0b0f13",
    "glyph": "#11161b",
    "hatch": "#4d565f",
    "accent": "#e2a06a",
}

FONT = (
    "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, "
    "Helvetica, Arial, sans-serif"
)


def _mix(a, b, t):
    """Blend two hex colours in sRGB."""
    pa = [int(a[i : i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i : i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(pa[i] + (pb[i] - pa[i]) * t) for i in range(3))


def band_tones(palette):
    """One tone per depth band, rim to deepest. Ease keeps shallow bands light."""
    span = max(BAND_LEVELS - 1, 1)
    return [
        _mix(palette["dish-lo"], palette["dish-hi"], (i / span) ** 1.7)
        for i in range(BAND_LEVELS)
    ]


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


def max_depth():
    y0, y1 = kp.recess_span()
    return max(
        spine_depth(y0 + (y1 - y0) * i / CONTOUR_STEPS)
        for i in range(CONTOUR_STEPS + 1)
    )


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


def _outline_span(pts, cx):
    """(y0, y1) where a closed plan outline crosses the section plane."""
    ys = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        if (x0 - cx) * (x1 - cx) <= 0 and x0 != x1:
            ys.append(y0 + (y1 - y0) * (cx - x0) / (x1 - x0))
    return (min(ys), max(ys)) if len(ys) >= 2 else None


def centreline_caps():
    """The caps the section plane passes through, with their section chords."""
    cx = kp.centerline_x()
    out = []
    for ref in capmod.cap_refs():
        x, y = board.components()[ref][:2]
        span = _outline_span(capmod.cap_outline(capmod.cap_body(ref), x, y), cx)
        if span:
            out.append((ref, span))
    return out


# --- SVG helpers ----------------------------------------------------------


def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def path_d(loops, project):
    out = []
    for loop in loops:
        pts = [project(*p) for p in loop]
        out.append("M" + " L".join(f"{fmt(a)} {fmt(b)}" for a, b in pts) + "Z")
    return "".join(out)


def poly_d(pts, close=False):
    d = "M" + " L".join(f"{fmt(a)} {fmt(b)}" for a, b in pts)
    return d + "Z" if close else d


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def label(x, y, text, cls="tag", anchor="start"):
    return (
        f'<text class="{cls}" x="{fmt(x)}" y="{fmt(y)}" '
        f'text-anchor="{anchor}">{esc(text)}</text>'
    )


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


# --- view 1 ---------------------------------------------------------------


def plan_view(P, deepest, plan_x, plan_y, plan_w, plan_h, bounds, annotations=True):
    ex0, ex1, ey0, ey1 = bounds
    out = ['<g id="plan">']
    out.append(f'<path class="face" d="{path_d([shell_outline()], P)}"/>')

    for i in range(BAND_LEVELS):
        loops = contour_loops(deepest * i / BAND_LEVELS)
        if loops:
            out.append(f'<path class="d{i}" d="{path_d(loops, P)}"/>')
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

    if not annotations:
        out.append("</g>")
        return "".join(out)

    gut = plan_x + plan_w + 16
    out.append(label(gut, plan_y + 8, "IR end", "note"))
    out.append(label(gut, plan_y + plan_h - 2, "grip end", "note"))
    ring_r = (wr.led_ring_roof_inner_r() + wr.led_ring_roof_outer_r()) / 2
    ang = math.radians(38)
    top_ref = capmod.cap_refs()[-1]
    tx, ty = board.components()[top_ref][:2]
    for (fx, fy), row, text in (
        ((mx + micmod.mic_mouth_r(), my), P(0, my)[1], "mic inlet"),
        (
            (wx + ring_r * math.cos(ang), wy + ring_r * math.sin(ang)),
            P(0, wy)[1] - 34,
            "LED ring roof",
        ),
        (
            (wx + stack.WHEEL_OPENING_R * math.cos(-ang), wy + stack.WHEEL_OPENING_R * math.sin(-ang)),
            P(0, wy)[1] + 34,
            "wheel opening",
        ),
        ((tx + capmod.cap_body(top_ref) / 2, ty), P(0, ty)[1], "keycap"),
    ):
        out.append(_callout(P(fx, fy), (gut - 8, row), text))

    base = plan_y + plan_h
    ax, bx = P(ex0, ey0)[0], P(ex1, ey0)[0]
    out.append(
        f'<path class="dim" d="M{fmt(ax)} {fmt(base + 17)} L{fmt(ax)} {fmt(base + 27)} '
        f'M{fmt(bx)} {fmt(base + 17)} L{fmt(bx)} {fmt(base + 27)} '
        f'M{fmt(ax)} {fmt(base + 22)} L{fmt(bx)} {fmt(base + 22)}"/>'
    )
    out.append(label((ax + bx) / 2, base + 39, f"{ex1 - ex0:.1f} mm", "tag", "middle"))

    dx = plan_x - 24
    ay, by = P(ex0, ey0)[1], P(ex0, ey1)[1]
    out.append(
        f'<path class="dim" d="M{fmt(dx - 5)} {fmt(ay)} L{fmt(dx + 5)} {fmt(ay)} '
        f'M{fmt(dx - 5)} {fmt(by)} L{fmt(dx + 5)} {fmt(by)} '
        f'M{fmt(dx)} {fmt(ay)} L{fmt(dx)} {fmt(by)}"/>'
    )
    mid = (ay + by) / 2
    out.append(
        f'<text class="tag" x="{fmt(dx - 7)}" y="{fmt(mid)}" text-anchor="middle" '
        f'transform="rotate(-90 {fmt(dx - 7)} {fmt(mid)})">'
        f"{esc(f'{ey1 - ey0:.1f} mm')}</text>"
    )

    out.append(
        label(
            plan_x,
            base + 66,
            "1   Front face plan, keypad recess as 8-step depth fill",
            "cap1",
        )
    )
    out.append("</g>")
    return "".join(out)


def _callout(anchor, target, text):
    ax, ay = anchor
    tx, ty = target
    return (
        f'<path class="lead" d="M{fmt(ax)} {fmt(ay)} L{fmt(tx)} {fmt(ty)}"/>'
        + label(tx + 8, ty + 3.5, text)
    )


# --- view 2 ---------------------------------------------------------------


def section_view(S, deepest, sec_x, sec_zero, z_span, y_bounds):
    """The centreline section, and the sheet y its caption sits on."""
    ey0, ey1 = y_bounds
    cx = kp.centerline_x()
    wx, wy = board.wheel_center()
    out = ['<g id="section">']

    half = math.sqrt(max(0.0, stack.WHEEL_OPENING_R**2 - (cx - wx) ** 2))
    gap = (wy - half, wy + half)
    slabs = [(ey0, gap[0]), (gap[1], ey1)]
    floor = stack.SHELL_FRONT - deepest - stack.KEYPAD_CEILING

    def surface(y0, y1, steps=560):
        ys = [y0 + (y1 - y0) * i / steps for i in range(steps + 1)]
        return [(y, stack.SHELL_FRONT - kp.face_depth_at(cx, y)) for y in ys]

    for i, (a, b) in enumerate(slabs):
        top = surface(a, b)
        under = [(y, z - stack.KEYPAD_CEILING) for y, z in reversed(top)]
        out.append(_body([S(y, z) for y, z in top + under], f"slab{i}", "slab", 9.0))

    # The wheel is a different body, so it takes the opposite hatch angle. Its
    # own measured top is flush with the flat face.
    corners = [
        S(gap[0], stack.WHEEL_TOP),
        S(gap[1], stack.WHEEL_TOP),
        S(gap[1], floor),
        S(gap[0], floor),
    ]
    out.append(_body(corners, "wheelbody", "wheel", 15.0, back=True, outline=False))
    out.append(f'<path class="wheeltop" d="{poly_d(corners[:2])}"/>')
    out.append(f'<path class="wheelside" d="{poly_d([corners[0], corners[3]])}"/>')
    out.append(f'<path class="wheelside" d="{poly_d([corners[1], corners[2]])}"/>')
    out.append(f'<path class="broke" d="{poly_d([corners[3], corners[2]])}"/>')
    out.append(
        label(
            (corners[0][0] + corners[1][0]) / 2,
            (corners[0][1] + corners[3][1]) / 2,
            "wheel",
            "tag",
            "middle",
        )
    )

    for a, b in slabs:
        out.append(
            f'<path class="skin" d="{poly_d([S(y, z) for y, z in surface(a, b)])}"/>'
        )

    # Each cap is seated on the floor under its own switch, so its underside is
    # the floor curve across its own chord and its top is that plus cap_proud.
    chords = centreline_caps()
    for i, (ref, (ya, yb)) in enumerate(chords):
        seat = kp.face_floor_at(cx, board.components()[ref][1])
        crown = seat + capmod.cap_proud(ref)
        under = [
            S(y, stack.SHELL_FRONT - kp.face_depth_at(cx, y))
            for y in (yb + (ya - yb) * j / 48 for j in range(49))
        ]
        out.append(
            _body(
                [S(ya, crown), S(yb, crown)] + under,
                f"cap{i}",
                "capsec",
                6.0,
                back=True,
            )
        )

    def crest(y):
        """Topmost thing on the section at y, so a leader lands on it rather
        than running through a cap or the wheel."""
        if gap[0] <= y <= gap[1]:
            return stack.WHEEL_TOP
        for _, (ya, yb) in chords:
            if ya <= y <= yb:
                return stack.CAP_TOP
        return kp.face_floor_at(cx, y)

    top_row = sec_zero - 40
    for name, recess in kp.keypad_recesses().items():
        # The wheel basin shows only as the dish ring outside the bore, so its
        # leader goes there rather than onto the knob.
        y = recess.cy
        if name == "wheel":
            y -= (stack.WHEEL_OPENING_R + recess.ay) / 2
        ax, ay = S(y, crest(y))
        out.append(f'<path class="lead" d="M{fmt(ax)} {fmt(ay)} L{fmt(ax)} {fmt(top_row + 6)}"/>')
        out.append(label(ax, top_row, f"{name} basin", "tag", "middle"))

    foot_row = sec_zero + z_span + 26
    for neck in kp.keypad_necks():
        y = kp.neck_waist(neck)[0]
        ax, ay = S(y, kp.face_floor_at(cx, y) - stack.KEYPAD_CEILING)
        out.append(f'<path class="lead" d="M{fmt(ax)} {fmt(ay)} L{fmt(ax)} {fmt(foot_row)}"/>')
        out.append(label(ax, foot_row + 13, f"{neck.name} neck", "tag", "middle"))

    out.append(label(S(ey0, 0)[0], foot_row + 34, "grip end", "note"))
    out.append(label(S(ey1, 0)[0], foot_row + 34, "IR end", "note", "end"))
    caption = foot_row + 62
    out.append(
        label(
            sec_x,
            caption,
            f"2   Inset profile on the keypad centreline, "
            f"vertical exaggeration {fmt(EXAG)}x",
            "cap1",
        )
    )
    out.append("</g>")
    return "".join(out), caption


def _body(pts, uid, cls, pitch, back=False, outline=True):
    """One sectioned body: its tint, its hatch and its outline. Hatch angle
    separates bodies, so the wheel and the caps do not read as more shell."""
    poly = poly_d(pts, True)
    edge = f'<path class="{cls}edge" d="{poly}"/>' if outline else ""
    return (
        f'<clipPath id="{uid}"><path d="{poly}"/></clipPath>'
        f'<path class="{cls}" d="{poly}"/>'
        f'<g clip-path="url(#{uid})">{_hatch(pts, pitch, back)}</g>' + edge
    )


def _hatch(pts, pitch, back):
    """Diagonal fill for a clipped body, as real lines so no pattern paint is
    needed: librsvg and the GitHub renderer both handle these."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    run = y1 - y0
    out, c = [], x0 - (0.0 if back else run)
    while c <= x1 + (run if back else 0.0):
        far = c - run if back else c + run
        out.append(f'<path class="hatch" d="M{fmt(c)} {fmt(y1)} L{fmt(far)} {fmt(y0)}"/>')
        c += pitch
    return "".join(out)



# --- keys -----------------------------------------------------------------


def spine_table(x, y):
    """The five features of the spine with the figures the model gives them,
    interleaved grip end to IR end the way the section runs."""
    cols = (0.0, 168.0, 258.0, 348.0)
    rows = [("feature", "floor depth", "recess width", "plan radius")]
    dishes = kp.keypad_recesses()
    necks = {n.lower.name: n for n in kp.keypad_necks()}
    for name, recess in dishes.items():
        rows.append(
            (f"{name} basin", f"{recess.depth:.2f}", f"{2 * recess.ax:.1f}", "")
        )
        neck = necks.get(name)
        if neck:
            _, waist, depth = kp.neck_waist(neck)
            rows.append(
                (
                    f"{neck.name} neck",
                    f"{depth:.2f}",
                    f"{2 * waist:.1f}",
                    f"{kp.neck_radius(neck):.1f}",
                )
            )
    out = [label(x, y, "spine figures, millimetres")]
    top = y + 14
    out.append(
        f'<path class="rule" d="M{fmt(x)} {fmt(top + 5)} '
        f'L{fmt(x + cols[-1] + 60)} {fmt(top + 5)}"/>'
    )
    for i, row in enumerate(rows):
        ry = top + 18 * i + (2 if i else 0)
        cls = "tag" if i else "th"
        for j, cell in enumerate(row):
            if cell:
                anchor = "start" if j == 0 else "end"
                cxp = x + cols[j] + (0 if j == 0 else 50)
                out.append(label(cxp, ry, cell, cls, anchor))
    return "".join(out)


def band_key(x, y, deepest):
    """What the band tones mean, in millimetres off the model."""
    w, h = 26.0, 15.0
    out = [label(x, y, "recess depth below the flat face", "tag")]
    top = y + 12
    for i in range(BAND_LEVELS):
        out.append(
            f'<path class="d{i}" d="M{fmt(x + i * w)} {fmt(top)} h{fmt(w)} '
            f'v{fmt(h)} h{fmt(-w)}Z"/>'
        )
    out.append(label(x, top + h + 15, "rim, 0.00 mm"))
    out.append(
        label(x + BAND_LEVELS * w, top + h + 15, f"{deepest:.2f} mm", "tag", "end")
    )
    return "".join(out)


def depth_key(x, y, deepest):
    """True scale against the drawn scale, so the exaggeration is recoverable."""
    w = 158.0
    drawn = deepest * SCALE * EXAG
    true = deepest * SCALE
    out = [label(x, y, "depth key, deepest point", "tag")]
    top = y + 13
    out.append(f'<path class="keyghost" d="M{fmt(x)} {fmt(top)} h{fmt(w)} v{fmt(drawn)} h{fmt(-w)}Z"/>')
    out.append(label(x + w + 12, top + drawn / 2 + 4, f"as drawn, {fmt(EXAG)}x"))
    base = top + drawn + 15
    out.append(f'<path class="keybar" d="M{fmt(x)} {fmt(base)} h{fmt(w)} v{fmt(true)} h{fmt(-w)}Z"/>')
    out.append(label(x + w + 12, base + true + 4, f"true scale, {deepest:.2f} mm"))
    return "".join(out)


# --- the sheet ------------------------------------------------------------


def build():
    ex0, ex1 = kp.exterior_x_bounds()
    ey0, ey1 = kp.exterior_y_bounds()
    plan_w, plan_h = (ex1 - ex0) * SCALE, (ey1 - ey0) * SCALE
    deepest = max_depth()

    plan_x, plan_y = MARGIN, MARGIN + TITLE_H

    def P(x, y):
        """Case plan to sheet. y is flipped so the IR end reads at the top."""
        return plan_x + (x - ex0) * SCALE, plan_y + (ey1 - y) * SCALE

    sec_x = plan_x + plan_w + GUTTER
    sec_w = (ey1 - ey0) * SCALE
    z_span = (deepest + stack.KEYPAD_CEILING) * SCALE * EXAG
    sec_zero = plan_y + 78.0
    col_bottom = plan_y + plan_h

    def S(y, z):
        """Case section to sheet. y runs left to right, z up and exaggerated."""
        return (
            sec_x + (y - ey0) * SCALE,
            sec_zero - (z - stack.SHELL_FRONT) * SCALE * EXAG,
        )

    sheet_w = sec_x + sec_w + MARGIN
    sheet_h = plan_y + plan_h + 78 + MARGIN

    body = [
        f'<rect class="bg" x="0" y="0" width="{fmt(sheet_w)}" height="{fmt(sheet_h)}"/>',
        f'<text class="h1" x="{fmt(MARGIN)}" y="{fmt(MARGIN + 12)}">c6remote front face</text>',
        f'<text class="h2" x="{fmt(MARGIN)}" y="{fmt(MARGIN + 38)}">Shell face and keypad '
        f"recess profile, drawn from the build123d case model</text>",
        f'<path class="rule" d="M{fmt(MARGIN)} {fmt(MARGIN + 54)} '
        f'L{fmt(sheet_w - MARGIN)} {fmt(MARGIN + 54)}"/>',
        plan_view(P, deepest, plan_x, plan_y, plan_w, plan_h, (ex0, ex1, ey0, ey1)),
    ]
    section, caption_y = section_view(S, deepest, sec_x, sec_zero, z_span, (ey0, ey1))
    body.append(section)

    # The three blocks under the section share out whatever the column has left,
    # so the last of them lands on the plan's own baseline.
    heights = (TABLE_H, BAND_KEY_H, 36.0 + deepest * SCALE * (EXAG + 1))
    start = caption_y + 24
    lead = max(26.0, (col_bottom - start - sum(heights)) / (len(heights) - 1))
    body.append(spine_table(sec_x, start))
    body.append(band_key(sec_x, start + heights[0] + lead, deepest))
    body.append(depth_key(sec_x, start + heights[0] + heights[1] + 2 * lead, deepest))

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(sheet_w)} '
        f'{fmt(sheet_h)}" width="{fmt(sheet_w)}" height="{fmt(sheet_h)}" role="img" '
        f'aria-label="Plan and centreline section of the c6remote front face">'
        + _style()
        + "".join(body)
        + "</svg>\n"
    )
    return svg, sheet_w, sheet_h


def build_plan():
    ex0, ex1 = kp.exterior_x_bounds()
    ey0, ey1 = kp.exterior_y_bounds()
    plan_w, plan_h = (ex1 - ex0) * SCALE, (ey1 - ey0) * SCALE
    plan_x = plan_y = PLAN_STROKE_PAD
    deepest = max_depth()

    def P(x, y):
        return plan_x + (x - ex0) * SCALE, plan_y + (ey1 - y) * SCALE

    sheet_w = plan_w + 2 * PLAN_STROKE_PAD
    sheet_h = plan_h + 2 * PLAN_STROKE_PAD
    body = [
        plan_view(
            P,
            deepest,
            plan_x,
            plan_y,
            plan_w,
            plan_h,
            (ex0, ex1, ey0, ey1),
            annotations=False,
        ),
    ]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(sheet_w)} '
        f'{fmt(sheet_h)}" width="{fmt(sheet_w)}" height="{fmt(sheet_h)}" role="img" '
        f'aria-label="Plan of the c6remote front face">'
        + _style()
        + "".join(body)
        + "</svg>\n"
    )
    return svg, sheet_w, sheet_h


def _style():
    def tok(prop, key):
        return f"{prop}:{LIGHT[key]};{prop}:var(--{key})"

    light_tones = band_tones(LIGHT)
    dark_tones = band_tones(DARK)
    rules = [
        ":root{"
        + ";".join(f"--{k}:{v}" for k, v in LIGHT.items())
        + ";"
        + ";".join(f"--d{i}:{t}" for i, t in enumerate(light_tones))
        + "}",
        "@media (prefers-color-scheme: dark){:root{"
        + ";".join(f"--{k}:{v}" for k, v in DARK.items())
        + ";"
        + ";".join(f"--d{i}:{t}" for i, t in enumerate(dark_tones))
        + "}}",
        f"text{{font-family:{FONT};{tok('fill', 'ink')}}}",
        "path{fill:none}",
        ".h1{font-size:23px;font-weight:600;letter-spacing:.2px}",
        f".h2{{font-size:13px;{tok('fill', 'mute')}}}",
        f".rule{{{tok('stroke', 'rule')};stroke-width:1}}",
        f".bg{{{tok('fill', 'bg')}}}",
        f".cap1{{font-size:13.5px;{tok('fill', 'mute')}}}",
        f".tag{{font-size:10.5px;{tok('fill', 'mute')}}}",
        f".note{{font-size:10.5px;letter-spacing:.7px;{tok('fill', 'mute')}}}",
        f".face{{{tok('fill', 'face')};{tok('stroke', 'edge')};stroke-width:1.4}}",
        f".rim{{{tok('stroke', 'rim')};stroke-width:1.1}}",
        f".ring{{{tok('fill', 'ring')};fill-opacity:.6;{tok('stroke', 'rim')};"
        "stroke-width:.5;stroke-opacity:.45}",
        f".bore{{{tok('fill', 'void')};{tok('stroke', 'edge')};stroke-width:.9}}",
        f".knob{{{tok('fill', 'knob')};{tok('stroke', 'void')};stroke-width:.9}}",
        f".wheelglyph{{{tok('fill', 'wheel-ink')}}}",
        f".wheelmark{{{tok('stroke', 'wheel-ink')};stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}}",
        ".directionring{stroke-width:1;stroke-opacity:.55}",
        ".scrolldial{stroke-width:1.2}",
        f".detent{{{tok('fill', 'wheel-ink')};fill-opacity:.8}}",
        f".duct{{{tok('stroke', 'rim')};stroke-width:.7;stroke-dasharray:2.5 2.5;"
        "stroke-opacity:.7}",
        f".seat{{{tok('stroke', 'rim')};stroke-width:.5;stroke-opacity:.5}}",
        f".cap{{{tok('fill', 'cap')};{tok('stroke', 'cap-edge')};stroke-width:1}}",
        f".glyph{{{tok('fill', 'glyph')}}}",
        f".slab{{{tok('fill', 'face')}}}",
        f".slabedge{{{tok('stroke', 'edge')};stroke-width:.9}}",
        f".hatch{{{tok('stroke', 'hatch')};stroke-width:.7;stroke-opacity:.5}}",
        f".skin{{{tok('stroke', 'edge')};stroke-width:2}}",
        f".wheel{{{tok('fill', 'knob')};fill-opacity:.12}}",
        f".wheelside{{{tok('stroke', 'edge')};stroke-width:1}}",
        f".wheeltop{{{tok('stroke', 'edge')};stroke-width:2}}",
        f".broke{{{tok('stroke', 'edge')};stroke-width:1;stroke-dasharray:5 4}}",
        f".capsec{{{tok('fill', 'cap')}}}",
        f".capsecedge{{{tok('stroke', 'cap-edge')};stroke-width:1}}",
        f".lead{{{tok('stroke', 'rule')};stroke-width:.8}}",
        f".th{{font-size:10.5px;font-weight:600;{tok('fill', 'ink')}}}",
        f".dim{{{tok('stroke', 'rule')};stroke-width:.9}}",
        f".keybar{{{tok('fill', 'accent')};{tok('stroke', 'accent')};stroke-width:.6}}",
        f".keyghost{{{tok('fill', 'accent')};fill-opacity:.2;{tok('stroke', 'accent')};"
        "stroke-width:.9}",
    ]
    for i in range(BAND_LEVELS):
        rules.append(
            f".d{i}{{fill:{light_tones[i]};fill:var(--d{i});"
            f"{tok('stroke', 'contour')};stroke-width:.7}}"
        )
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
