"""Checks the operator diagrams of docs/factory-self-test.md.

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
DOC = (ROOT / "docs" / "factory-self-test.md").read_text()
CPP = (ROOT / "components" / "self_test" / "self_test.cpp").read_text()
SCRIPT = (ROOT / "scripts" / "render-self-test-svg.py").read_text()
GROUP = json.loads((ROOT / "scripts" / "renders.json").read_text())["self-test-diagrams"]

STEPS = 9
IMAGE = re.compile(r"!\[([^\]]+)\]\((readme-assets/(self-test-[a-z0-9-]+\.svg))\)")
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
    return IMAGE.findall(DOC)


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
        self.assertEqual(len(outputs), STEPS + 1)
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
        names = [name for _, _, name in self.images]
        self.assertEqual(names, written())
        self.assertEqual(len(set(names)), len(names))

    def test_the_map_comes_first_and_each_step_carries_its_own_sheet(self):
        self.assertEqual(self.images[0][2], "self-test-led-map.svg")
        self.assertIn("](readme-assets/self-test-led-map.svg)",
                      DOC.split("## LED positions", 1)[1].split("###", 1)[0])
        for step in range(1, STEPS + 1):
            body = DOC.split(f"### Step {step}:", 1)[1].split("\n### ", 1)[0]
            found = [name for _, _, name in IMAGE.findall(body)]
            with self.subTest(step=step):
                self.assertEqual(len(found), 1)
                self.assertTrue(found[0].startswith(f"self-test-step-{step}-"), found[0])

    def test_the_document_states_the_two_marker_kinds(self):
        intro = DOC.split("## LED positions", 1)[1].split("![", 1)[0]
        self.assertIn("orange outline", intro)
        self.assertIn("blue ring", intro)

    def test_the_position_words_moved_out_of_the_tables(self):
        # The diagrams carry the positions now, so no table repeats them.
        for row in re.findall(r"(?m)^\| `D\d` \|.*$", DOC):
            with self.subTest(row=row):
                self.assertNotRegex(row, r"(?i)top (left|right|cent)|bottom (left|right|cent)")

    def test_the_v2_difference_names_the_two_missing_positions(self):
        tail = DOC.split("## V3 and V2 boards", 1)[1]
        self.assertIn("The diagrams show a V3 board.", tail)
        self.assertIn("no `D6` and no `D7`", tail)


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
        for alt, _, name in document_images():
            with self.subTest(sheet=name):
                self.assertEqual(alt, titles[name])
                self.assertEqual(alt, self.trees[name].get("aria-label"))
                # A printed copy can lose the image, so the alt text stands alone.
                self.assertGreater(len(alt), 120)
                self.assertRegex(alt, r"D\d")

    def test_one_file_serves_the_light_and_the_dark_theme(self):
        for name, text in self.text.items():
            with self.subTest(sheet=name):
                self.assertIn("@media (prefers-color-scheme: dark)", text)
                self.assertEqual(len(re.findall(r"self-test-.*-dark", text)), 0)

    def test_the_map_names_every_led_of_the_chain(self):
        # The sheet draws one gutter and then the other, so the set is the check.
        labels = self.labels("self-test-led-map.svg")
        self.assertEqual({label for label in labels if re.fullmatch(r"D\d", label)},
                         set(constant("LED_CHAIN")))

    def test_the_boot_sheet_names_each_chase_colour_at_its_led(self):
        labels = self.labels("self-test-step-1-boot.svg")
        pairs = dict(zip(labels[::2], labels[1::2]))
        self.assertEqual(pairs, dict(zip(constant("LED_CHAIN"), constant("CHASE_NAME"))))

    def test_only_the_v3_sheets_carry_the_v3_note(self):
        v3 = {name for name in written() if "V3 only" in self.labels(name)}
        self.assertEqual(v3, {"self-test-led-map.svg",
                              "self-test-step-5-ir-transmit.svg",
                              "self-test-step-7-usb-power.svg"})


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

    def test_the_sheet_leds_match_the_overview_of_the_component(self):
        overview = CPP.split("void SelfTest::draw_overview_", 1)[1].split("\n}\n", 1)[0]
        shown = re.findall(r"show\((?:LED_)?(\w+), this->(\w+?)(?:\(\))?\);", overview)
        self.assertEqual({led.upper() for led, _ in shown}, set(constant("LED_CHAIN")))


if __name__ == "__main__":
    unittest.main()
