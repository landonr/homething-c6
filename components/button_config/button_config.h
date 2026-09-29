#pragma once

#include "esphome/components/web_server_base/web_server_base.h"
#include "esphome/core/component.h"
#include "esphome/core/defines.h"
#include "esphome/core/preferences.h"
#include "esphome/core/string_ref.h"

#ifdef USE_BUTTON_CONFIG_IDLE_SLEEP
#include "esphome/components/idle_sleep/idle_sleep.h"
#endif

#include <atomic>
#include <cstdint>
#include <string>

namespace esphome::button_config {

// One row per assignable slot. Slot numbers are frozen by the NVS key layout in
// ir_learning.h, so the table is ordered by slot and not by physical position.
struct SlotInfo {
  uint8_t slot;
  bool voice;  // false where push-to-talk has no usable release edge
};

class ButtonConfig final : public AsyncWebHandler, public Component {
 public:
  // Bytes, not characters, so a multibyte name holds fewer characters.
  static constexpr size_t FRIENDLY_NAME_MAX = 40;

  ButtonConfig(web_server_base::WebServerBase *base) : base_(base) {}

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  bool canHandle(AsyncWebServerRequest *request) const override;
  void handleRequest(AsyncWebServerRequest *request) override;
  void set_page(const uint8_t *page, size_t size) {
    this->page_ = page;
    this->page_size_ = size;
  }

  // When false, D2 stays solid orange on Wi-Fi alone instead of pulsing for a
  // missing API. The API server itself keeps running either way.
  bool ha_api_expected() const { return this->ha_api_expected_.load(std::memory_order_acquire); }
  bool set_ha_api_expected(bool expected);
  bool wifi_always_on() const { return this->wifi_always_on_.load(std::memory_order_acquire); }
  void toggle_temporary_wifi();
#ifdef USE_BUTTON_CONFIG_IDLE_SLEEP
  void set_idle_sleep(idle_sleep::IdleSleep *sleep) { this->idle_sleep_ = sleep; }
#endif

 protected:
  void handle_page_(AsyncWebServerRequest *request);
  void handle_state_(AsyncWebServerRequest *request);
  void handle_code_(AsyncWebServerRequest *request);
  void handle_action_(AsyncWebServerRequest *request);
  void handle_activity_(AsyncWebServerRequest *request);
  void complete_action_(uint32_t id, bool ok);
  void load_ha_pref_();
  bool save_ha_pref_();
  void load_wifi_pref_();
  bool set_wifi_always_on_(bool enabled);
  void note_activity_();
  void open_temporary_wifi_(const char *reason);
  // Zeros and available=false when the build has no idle_sleep_id.
  struct SleepState {
    bool available;
    bool enabled;
    uint32_t after_s;
  };
  SleepState sleep_state_() const;
  bool set_sleep_enabled_(bool enabled);
  bool set_sleep_after_(uint32_t seconds);
  void load_name_pref_();
  bool set_friendly_name_(const std::string &name);
  void apply_friendly_name_(const std::string &name);

  // 'HAP1' record under key 'HAPI'. Missing or corrupt means expected=true.
  static constexpr uint32_t HA_PREF_KEY = 0x48415049U;
  static constexpr uint32_t HA_PREF_MAGIC = 0x48415031U;
  struct HaPref {
    uint32_t magic;
    uint8_t expected;
    uint8_t reserved[3];
  };
  static constexpr uint32_t WIFI_PREF_KEY = 0x5746414FU;
  static constexpr uint32_t WIFI_PREF_MAGIC = 0x57465031U;
  static constexpr uint32_t WIFI_IDLE_MS = 10U * 60U * 1000U;
  struct WifiPref {
    uint32_t magic;
    uint8_t enabled;
    uint8_t reserved[3];
  };
  // 'NAM1' record under key 'NAME'. Length 0 means the YAML friendly name.
  static constexpr uint32_t NAME_PREF_KEY = 0x4E414D45U;
  static constexpr uint32_t NAME_PREF_MAGIC = 0x4E414D31U;
  struct NamePref {
    uint32_t magic;
    uint8_t length;
    char name[FRIENDLY_NAME_MAX];  // not terminated
    uint8_t reserved[3];
  };

  web_server_base::WebServerBase *base_;
  const uint8_t *page_{nullptr};
  size_t page_size_{0};
  std::atomic<bool> action_pending_{false};
  std::atomic<uint32_t> next_action_id_{0};
  std::atomic<uint32_t> completed_action_id_{0};
  std::atomic<bool> completed_action_ok_{false};
  std::atomic<bool> ha_api_expected_{true};
  std::atomic<bool> wifi_always_on_{false};
  std::atomic<uint32_t> last_activity_ms_{0};
  bool boot_wifi_always_on_{false};
  bool temporary_wifi_{false};
  ESPPreferenceObject ha_pref_;
  ESPPreferenceObject wifi_pref_;
  ESPPreferenceObject name_pref_;
  // The YAML name is a static buffer or a literal, so it outlives this
  // component and nothing writes it after boot.
  StringRef default_name_;
  // The main loop fills the buffer that current_name_ does not point at, then
  // swaps the pointer. httpd runs one task, and a rename is accepted on that
  // task, so a state reply never reads a buffer that is being filled.
  char names_[2][FRIENDLY_NAME_MAX + 1]{};
  std::atomic<const char *> current_name_{""};
#ifdef USE_BUTTON_CONFIG_IDLE_SLEEP
  idle_sleep::IdleSleep *idle_sleep_{nullptr};
#endif
};

}  // namespace esphome::button_config
