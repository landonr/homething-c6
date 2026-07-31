#!/usr/bin/env python3
"""Detect eeschema clobbering board settings in c6remote.kicad_pro.

A save in the schematic editor rewrites the whole project file from the copy
eeschema loaded when the project was opened, so board settings changed in
pcbnew since then silently revert. See the drift bullet in AGENTS.md.

Compares a candidate version of the project file against HEAD on the fields
that have bitten this project, and reports any that moved.

  scripts/check-kicad-pro-drift.py            # staged blob vs HEAD (hook mode)
  scripts/check-kicad-pro-drift.py --worktree  # working tree vs HEAD

Exit 0 when the protected fields match HEAD or the file is absent from the
comparison, 1 when any drifted, 2 on a usage or parse error.
"""

import json
import subprocess
import sys

PRO = "c6remote-kicad/c6remote.kicad_pro"

# Whole dicts rather than a hand-picked field list: the first version guarded
# only the five board severities seen drifting, and the very next clobber landed
# on erc.rule_severities.pin_to_pin instead. Anything a stale editor copy can
# revert belongs here.
GUARDED_DICTS = (
    ("board", "design_settings", "rules"),
    ("board", "design_settings", "rule_severities"),
    ("erc", "rule_severities"),
)


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False
    )


def blob(rev):
    """Return parsed JSON for PRO at rev, or None if not present there."""
    spec = f"{rev}:{PRO}" if rev != ":" else f":{PRO}"
    r = git("show", spec)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f"[pro-drift] cannot parse {spec}: {e}", file=sys.stderr)
        sys.exit(2)


def fields(d):
    """Flatten the guarded subset into one flat dict of dotted path -> value."""
    out = {}
    for path in GUARDED_DICTS:
        node = d
        for k in path:
            node = node.get(k, {}) if isinstance(node, dict) else {}
        prefix = ".".join(path)
        for k, v in (node.items() if isinstance(node, dict) else ()):
            out[f"{prefix}.{k}"] = v
    classes = d.get("net_settings", {}).get("classes", [])
    out["net_settings.classes (names)"] = [c.get("name") for c in classes]
    for c in classes:
        if c.get("name") == "Default":
            out["net_settings.Default.priority"] = c.get("priority")
    return out


def main():
    args = sys.argv[1:]
    if args and args != ["--worktree"]:
        print(__doc__, file=sys.stderr)
        return 2

    head = blob("HEAD")
    if head is None:
        return 0  # no committed baseline to compare against

    if args == ["--worktree"]:
        try:
            with open(PRO) as fh:
                cand = json.load(fh)
        except FileNotFoundError:
            return 0
        except json.JSONDecodeError as e:
            print(f"[pro-drift] cannot parse {PRO}: {e}", file=sys.stderr)
            return 2
        label = "working tree"
    else:
        if PRO not in git("diff", "--cached", "--name-only").stdout.split("\n"):
            return 0  # not part of this commit
        cand = blob(":")
        if cand is None:
            return 0
        label = "staged"

    ref, got = fields(head), fields(cand)
    drifted = [k for k in ref if ref[k] != got[k]]
    if not drifted:
        return 0

    print(
        f"[pro-drift] BLOCKED: {label} {PRO} moved on {len(drifted)} guarded "
        f"field(s) vs HEAD",
        file=sys.stderr,
    )
    for k in drifted:
        print(f"[pro-drift]   {k}: {ref[k]!r} -> {got[k]!r}", file=sys.stderr)
    print(
        "[pro-drift] Usual cause: a save in eeschema rewrote the project file "
        "from the stale copy it loaded at open time, reverting board settings. "
        "Fix with: git checkout -- " + PRO,
        file=sys.stderr,
    )
    print(
        "[pro-drift] If the change IS deliberate, commit with --no-verify and "
        "say so in the message.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
