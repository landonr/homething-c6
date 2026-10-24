"""Builds hold_actions.h with the host compiler and drives its hold logic.

The header takes the time as an argument and includes no ESPHome code, so a
plain C++17 build can run the press, release, tick, and wake paths. Without a
compiler on PATH the checks skip, as the page check skips without node.
"""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[2]
COMPILER = shutil.which("c++")

DRIVER = r"""
#include "hold_actions.h"

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

using H = HoldActions;
static const uint8_t SLOT_WIFI = 5, SLOT_STATUS = 7, SLOT_SLEEP = 20, SLOT_ASSIGN = 9, PLAIN = 3;

// The tick() mask bit of one action.
static uint8_t bit(uint8_t action) { return static_cast<uint8_t>(1u << action); }

static void press_without_hold_taps_now() {
  H h;
  EXPECT(!h.defers(PLAIN));
  EXPECT(h.press(PLAIN, 0));
  EXPECT(h.tick(60000) == 0);
  EXPECT(h.release(PLAIN) == H::RELEASE_ONLY);
}

static void deferred_short_press_taps_on_release() {
  H h;
  EXPECT(h.defers(SLOT_WIFI));
  EXPECT(!h.press(SLOT_WIFI, 1000));
  EXPECT(h.tick(2999) == 0);
  EXPECT(h.release(SLOT_WIFI) == H::TAP_AND_RELEASE);
  EXPECT(h.tick(60000) == 0);
}

static void each_hold_fires_once_at_its_time() {
  const uint8_t slots[H::COUNT] = {SLOT_WIFI, SLOT_STATUS, SLOT_SLEEP, SLOT_ASSIGN};
  const uint32_t want_ms[H::COUNT] = {2000, 1000, 2000, 2000};
  for (uint8_t a = 0; a < H::COUNT; a++) {
    H h;
    h.set_status_active(true);
    EXPECT(H::DEFAULT_SLOT[a] == slots[a]);
    EXPECT(H::HOLD_MS[a] == want_ms[a]);
    // The hold time crosses the millis() wrap.
    const uint32_t start = 0xFFFFFC00u;
    EXPECT(!h.press(slots[a], start));
    EXPECT(h.tick(start + want_ms[a] - 1) == 0);
    EXPECT(h.tick(start + want_ms[a]) == bit(a));
    EXPECT(h.tick(start + want_ms[a] + 60000) == 0);
    EXPECT(h.release(slots[a]) == H::SILENT);
  }
}

static void status_defers_only_in_hold_mode() {
  H h;
  EXPECT(!h.status_active());
  EXPECT(!h.defers(SLOT_STATUS));
  EXPECT(h.press(SLOT_STATUS, 0));
  EXPECT(h.tick(5000) == 0);
  EXPECT(!h.peeking());
  EXPECT(h.release(SLOT_STATUS) == H::RELEASE_ONLY);
  h.set_status_active(true);
  EXPECT(h.defers(SLOT_STATUS));
  EXPECT(!h.press(SLOT_STATUS, 0));
  EXPECT(h.release(SLOT_STATUS) == H::TAP_AND_RELEASE);
}

static void leaving_hold_mode_ends_a_peek() {
  H h;
  h.set_status_active(true);
  EXPECT(!h.press(SLOT_STATUS, 0));
  EXPECT(!h.peeking());
  EXPECT(h.tick(1000) == bit(H::STATUS));
  EXPECT(h.peeking());
  h.set_status_active(false);
  EXPECT(!h.peeking());
  EXPECT(h.release(SLOT_STATUS) == H::SILENT);
  // A status hold that has not fired taps on its release instead.
  h.set_status_active(true);
  EXPECT(!h.press(SLOT_STATUS, 2000));
  h.set_status_active(false);
  EXPECT(h.tick(10000) == 0);
  EXPECT(!h.peeking());
  EXPECT(h.release(SLOT_STATUS) == H::TAP_AND_RELEASE);
}

static void release_ends_a_peek() {
  H h;
  h.set_status_active(true);
  EXPECT(!h.press(SLOT_STATUS, 0));
  EXPECT(h.tick(1000) == bit(H::STATUS));
  EXPECT(h.peeking());
  EXPECT(h.release(SLOT_STATUS) == H::SILENT);
  EXPECT(!h.peeking());
}

static void a_silent_wake_mark_makes_a_short_release_silent() {
  H h;
  // Released before the first wake tick.
  h.wake_held(SLOT_WIFI, true);
  EXPECT(h.release(SLOT_WIFI) != H::TAP_AND_RELEASE);
  // Released after the first wake tick, before the hold time.
  h.wake_held(SLOT_WIFI, true);
  h.wake_start(SLOT_WIFI, 0);
  EXPECT(h.tick(1999) == 0);
  EXPECT(h.release(SLOT_WIFI) == H::SILENT);
  // The hold itself still runs from a wake.
  h.wake_held(SLOT_SLEEP, true);
  h.wake_start(SLOT_SLEEP, 0);
  EXPECT(h.tick(2000) == bit(H::SLEEP));
  EXPECT(h.release(SLOT_SLEEP) == H::SILENT);
}

static void a_replay_wake_mark_taps_on_release() {
  H h;
  // Released during setup, before the first wake tick.
  h.wake_held(SLOT_WIFI, false);
  EXPECT(h.release(SLOT_WIFI) == H::TAP_AND_RELEASE);
  h.wake_held(SLOT_WIFI, false);
  h.wake_start(SLOT_WIFI, 0);
  EXPECT(h.tick(1999) == 0);
  EXPECT(h.release(SLOT_WIFI) == H::TAP_AND_RELEASE);
  // An input without a hold already sent its wake press through the replay.
  h.wake_held(PLAIN, false);
  h.wake_start(PLAIN, 0);
  EXPECT(h.release(PLAIN) == H::RELEASE_ONLY);
}

static void wake_start_skips_the_assignment_hold() {
  H h;
  h.wake_held(SLOT_ASSIGN, false);
  h.wake_start(SLOT_ASSIGN, 0);
  EXPECT(h.tick(60000) == 0);
  EXPECT(h.release(SLOT_ASSIGN) == H::TAP_AND_RELEASE);
  // A normal press of the same input still opens assignment mode.
  EXPECT(!h.press(SLOT_ASSIGN, 70000));
  EXPECT(h.tick(72000) == bit(H::ASSIGN));
}

static void a_press_clears_a_wake_mark() {
  H h;
  h.wake_held(SLOT_WIFI, true);
  EXPECT(!h.press(SLOT_WIFI, 0));
  EXPECT(h.release(SLOT_WIFI) == H::TAP_AND_RELEASE);
  // A stale replay mark must not tap again after a tapped press gains a hold.
  h.wake_held(PLAIN, false);
  EXPECT(h.press(PLAIN, 10000));
  EXPECT(h.set_slot(H::WIFI, PLAIN));
  EXPECT(h.release(PLAIN) == H::RELEASE_ONLY);
}

static void two_holds_never_share_an_input() {
  H h;
  EXPECT(!h.set_slot(H::WIFI, SLOT_STATUS));
  EXPECT(h.slot(H::WIFI) == SLOT_WIFI);
  EXPECT(h.slot(H::STATUS) == SLOT_STATUS);
  // Wheel rotation has no release edge, and 21 is past the last slot.
  EXPECT(!h.set_slot(H::WIFI, 17));
  EXPECT(!h.set_slot(H::WIFI, 18));
  EXPECT(!h.set_slot(H::WIFI, 21));
  EXPECT(h.slot(H::WIFI) == SLOT_WIFI);
  EXPECT(h.set_slot(H::WIFI, 0));
  EXPECT(!h.defers(SLOT_WIFI));
  EXPECT(h.set_slot(H::STATUS, SLOT_WIFI));
  const uint8_t shared[H::COUNT] = {3, 3, 0, 0};
  EXPECT(!H::valid_slots(shared));
  EXPECT(!h.set_slots(shared));
  EXPECT(h.slot(H::STATUS) == SLOT_WIFI);
  const uint8_t none[H::COUNT] = {0, 0, 0, 0};
  EXPECT(H::valid_slots(none));
  EXPECT(H::valid_slots(H::DEFAULT_SLOT));
  EXPECT(!H::valid_slot(0));
  for (uint8_t bit = 0; bit < 16; bit++)
    EXPECT(H::valid_slot(H::SLOT_OF_BIT[bit]));
}

static void a_latched_press_ignores_a_later_settings_change() {
  H h;
  EXPECT(!h.press(SLOT_WIFI, 0));
  EXPECT(h.set_slot(H::WIFI, PLAIN));
  EXPECT(h.tick(2000) == bit(H::WIFI));
  EXPECT(h.release(SLOT_WIFI) == H::SILENT);
  // An input that tapped on press does not tap again after it gains a hold.
  EXPECT(h.press(SLOT_WIFI, 3000));
  EXPECT(h.set_slot(H::SLEEP, SLOT_WIFI));
  EXPECT(h.tick(10000) == 0);
  EXPECT(h.release(SLOT_WIFI) == H::RELEASE_ONLY);
}

struct Case {
  const char *name;
  void (*run)();
};

static const Case CASES[] = {
    {"press_without_hold_taps_now", press_without_hold_taps_now},
    {"deferred_short_press_taps_on_release", deferred_short_press_taps_on_release},
    {"each_hold_fires_once_at_its_time", each_hold_fires_once_at_its_time},
    {"status_defers_only_in_hold_mode", status_defers_only_in_hold_mode},
    {"leaving_hold_mode_ends_a_peek", leaving_hold_mode_ends_a_peek},
    {"release_ends_a_peek", release_ends_a_peek},
    {"a_silent_wake_mark_makes_a_short_release_silent", a_silent_wake_mark_makes_a_short_release_silent},
    {"a_replay_wake_mark_taps_on_release", a_replay_wake_mark_taps_on_release},
    {"wake_start_skips_the_assignment_hold", wake_start_skips_the_assignment_hold},
    {"a_press_clears_a_wake_mark", a_press_clears_a_wake_mark},
    {"two_holds_never_share_an_input", two_holds_never_share_an_input},
    {"a_latched_press_ignores_a_later_settings_change", a_latched_press_ignores_a_later_settings_change},
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
class HoldActionsTest(unittest.TestCase):
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

    def test_a_press_without_a_hold_taps_at_once(self) -> None:
        self.run_case("press_without_hold_taps_now")

    def test_a_short_deferred_press_taps_on_release(self) -> None:
        self.run_case("deferred_short_press_taps_on_release")

    def test_each_hold_fires_once_at_its_time_and_its_release_is_silent(self) -> None:
        self.run_case("each_hold_fires_once_at_its_time")

    def test_the_status_hold_defers_only_in_hold_mode(self) -> None:
        self.run_case("status_defers_only_in_hold_mode")

    def test_leaving_hold_mode_ends_a_peek(self) -> None:
        self.run_case("leaving_hold_mode_ends_a_peek")

    def test_the_release_ends_a_peek(self) -> None:
        self.run_case("release_ends_a_peek")

    def test_a_silent_wake_mark_makes_a_short_release_silent(self) -> None:
        self.run_case("a_silent_wake_mark_makes_a_short_release_silent")

    def test_a_replay_wake_mark_taps_on_release(self) -> None:
        self.run_case("a_replay_wake_mark_taps_on_release")

    def test_wake_start_skips_the_assignment_hold(self) -> None:
        self.run_case("wake_start_skips_the_assignment_hold")

    def test_a_press_clears_a_wake_mark(self) -> None:
        self.run_case("a_press_clears_a_wake_mark")

    def test_two_holds_never_share_an_input(self) -> None:
        self.run_case("two_holds_never_share_an_input")

    def test_a_latched_press_ignores_a_later_settings_change(self) -> None:
        self.run_case("a_latched_press_ignores_a_later_settings_change")


if __name__ == "__main__":
    unittest.main()
