"""Checks for the render registry in scripts/renders.json and scripts/render-status.py."""

import ast
import contextlib
import importlib.util
import io
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]
SPEC = importlib.util.spec_from_file_location('render_status', ROOT / 'scripts' / 'render-status.py')
rs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rs)

MEDIA = re.compile(r'\.(png|jpe?g|gif|webp|svg|mp4|mov|webm)$', re.I)


def git(root, *args, stdin=None):
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True, input=stdin).stdout


def hook_outputs():
    """The README files that the pre-commit hook regenerates, read from the two generators."""
    shell = (ROOT / 'scripts' / 'render-readme-assets.sh').read_text()
    loop = re.search(r'for f in ([\w -]+); do', shell).group(1).split()
    names = set()
    for name in re.findall(r'echo "Wrote \$\{OUTPUT_DIR\}/([^"]+)"', shell):
        if '${f}' in name:
            names |= {name.replace('${f}', f) for f in loop}
        elif '${side}' in name:
            names |= {name.replace('${side}', side) for side in ('top', 'bottom')}
        else:
            names.add(name)

    tree = ast.parse((ROOT / 'scripts' / 'render-annotated-remote.py').read_text())
    literals = {t.id: node.value for node in tree.body if isinstance(node, ast.Assign)
                for t in node.targets if isinstance(t, ast.Name)}
    sets = {ast.literal_eval(k): v.elts[0].value for k, v in zip(literals['SETS'].keys, literals['SETS'].values)}
    board = next(ast.literal_eval(v) for k, v in zip(literals['GROUPS'].keys, literals['GROUPS'].values)
                 if ast.literal_eval(k) == 'board')
    names |= {f'{sets[key]}{suffix}.svg' for key in board for suffix in ('', '-dark')}
    return {f'docs/readme-assets/{name}' for name in names}, {f'docs/readme-assets/{v}{s}.svg'
                                                               for v in sets.values() for s in ('', '-dark')}


class ManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.groups = rs.load_manifest(ROOT)
        cls.files = rs.tracked_files(ROOT)

    def owners(self):
        owners = {}
        for name, group in self.groups.items():
            for path in rs.expand(group['outputs'], self.files):
                owners.setdefault(path, []).append(name)
        return owners

    def test_every_output_and_input_is_tracked(self):
        for name, group in self.groups.items():
            for kind in ('outputs', 'inputs'):
                for path in group.get(kind, ()):
                    with self.subTest(group=name, path=path):
                        self.assertTrue(rs.expand([path], self.files), f'{kind[:-1]} {path} is not tracked')

    def test_no_output_is_in_two_groups(self):
        for path, names in self.owners().items():
            with self.subTest(path=path):
                self.assertEqual(len(names), 1, f'{path} is in {", ".join(names)}')

    def test_every_live_group_has_refresh_steps_and_a_stamp(self):
        stamp = json.loads((ROOT / rs.STAMP).read_text())
        for name, group in self.groups.items():
            with self.subTest(group=name):
                if group['made_by'] == 'static':
                    self.assertNotIn(name, stamp)
                    continue
                self.assertTrue(group['refresh'])
                self.assertIn(f'render-status.py --write {name}', group['refresh'][-1])
                self.assertEqual(set(stamp[name]), {'fingerprint', 'source'})
        self.assertLessEqual(set(stamp), set(self.groups))

    def test_hook_outputs_belong_to_hook_groups(self):
        hook, annotated = hook_outputs()
        owners = self.owners()
        self.assertGreaterEqual(len(hook), 10)
        for path in hook:
            with self.subTest(path=path):
                self.assertIn(path, owners)
                self.assertEqual(self.groups[owners[path][0]]['made_by'], 'hook')
        for path in annotated:
            with self.subTest(path=path):
                self.assertIn(path, owners)

    def test_every_tracked_image_and_video_has_one_group(self):
        owners = self.owners()
        media = [f for f in self.files if f.startswith(('docs/readme-assets/', 'site/assets/')) and MEDIA.search(f)]
        self.assertTrue(media)
        for path in media:
            with self.subTest(path=path):
                self.assertEqual(len(owners.get(path, [])), 1)


class FingerprintTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        git(self.root, 'init', '-q')
        (self.root / 'a.txt').write_text('one\n')
        (self.root / 'dir').mkdir()
        (self.root / 'dir' / 'b.txt').write_text('two\n')
        (self.root / 'other.txt').write_text('three\n')
        git(self.root, 'add', '.')

    def tearDown(self):
        self.tmp.cleanup()

    def test_fingerprint_follows_the_input_blobs(self):
        inputs = ['a.txt', 'dir/']
        before = rs.fingerprint(self.root, inputs)
        tree = git(self.root, 'write-tree').strip()
        self.assertEqual(rs.fingerprint(self.root, inputs, rev=tree), before)

        (self.root / 'other.txt').write_text('changed\n')
        git(self.root, 'add', 'other.txt')
        self.assertEqual(rs.fingerprint(self.root, inputs), before)

        (self.root / 'dir' / 'b.txt').write_text('changed\n')
        self.assertEqual(rs.fingerprint(self.root, inputs), before, 'the working tree must not count')
        git(self.root, 'add', 'dir/b.txt')
        after = rs.fingerprint(self.root, inputs)
        self.assertNotEqual(after, before)
        self.assertEqual(rs.fingerprint(self.root, inputs, rev=tree), before)

    def test_stage_adds_only_the_written_groups(self):
        (self.root / 'docs' / 'readme-assets').mkdir(parents=True)
        stamp = self.root / rs.STAMP
        groups = {'one': {'made_by': 'hook', 'inputs': ['a.txt']}, 'two': {'made_by': 'repo', 'inputs': ['dir/']}}
        stamp.write_text(rs.dump_stamp({'one': {'fingerprint': 'old', 'source': 'index'}}))
        git(self.root, 'add', rs.STAMP)
        stamp.write_text(rs.dump_stamp({'one': {'fingerprint': 'old', 'source': 'index'},
                                        'two': {'fingerprint': 'unstaged', 'source': 'index'}}))

        with contextlib.redirect_stdout(io.StringIO()):
            rs.write(self.root, groups, ['one'], stage=True)

        staged = json.loads(git(self.root, 'show', f':{rs.STAMP}'))
        working = json.loads(stamp.read_text())
        self.assertEqual(staged['one']['fingerprint'], rs.fingerprint(self.root, ['a.txt']))
        self.assertNotIn('two', staged)
        self.assertEqual(working['one'], staged['one'])
        self.assertEqual(working['two']['fingerprint'], 'unstaged')

    def test_an_untracked_path_fails_clearly(self):
        groups = {'one': {'made_by': 'repo', 'outputs': ['a.txt'], 'inputs': ['missing.txt']}}
        with self.assertRaises(SystemExit) as caught:
            rs.check_tracked(groups, rs.tracked_files(self.root))
        self.assertIn('one: input missing.txt is not tracked', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
