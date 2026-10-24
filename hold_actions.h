#pragma once

#include <cstdint>

// Button holds that run a device action instead of the button assignment. An
// input that carries an active hold defers its tap to the release, so a hold
// sends nothing. Main loop only. Every call that needs the time takes it, so a
// host compiler can build this header without ESPHome.
class HoldActions {
 public:
  enum Action : uint8_t { WIFI = 0, STATUS = 1, SLEEP = 2, ASSIGN = 3, COUNT = 4 };
  // The table value of an input without a hold.
  static constexpr uint8_t NONE = COUNT;
  // RELEASE_ONLY: the press tapped, so end push-to-talk. TAP_AND_RELEASE: a
  // deferred press sends its assignment now. SILENT: the hold fired.
  enum Release : uint8_t { RELEASE_ONLY = 0, TAP_AND_RELEASE = 1, SILENT = 2 };

  static constexpr uint32_t HOLD_MS[COUNT] = {2000, 1000, 2000, 2000};
  static constexpr uint8_t DEFAULT_SLOT[COUNT] = {5, 7, 20, 9};
  // Expander bit to slot, from the Button and Wheel binary_sensor entries.
  static constexpr uint8_t SLOT_OF_BIT[16] = {20, 19, 3, 4, 5, 6, 7, 8, 10, 9, 11, 12, 13, 14, 15, 16};
  static constexpr uint8_t SLOT_LIMIT = 21;

  // Wheel rotation, 17 and 18, has no release edge, so it cannot carry a hold.
  static bool valid_slot(uint8_t slot) {
    for (const uint8_t value : SLOT_OF_BIT) {
      if (value == slot)
        return true;
    }
    return false;
  }

  static uint8_t default_hold(uint8_t slot) {
    for (uint8_t a = 0; a < COUNT; a++) {
      if (DEFAULT_SLOT[a] == slot)
        return a;
    }
    return NONE;
  }

  // Several inputs can share a hold, and each input carries one hold or NONE.
  static bool valid_hold(uint8_t slot, uint8_t hold) {
    if (slot >= SLOT_LIMIT || hold > NONE)
      return false;
    return hold == NONE || valid_slot(slot);
  }

  // SLOT_LIMIT entries indexed by slot. An entry that is not valid takes its default.
  void set_holds(const uint8_t *holds) {
    for (uint8_t s = 0; s < SLOT_LIMIT; s++)
      holds_[s] = valid_hold(s, holds[s]) ? holds[s] : default_hold(s);
  }

  bool set_hold(uint8_t slot, uint8_t hold) {
    if (!valid_slot(slot) || hold > NONE)
      return false;
    holds_[slot] = hold;
    return true;
  }

  uint8_t hold(uint8_t slot) const { return slot < SLOT_LIMIT ? holds_[slot] : NONE; }

  // True only in the Hold status mode. Off also ends a peek, and a status hold
  // that has not fired taps on its release instead.
  void set_status_active(bool active) {
    status_active_ = active;
    if (active)
      return;
    for (Press &entry : presses_) {
      if (entry.down && entry.action == STATUS) {
        entry.timing = false;
        entry.fired = false;
      }
    }
  }
  bool status_active() const { return status_active_; }

  bool defers(uint8_t slot) const { return active_action_(slot) != NONE; }

  // True when the press taps now. A deferring press latches its action here, so
  // a settings change during the hold does not move it.
  bool press(uint8_t slot, uint32_t now) {
    if (slot >= SLOT_LIMIT)
      return true;
    wake_[slot] = WAKE_NONE;
    Press &entry = presses_[slot];
    const uint8_t action = active_action_(slot);
    if (action == NONE) {
      entry.down = false;
      return true;
    }
    entry = Press{true, true, false, false, action, now};
    return false;
  }

  Release release(uint8_t slot) {
    if (slot >= SLOT_LIMIT)
      return RELEASE_ONLY;
    const uint8_t wake = wake_[slot];
    wake_[slot] = WAKE_NONE;
    Press &entry = presses_[slot];
    if (!entry.down) {
      // Held through the boot and released before the first wake tick. The
      // replay hook skipped a deferring input, so it taps here.
      return wake == WAKE_TAP && defers(slot) ? TAP_AND_RELEASE : RELEASE_ONLY;
    }
    entry.down = false;
    entry.timing = false;
    entry.fired = false;
    return entry.silent ? SILENT : TAP_AND_RELEASE;
  }

  // From on_boot, before any loop. A button held through the boot fires no
  // on_press. silent is true when wake press replay is off.
  void wake_held(uint8_t slot, bool silent) {
    if (slot < SLOT_LIMIT)
      wake_[slot] = silent ? WAKE_SILENT : WAKE_TAP;
  }

  // From the first wake tick, for a held button that still reads down. The
  // assignment mode hold never starts from a wake.
  void wake_start(uint8_t slot, uint32_t now) {
    if (slot >= SLOT_LIMIT || presses_[slot].down)
      return;
    const uint8_t action = active_action_(slot);
    if (action == NONE)
      return;
    const bool silent = wake_[slot] == WAKE_SILENT;
    wake_[slot] = WAKE_NONE;
    presses_[slot] = Press{true, action != ASSIGN, silent, false, action, now};
  }

  // Bit n set: action n fired on this call. Each press fires once, and two
  // inputs with the same hold that fire together set one bit.
  uint8_t tick(uint32_t now) {
    uint8_t fired = 0;
    for (Press &entry : presses_) {
      if (!entry.down || !entry.timing || now - entry.since < HOLD_MS[entry.action])
        continue;
      entry.timing = false;
      entry.silent = true;
      entry.fired = true;
      fired |= static_cast<uint8_t>(1u << entry.action);
    }
    return fired;
  }

  // True while any status hold that fired is still down, so a second status
  // input keeps the peek until the last release.
  bool peeking() const {
    if (!status_active_)
      return false;
    for (const Press &entry : presses_) {
      if (entry.down && entry.fired && entry.action == STATUS)
        return true;
    }
    return false;
  }

 private:
  enum : uint8_t { WAKE_NONE = 0, WAKE_TAP = 1, WAKE_SILENT = 2 };

  struct Press {
    bool down;
    bool timing;
    bool silent;
    bool fired;
    uint8_t action;
    uint32_t since;
  };

  uint8_t active_action_(uint8_t slot) const {
    if (slot >= SLOT_LIMIT)
      return NONE;
    const uint8_t action = holds_[slot];
    if (action == STATUS && !status_active_)
      return NONE;
    return action;
  }

  // The defaults, one entry per slot: DEFAULT_SLOT in table form.
  uint8_t holds_[SLOT_LIMIT] = {NONE, NONE, NONE, NONE, NONE, WIFI, NONE, STATUS, NONE, ASSIGN, NONE,
                                NONE, NONE, NONE, NONE, NONE, NONE, NONE, NONE, NONE, SLEEP};
  bool status_active_ = false;
  Press presses_[SLOT_LIMIT] = {};
  uint8_t wake_[SLOT_LIMIT] = {};
};

inline HoldActions hold_actions;
