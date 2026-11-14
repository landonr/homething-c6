"""Executes the web page script against a DOM stub.

The other page checks match patterns in the source. They cannot catch an
undeclared variable or a renamed helper, because those fail only when the code
runs. One such slip shipped to hardware and left every button unlabelled.

The firmware embeds the minified script, so these checks run the minified copy
as well, and they prove that the committed copy still matches the source.
"""

import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[2]
STUB = Path(__file__).parent / "page_dom_stub.js"
COMPONENT = ROOT / "components" / "button_config"

_SPEC = importlib.util.spec_from_file_location("page_build", COMPONENT / "page_build.py")
page_build = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(page_build)

_MINIFY_SPEC = importlib.util.spec_from_file_location("minify_page", ROOT / "scripts" / "minify-page.py")
minify_page = importlib.util.module_from_spec(_MINIFY_SPEC)
_MINIFY_SPEC.loader.exec_module(minify_page)


def run_stub(script: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as work:
        path = Path(work) / "page.js"
        path.write_text(script)
        return subprocess.run(
            ["node", str(STUB), str(path)],
            capture_output=True, text=True, timeout=120,
        )


class PageScriptTest(unittest.TestCase):
    @unittest.skipIf(shutil.which("node") is None, "node is not installed")
    def test_the_page_script_runs_without_a_browser(self) -> None:
        result = run_stub(page_build.source_script())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipIf(shutil.which("node") is None, "node is not installed")
    def test_the_minified_script_runs_the_same_way(self) -> None:
        """The firmware embeds this copy, so a minifier fault must fail here."""
        result = run_stub(page_build.MINIFIED.read_text())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipIf(shutil.which("esbuild") is None, "esbuild is not installed")
    def test_the_committed_minified_script_matches_the_source(self) -> None:
        """A stale copy would ship the page of an older commit."""
        wanted = minify_page.minify(page_build.source_script())
        self.assertEqual(page_build.MINIFIED.read_text().strip("\n"), wanted,
                         "Run `python3 scripts/minify-page.py`.")

    def test_the_script_tags_still_wrap_one_block(self) -> None:
        """The extraction is positional, so a second block would hide code from
        this check without failing it."""
        html = page_build.page_html()
        self.assertEqual(html.count("<script>"), 1)
        self.assertEqual(html.count("</script>"), 1)
        self.assertIn("function paint(){", page_build.source_script())

    def test_minification_keeps_every_entry_point(self) -> None:
        """esbuild renames no top-level name, because a plain script shares the
        global scope. The stub calls these, and the page wires its own events."""
        minified = page_build.MINIFIED.read_text()
        for name in ("function paint(", "function haFix(", "function haOpts("):
            with self.subTest(entry=name):
                self.assertIn(name, minified)

    def test_the_firmware_embeds_the_minified_script_and_the_preview_does_not(self) -> None:
        """The preview keeps the readable script, so an edit shows at once."""
        page = (COMPONENT / "__init__.py").read_text()
        self.assertIn("from .page_build import compose", page)
        self.assertIn("html = compose(svg)", page)
        preview = (ROOT / "scripts" / "preview-buttons-page.py").read_text()
        self.assertIn("page_build.compose(svg, minified=False)", preview)

    def test_the_minified_page_is_smaller_after_gzip(self) -> None:
        """Flash holds the gzipped page, so that is the size that matters."""
        import gzip

        def packed(minified: bool) -> int:
            return len(gzip.compress(page_build.compose("", minified).encode(),
                                     compresslevel=9, mtime=0))

        saved = packed(False) - packed(True)
        self.assertGreater(saved, 8 * 1024, f"minification saved only {saved} bytes")


if __name__ == "__main__":
    unittest.main()
