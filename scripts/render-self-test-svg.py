#!/usr/bin/env python3
"""Draw the operator diagrams of site/factory-self-test.html.

Each sheet is the front face plan of scripts/face_plan.py with two callout
kinds: an orange outline round the control to press, and a blue ring round the
status LED that answers. One sheet follows each step of the procedure.

Every position comes from the model at run time. The six LED positions come
from the KiCad position file through case/board.py, so this file holds no
coordinate of its own."""

import argparse
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))

import face_plan  # noqa: E402
from face_plan import ROOT, circle_pts, fmt, path_d  # noqa: E402

sys.path.insert(0, str(ROOT / "case"))

import board  # noqa: E402
from model import caps as capmod  # noqa: E402
from model import keypad as kp  # noqa: E402
from model import mic as micmod  # noqa: E402

# Chain order of the status LEDs. components/self_test/self_test.cpp uses the
# same order as its strip index, and the boot chase gives each LED one colour.
LED_CHAIN = ("D2", "D3", "D6", "D4", "D5", "D7")
CHASE_COLOUR = ("#ff0000", "#0070ff", "#aa00ab", "#00ff00", "#0000ff", "#00abaa")
CHASE_NAME = ("red", "azure", "magenta", "green", "blue", "cyan")

OUT_DIR = ROOT / "docs" / "readme-assets"

# Sheet layout in px. Nothing here describes the part.
SCALE = 3.6
GUTTER = 150.0
MARGIN = 12.0
LINE_H = 14.0
LABEL_GAP = 8.0
LEAD_IN = 16.0  # straight run out of a marker before the leader bends
TEXT_INSET = 24.0
LEAD_INSET = 20.0

# Marker sizes in mm, so each marker tracks the feature it rings.
PRESS_GROW = 0.8  # outside the keycap seat
WHEEL_PRESS_R = 16.5
SELECT_PRESS_R = 5.1
EMITTER_R = 2.6
LED_DOT_R = 1.5
LED_RING_R = 3.1
LED_SPOT_R = 2.2
ARC_TRIM = 3.6  # arc dropped either side of an LED, so the dot stays clear
ARROW_L = 2.6
ARROW_W = 1.1

LIGHT = {"act": "#d24a12", "watch": "#155fc0", "ink": "#2a2520", "muted": "#8f877c"}
DARK = {"act": "#ff9b70", "watch": "#7fb8ff", "ink": "#e8e3da", "muted": "#949ba2"}

FONT = "'DejaVu Sans',Verdana,Helvetica,Arial,sans-serif"


# --- targets --------------------------------------------------------------


def led_xy(ref):
    return board.components()[ref][:2]


def target(ref):
    """Plan center, leader reach either side, and the marker loops of one
    target. Every value comes from the case model or the board."""
    if ref in capmod.cap_refs():
        x, y = board.components()[ref][:2]
        size = kp.key_size(ref) + PRESS_GROW
        return x, y, size / 2, [capmod.cap_outline(size, x, y)]
    if ref == "wheel-center":
        wx, wy = board.wheel_center()
        return wx, wy, SELECT_PRESS_R, [circle_pts(wx, wy, SELECT_PRESS_R)]
    if ref == "wheel-ring":
        wx, wy = board.wheel_center()
        return wx, wy, WHEEL_PRESS_R, [circle_pts(wx, wy, WHEEL_PRESS_R)]
    if ref == "mic":
        mx, my = micmod.mic_port()
        r = micmod.mic_mouth_r() + 1.1
        return mx, my, r, [circle_pts(mx, my, r)]
    if ref == "D1":
        x, y = board.components()["D1"][:2]
        return x, y, EMITTER_R, [circle_pts(x, y, EMITTER_R)]
    if ref in LED_CHAIN:
        x, y = led_xy(ref)
        return x, y, LED_RING_R, [circle_pts(x, y, LED_RING_R)]
    raise KeyError(ref)


def ring_radius():
    """Radius of the bolt circle the six LEDs sit on."""
    wx, wy = board.wheel_center()
    x, y = led_xy("D6")
    return math.hypot(x - wx, y - wy)


# --- sheet pieces ---------------------------------------------------------


