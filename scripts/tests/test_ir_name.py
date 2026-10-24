"""Builds ir_name.h with the host compiler and checks the IR code name rules.

The firmware refuses a name that set_name() would change, and it reads the
"Slot<n>" placeholder of the code block as no name. Both rules live in a header
without ESPHome, so a plain C++17 build can run them. Without a compiler on PATH
the checks skip, as the page check skips without node.
"""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[2]
COMPILER = shutil.which("c++")

DRIVER = r"""
#include "ir_name.h"

#include <cstdio>
#include <cstring>

static int failures = 0;
#define EXPECT(cond)                                         \
  do {                                                       \
    if (!(cond)) {                                           \
      std::printf("line %d: expected %s\n", __LINE__, #cond); \
      failures++;                                            \
    }                                                        \
  } while (0)

static bool fits(const char *text) { return ir_name::fits(text, std::strlen(text)); }
static bool placeholder(const char *text) { return ir_name::placeholder(text, std::strlen(text)); }

static void a_name_fits_only_as_set_name_stores_it() {
  EXPECT(fits("Power"));
  EXPECT(fits("Vol_up 2"));
  EXPECT(fits(""));
  EXPECT(fits("abcdefghijklmnopqrstuvw"));
  EXPECT(!fits("abcdefghijklmnopqrstuvwx"));
  EXPECT(!fits(" Power"));
  EXPECT(!fits("Power "));
  EXPECT(!fits("TV \"Power\""));
  EXPECT(!fits("A\\B"));
  EXPECT(!fits("Tab\there"));
  EXPECT(!fits("Del\x7f"));
  EXPECT(!fits("P\xc3\xb6wer"));
}

static void keeps_matches_the_printable_ascii_rule() {
  for (int value = 0; value < 256; value++) {
    const char c = static_cast<char>(value);
    const bool want = value >= 0x20 && value <= 0x7E && value != '"' && value != '\\';
    EXPECT(ir_name::keeps(c) == want);
  }
}

static void only_slot3_to_slot20_are_placeholders() {
  EXPECT(placeholder("Slot3"));
  EXPECT(placeholder("Slot9"));
  EXPECT(placeholder("Slot10"));
  EXPECT(placeholder("Slot20"));
  EXPECT(!placeholder("Slot2"));
  EXPECT(!placeholder("Slot21"));
  EXPECT(!placeholder("Slot03"));
  EXPECT(!placeholder("Slot"));
  EXPECT(!placeholder("slot6"));
  EXPECT(!placeholder("Slot6a"));
  EXPECT(!placeholder("Slot100"));
  EXPECT(!placeholder("Slots"));
  EXPECT(!placeholder("Power"));
}

struct Case {
  const char *name;
  void (*run)();
};

static const Case CASES[] = {
    {"a_name_fits_only_as_set_name_stores_it", a_name_fits_only_as_set_name_stores_it},
    {"keeps_matches_the_printable_ascii_rule", keeps_matches_the_printable_ascii_rule},
    {"only_slot3_to_slot20_are_placeholders", only_slot3_to_slot20_are_placeholders},
};

int main(int argc, char **argv) {
  if (argc != 2)
    return 2;
  for (const Case &item : CASES) {
    if (std::strcmp(item.name, argv[1]) == 0) {
      item.run();
      return failures == 0 ? 0 : 1;
    }
  }
  std::printf("unknown case %s\n", argv[1]);
  return 2;
}
"""


@unittest.skipIf(COMPILER is None, "no C++ compiler on PATH")
class IrNameTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.work = tempfile.TemporaryDirectory()
        source = Path(cls.work.name) / "driver.cpp"
        source.write_text(DRIVER)
        cls.binary = Path(cls.work.name) / "driver"
        result = subprocess.run(
            [COMPILER, "-std=c++17", "-Wall", "-Wextra", "-I", str(ROOT), str(source), "-o", str(cls.binary)],
            capture_output=True, text=True, timeout=120,
        )
        cls.build_error = None if result.returncode == 0 else result.stdout + result.stderr

    @classmethod
    def tearDownClass(cls) -> None:
        cls.work.cleanup()

    def run_case(self, name: str) -> None:
        self.assertIsNone(self.build_error, self.build_error)
        result = subprocess.run([str(self.binary), name], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_name_fits_only_as_set_name_stores_it(self) -> None:
        self.run_case("a_name_fits_only_as_set_name_stores_it")

    def test_keeps_matches_the_printable_ascii_rule(self) -> None:
        self.run_case("keeps_matches_the_printable_ascii_rule")

    def test_only_slot3_to_slot20_are_placeholders(self) -> None:
        self.run_case("only_slot3_to_slot20_are_placeholders")


if __name__ == "__main__":
    unittest.main()
