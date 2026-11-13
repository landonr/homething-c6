"""Checks for the outside-fill guard in scripts/refill-zones.py."""

import contextlib
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / 'scripts' / 'refill-zones.py'
BOARD = ROOT / 'c6remote-kicad' / 'c6remote.kicad_pcb'
SPEC = importlib.util.spec_from_file_location('refill_zones', SCRIPT)
rz = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rz)

REFUSED = 'Content outside filled_polygon blocks changed. Board not written.'
NUM = r'-?\d+(?:\.\d+)?'
TOP_BLOCK = r'^\t\((?:{})\n.*?^\t\)\n'

SYNTH = '''(kicad_pcb
\t(version 20260206)
\t(generator "pcbnew")
\t(general
\t\t(thickness 1.6)
\t)
\t(footprint "Library:LED"
\t\t(layer "F.Cu")
\t\t(uuid "f1ed3982-01a8-4a44-af03-29462bfabad3")
\t\t(at 39.905055 54.281655 45)
\t\t(property "Value" "1.2"
\t\t\t(at 0 0 45)
\t\t\t(layer "F.Fab")
\t\t\t(uuid "11111111-0000-4000-8000-000000000001")
\t\t)
\t\t(fp_line
\t\t\t(start -1.1 -1.2)
\t\t\t(end 1.3 -1.2)
\t\t\t(stroke
\t\t\t\t(width 0.15)
\t\t\t\t(type solid)
\t\t\t)
\t\t\t(layer "F.SilkS")
\t\t\t(uuid "11111111-0000-4000-8000-000000000002")
\t\t)
\t)
\t(segment
\t\t(start 5 20)
\t\t(end 10 20)
\t\t(width 0.2)
\t\t(layer "F.Cu")
\t\t(net "GND")
\t\t(uuid "22222222-0000-4000-8000-000000000001")
\t)
\t(segment
\t\t(start 10 20)
\t\t(end 10 30)
\t\t(width 0.2)
\t\t(layer "F.Cu")
\t\t(net "GND")
\t\t(uuid "22222222-0000-4000-8000-000000000002")
\t)
\t(zone
\t\t(net "GND")
\t\t(layer "F.Cu")
\t\t(uuid "33333333-0000-4000-8000-000000000001")
\t\t(polygon
\t\t\t(pts
\t\t\t\t(xy 0 0) (xy 80 0) (xy 80 80) (xy 0 80)
\t\t\t)
\t\t)
\t\t(filled_polygon
\t\t\t(layer "F.Cu")
\t\t\t(pts
\t\t\t\t(xy 0.5 0.5) (xy 79.5 0.5) (xy 79.5 79.5) (xy 0.5 79.5)
\t\t\t)
\t\t)
\t)
\t(gr_circle
\t\t(center 60.967455 29.824)
\t\t(end 61.140830 29.824)
\t\t(stroke
\t\t\t(width 0)
\t\t\t(type solid)
\t\t)
\t\t(fill yes)
\t\t(layer "F.SilkS")
\t\t(uuid "44444444-0000-4000-8000-000000000001")
\t)
\t(gr_circle
\t\t(center 36.007455 51.104)
\t\t(end 36.12671 51.104)
\t\t(stroke
\t\t\t(width 0)
\t\t\t(type solid)
\t\t)
\t\t(fill yes)
\t\t(layer "F.SilkS")
\t\t(uuid "44444444-0000-4000-8000-000000000002")
\t)
)
'''

VIA = '''\t(via
\t\t(at 20 20)
\t\t(size 0.6)
\t\t(drill 0.3)
\t\t(layers "F.Cu" "B.Cu")
\t\t(net "GND")
\t\t(uuid "55555555-0000-4000-8000-000000000001")
\t)
'''


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new)


def refill(text):
    return replace_once(text, '(xy 79.5 0.5)', '(xy 79.25 0.5) (xy 79.5 1)')


def top_blocks(text, heads):
    return list(re.finditer(TOP_BLOCK.format(heads), text, re.M | re.S))


def swap_gr_circles(text):
    a, b = top_blocks(text, 'gr_circle')[:2]
    return text[:a.start()] + b.group() + text[a.end():b.start()] + a.group() + text[b.end():]


