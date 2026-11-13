#!/usr/bin/env python3
"""Write the c6remote front face plan as one SVG sheet.

scripts/face_plan.py holds the drawing. This script is the command line for the
three sheets: the web page plan, and the detailed SLS and FDM README faces."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import face_plan  # noqa: E402
from face_plan import OUTPUTS, ROOT, build_plan, fmt  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--version",
        choices=sorted(OUTPUTS),
        default="web",
        help="web: the web page plan. sls, fdm: detailed README faces",
    )
    ap.add_argument("-o", "--out", help="where to write the SVG")
    args = ap.parse_args()
    if args.version != "web":
        vars(face_plan).update(face_plan.DETAIL)
    svg, w, h = build_plan(args.version)
    out = Path(args.out or ROOT / "docs" / "readme-assets" / OUTPUTS[args.version])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg)
    print(f"wrote {out}, {fmt(w)} by {fmt(h)} px, {len(svg) / 1024:.0f} kB")


if __name__ == "__main__":
    main()
