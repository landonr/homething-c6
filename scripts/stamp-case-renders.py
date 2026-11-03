#!/usr/bin/env python3
"""Tell when the README case renders no longer show the committed board and case.

The case renders come from the sibling c6remote-explode checkout and are copied
in by hand, so nothing else notices when the geometry moves on. The fingerprint
hashes git blob ids, not working-tree bytes, so it follows what is committed.

    stamp-case-renders.py                    print the index fingerprint
    stamp-case-renders.py --write [--rev R]  record the renders' sources in the stamp
    stamp-case-renders.py --check [--strict] warn when the index differs from the stamp
"""

import argparse
import hashlib
import os
import subprocess
import sys
from pathlib import Path

INPUTS = (
    'c6remote-kicad/c6remote.kicad_pcb',
    'scripts/board_extras.py',
    'case/case.py',
    'case/params.py',
    'case/board.py',
    'case/cache.py',
    'case/model/',
    'case/fonts/DejaVuSans.ttf',
    'case/glyphs/',
)
"""Tracked sources of what the case renders show. cache.py sets the STL mesh
tolerance, and the font and glyphs cut the key legends. case/board/*.step is
left out because its export embeds a timestamp, and the PCB already covers it."""

RENDERS = (
    'case-annotated-front.png',
    'case-annotated-back.png',
    'case-assembled.png',
    'case-exploded.png',
    'case-explode-loop.webp',
    'remote-controls-annotated.svg',
    'remote-controls-annotated-dark.svg',
    'remote-back-annotated.svg',
    'remote-back-annotated-dark.svg',
)

ROOT = Path(__file__).resolve().parents[1]
STAMP = ROOT / 'docs/readme-assets/case-renders.stamp'
TAG = '[case-renders]'


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def fingerprint(rev=None):
    if rev:
        # <mode> <type> <blob>\t<path>
        out, blob = git('ls-tree', '-r', '-z', rev, '--', *INPUTS), 2
    else:
        # <mode> <blob> <stage>\t<path>
        out, blob = git('ls-files', '-s', '-z', '--', *INPUTS), 1
    lines = []
    for entry in filter(None, out.split('\0')):
        meta, path = entry.split('\t', 1)
        lines.append(f'{path} {meta.split()[blob]}')
    if not lines:
        sys.exit(f'{TAG} no input file found in {rev or "the index"}')
    return hashlib.sha256(('\n'.join(sorted(lines)) + '\n').encode()).hexdigest()


def read_stamp():
    if not STAMP.exists():
        return None
    fields = {}
    for line in STAMP.read_text().splitlines():
        key, _, value = line.partition(' ')
        fields.setdefault(key, value)
    return fields


def write(rev):
    source = git('rev-parse', '--verify', f'{rev}^{{commit}}').strip() if rev else 'index'
    lines = [f'fingerprint {fingerprint(rev)}', f'source {source}', *(f'input {p}' for p in INPUTS)]
    STAMP.write_text('\n'.join(lines) + '\n')
    print(f'{TAG} wrote {STAMP.relative_to(ROOT)} from {source}')


def inputs_staged():
    """True when the index changes an input relative to HEAD."""
    return subprocess.run(['git', 'diff', '--cached', '--quiet', '--', *INPUTS], cwd=ROOT).returncode != 0


def check(strict):
    current = fingerprint()
    stamp = read_stamp()
    if stamp and stamp.get('fingerprint') == current:
        print(f'{TAG} case renders match the staged board and case sources')
        return 0

    explode = Path(os.environ.get('C6REMOTE_EXPLODE', ROOT.parent / 'c6remote-explode')).resolve()

    def say(text):
        print(f'{TAG} {text}', file=sys.stderr)

    if stamp is None:
        say(f'WARNING: no {STAMP.relative_to(ROOT)}, so the case renders count as stale.')
    else:
        source = stamp.get('source', '?')
        say(f'WARNING: the case renders are stale. Stamp {stamp.get("fingerprint", "?")[:12]} '
            f'from {source[:12]}, index {current[:12]}.')
        if source != 'index':
            changed = git('diff', '--cached', '--name-only', source, '--', *INPUTS).split()
            if changed:
                say('Changed since the stamp: ' + ', '.join(changed))
    say('Stale files in docs/readme-assets/: ' + ', '.join(RENDERS))
    say('To refresh them:')
    print(f'''  1. In this checkout, export the board GLB and build the case STLs:
       scripts/export-case-refs.sh
       case/.venv/bin/python case/case.py
  2. In {explode}, copy that geometry in:
       REPO={ROOT} ./refresh-assets.sh
  3. Render there with the case scripts. Add --rig to render on the Rig:
       scripts/render-case-assembled.sh --blender
       scripts/render-case-exploded.sh --blender
       scripts/render-case-explode-loop.sh
       python3 scripts/render-blender.py --preset readme-annotated-front --width 900 --out-default case-annotated-front.png
       python3 scripts/render-blender.py --preset readme-annotated-back --width 900 --out-default case-annotated-back.png
  4. Copy the dated outputs into docs/readme-assets/ under the case-* names above.
  5. python3 scripts/render-annotated-remote.py
  6. python3 scripts/stamp-case-renders.py --write''', file=sys.stderr)
    return 1 if strict else 0


def main():
    parser = argparse.ArgumentParser(description='Fingerprint the sources that the README case renders show.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--write', action='store_true', help='write the stamp from the index, or from --rev')
    mode.add_argument('--check', action='store_true', help='warn when the index fingerprint differs from the stamp')
    parser.add_argument('--rev', help='read this commit instead of the index (fingerprint and --write)')
    parser.add_argument('--strict', action='store_true', help='with --check, exit 1 when stale')
    parser.add_argument('--if-staged', action='store_true',
                        help='with --check, stay silent unless the index changes an input (for the pre-commit hook)')
    args = parser.parse_args()
    if args.check and args.rev:
        parser.error('--check always reads the index')

    if args.write:
        write(args.rev)
        return 0
    if args.check:
        if args.if_staged and not inputs_staged():
            return 0
        return check(args.strict)
    print(fingerprint(args.rev))
    return 0


if __name__ == '__main__':
    sys.exit(main())
