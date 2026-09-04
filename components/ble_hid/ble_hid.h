#pragma once

#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

#include "esp_hidd.h"

#include <array>
#include <atomic>
#include <cstdint>
#include <mutex>
#include <string>

struct ble_gap_event;
struct ble_gatt_attr;
struct ble_gatt_error;

namespace esphome::ble_hid {

class BleHid final : public Component {
 public:
  static constexpr uint8_t FIRST_SLOT = 3;
  static constexpr uint8_t LAST_SLOT = 20;
  static constexpr size_t SLOT_COUNT = LAST_SLOT - FIRST_SLOT + 1;

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
  std::string host_name() const;

  static BleHid *instance() { return global_instance_; }

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

  static constexpr size_t HOST_NAME_SIZE = 32;
  static constexpr uint16_t NO_CONNECTION = 0xFFFF;

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
  void read_host_name_();
  void set_host_name_(const char *name);
  void save_host_name_();
  int handle_gap_event_(ble_gap_event *event);
  static int gap_event_(ble_gap_event *event, void *arg);
  static int host_name_read_(uint16_t connection, const ble_gatt_error *error, ble_gatt_attr *attr,
                             void *arg);
  static void hidd_event_handler_(void *args, esp_event_base_t base, int32_t id, void *data);

  esp_hidd_dev_t *device_{nullptr};
  esphome::ESPPreferenceObject pref_{};
  // The host name is read from the host over GATT, so it survives the link and
  // a reboot only in its own record. The page names the bonded host with it
  // while the radio is off.
  esphome::ESPPreferenceObject host_pref_{};
  std::atomic<bool> host_save_pending_{false};
  Record record_{};
  std::array<bool, SLOT_COUNT> active_{};
  std::atomic<bool> connected_{false};
  std::atomic<bool> link_connected_{false};
  std::atomic<bool> bonded_{false};
  std::atomic<bool> pairing_{false};
  std::atomic<bool> disconnect_pending_{false};
  std::atomic<bool> report_sync_pending_{false};
  std::atomic<bool> advertising_{false};
  std::atomic<bool> radio_on_{true};
  bool assignments_ready_{false};
  bool stack_ready_{false};
  std::atomic<bool> hid_started_{false};
  mutable std::mutex record_mutex_;
  mutable std::mutex host_name_mutex_;
  std::array<char, HOST_NAME_SIZE> host_name_{};
  std::atomic<uint16_t> connection_{NO_CONNECTION};

  static BleHid *global_instance_;
};

}  // namespace esphome::ble_hid