def led_spots(P, skip):
    """A faint ring at each LED the sheet does not call out, so the ring of six
    positions reads whole."""
    loops = [circle_pts(*led_xy(ref), LED_SPOT_R) for ref in LED_CHAIN if ref not in skip]
    return f'<path class="ledspot" d="{path_d(loops, P)}"/>' if loops else ""


def ring_guide(P):
    wx, wy = board.wheel_center()
    return f'<path class="ledpath" d="{path_d([circle_pts(wx, wy, ring_radius())], P)}"/>'


def chain_arrows(P):
    """One arc with an arrowhead between each pair of LEDs in chain order. The
    arcs run clockwise, because the chain does."""
    wx, wy = board.wheel_center()
    r = ring_radius()
    trim = ARC_TRIM / r
    out = []
    for first, second in zip(LED_CHAIN, LED_CHAIN[1:]):
        ax, ay = led_xy(first)
        bx, by = led_xy(second)
        start = math.atan2(ay - wy, ax - wx)
        end = math.atan2(by - wy, bx - wx)
        while end > start:
            end -= 2 * math.pi
        start, end = start - trim, end + trim
        steps = max(8, int(abs(start - end) * 20))
        pts = [
            (
                wx + r * math.cos(start + (end - start) * i / steps),
                wy + r * math.sin(start + (end - start) * i / steps),
            )
            for i in range(steps + 1)
        ]
        line = " L".join(f"{fmt(px, 1)} {fmt(py, 1)}" for px, py in (P(*p) for p in pts))
        out.append(f'<path class="chain" d="M{line}"/>')
        back = end + ARROW_L / r
        head = [
            (wx + r * math.cos(end), wy + r * math.sin(end)),
            (wx + (r + ARROW_W) * math.cos(back), wy + (r + ARROW_W) * math.sin(back)),
            (wx + (r - ARROW_W) * math.cos(back), wy + (r - ARROW_W) * math.sin(back)),
        ]
        out.append(f'<path class="chainhead" d="{path_d([head], P)}"/>')
    return "".join(out)


def pack(wants, heights, lo, hi):
    """Label block centers down one gutter, without an overlap.

    The pass runs down and then back up, so a crowded pair opens either side of
    the position it wants."""
    order = sorted(range(len(wants)), key=lambda i: wants[i])
    top = {}
    cursor = lo
    for i in order:
        top[i] = max(wants[i] - heights[i] / 2, cursor)
        cursor = top[i] + heights[i] + LABEL_GAP
    cursor = hi
    for i in reversed(order):
        top[i] = min(top[i] + heights[i], cursor) - heights[i]
        cursor = top[i] - LABEL_GAP
    return [top[i] + heights[i] / 2 for i in range(len(wants))]


def callouts(P, calls, sheet_w, sheet_h):
    marks, leads, texts = [], [], []
    sides = {"left": [], "right": []}
    for call in calls:
        cx, cy, reach, loops = target(call["ref"])
        marks.append(f'<path class="{call["kind"]}" d="{path_d(loops, P)}"/>')
        if call["ref"] == "wheel-ring":
            # The four arrows carry the directions, so the ring alone is weak.
            arrows = face_plan.wheel_arrows(*board.wheel_center())
            marks.append(f'<path class="pressfill" d="{path_d(arrows, P)}"/>')
        if call["kind"] == "watch" and call["ref"] in LED_CHAIN:
            fill = f' style="fill:{call["fill"]}"' if call.get("fill") else ""
            marks.append(
                f'<path class="leddot"{fill} d="{path_d([circle_pts(cx, cy, LED_DOT_R)], P)}"/>'
            )
        if call["lines"]:
            sign = -1 if call["side"] == "left" else 1
            sides[call["side"]].append((P(cx + sign * reach, cy), call))

    for side, items in sides.items():
        if not items:
            continue
        heights = [LINE_H * len(call["lines"]) for _, call in items]
        middles = pack(
            [anchor[1] for anchor, _ in items], heights, MARGIN, sheet_h - MARGIN
        )
        for (anchor, call), middle in zip(items, middles):
            ax, ay = anchor
            if side == "left":
                bend, end = ax - LEAD_IN, GUTTER - LEAD_INSET
                text_x, align = GUTTER - TEXT_INSET, "end"
            else:
                bend, end = ax + LEAD_IN, sheet_w - GUTTER + LEAD_INSET
                text_x, align = sheet_w - GUTTER + TEXT_INSET, "start"
            leads.append(
                f'<path class="leader lead{call["kind"]}" d="M{fmt(ax, 1)} {fmt(ay, 1)} '
                f'L{fmt(bend, 1)} {fmt(ay, 1)} L{fmt(end, 1)} {fmt(middle, 1)}"/>'
            )
            top = middle - LINE_H * len(call["lines"]) / 2
            for i, text in enumerate(call["lines"]):
                klass = "lname" if i == 0 else "ldetail"
                base = top + LINE_H * (i + 1) - 3.5
                texts.append(
                    f'<text class="{klass}" x="{fmt(text_x, 1)}" y="{fmt(base, 1)}" '
                    f'text-anchor="{align}">{escape(text)}</text>'
                )
    return "".join(marks) + "".join(leads) + "".join(texts)


