#!/usr/bin/env python3
"""Fill the copper zones and save the fill into the board file.

kicad-cli pcb drc --refill-zones fills in memory only. This script fills a copy
of the board with KiCad's Python in a temporary directory, because SaveBoard()
also rewrites the .kicad_pro and writes a .kicad_prl. It checks that only
filled_polygon blocks changed, copies the board back, and checks that DRC gives
the same result with and without --refill-zones.

  scripts/refill-zones.py                  # c6remote-kicad/c6remote.kicad_pcb
  scripts/refill-zones.py --dry-run        # fill and check, write nothing
  scripts/refill-zones.py --board PATH --no-drc

Override the binaries with KICAD_PYTHON and KICAD_CLI. Exit 0 on success, 1
when a check fails, 2 when KiCad is open or a tool fails.
"""

import argparse
import collections
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_PYTHON = (
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework"
    "/Versions/Current/bin/python3"
)
DEFAULT_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"

# Matched against the executable only, so a shell whose arguments name the
# app does not match. The standalone editors live in nested apps. kicad-cli
# and the KiCad MCP server's Python must not match.
GUI = re.compile(
    r"KiCad\.app/Contents/(?:Applications/\w+\.app/Contents/)?"
    r"MacOS/(?:kicad|pcbnew|eeschema)$"
)
# import pcbnew prints these on every run.
NOISE = re.compile(r"^(?:Fontconfig |\S+\(\d+\): assert )")


def err(msg):
    sys.stdout.flush()
    print(msg, file=sys.stderr)


def fail(msg, code=2):
    err(msg)
    sys.exit(code)


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True)
    except OSError as e:
        fail(f"cannot run {cmd[0]}: {e}")


def kicad_cli():
    # Same lookup as check-design.py.
    override = os.environ.get("KICAD_CLI")
    if override:
        return override
    found = shutil.which("kicad-cli")
    if found:
        return found
    if Path(DEFAULT_CLI).exists():
        return DEFAULT_CLI
    fail("kicad-cli not found; set KICAD_CLI")


def kicad_python():
    override = os.environ.get("KICAD_PYTHON")
    if override:
        return override
    if importlib.util.find_spec("pcbnew"):
        return sys.executable
    if Path(DEFAULT_PYTHON).exists():
        return DEFAULT_PYTHON
    fail("KiCad Python not found; set KICAD_PYTHON")


def kicad_gui():
    ps = run(["ps", "-Ao", "pid=,comm="])
    lines = [line.strip() for line in ps.stdout.splitlines()]
    return [line for line in lines if GUI.search(line)]


def repo_root():
    here = Path(__file__).resolve().parent
    git = run(["git", "-C", str(here), "rev-parse", "--show-toplevel"])
    return Path(git.stdout.strip()) if git.returncode == 0 else here.parent


def zone_rows(board):
    rows = []
    for zone in board.Zones():
        if zone.GetIsRuleArea():
            continue
        for layer in zone.GetLayerSet().Seq():
            outlines = zone.GetFilledPolysList(layer).OutlineCount()
            rows.append([zone.GetNetname(), board.GetLayerName(layer), outlines])
    return rows


def fill_child(board_path, out_path):
    import pcbnew

    board = pcbnew.LoadBoard(board_path)
    if board is None:
        print("LoadBoard() failed")
        return 1
    before = zone_rows(board)
    if not pcbnew.ZONE_FILLER(board).Fill(board.Zones()):
        print("ZONE_FILLER.Fill() failed")
        return 1
    after = zone_rows(board)
    if not pcbnew.SaveBoard(board_path, board):
        print("SaveBoard() failed")
        return 1
    Path(out_path).write_text(json.dumps({"before": before, "after": after}))
    return 0


def run_fill(python, board, out):
    cmd = [python, str(Path(__file__).resolve()), "--fill-child", str(board), str(out)]
    proc = run(cmd)
    lines = (proc.stdout + proc.stderr).splitlines()
    lines = [line for line in lines if not NOISE.match(line)]
    if proc.returncode != 0 or not out.exists():
        err("\n".join(lines))
        fail(f"zone fill failed (exit {proc.returncode}): {' '.join(cmd)}")
    for line in lines:
        print(f"  pcbnew: {line}")
    return json.loads(out.read_text())


