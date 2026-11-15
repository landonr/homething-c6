"""Checks the split of the web page into a shell, a loader, and a bundle."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "components" / "button_config"))

import shell_build  # noqa: E402

VENDOR = ROOT / "third_party" / "noble"
LOADER_SRC = shell_build.BUNDLE_DIR / "loader.src.js"
PUBLIC_KEY = shell_build.BUNDLE_DIR / "ui-signing-key.pub"


class ShellTest(unittest.TestCase):
    def setUp(self) -> None:
        self.loader = shell_build.loader_text()
        self.shell = shell_build.shell_html()

    def test_the_loader_that_the_shell_pins_is_committed(self) -> None:
        path = shell_build.BUNDLE_DIR / shell_build.loader_name()
        self.assertTrue(path.exists(), f"{path.name} is missing. Run scripts/build-ui-loader.py.")

    def test_the_loader_name_carries_its_hash(self) -> None:
        digest = hashlib.sha384(self.loader.encode()).hexdigest()
        self.assertEqual(shell_build.loader_name(),
                         f"loader-{digest[:shell_build.ID_CHARS]}.js")

    def test_the_shell_pins_and_names_the_loader(self) -> None:
        self.assertIn(shell_build.sri_hash(self.loader), self.shell)
        self.assertIn(shell_build.BUNDLE_BASE + shell_build.loader_name(), self.shell)

    def test_the_shell_holds_no_interface(self) -> None:
        """The shell is the flash cost, so it keeps no style, markup, or script."""
        self.assertLess(len(self.shell), 2048)
        self.assertNotIn("<style>", self.shell)
        self.assertNotIn("tabgrid", self.shell)

    def test_the_shell_cache_key_carries_the_pin(self) -> None:
        """A firmware with a new pin must ignore the copy saved for the old one."""
        self.assertIn('K="' + shell_build.CACHE_KEY + '"+H', self.shell)


class BundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = shell_build.bundle_js()

    def test_the_website_carries_the_current_bundle(self) -> None:
        self.assertTrue(shell_build.APP.exists(), "run scripts/build-shell-bundle.py")
        self.assertEqual(shell_build.APP.read_text(), self.bundle)

    def test_the_bundle_is_signed(self) -> None:
        self.assertTrue(shell_build.SIGNATURE.exists(), "run scripts/build-shell-bundle.py")
        self.assertEqual(len(shell_build.SIGNATURE.read_text().strip()), 128)

    def test_the_first_line_is_the_version(self) -> None:
        """The loader refuses a bundle older than the one that it holds."""
        self.assertTrue(self.bundle.startswith(f"//v={shell_build.ui_version()}\n"))

    def test_the_bundle_holds_the_interface(self) -> None:
        self.assertIn("tabgrid", self.bundle)
        self.assertIn("document.body.innerHTML=", self.bundle)
        self.assertNotIn("__CASE_FRONT_FACE_SVG__", self.bundle)

    def test_the_bundle_reaches_the_device_on_its_own_origin(self) -> None:
        """A relative path keeps the API calls same-origin, so they need no CORS."""
        self.assertIn("/buttons/api/state", self.bundle)
        self.assertNotIn("http://homething", self.bundle)


class LoaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.loader = shell_build.loader_text()

    def test_the_loader_holds_the_key_and_no_placeholder(self) -> None:
        self.assertIn(PUBLIC_KEY.read_text().strip(), self.loader)
        self.assertIn(shell_build.BUNDLE_BASE, self.loader)
        for name in ("__PUBLIC_KEY__", "__BASE__"):
            self.assertNotIn(name, self.loader)

    def test_the_loader_source_carries_no_key(self) -> None:
        """The key is filled in at build time, so the source stays general."""
        self.assertIn("__PUBLIC_KEY__", LOADER_SRC.read_text())

    def test_the_loader_carries_its_own_sha512(self) -> None:
        """An insecure origin gives the page no crypto.subtle, so the sync
        SHA-512 must be in the bundle. The unused async branch of noble still
        names crypto.subtle, so look for the round constants instead."""
        self.assertIn("0x428a2f98d728ae22", self.loader)
        self.assertIn("0x6c44198c4a475817", self.loader)

    def test_the_vendored_versions_are_recorded(self) -> None:
        notes = (VENDOR / "README.md").read_text()
        for name in ("ed25519.js", "sha2.js", "_md.js", "_u64.js", "utils.js"):
            with self.subTest(file=name):
                self.assertTrue((VENDOR / name).exists())
                self.assertIn(name, notes)


class PageModeTest(unittest.TestCase):
    """`page: embedded` puts the interface in flash, so a fork needs no key."""

    INIT = (ROOT / "components" / "button_config" / "__init__.py").read_text()

    def test_the_component_offers_both_modes_and_hosts_by_default(self) -> None:
        self.assertIn('PAGE_HOSTED = "hosted"', self.INIT)
        self.assertIn('PAGE_EMBEDDED = "embedded"', self.INIT)
        self.assertIn("cv.Optional(CONF_PAGE, default=PAGE_HOSTED)", self.INIT)
        self.assertIn("cv.one_of(\n                PAGE_HOSTED, PAGE_EMBEDDED, lower=True)",
                      self.INIT)

    def test_embedded_takes_the_whole_page_and_hosted_takes_the_shell(self) -> None:
        self.assertIn("html = shell_html() if hosted else page()", self.INIT)

    def test_only_the_hosted_mode_needs_the_website(self) -> None:
        """An embedded build must not fail on a missing loader or signature."""
        guarded = self.INIT.split("if hosted:\n", 1)[1].split("    try:", 1)[0]
        for name in ("CURRENT_LOADER", "APP", "SIGNATURE"):
            with self.subTest(needs=name):
                self.assertIn(name, guarded)

    def test_the_files_are_checked_before_they_are_read(self) -> None:
        """A clone with no site/app must get the message, not a read error."""
        check = self.INIT.index("missing = [path.name for path")
        read = self.INIT.index("html = shell_html() if hosted else page()")
        self.assertLess(check, read)

    def test_the_error_names_the_way_out_for_a_fork(self) -> None:
        self.assertIn("A fork can set `page: {PAGE_EMBEDDED}` instead.", self.INIT)

    def test_the_embedded_page_is_the_whole_document(self) -> None:
        whole = shell_build.page()
        self.assertIn("tabgrid", whole)
        self.assertIn("<style>", whole)
        self.assertNotIn("__CASE_FRONT_FACE_SVG__", whole)
        self.assertNotIn(shell_build.BUNDLE_BASE, whole)


class LoaderPublishingTest(unittest.TestCase):
    """The committed loader must be current, and published ones must stay."""

    KEPT = shell_build.BUNDLE_DIR / "loaders.kept"

    def test_the_committed_loader_matches_its_source(self) -> None:
        """Without this, an edit to loader.src.js silently fails to ship."""
        if shutil.which("esbuild") is None:
            self.skipTest("esbuild is not installed")
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build-ui-loader.py"), "--check"],
            capture_output=True, text=True)
        self.assertEqual(done.returncode, 0,
                         f"run scripts/build-ui-loader.py. {done.stderr.strip()}")

    def test_a_bench_loader_is_not_published(self) -> None:
        """HOMETHING_UI_BASE builds a loader for another server, never a release."""
        build = (ROOT / "scripts" / "build-ui-loader.py").read_text()
        self.assertIn("if BUNDLE_BASE == DEFAULT_BUNDLE_BASE:", build)
        listed = self.KEPT.read_text().split()
        self.assertEqual(sorted(set(listed)), sorted(listed), "a name is listed twice")

    def test_every_published_loader_is_still_here(self) -> None:
        """A firmware pins one loader for the life of its release."""
        for name in self.KEPT.read_text().split():
            with self.subTest(loader=name):
                self.assertTrue((shell_build.BUNDLE_DIR / name).exists(),
                                f"{name} is published, so it must not be deleted")

    def test_the_current_loader_is_published(self) -> None:
        self.assertIn(shell_build.loader_name(), self.KEPT.read_text().split())


class SignatureTest(unittest.TestCase):
    """Proves that the committed signature matches the committed bundle."""

    def test_node_verifies_the_committed_signature(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("node is not installed")
        script = """
import { createPublicKey, verify } from "node:crypto";
import { readFileSync } from "node:fs";
const [app, sig, pub] = process.argv.slice(2);
const raw = Buffer.from(readFileSync(pub, "utf8").trim(), "hex");
const der = Buffer.concat([Buffer.from("302a300506032b6570032100", "hex"), raw]);
const key = createPublicKey({ key: der, format: "der", type: "spki" });
const ok = verify(null, readFileSync(app),
                  key, Buffer.from(readFileSync(sig, "utf8").trim(), "hex"));
process.exit(ok ? 0 : 1);
"""
        with tempfile.TemporaryDirectory() as hold:
            path = Path(hold) / "verify.mjs"
            path.write_text(script)
            done = subprocess.run(
                ["node", str(path), str(shell_build.APP), str(shell_build.SIGNATURE),
                 str(PUBLIC_KEY)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0,
                         f"the signature does not match the bundle. {done.stderr}")


if __name__ == "__main__":
    unittest.main()
