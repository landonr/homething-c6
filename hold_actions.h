#pragma once

#include <cstdint>

// Button holds that run a device action instead of the button assignment. An
// input that carries an active hold defers its tap to the release, so a hold
// sends nothing. Main loop only. Every call that needs the time takes it, so a
// host compiler can build this header without ESPHome.
class HoldActions {
 public:
  enum Action : uint8_t { WIFI = 0, STATUS = 1, SLEEP = 2, ASSIGN = 3, COUNT = 4 };
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

  // COUNT entries in Action order. 0 is no button, and two holds never share one.
  static bool valid_slots(const uint8_t *slots) {
    for (uint8_t a = 0; a < COUNT; a++) {
      if (slots[a] == 0)
        continue;
      if (!valid_slot(slots[a]))
        return false;
      for (uint8_t b = a + 1; b < COUNT; b++) {
        if (slots[b] == slots[a])
          return false;
      }
    }
    return true;
  }

  bool set_slots(const uint8_t *slots) {
    if (!valid_slots(slots))
      return false;
    for (uint8_t a = 0; a < COUNT; a++)
      slots_[a] = slots[a];
    return true;
  }

  bool set_slot(Action action, uint8_t slot) {
    if (action >= COUNT)
      return false;
    uint8_t next[COUNT];
    for (uint8_t a = 0; a < COUNT; a++)
      next[a] = slots_[a];
    next[action] = slot;
    return set_slots(next);
  }

  uint8_t slot(Action action) const { return action < COUNT ? slots_[action] : 0; }

  // True only in the Hold status mode. Off also ends a peek, and a status hold
  // that has not fired taps on its release instead.
  void set_status_active(bool active) {
    status_active_ = active;
    if (active)
      return;
    peeking_ = false;
    for (Press &entry : presses_) {
      if (entry.down && entry.action == STATUS)
        entry.timing = false;
    }
  }
  bool status_active() const { return status_active_; }

  bool defers(uint8_t slot) const { return active_action_(slot) != COUNT; }

  // True when the press taps now. A deferring press latches its action here, so
  // a settings change during the hold does not move it.
  bool press(uint8_t slot, uint32_t now) {
    if (slot >= SLOT_LIMIT)
      return true;
    wake_[slot] = WAKE_NONE;
    Press &entry = presses_[slot];
    const uint8_t action = active_action_(slot);
    if (action == COUNT) {
      entry.down = false;
      return true;
    }
    entry = Press{true, true, false, action, now};
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
    if (entry.action == STATUS)
      peeking_ = false;
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
    if (action == COUNT)
      return;
    const bool silent = wake_[slot] == WAKE_SILENT;
    wake_[slot] = WAKE_NONE;
    presses_[slot] = Press{true, action != ASSIGN, silent, action, now};
  }

  // Bit n set: action n fired on this call. Each hold fires once.
  uint8_t tick(uint32_t now) {
    uint8_t fired = 0;
    for (Press &entry : presses_) {
      if (!entry.down || !entry.timing || now - entry.since < HOLD_MS[entry.action])
        continue;
      entry.timing = false;
      entry.silent = true;
      if (entry.action == STATUS)
        peeking_ = true;
      fired |= static_cast<uint8_t>(1u << entry.action);
    }
    return fired;
  }

  // True from the status hold until its release.
  bool peeking() const { return peeking_; }

 private:
  enum : uint8_t { WAKE_NONE = 0, WAKE_TAP = 1, WAKE_SILENT = 2 };

  struct Press {
    bool down;
    bool timing;
    bool silent;
    uint8_t action;
    uint32_t since;
  };

  uint8_t active_action_(uint8_t slot) const {
    if (slot == 0)
      return COUNT;
    for (uint8_t a = 0; a < COUNT; a++) {
      if (slots_[a] == slot && (a != STATUS || status_active_))
        return a;
    }
    return COUNT;
  }

  uint8_t slots_[COUNT] = {DEFAULT_SLOT[WIFI], DEFAULT_SLOT[STATUS], DEFAULT_SLOT[SLEEP], DEFAULT_SLOT[ASSIGN]};
  bool status_active_ = false;
  bool peeking_ = false;
  Press presses_[SLOT_LIMIT] = {};
  uint8_t wake_[SLOT_LIMIT] = {};
};

inline HoldActions hold_actions;
