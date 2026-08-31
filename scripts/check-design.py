#!/usr/bin/env python3
"""Run ERC and DRC and compare the result against the documented baseline.

The baseline in AGENTS.md has no ERC violations and six allowed DRC warnings.
It has no unconnected items or schematic parity issues. Anything else is a
regression from the change under test.

DRC runs with --refill-zones because without it the stored fill is what gets
checked, and a stale fill reports phantom isolated_copper and zone-to-zone
unconnected_items.

  scripts/check-design.py              # both checks
  scripts/check-design.py --only erc   # or --only drc

Override the binary with KICAD_CLI=/path/to/kicad-cli. Exit 0 when the result
matches the baseline, 1 when it does not, 2 on a usage or tooling error.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROJECT = REPO / "c6remote-kicad"
SCH = PROJECT / "c6remote.kicad_sch"
PCB = PROJECT / "c6remote.kicad_pcb"

DEFAULT_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"

# (type, first item description) pairs that predate current work. U1 has an
# edited board footprint. The XIAO labels use a small text height. The product
# label uses TrueType characters with insufficient stroke weight.
ALLOWED_DRC = {
    ("lib_footprint_mismatch", "Footprint U1"),
    (
        "text_height",
        "PCB text '8\n\n9\n\n10\n\n11\n\n12\n\ngnd\n\nvcc' on F.Silkscreen",
    ),
    (
        "text_height",
        "PCB text '7\n\n6\n\n5\n\n4\n\n3\n\n2\n\n1' on F.Silkscreen",
    ),
    (
        "text_height",
        "PCB text '8\n\n9\n\n10\n\n11\n\n12\n\ngnd\n\nvcc' on B.Silkscreen",
    ),
    (
        "text_height",
        "PCB text '7\n\n6\n\n5\n\n4\n\n3\n\n2\n\n1' on B.Silkscreen",
    ),
    (
        "text_thickness",
        "PCB text 'homeThing-c6 v1.3\n2026.8.1' on F.Silkscreen",
    ),
}


def kicad_cli():
    override = os.environ.get("KICAD_CLI")
    if override:
        return override
    found = shutil.which("kicad-cli")
    if found:
        return found
    if Path(DEFAULT_CLI).exists():
        return DEFAULT_CLI
    sys.exit("kicad-cli not found; set KICAD_CLI")


def run(cli, args, report):
    cmd = [cli, *args, "--format", "json", "-o", str(report)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if not report.exists():
        sys.exit(f"no report written by: {' '.join(cmd)}")
    return json.loads(report.read_text())


def key(v):
    items = v.get("items") or [{}]
    return (v.get("type", "?"), items[0].get("description", ""))


def show(label, violations):
    print(f"  {label}:")
    for v in violations:
        t, where = key(v)
        print(f"    [{v.get('severity','?')}] {t} on {where or '?'}: {v.get('description','')}")


def check_erc(cli, tmp):
    data = run(cli, ["sch", "erc", str(SCH)], tmp / "erc.json")
    found = data.get("violations", [])
    print(f"ERC: {len(found)} violations (baseline 0)")
    if found:
        show("unexpected", found)
    return not found


def check_drc(cli, tmp):
    data = run(
        cli,
        ["pcb", "drc", str(PCB), "--schematic-parity", "--refill-zones"],
        tmp / "drc.json",
    )
    found = data.get("violations", [])
    unexpected = [v for v in found if key(v) not in ALLOWED_DRC]
    unconnected = data.get("unconnected_items", [])
    parity = data.get("schematic_parity", [])

    print(
        f"DRC: {len(found)} violations ({len(unexpected)} unexpected), "
        f"{len(unconnected)} unconnected, {len(parity)} parity "
        f"(baseline 6 allowed warnings, 0, 0)"
    )
    if unexpected:
        show("unexpected violations", unexpected)
    if unconnected:
        show("unconnected", unconnected)
    if parity:
        show("parity", parity)
    return not (unexpected or unconnected or parity)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["erc", "drc"])
    args = ap.parse_args()

    cli = kicad_cli()
    print(f"kicad-cli: {cli}")
    ok = True
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        if args.only != "drc":
            ok &= check_erc(cli, tmp)
        if args.only != "erc":
            ok &= check_drc(cli, tmp)

    sys.stdout.flush()
    if not ok:
        print("\nRegression from the AGENTS.md baseline.", file=sys.stderr)
        return 1
    print("\nMatches baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