def move_to_end(text, block):
    text = text[:block.start()] + text[block.end():]
    close = text.rstrip().rfind(')')
    return text[:close] + block.group() + text[close:]


def append_item(text, item):
    close = text.rstrip().rfind(')')
    return text[:close] + item + text[close:]


def line_number(text, needle):
    return text[:text.index(needle)].count('\n') + 1


def compare(old, new):
    return rz.compare_boards(old.encode(), new.encode())


class SyntheticBoardTest(unittest.TestCase):
    def test_fill_only_change_passes(self):
        diff, noise = compare(SYNTH, refill(SYNTH))
        self.assertIsNone(diff)
        self.assertEqual(noise, rz.Noise(0, 0.0, False))

    def test_float_noise_number_format_and_order_pass(self):
        new = refill(SYNTH)
        new = replace_once(new, '(start -1.1 -1.2)', '(start -1.1 -1.200001)')
        new = replace_once(new, '61.140830', '61.14083')
        new = swap_gr_circles(new)
        diff, noise = compare(SYNTH, new)
        self.assertIsNone(diff)
        self.assertEqual(noise.numbers, 2)
        self.assertTrue(noise.reordered)
        self.assertAlmostEqual(noise.max_mm, 1e-6, delta=1e-9)

    def test_moved_track_end_refused(self):
        diff, _ = compare(SYNTH, replace_once(SYNTH, '(end 10 20)', '(end 10.25 20)'))
        n = line_number(SYNTH, '(end 10 20)')
        self.assertIsNotNone(diff)
        self.assertIn(f'stored line {n}: (end 10 20)', diff)
        self.assertIn(f'new line {n}: (end 10.25 20)', diff)

    def test_change_above_noise_limit_refused(self):
        moved = f'{-1.2 - rz.NOISE_MM * 10:.6f}'
        diff, _ = compare(SYNTH, replace_once(SYNTH, '(start -1.1 -1.2)', f'(start -1.1 {moved})'))
        n = line_number(SYNTH, '(start -1.1 -1.2)')
        self.assertIsNotNone(diff)
        self.assertIn(f'stored line {n}: (start -1.1 -1.2)', diff)

    def test_quoted_number_change_refused(self):
        diff, _ = compare(SYNTH, replace_once(SYNTH, '"1.2"', '"1.200001"'))
        self.assertIsNotNone(diff)
        self.assertIn('(property "Value" "1.2"', diff)

    def test_changed_net_refused(self):
        uuid = '\n\t\t(uuid "22222222-0000-4000-8000-000000000001")'
        diff, _ = compare(SYNTH, replace_once(SYNTH, '(net "GND")' + uuid, '(net "+3.3V")' + uuid))
        n = line_number(SYNTH, '(net "GND")' + uuid)
        self.assertIsNotNone(diff)
        self.assertIn(f'new line {n}: (net "+3.3V")', diff)

    def test_removed_item_refused(self):
        second = top_blocks(SYNTH, 'segment')[1]
        new = SYNTH[:second.start()] + SYNTH[second.end():]
        diff, _ = compare(SYNTH, new)
        self.assertIsNotNone(diff)
        self.assertIn('only the stored board has segment "22222222-0000-4000-8000-000000000002"', diff)

    def test_added_item_refused(self):
        diff, _ = compare(SYNTH, append_item(SYNTH, VIA))
        self.assertIsNotNone(diff)
        self.assertIn('only the new board has via "55555555-0000-4000-8000-000000000001"', diff)


