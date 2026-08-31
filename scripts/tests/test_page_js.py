"""Executes the /buttons page script against a DOM stub.

The other page checks match patterns in the source. They cannot catch an
undeclared variable or a renamed helper, because those fail only when the code
runs. One such slip shipped to hardware and left every button unlabelled.
"""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[2]
PAGE = ROOT / "components" / "button_config" / "button_config_page.h"
STUB = Path(__file__).parent / "page_dom_stub.js"


def page_script() -> str:
    """Returns the JavaScript between the page's script tags."""
    text = PAGE.read_text()
    start = text.index("<script>\n") + len("<script>\n")
    return text[start:text.index("\n</script>", start)]


class PageScriptTest(unittest.TestCase):
    @unittest.skipIf(shutil.which("node") is None, "node is not installed")
    def test_the_page_script_runs_without_a_browser(self) -> None:
        with tempfile.TemporaryDirectory() as work:
            script = Path(work) / "page.js"
            script.write_text(page_script())
            result = subprocess.run(
                ["node", str(STUB), str(script)],
                capture_output=True, text=True, timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_script_tags_still_wrap_one_block(self) -> None:
        """The extraction above is positional, so a second block would hide code
        from this check without failing it."""
        text = PAGE.read_text()
        self.assertEqual(text.count("<script>"), 1)
        self.assertEqual(text.count("</script>"), 1)
        self.assertIn("function paint(){", page_script())


if __name__ == "__main__":
    unittest.main()
