#!/usr/bin/env python3
"""Tell which tracked renders are stale, and how to refresh them.

scripts/renders.json lists the render groups. A fingerprint hashes the git blob ids of
a group's inputs, so it follows the index or a commit, not the working tree.

    render-status.py [--check] [GROUP...] [--strict] [--if-staged]
    render-status.py --write GROUP... [--rev R] [--stage] [--allow-unstaged]
    render-status.py --list
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'scripts/renders.json'
STAMP = 'docs/readme-assets/renders.stamp.json'
TAG = '[renders]'
MADE_BY = ('hook', 'repo', 'c6remote-explode', 'static')


def fail(text):
    sys.exit(f'{TAG} ERROR: {text}')


def git(root, *args, check=True, stdin=None):
    run = subprocess.run(['git', '--literal-pathspecs', *args], cwd=root, input=stdin,
                         capture_output=True, text=True)
    if check and run.returncode:
        fail(f'git {" ".join(args)} failed: {run.stderr.strip()}')
    return run


def load_manifest(root=ROOT):
    try:
        groups = json.loads((root / MANIFEST).read_text())
    except (OSError, ValueError) as err:
        fail(f'cannot read {MANIFEST}: {err}')
    for name, group in groups.items():
        missing = sorted({'description', 'made_by', 'outputs'} - group.keys())
        if missing:
            fail(f'{name}: no {", ".join(missing)} in {MANIFEST}')
        if group['made_by'] not in MADE_BY:
            fail(f'{name}: made_by {group["made_by"]!r} is not one of {", ".join(MADE_BY)}')
        if group['made_by'] == 'static':
            if group.get('inputs') or group.get('refresh'):
                fail(f'{name}: a static group has no inputs and no refresh steps')
        elif not group.get('inputs') or not group.get('refresh'):
            fail(f'{name}: a {group["made_by"]} group needs inputs and refresh steps')
    return groups


def tracked_files(root=ROOT):
    return set(filter(None, git(root, 'ls-files', '-z').stdout.split('\0')))


def expand(paths, files):
    """Each path as the tracked files it names. A path that ends in / names a directory."""
    out = []
    for path in paths:
        if path.endswith('/'):
            out += sorted(f for f in files if f.startswith(path))
        elif path in files:
            out.append(path)
    return out


def check_tracked(groups, files):
    problems = [f'{name}: {kind[:-1]} {path} is not tracked'
                for name, group in groups.items()
                for kind in ('outputs', 'inputs')
                for path in group.get(kind, ())
                if not expand([path], files)]
    for problem in problems[:-1]:
        print(f'{TAG} ERROR: {problem}', file=sys.stderr)
    if problems:
        fail(problems[-1])


def fingerprint(root, inputs, rev=None):
    if rev:
        # <mode> <type> <blob>\t<path>
        out, blob = git(root, 'ls-tree', '-r', '-z', rev, '--', *inputs).stdout, 2
    else:
        # <mode> <blob> <stage>\t<path>
        out, blob = git(root, 'ls-files', '-s', '-z', '--', *inputs).stdout, 1
    lines = []
    for entry in filter(None, out.split('\0')):
        meta, path = entry.split('\t', 1)
        lines.append(f'{path} {meta.split()[blob]}')
    if not lines:
        fail(f'no input file found in {rev or "the index"}: {", ".join(inputs)}')
    return hashlib.sha256(('\n'.join(sorted(lines)) + '\n').encode()).hexdigest()


def parse_stamp(text, where):
    try:
        data = json.loads(text)
    except ValueError as err:
        fail(f'{where} is not JSON: {err}')
    if not isinstance(data, dict):
        fail(f'{where} is not a JSON object')
    return data


def read_stamp(root=ROOT):
    path = root / STAMP
    return parse_stamp(path.read_text(), STAMP) if path.exists() else {}


def dump_stamp(data):
    return json.dumps(data, indent=2, sort_keys=True) + '\n'


def staged(root, inputs):
    """True when the index changes an input relative to HEAD."""
    run = git(root, 'diff', '--cached', '--quiet', '--', *inputs, check=False)
    if run.returncode > 1:
        fail(f'git diff --cached failed: {run.stderr.strip()}')
    return run.returncode == 1


def unstaged(root, inputs):
    """Input files that the index does not hold as they are: unstaged edits and untracked files."""
    edited = git(root, 'diff', '--name-only', '-z', '--', *inputs).stdout.split('\0')
    others = git(root, 'ls-files', '--others', '--exclude-standard', '-z', '--', *inputs).stdout.split('\0')
    return ([f'{path} has unstaged changes' for path in sorted(filter(None, edited))]
            + [f'{path} is not tracked' for path in sorted(filter(None, others))])


def status(root, name, group, stamp):
    if group['made_by'] == 'static':
        return 'static', None
    current = fingerprint(root, group['inputs'])
    entry = stamp.get(name) or {}
    return ('OK' if entry.get('fingerprint') == current else 'STALE'), current


def report_stale(root, name, group, entry, current, files):
    def say(text):
        print(f'{TAG} {text}', file=sys.stderr, flush=True)

    if not entry:
        say(f'STALE {name}: no stamp in {STAMP}.')
    else:
        source = entry.get('source', '?')
        say(f'STALE {name}: stamp {entry.get("fingerprint", "?")[:12]} from {source[:12]}, '
            f'index {current[:12]}.')
        if source != 'index':
            changed = set(git(root, 'diff', '--cached', '--name-only', '-z', source, '--', *group['inputs'],
                              check=False).stdout.split('\0'))
            shown = []
            for path in group['inputs']:
                under = [p for p in changed if p.startswith(path)] if path.endswith('/') else []
                if path in changed:
                    shown.append(path)
                elif under:
                    shown.append(f'{path} ({len(under)} file{"s" if len(under) > 1 else ""})')
            if shown:
                say('Changed since the stamp: ' + ', '.join(shown))
    say('Outputs: ' + ', '.join(expand(group['outputs'], files)))
    say(f'To refresh {name}, run these steps in one shell from {root}:')
    for number, step in enumerate(group['refresh'], 1):
        first, *rest = step.split('\n')
        # Continuation lines stay at column 0, so a pasted heredoc still ends at its EOF line.
        print(f'  {number}. {first}', *rest, sep='\n', file=sys.stderr, flush=True)


def check(root, groups, names, strict=False, if_staged=False):
    stamp = read_stamp(root)
    files = tracked_files(root)
    stale = 0
    for name in names or groups:
        group = groups[name]
        if group['made_by'] == 'static':
            if names:
                print(f'{TAG} static {name}: no inputs, so it is never stale', flush=True)
            continue
        if if_staged and not staged(root, group['inputs']):
            continue
        state, current = status(root, name, group, stamp)
        if state == 'OK':
            print(f'{TAG} OK {name}', flush=True)
        else:
            stale += 1
            report_stale(root, name, group, stamp.get(name), current, files)
    return 1 if strict and stale else 0


def write(root, groups, names, rev=None, stage=False, allow_unstaged=False):
    for name in names:
        if groups[name]['made_by'] == 'static':
            fail(f'{name} is static, so it has no stamp')
    if not rev and not allow_unstaged:
        problems = [f'{name}: input {problem}' for name in names for problem in unstaged(root, groups[name]['inputs'])]
        for problem in problems:
            print(f'{TAG} ERROR: {problem}', file=sys.stderr)
        if problems:
            fail('wrote no stamp, because the index does not hold these inputs. Run git add on them first, '
                 'or add --allow-unstaged to record the staged state.')
    if rev:
        run = git(root, 'rev-parse', '--verify', '--quiet', f'{rev}^{{commit}}', check=False)
        if run.returncode:
            fail(f'{rev} is not a commit')
        source = run.stdout.strip()
    else:
        source = 'index'
    entries = {name: {'fingerprint': fingerprint(root, groups[name]['inputs'], rev), 'source': source}
               for name in names}

    data = read_stamp(root)
    data.update(entries)
    (root / STAMP).write_text(dump_stamp(data))
    if stage:
        # Start from the staged stamp, so unstaged entries of other groups stay out of the commit.
        blob = git(root, 'rev-parse', '--verify', '--quiet', f':{STAMP}', check=False).stdout.strip()
        index = parse_stamp(git(root, 'cat-file', 'blob', blob).stdout, f'the staged {STAMP}') if blob else {}
        index.update(entries)
        sha = git(root, 'hash-object', '-w', '--stdin', stdin=dump_stamp(index)).stdout.strip()
        git(root, 'update-index', '--add', '--cacheinfo', f'100644,{sha},{STAMP}')
    for name in names:
        print(f'{TAG} wrote the {name} stamp from {source[:12]}' + (' and staged it' if stage else ''), flush=True)
    return 0


def list_groups(root, groups):
    stamp = read_stamp(root)
    files = tracked_files(root)
    width = max(map(len, groups))
    for name, group in groups.items():
        state, _ = status(root, name, group, stamp)
        count = len(expand(group['outputs'], files))
        print(f'{TAG} {name:<{width}}  {group["made_by"]:<16}  {count:>3} output{"s" if count != 1 else " "}  {state}')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Report and record the staleness of the render groups in '
                                                 f'{MANIFEST}.')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='print OK or STALE for each group (the default)')
    mode.add_argument('--write', action='store_true', help='record the fingerprints of the named groups')
    mode.add_argument('--list', action='store_true', help='print one line for each group')
    parser.add_argument('groups', nargs='*', metavar='GROUP', help='groups to check or write (default: all)')
    parser.add_argument('--rev', help='with --write, read this commit instead of the index')
    parser.add_argument('--stage', action='store_true',
                        help='with --write, also stage the new entries, and only those (for the pre-commit hook)')
    parser.add_argument('--allow-unstaged', action='store_true',
                        help='with --write, record the staged state when an input has unstaged changes or untracked files')
    parser.add_argument('--strict', action='store_true', help='with --check, exit 1 when a group is stale')
    parser.add_argument('--if-staged', action='store_true',
                        help='with --check, check only the groups whose inputs the index changes (for the pre-commit hook)')
    args = parser.parse_args(argv)
    if (args.rev or args.stage or args.allow_unstaged) and not args.write:
        parser.error('--rev, --stage and --allow-unstaged need --write')
    if (args.strict or args.if_staged) and (args.write or args.list):
        parser.error('--strict and --if-staged need --check')
    if args.write and not args.groups:
        parser.error('--write needs at least one GROUP')
    if args.list and args.groups:
        parser.error('--list takes no GROUP')

    groups = load_manifest(ROOT)
    check_tracked(groups, tracked_files(ROOT))
    unknown = [name for name in args.groups if name not in groups]
    if unknown:
        parser.error(f'unknown group {", ".join(unknown)}. Groups: {", ".join(groups)}')
    if args.write:
        return write(ROOT, groups, args.groups, args.rev, args.stage, args.allow_unstaged)
    if args.list:
        return list_groups(ROOT, groups)
    return check(ROOT, groups, args.groups, args.strict, args.if_staged)


if __name__ == '__main__':
    sys.exit(main())
