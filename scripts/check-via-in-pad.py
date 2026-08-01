#!/usr/bin/env python3
"""Report vias that sit in or near a pad, the fab house's solder-paste leakage check.

Usage: scripts/check-via-in-pad.py [board.kicad_pcb] [--gap MM]

Exits 1 when any via overlaps a pad (gap < 0). --gap widens the report so near
misses are visible; it never changes the exit code.
"""

import argparse
import math
import os
import sys


def parse(text):
    """Minimal s-expression reader: returns nested lists of str."""
    root = []
    stack = [root]
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == "(":
            node = []
            stack[-1].append(node)
            stack.append(node)
            i += 1
        elif c == ")":
            stack.pop()
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while text[j] != '"' or text[j - 1] == "\\":
                buf.append(text[j])
                j += 1
            stack[-1].append("".join(buf))
            i = j + 1
        elif c.isspace():
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()"':
                j += 1
            stack[-1].append(text[i:j])
            i = j
    return root[0]


def children(node, name):
    return [x for x in node if isinstance(x, list) and x and x[0] == name]


def first(node, name):
    found = children(node, name)
    return found[0] if found else None


def read_vias(board):
    out = []
    for via in children(board, "via"):
        at, size, net = first(via, "at"), first(via, "size"), first(via, "net")
        out.append(
            {
                "x": float(at[1]),
                "y": float(at[2]),
                "d": float(size[1]),
                "net": net[1] if net else "",
            }
        )
    return out


def read_pads(board):
    """Pad rectangles in board coordinates. Circles and ovals are treated as
    their bounding box, which errs toward reporting rather than missing."""
    out = []
    for fp in children(board, "footprint"):
        fat = first(fp, "at")
        fx, fy = float(fat[1]), float(fat[2])
        frot = float(fat[3]) if len(fat) > 3 else 0.0
        ref = next(
            (p[2] for p in children(fp, "property") if p[1] == "Reference"), "?"
        )
        for pad in children(fp, "pad"):
            pat, psize = first(pad, "at"), first(pad, "size")
            px, py = float(pat[1]), float(pat[2])
            a = math.radians(-frot)
            w, h = float(psize[1]), float(psize[2])
            padrot = float(pat[3]) if len(pat) > 3 else 0.0
            if abs((frot + padrot) % 180 - 90) < 1:
                w, h = h, w
            out.append(
                {
                    "ref": ref,
                    "num": pad[1],
                    "type": pad[2],
                    "shape": pad[3],
                    "x": fx + px * math.cos(a) - py * math.sin(a),
                    "y": fy + px * math.sin(a) + py * math.cos(a),
                    "w": w,
                    "h": h,
                }
            )
    return out


def main():
    ap = argparse.ArgumentParser()
    default = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "c6remote-kicad",
        "c6remote.kicad_pcb",
    )
    ap.add_argument("board", nargs="?", default=os.path.normpath(default))
    ap.add_argument(
        "--gap",
        type=float,
        default=0.0,
        help="also list vias clearing a pad by less than this, in mm",
    )
    args = ap.parse_args()

    board = parse(open(args.board).read())
    vias, pads = read_vias(board), read_pads(board)

    hits = []
    for v in vias:
        for p in pads:
            dx = max(abs(v["x"] - p["x"]) - p["w"] / 2.0, 0.0)
            dy = max(abs(v["y"] - p["y"]) - p["h"] / 2.0, 0.0)
            gap = math.hypot(dx, dy) - v["d"] / 2.0
            if gap < max(args.gap, 0.0) or gap < 0:
                hits.append((gap, v, p))

    print(f"{os.path.basename(args.board)}: {len(vias)} vias, {len(pads)} pads")
    for gap, v, p in sorted(hits, key=lambda t: t[0]):
        state = "IN PAD" if gap < 0 else "near"
        print(
            f"  {state:6s} gap={gap:+.3f}mm  via ({v['x']:.3f}, {v['y']:.3f}) "
            f"d{v['d']} net '{v['net']}'  pad {p['ref']}.{p['num']} "
            f"{p['type']} {p['shape']} ({p['x']:.3f}, {p['y']:.3f}) {p['w']}x{p['h']}"
        )

    overlaps = [h for h in hits if h[0] < 0]
    if overlaps:
        print(f"FAIL: {len(overlaps)} via/pad overlaps")
        return 1
    print("PASS: no via overlaps a pad")
    return 0


if __name__ == "__main__":
    sys.exit(main())
