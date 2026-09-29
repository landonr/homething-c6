#pragma once

#include "esphome/components/i2c/i2c.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

#include <atomic>
#include <cstdint>
#include <functional>

namespace esphome::idle_sleep {

class IdleSleep : public Component, public i2c::I2CDevice {
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  // After the I2C bus, before the GPIO switches, RMT, I2S and LEDC claim held pins.
  float get_setup_priority() const override { return setup_priority::BUS - 1.0f; }

  static constexpr uint32_t MIN_SLEEP_AFTER_S = 10;
  static constexpr uint32_t MAX_SLEEP_AFTER_S = 3600;

  // Used until a set_sleep_after_s() call is stored.
  void set_default_sleep_after_s(uint32_t seconds) { this->default_sleep_after_s_ = seconds; }
  void set_cold_boot_grace(uint32_t ms) { this->cold_boot_grace_ms_ = ms; }
  void set_sleep_hold_bit(uint8_t bit) { this->sleep_hold_bit_ = bit; }
  void set_sleep_hold_time(uint32_t ms) { this->sleep_hold_time_ms_ = ms; }
  void set_link_probe(std::function<bool()> probe) { this->link_probe_ = std::move(probe); }
  void set_block_probe(std::function<bool()> probe) { this->block_probe_ = std::move(probe); }
  // bit is the expander pin. held is true when the first read still showed it
  // down. Returns true when something was sent.
  void set_replay(std::function<bool(uint8_t, bool)> replay) { this->replay_ = std::move(replay); }

  bool woke_from_sleep() const { return !this->cold_boot_; }
  // True once the hold arms the forced sleep. Main loop only, like the setters.
  bool sleep_armed() const { return this->forced_sleep_; }
  // True until the latched wake press is sent or dropped.
  // Bits down at the stub read and at the first read. Zero without the stub latch.
  uint16_t held_at_wake() const { return this->held_mask_; }

  // The getters are safe from any task. Call the setters on the main loop only.
  // A successful set is stored in flash and restarts the idle window.
  bool enabled() const { return this->enabled_.load(std::memory_order_relaxed); }
  uint32_t sleep_after_s() const { return this->sleep_after_s_.load(std::memory_order_relaxed); }
  bool set_enabled(bool enabled);
  bool set_sleep_after_s(uint32_t seconds);

 protected:
  bool read_port_(uint16_t *port);
  void set_pressed_(uint16_t pressed, uint32_t now);
  void track_hold_(uint16_t pressed, uint32_t now);
  void try_sleep_();
  [[noreturn]] void enter_sleep_();
  void load_settings_();
  bool save_settings_(bool enabled, uint32_t stored_after_s);
  void attach_int_isr_();
  void detach_int_isr_();

  // 'SLC1' record under key 'SLCF'. stored_after_s 0 means the YAML default.
  static constexpr uint32_t SETTINGS_KEY = 0x534C4346U;
  static constexpr uint32_t SETTINGS_MAGIC = 0x534C4331U;
  struct SettingsPref {
    uint32_t magic;
    uint32_t stored_after_s;
    uint8_t enabled;
    uint8_t reserved[3];
  };

  uint32_t default_sleep_after_s_{300};
  uint32_t stored_after_s_{0};
  std::atomic<bool> enabled_{true};
  std::atomic<uint32_t> sleep_after_s_{300};
  ESPPreferenceObject settings_pref_;
  bool int_isr_tried_{false};
  bool int_isr_attached_{false};
  uint32_t cold_boot_grace_ms_{60000};
  // 0xFF turns the hold-to-sleep off.
  uint8_t sleep_hold_bit_{0xFF};
  uint32_t sleep_hold_time_ms_{2000};
  std::function<bool()> link_probe_{};
  std::function<bool()> block_probe_{};
  std::function<bool(uint8_t, bool)> replay_{};

  bool cold_boot_{true};
  uint16_t replay_mask_{0};
  uint16_t held_mask_{0};
  bool replay_pending_{false};
  bool link_seen_{false};
  int64_t setup_us_{0};
  uint32_t last_activity_ms_{0};
  uint32_t last_poll_ms_{0};
  uint16_t pressed_{0};
  bool hold_down_{false};
  uint32_t hold_since_ms_{0};
  bool forced_sleep_{false};
};

}  // namespace esphome::idle_sleep
