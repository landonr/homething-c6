"""Checks the operator diagrams of site/factory-self-test.html.

The sheets need build123d to render, so this check reads the written SVGs, the
document, the render group, and the firmware, and never imports the script."""

import ast
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).parents[2]
ASSETS = ROOT / "docs" / "readme-assets"
PAGE = (ROOT / "site" / "factory-self-test.html").read_text()
CPP = (ROOT / "components" / "self_test" / "self_test.cpp").read_text()
SCRIPT = (ROOT / "scripts" / "render-self-test-svg.py").read_text()
GROUP = json.loads((ROOT / "scripts" / "renders.json").read_text())["self-test-diagrams"]

STEPS = 8
IMAGE = re.compile(r'<img alt="([^"]+)" src="assets/(self-test-[a-z0-9-]+\.svg)"')
SVG_NS = "{http://www.w3.org/2000/svg}"


def constant(name):
    """One literal module constant of the render script."""
    for node in ast.parse(SCRIPT).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} is not a module constant of the render script")


def written():
    """The file name of each sheet the script writes, in script order."""
    return re.findall(r'file="(self-test-[a-z0-9-]+\.svg)"', SCRIPT)


def document_images():
    return IMAGE.findall(PAGE)


def steps():
    """The markup of each step section, in page order."""
    return re.findall(r'<section class="step">(.*?)</section>', PAGE, re.S)


def chase_colours():
    block = CPP.split("static const Color CHASE_COLOUR[6]", 1)[1].split(";", 1)[0]
    return ["#%02x%02x%02x" % tuple(int(v) for v in rgb)
            for rgb in re.findall(r"Color\((\d+), *(\d+), *(\d+)\)", block)]


def chase_comment():
    head = CPP[: CPP.index("static const Color CHASE_COLOUR[6]")]
    return re.findall(r"(D\d) (\w+)", head[head.rindex("in chain order:"):])


class RenderGroupTest(unittest.TestCase):
    def test_the_group_lists_every_sheet_the_script_writes(self):
        outputs = [Path(path).name for path in GROUP["outputs"]]
        self.assertEqual(sorted(outputs), sorted(written()))
        self.assertEqual(len(outputs), STEPS)
        for path in GROUP["outputs"]:
            self.assertTrue(path.startswith("docs/readme-assets/"), path)
            self.assertTrue((ROOT / path).is_file(), f"{path} is not written")

    def test_the_group_names_its_script_and_the_shared_face_plan(self):
        self.assertIn("scripts/render-self-test-svg.py", GROUP["inputs"])
        self.assertIn("scripts/face_plan.py", GROUP["inputs"])
        self.assertIn("case/.venv/bin/python scripts/render-self-test-svg.py", GROUP["refresh"])

    def test_the_script_reuses_the_face_plan_instead_of_a_copy(self):
        self.assertIn("face_plan.plan_view(P)", SCRIPT)
        self.assertNotIn("def plan_view", SCRIPT)
        self.assertNotIn("def shell_outline", SCRIPT)
        # The positions come from the board, so no sheet holds an LED coordinate.
        self.assertIn("board.components()", SCRIPT)


class DocumentTest(unittest.TestCase):
    def setUp(self):
        self.images = document_images()

    def test_the_document_shows_every_sheet_once(self):
        names = [name for _, name in self.images]
        self.assertEqual(names, written())
        self.assertEqual(len(set(names)), len(names))

    def test_each_step_carries_its_own_sheet(self):
        sections = steps()
        self.assertEqual(len(sections), STEPS)
        for number, section in enumerate(sections, start=1):
            found = [name for _, name in IMAGE.findall(section)]
            with self.subTest(step=number):
                self.assertEqual(len(found), 1)
                self.assertTrue(found[0].startswith(f"self-test-step-{number}-"), found[0])

    def test_the_transmit_step_marks_the_ir_led_it_names(self):
        """Step 5 says `D1` on the top edge, so its sheet must mark that position."""
        step5 = steps()[4]
        # The sentence can open a step or sit mid-sentence, so the case is free.
        self.assertIn("aim it at <code>d1</code> on the top edge of the board.", step5.lower())
        labels = [el.text for el in ET.fromstring(
            (ASSETS / "self-test-step-5-ir-transmit.svg").read_text()).iter(f"{SVG_NS}text")]
        self.assertIn("D1 IR LED", labels)
        alt = next(a for a, name in document_images() if name == "self-test-step-5-ir-transmit.svg")
        self.assertIn("IR LED D1 marked inside the top end", alt)

    def test_no_sheet_text_forks_on_the_board_version(self):
        # Every board at the station has six LEDs, so a version note separates nothing.
        self.assertNotIn("V2", PAGE)
        self.assertNotIn("V3 only", SCRIPT)


class SheetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trees = {name: ET.fromstring((ASSETS / name).read_text()) for name in written()}
        cls.text = {name: (ASSETS / name).read_text() for name in written()}

    def labels(self, name):
        return [el.text for el in self.trees[name].iter(f"{SVG_NS}text")]

    def test_each_sheet_is_an_svg_of_the_face(self):
        for name, tree in self.trees.items():
            with self.subTest(sheet=name):
                self.assertEqual(tree.tag, f"{SVG_NS}svg")
                self.assertTrue(tree.get("viewBox"))
                # plan_view() writes the face group, so the sheet shows the face.
                self.assertIn('<g id="plan">', self.text[name])
                self.assertIn('class="face"', self.text[name])

    def test_each_alt_text_is_the_title_of_its_sheet(self):
        titles = {name: tree.find(f"{SVG_NS}title").text for name, tree in self.trees.items()}
        for alt, name in document_images():
            with self.subTest(sheet=name):
                self.assertEqual(alt, titles[name])
                self.assertEqual(alt, self.trees[name].get("aria-label"))
                # A printed copy can lose the image, so the alt text stands alone.
                self.assertGreater(len(alt), 100)
        
    def test_one_file_serves_the_light_and_the_dark_theme(self):
        for name, text in self.text.items():
            with self.subTest(sheet=name):
                self.assertIn("@media (prefers-color-scheme: dark)", text)
                self.assertEqual(len(re.findall(r"self-test-.*-dark", text)), 0)

    def test_the_boot_sheet_names_each_chase_colour_at_its_led(self):
        labels = self.labels("self-test-step-1-boot.svg")
        pairs = dict(zip(labels[::2], labels[1::2]))
        self.assertEqual(pairs, dict(zip(constant("LED_CHAIN"), constant("CHASE_NAME"))))

    def test_no_sheet_carries_a_version_note(self):
        for name in written():
            with self.subTest(sheet=name):
                self.assertNotIn("V3 only", self.labels(name))
                self.assertNotIn("V2", self.text[name])


class FirmwareTest(unittest.TestCase):
    def test_the_chain_order_matches_the_strip_indices(self):
        chain = list(constant("LED_CHAIN"))
        for led, index in re.findall(r"static constexpr int32_t LED_(D\d) = (\d+);", CPP):
            with self.subTest(led=led):
                self.assertEqual(chain.index(led), int(index))
        self.assertEqual(len(chain), 6)

    def test_the_chain_order_matches_the_chase_comment(self):
        self.assertEqual([led for led, _ in chase_comment()], list(constant("LED_CHAIN")))

    def test_the_chase_colours_match_the_component(self):
        self.assertEqual(chase_colours(), list(constant("CHASE_COLOUR")))
        self.assertEqual([name for _, name in chase_comment()], list(constant("CHASE_NAME")))


if __name__ == "__main__":
    unittest.main()