def style():
    def tok(prop, key):
        return f"{prop}:{LIGHT[key]};{prop}:var(--{key})"

    rules = [
        ":root{" + ";".join(f"--{k}:{v}" for k, v in LIGHT.items()) + "}",
        "@media (prefers-color-scheme: dark){:root{"
        + ";".join(f"--{k}:{v}" for k, v in DARK.items())
        + "}}",
        f".press{{fill:none;{tok('stroke', 'act')};stroke-width:3;stroke-linejoin:round}}",
        f".pressfill{{{tok('fill', 'act')};stroke:none}}",
        f".watch{{fill:none;{tok('stroke', 'watch')};stroke-width:2.4}}",
        f".leddot{{{tok('fill', 'watch')};stroke:none}}",
        f".ledspot{{fill:none;{tok('stroke', 'muted')};stroke-width:1}}",
        f".ledpath{{fill:none;{tok('stroke', 'muted')};stroke-width:.8;"
        "stroke-opacity:.55;stroke-dasharray:3 4}",
        f".chain{{fill:none;{tok('stroke', 'act')};stroke-width:2.2;stroke-linecap:round}}",
        f".chainhead{{{tok('fill', 'act')};stroke:none}}",
        f".leader{{fill:none;{tok('stroke', 'muted')};stroke-width:1.1}}",
        f".leadpress{{{tok('stroke', 'act')}}}",
        f".leadwatch{{{tok('stroke', 'watch')}}}",
        f"text{{font-family:{FONT};{tok('fill', 'ink')}}}",
        ".lname{font-size:12px;font-weight:700}",
        f".ldetail{{font-size:10.5px;{tok('fill', 'muted')}}}",
    ]
    return "<style>" + "".join(rules) + "</style>"


def build(spec):
    ex0, ex1 = kp.exterior_x_bounds()
    ey0, ey1 = kp.exterior_y_bounds()
    plan_w, plan_h = (ex1 - ex0) * SCALE, (ey1 - ey0) * SCALE
    sheet_w, sheet_h = plan_w + 2 * GUTTER, plan_h + 2 * MARGIN

    def P(x, y):
        """Case plan to sheet. y is flipped so the IR end reads at the top."""
        return GUTTER + (x - ex0) * SCALE, MARGIN + (ey1 - y) * SCALE

    calls = [dict(kind="press", ref=ref, side="left", lines=[]) for ref in spec.get("quiet", ())]
    calls += spec["calls"]
    body = [
        face_plan.plan_view(P),
        ring_guide(P),
        led_spots(P, {call["ref"] for call in calls}),
    ]
    if spec.get("chain"):
        body.append(chain_arrows(P))
    body.append(callouts(P, calls, sheet_w, sheet_h))
    label = escape(spec["alt"])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(sheet_w)} {fmt(sheet_h)}" '
        f'width="{fmt(sheet_w)}" height="{fmt(sheet_h)}" role="img" aria-label="{label}">'
        f"<title>{label}</title>"
        + face_plan.plan_style()
        + style()
        + "".join(body)
        + "</svg>\n"
    )


# --- the sheets -----------------------------------------------------------