@unittest.skipUnless(BOARD.exists(), 'board file not found')
class RealBoardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = BOARD.read_text(encoding='utf-8')

    def test_float_noise_and_order_pass(self):
        text = self.text
        m = re.search(rf'\(fp_line\n\s*\(start {NUM} ({NUM})\)', text)
        self.assertIsNotNone(m)
        noisy = f'{float(m.group(1)) + 1e-6:.6f}'
        new = text[:m.start(1)] + noisy + text[m.end(1):]
        new = move_to_end(new, top_blocks(new, r'gr_\w+|segment|via')[0])
        diff, noise = compare(text, new)
        self.assertIsNone(diff)
        self.assertGreaterEqual(noise.numbers, 1)
        self.assertTrue(noise.reordered)

    def test_moved_track_end_refused(self):
        text = self.text
        block = top_blocks(text, 'segment')[0]
        m = re.compile(rf'\(end ({NUM}) {NUM}\)').search(text, block.start(), block.end())
        self.assertIsNotNone(m)
        line_start = text.rfind('\n', 0, m.start()) + 1
        line = text[line_start:text.index('\n', m.end())].strip()
        moved = f'{float(m.group(1)) + 0.1:.6f}'
        new = text[:m.start(1)] + moved + text[m.end(1):]
        diff, _ = compare(text, new)
        n = text[:m.start()].count('\n') + 1
        self.assertIsNotNone(diff)
        self.assertIn(f'stored line {n}: {line}', diff)


class MainTest(unittest.TestCase):
    def run_main(self, kicad_output):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        board = Path(tmp.name) / 'test.kicad_pcb'
        board.write_text(SYNTH, encoding='utf-8')
        board.with_suffix('.kicad_pro').write_text('', encoding='utf-8')

        def fake_fill(python, work_board, out):
            Path(work_board).write_text(kicad_output, encoding='utf-8')
            return {'before': [['GND', 'F.Cu', 1]], 'after': [['GND', 'F.Cu', 1]]}

        out, errs = io.StringIO(), io.StringIO()
        argv = ['refill-zones.py', '--board', str(board), '--no-drc']
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(rz, 'kicad_gui', return_value=[]))
            stack.enter_context(mock.patch.object(rz, 'kicad_python', return_value='python'))
            stack.enter_context(mock.patch.object(rz, 'run_fill', side_effect=fake_fill))
            stack.enter_context(mock.patch.object(sys, 'argv', argv))
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(errs))
            code = rz.main()
        return code, board.read_text(encoding='utf-8'), out.getvalue(), errs.getvalue()

    def test_noise_accepted_and_board_written(self):
        kicad = swap_gr_circles(replace_once(refill(SYNTH), '(start -1.1 -1.2)', '(start -1.1 -1.200001)'))
        code, board, out, errs = self.run_main(kicad)
        self.assertEqual(code, 0, out + errs)
        self.assertEqual(board, kicad)
        self.assertIn('Ignored KiCad save noise outside filled_polygon blocks', out)
        self.assertIn('Only filled_polygon blocks changed.', out)
        self.assertNotIn(REFUSED, errs)

    def test_moved_track_end_refused_and_board_kept(self):
        kicad = replace_once(refill(SYNTH), '(end 10 20)', '(end 10.25 20)')
        code, board, out, errs = self.run_main(kicad)
        self.assertEqual(code, 1, out + errs)
        self.assertEqual(board, SYNTH)
        self.assertIn(REFUSED, errs)
        self.assertIn('(end 10.25 20)', errs)


def kicad_python():
    override = os.environ.get('KICAD_PYTHON')
    if override:
        return override
    return rz.DEFAULT_PYTHON if Path(rz.DEFAULT_PYTHON).exists() else None


KICAD_PYTHON = kicad_python()


@unittest.skipUnless(KICAD_PYTHON and BOARD.exists(), 'KiCad Python not found')
class KiCadFillTest(unittest.TestCase):
    def test_develop_board_fill_passes_guard(self):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td)
            for src in (
                BOARD,
                BOARD.with_suffix('.kicad_pro'),
                BOARD.parent / 'fp-lib-table',
                BOARD.parent / 'sym-lib-table',
            ):
                if src.exists():
                    shutil.copyfile(src, work / src.name)
            board = work / BOARD.name
            out = work / 'zones.json'
            proc = subprocess.run(
                [KICAD_PYTHON, str(SCRIPT), '--fill-child', str(board), str(out)],
                capture_output=True, text=True, timeout=600,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout[-2000:] + proc.stderr[-2000:])
            diff, _ = rz.compare_boards(BOARD.read_bytes(), board.read_bytes())
            self.assertIsNone(diff)


if __name__ == '__main__':
    unittest.main()
