#pragma once

#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/core/preferences.h"

#include "esp_hidd.h"
// ble_uuid128_t is a typedef of an anonymous struct, so it cannot be declared
// ahead of use the way the other NimBLE types below can.
#include "host/ble_uuid.h"

#include <array>
#include <atomic>
#include <cstdint>
#include <mutex>

struct ble_gap_event;
struct ble_gatt_svc_def;

namespace esphome::ble_hid {

class BleHid final : public Component {
 public:
  static constexpr uint32_t PAIR_FAILED_SHOW_MS = 3000;
  static constexpr uint8_t FIRST_SLOT = 3;
  static constexpr uint8_t LAST_SLOT = 20;
  static constexpr size_t SLOT_COUNT = LAST_SLOT - FIRST_SLOT + 1;
  // The friendly name holds up to 40 bytes, and the GAP name is that name.
  static constexpr size_t DEVICE_NAME_MAX = 40;

  enum Kind : uint8_t {
    NONE = 0,
    KEYBOARD = 1,
    CONSUMER = 2,
    GAMEPAD_BUTTON = 3,
    GAMEPAD_DPAD = 4,
  };

  struct Assignment {
    bool assigned{false};
    Kind kind{NONE};
    uint16_t usage{0};
    uint8_t modifiers{0};
  };

  BleHid() { global_instance_ = this; }

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  void setup_assignments();
  Assignment assignment(uint8_t slot) const;
  bool assign(uint8_t slot, Kind kind, uint16_t usage, uint8_t modifiers);
  void clear(uint8_t slot);
  bool set_pressed(uint8_t slot, bool pressed);
  bool forget_bond();

  bool radio_enabled() const { return radio_on_.load(std::memory_order_acquire); }
  bool set_radio_enabled(bool enabled);

  bool connected() const { return connected_.load(std::memory_order_acquire); }
  bool bonded() const { return bonded_.load(std::memory_order_acquire); }
  bool pairing() const { return pairing_.load(std::memory_order_acquire); }
  // Main loop only. True when the stack never started.
  bool stack_failed() const { return this->stack_failed_ || this->is_failed(); }
  // Main loop only. True for PAIR_FAILED_SHOW_MS after a failed pair or a rejected host.
  bool pair_failed_recently() const {
    return this->pair_failed_seen_ && millis() - this->pair_failed_at_ < PAIR_FAILED_SHOW_MS;
  }
  // Main loop only. A running advert restarts from loop() with the new name.
  void set_device_name(const char *name);

  static BleHid *instance() { return global_instance_; }

  // Another component can put its own services on this server. NimBLE takes the
  // whole database before the host task starts, so a caller has to register
  // from its constructor, ahead of every setup().
  static bool add_gatt_services(const ble_gatt_svc_def *services);
  // While this is set, the scan response carries the UUID and the name takes
  // the space that is left. The pointer has to outlive the component.
  void set_extra_service_uuid(const ble_uuid128_t *uuid);
  // Puts the current advertising data back on air. Main loop only.
  void refresh_advertising() { this->name_update_pending_.store(true, std::memory_order_release); }
  // BleHid::NO_CONNECTION when no host is connected.
  uint16_t connection_handle() const { return connection_.load(std::memory_order_acquire); }

 protected:
  struct Entry {
    uint8_t kind;
    uint8_t modifiers;
    uint16_t usage;
  };

  // flags bit 0 holds the radio switch. An old record has the byte at zero, so
  // it loads with the radio on and the layout stays the same length.
  static constexpr uint8_t FLAG_RADIO_OFF = 0x01;

  struct Record {
    uint32_t magic;
    uint8_t version;
    uint8_t flags;
    uint8_t reserved[2];
    Entry entries[SLOT_COUNT];
    uint32_t checksum;
  };

  static constexpr uint16_t NO_CONNECTION = 0xFFFF;
  using DeviceName = std::array<char, DEVICE_NAME_MAX + 1>;

  static bool slot_valid_(uint8_t slot);
  static uint32_t checksum_(const Record &record);
  static bool valid_record_(const Record &record);
  static bool valid_assignment_(Kind kind, uint16_t usage, uint8_t modifiers);
  bool save_();
  bool init_stack_();
  void init_hid_();
  void send_reports_();
  void release_all_();
  void start_advertising_();
  void store_device_name_(const char *name, size_t length);
  uint32_t copy_device_name_(DeviceName &name) const;
  bool device_name_current_(uint32_t generation) const;
  void apply_device_name_();
  int handle_gap_event_(ble_gap_event *event);
  static int gap_event_(ble_gap_event *event, void *arg);
  static void hidd_event_handler_(void *args, esp_event_base_t base, int32_t id, void *data);

  esp_hidd_dev_t *device_{nullptr};
  esphome::ESPPreferenceObject pref_{};
  Record record_{};
  std::array<bool, SLOT_COUNT> active_{};
  std::atomic<bool> connected_{false};
  std::atomic<bool> link_connected_{false};
  std::atomic<bool> bonded_{false};
  std::atomic<bool> pairing_{false};
  std::atomic<bool> disconnect_pending_{false};
  std::atomic<bool> report_sync_pending_{false};
  // The NimBLE task sets it, and loop() stamps the time on the main loop.
  std::atomic<bool> pair_failed_pending_{false};
  bool pair_failed_seen_{false};
  uint32_t pair_failed_at_{0};
  bool stack_failed_{false};
  std::atomic<bool> advertising_{false};
  std::atomic<bool> radio_on_{true};
  bool assignments_ready_{false};
  bool stack_ready_{false};
  std::atomic<bool> hid_started_{false};
  mutable std::mutex record_mutex_;
  // The main loop writes the name, and the NimBLE and HID event tasks read it
  // to advertise. Each write bumps the generation, so an advert that copied an
  // older name can tell. Generation 0 means that nothing set a name yet.
  mutable std::mutex device_name_mutex_;
  DeviceName device_name_{};
  uint32_t device_name_generation_{0};
  std::atomic<bool> name_update_pending_{false};
  std::atomic<uint16_t> connection_{NO_CONNECTION};
  std::atomic<const ble_uuid128_t *> extra_uuid_{nullptr};

  static constexpr size_t MAX_EXTRA_SERVICES = 2;
  static const ble_gatt_svc_def *extra_services_[MAX_EXTRA_SERVICES];
  static size_t extra_service_count_;

  static BleHid *global_instance_;
};

}  // namespace esphome::ble_hid