def show_zones(counts):
    print("Zone fill outlines (stored -> new):")
    for (net, layer, old), (_, _, new) in zip(counts["before"], counts["after"]):
        mark = "" if old == new else "  changed"
        print(f"  {net or '(no net)':<12} {layer:<8} {old} -> {new}{mark}")


def strip_fills(text):
    kept, depth = [], 0
    for n, line in enumerate(text.splitlines(keepends=True), 1):
        if depth == 0 and not line.lstrip().startswith("(filled_polygon"):
            kept.append((n, line))
            continue
        depth += line.count("(") - line.count(")")
        if depth < 0:
            # The block's last line also closes its parent. Keep that line.
            kept.append((n, line))
            depth = 0
    return kept


def first_difference(old, new):
    a = strip_fills(old.decode("utf-8", "surrogateescape"))
    b = strip_fills(new.decode("utf-8", "surrogateescape"))
    for (na, la), (nb, lb) in zip(a, b):
        if la != lb:
            return f"stored line {na}: {la.rstrip()}\nnew line {nb}: {lb.rstrip()}"
    if len(a) == len(b):
        return None
    label, extra = ("stored", a) if len(a) > len(b) else ("new", b)
    n, line = extra[min(len(a), len(b))]
    return f"only the {label} board has line {n}: {line.rstrip()}"


def snapshot(board):
    files = {}
    for suffix in (".kicad_pro", ".kicad_prl"):
        path = board.with_suffix(suffix)
        files[path] = path.read_bytes() if path.exists() else None
    reports = {p: p.stat().st_mtime_ns for p in board.parent.glob("*.rpt")}
    return files, reports


def restore(board, snap):
    # kicad-cli drops reports and writes a .kicad_prl when none exists.
    files, reports = snap
    for path, data in files.items():
        if data is None:
            if path.exists():
                path.unlink()
                print(f"  removed {path.name} written by kicad-cli")
        elif not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)
            print(f"  restored {path.name} changed by kicad-cli")
    for path in board.parent.glob("*.rpt"):
        if reports.get(path) != path.stat().st_mtime_ns:
            path.unlink()


def drc(cli, board, report, refill):
    cmd = [cli, "pcb", "drc", str(board), "--schematic-parity"]
    if refill:
        cmd.append("--refill-zones")
    cmd += ["--format", "json", "-o", str(report)]
    proc = run(cmd)
    if not report.exists():
        err(proc.stdout + proc.stderr)
        fail(f"no report written by: {' '.join(cmd)}")
    return json.loads(report.read_text())


def drc_key(v):
    pos = sorted(
        ((i.get("pos") or {}).get("x", 0.0), (i.get("pos") or {}).get("y", 0.0))
        for i in v.get("items", [])
    )
    return (
        v.get("type", "?"),
        v.get("severity", "?"),
        v.get("description", ""),
        tuple(pos),
    )


def drc_summary(data):
    violations = collections.Counter(drc_key(v) for v in data.get("violations", []))
    unconnected = len(data.get("unconnected_items", []))
    return violations, unconnected, len(data.get("schematic_parity", []))


def show_summary(label, summary):
    violations, unconnected, parity = summary
    types = collections.Counter(k[0] for k in violations.elements())
    detail = ", ".join(f"{t} {n}" for t, n in sorted(types.items()))
    detail = f" ({detail})" if detail else ""
    print(
        f"  {label}: {sum(violations.values())} violations{detail}, "
        f"{unconnected} unconnected, {parity} parity"
    )