def press(ref, side, *lines):
    return dict(kind="press", ref=ref, side=side, lines=list(lines))


def watch(ref, side, *lines, fill=None):
    return dict(kind="watch", ref=ref, side=side, lines=list(lines), fill=fill)


LED_SIDE = {"D2": "left", "D3": "left", "D7": "left", "D4": "right", "D5": "right", "D6": "right"}

SHEETS = {
    "step-1-boot": dict(
        file="self-test-step-1-boot.svg",
        chain=True,
        alt=(
            "Front face of the remote with the boot animation. Arrows run clockwise "
            "round the wheel in chain order from D2 at the bottom left, through D3 at "
            "the top left, D6 at the top center, D4 at the top right and D5 at the "
            "bottom right, to D7 at the bottom center. D2 lights red, D3 azure, D6 "
            "magenta, D4 green, D5 blue and D7 cyan."
        ),
        calls=[
            watch(ref, LED_SIDE[ref], ref, CHASE_NAME[i], fill=CHASE_COLOUR[i])
            for i, ref in enumerate(LED_CHAIN)
        ],
    ),
    "step-2-inputs": dict(
        file="self-test-step-2-inputs.svg",
        quiet=[ref for ref in capmod.cap_refs() if ref != "SW2"],
        alt=(
            "Front face of the remote with every input marked for a press: the two "
            "buttons above the wheel, the nine buttons below it, the wheel direction "
            "ring and the wheel center."
        ),
        calls=[
            press("SW2", "left", "SW1 to SW11", "press each button"),
            press("wheel-ring", "right", "wheel", "press up, down,", "left and right"),
            press("wheel-center", "right", "wheel center", "press it once"),
        ],
    ),
    "step-3-microphone": dict(
        file="self-test-step-3-microphone.svg",
        alt=(
            "Front face of the remote with the wheel center marked for a 2 s hold and "
            "the microphone hole marked at the top center of the face."
        ),
        calls=[
            press("wheel-center", "right", "wheel center", "hold 2 s for the", "VU meter"),
            watch("mic", "right", "microphone hole", "speak at the front"),
        ],
    ),
    "step-4-ir-receive": dict(
        file="self-test-step-4-ir-receive.svg",
        alt=(
            "Front face of the remote for the IR receive check. The sheet marks no "
            "button, because the receiver is on the back of the board."
        ),
        calls=[],
    ),
    "step-5-ir-transmit": dict(
        file="self-test-step-5-ir-transmit.svg",
        alt=(
            "Front face of the remote with the top right button SW1 marked for a 2 s "
            "hold, and the IR LED D1 marked inside the top end."
        ),
        calls=[
            press("SW1", "right", "SW1", "hold 2 s"),
            watch("D1", "right", "D1 IR LED", "aim the phone", "camera here"),
        ],
    ),
    "step-6-battery": dict(
        file="self-test-step-6-battery.svg",
        alt=(
            "Front face of the remote for the battery check. The sheet marks no "
            "button, because the step disconnects USB power."
        ),
        calls=[],
    ),
    "step-7-usb-power": dict(
        file="self-test-step-7-usb-power.svg",
        alt=(
            "Front face of the remote for the USB power check. The sheet marks no "
            "button, because the step connects USB power again."
        ),
        calls=[],
    ),
    "step-8-sleep-wake": dict(
        file="self-test-step-8-sleep-wake.svg",
        alt=(
            "Front face of the remote with SW3, below the wheel at the top left, "
            "marked for the 3 s hold that sleeps the board and for the press that "
            "wakes it."
        ),
        calls=[
            press("SW3", "left", "SW3", "hold 3 s to sleep,", "press to wake"),
        ],
    ),
}



def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="comma list of sheet names, default all")
    ap.add_argument("-o", "--out-dir", help="where to write the SVGs")
    args = ap.parse_args()
    out_dir = Path(args.out_dir or OUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in args.only.split(",") if args.only else list(SHEETS):
        svg = build(SHEETS[name])
        out = out_dir / SHEETS[name]["file"]
        out.write_text(svg)
        print(f"wrote {out}, {len(svg) / 1024:.0f} kB")


if __name__ == "__main__":
    main()
