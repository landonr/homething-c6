#!/usr/bin/env python3
"""Fill the copper zones and save the fill into the board file.

kicad-cli pcb drc --refill-zones fills in memory only. This script fills a copy
of the board with KiCad's Python in a temporary directory, because SaveBoard()
also rewrites the .kicad_pro and writes a .kicad_prl. It checks that only
filled_polygon blocks changed, copies the board back, and checks that DRC gives
the same result with and without --refill-zones. The first check ignores item
order, number format, and number changes up to NOISE_MM, because a KiCad save
makes these changes to a board that another tool wrote.

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

TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()"]+')
NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
# KiCad stores 1 nm integers, so a rotated footprint can re-save a coordinate 1 nm off.
NOISE_MM = 1e-5

Noise = collections.namedtuple("Noise", "numbers max_mm reordered")


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


class Node(list):
    """One parenthesised list. Its atoms are (line, text) tuples."""

    def __init__(self, line):
        super().__init__()
        self.line = line


def head(item):
    if isinstance(item, tuple):
        return item[1]
    return item[0][1] if item and isinstance(item[0], tuple) else ""


def line_of(item):
    return item.line if isinstance(item, Node) else item[0]


def parse_tree(text):
    # Drops every filled_polygon list, at any depth.
    stack = [Node(0)]
    line, pos = 1, 0
    for m in TOKEN.finditer(text):
        line += text.count("\n", pos, m.start())
        pos = m.start()
        tok = m.group()
        if tok == "(":
            stack.append(Node(line))
        elif tok == ")":
            if len(stack) < 2:
                raise ValueError(f"unmatched ) at line {line}")
            node = stack.pop()
            if head(node) != "filled_polygon":
                stack[-1].append(node)
        else:
            stack[-1].append((line, tok))
    root = stack[0]
    if len(stack) != 1 or len(root) != 1 or not isinstance(root[0], Node):
        raise ValueError("the file is not one complete list")
    return root[0]


def item_uuid(item):
    if isinstance(item, Node):
        for child in item[1:]:
            if (
                isinstance(child, Node)
                and len(child) == 2
                and head(child) == "uuid"
                and isinstance(child[1], tuple)
            ):
                return child[1][1]
    return None


def item_keys(items):
    # Items without a uuid match in order among themselves.
    keys, seen = [], collections.Counter()
    for item in items:
        uuid = item_uuid(item)
        keys.append((uuid, seen[uuid]))
        seen[uuid] += 1
    return keys


def describe(item):
    uuid = item_uuid(item)
    return f"{head(item)} {uuid}" if uuid else head(item)


def mismatch(a, b, tally):
    """Return the (stored line, new line) of the first difference, or None."""
    if isinstance(a, Node) and isinstance(b, Node):
        for x, y in zip(a, b):
            hit = mismatch(x, y, tally)
            if hit:
                return hit
        if len(a) == len(b):
            return None
        n = min(len(a), len(b))
        return (
            line_of(a[n]) if len(a) > n else a.line,
            line_of(b[n]) if len(b) > n else b.line,
        )
    if isinstance(a, Node) or isinstance(b, Node):
        return line_of(a), line_of(b)
    if a[1] == b[1]:
        return None
    if NUMBER.fullmatch(a[1]) and NUMBER.fullmatch(b[1]):
        delta = abs(float(a[1]) - float(b[1]))
        if delta <= NOISE_MM:
            tally[0] += 1
            tally[1] = max(tally[1], delta)
            return None
    return a[0], b[0]


def compare_boards(old, new):
    """Compare two board files outside the filled_polygon blocks.

    Return (difference, Noise). The difference is None or a message.
    """
    texts = [data.decode("utf-8", "surrogateescape") for data in (old, new)]
    trees = []
    for label, text in zip(("stored", "new"), texts):
        try:
            trees.append(parse_tree(text))
        except ValueError as e:
            return f"cannot parse the {label} board: {e}", Noise(0, 0.0, False)
    a, b = trees
    lines = [text.split("\n") for text in texts]
    tally = [0, 0.0]

    def report(hit):
        na, nb = hit
        return (
            f"stored line {na}: {lines[0][na - 1].strip()}\n"
            f"new line {nb}: {lines[1][nb - 1].strip()}"
        )

    if head(a) != head(b):
        return report((a.line, b.line)), Noise(0, 0.0, False)
    old_items, new_items = a[1:], b[1:]
    old_keys, new_keys = item_keys(old_items), item_keys(new_items)
    new_by_key = dict(zip(new_keys, new_items))
    for key, item in zip(old_keys, old_items):
        other = new_by_key.get(key)
        if other is None:
            msg = f"only the stored board has {describe(item)} at line {line_of(item)}"
            return msg, Noise(*tally, False)
        hit = mismatch(item, other, tally)
        if hit:
            return report(hit), Noise(*tally, False)
    old_set = set(old_keys)
    for key, item in zip(new_keys, new_items):
        if key not in old_set:
            msg = f"only the new board has {describe(item)} at line {line_of(item)}"
            return msg, Noise(*tally, False)
    return None, Noise(tally[0], tally[1], old_keys != new_keys)


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
            diff, noise = compare_boards(old, new)
            if diff:
                err("Content outside filled_polygon blocks changed. Board not written.")
                err(diff)
                return 1
            ignored = []
            if noise.numbers:
                ignored.append(
                    f"{noise.numbers} numbers within NOISE_MM"
                    f" (max {noise.max_mm:.6f} mm)"
                )
            if noise.reordered:
                ignored.append("item order changed")
            if ignored:
                print(
                    "Ignored KiCad save noise outside filled_polygon blocks: "
                    + ", ".join(ignored)
                    + "."
                )
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