def compare_drc(cli, board, tmp, label, guard):
    results = []
    for refill in (False, True):
        snap = snapshot(board) if guard else None
        try:
            data = drc(cli, board, tmp / f"drc-{int(refill)}.json", refill)
        finally:
            if snap:
                restore(board, snap)
        results.append(drc_summary(data))
    stored, refilled = results

    print(f"DRC on {label}:")
    show_summary("stored fill   ", stored)
    show_summary("--refill-zones", refilled)
    if stored == refilled:
        print("DRC results match.")
        return True
    for label, extra in (
        ("stored fill only", stored[0] - refilled[0]),
        ("--refill-zones only", refilled[0] - stored[0]),
    ):
        for (kind, severity, desc, pos), n in sorted(extra.items()):
            print(f"  {label}: {n}x [{severity}] {kind}: {desc} at {list(pos)}")
    err("DRC results differ.")
    return False


def prepare_drc_copy(board, work_board):
    # SaveBoard() rewrote the copied .kicad_pro. Parity needs the schematic,
    # and ${KIPRJMOD} must still point at the real project libraries.
    work = work_board.parent
    for suffix in (".kicad_pro", ".kicad_sch"):
        src = board.with_suffix(suffix)
        if src.exists():
            shutil.copyfile(src, work_board.with_suffix(suffix))
    for name in ("fp-lib-table", "sym-lib-table"):
        src = board.parent / name
        if src.exists():
            text = src.read_text(encoding="utf-8")
            text = text.replace("${KIPRJMOD}", str(board.parent))
            (work / name).write_text(text, encoding="utf-8")


def main():
    if sys.argv[1:2] == ["--fill-child"]:
        return fill_child(sys.argv[2], sys.argv[3])

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--board", type=Path, help="default: c6remote-kicad/c6remote.kicad_pcb"
    )
    ap.add_argument("--no-drc", action="store_true", help="skip the DRC comparison")
    ap.add_argument(
        "--dry-run", action="store_true", help="fill and check, write nothing"
    )
    args = ap.parse_args()

    board = args.board or repo_root() / "c6remote-kicad" / "c6remote.kicad_pcb"
    board = board.resolve()
    if board.suffix != ".kicad_pcb" or not board.is_file():
        fail(f"not a board file: {board}")
    if not board.with_suffix(".kicad_pro").is_file():
        fail(f"missing project file: {board.with_suffix('.kicad_pro')}")

    gui = kicad_gui()
    if gui:
        fail(
            "KiCad is open. Close it, then run again. The GUI can overwrite the"
            " board or keep a stale copy.\n  " + "\n  ".join(gui)
        )

    python = kicad_python()
    cli = None if args.no_drc else kicad_cli()
    print(f"board: {board}")
    print(f"KiCad Python: {python}")
    if cli:
        print(f"kicad-cli: {cli}")

    with tempfile.TemporaryDirectory(prefix="refill-zones-") as td:
        tmp = Path(td)
        work = tmp / "project"
        work.mkdir()
        work_board = work / board.name
        old = board.read_bytes()
        work_board.write_bytes(old)
        for src in (
            board.with_suffix(".kicad_pro"),
            board.parent / "fp-lib-table",
            board.parent / "sym-lib-table",
        ):
            if src.exists():
                shutil.copyfile(src, work / src.name)

        counts = run_fill(python, work_board, tmp / "zones.json")
        show_zones(counts)

        new = work_board.read_bytes()
        changed = old != new
        if changed:
            diff = first_difference(old, new)
            if diff:
                err("Content outside filled_polygon blocks changed. Board not written.")
                err(diff)
                return 1
            print("Only filled_polygon blocks changed.")
        else:
            print("The stored fill is already current. Board not written.")

        if changed and args.dry_run:
            print("Dry run. Board not written.")
        elif changed:
            if board.read_bytes() != old:
                fail("The board changed on disk during the fill. Board not written.")
            shutil.copyfile(work_board, board)
            print(f"Wrote {board}")

        if args.no_drc:
            return 0
        if args.dry_run:
            prepare_drc_copy(board, work_board)
            ok = compare_drc(cli, work_board, tmp, "the filled copy", guard=False)
        else:
            ok = compare_drc(cli, board, tmp, board, guard=True)
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
