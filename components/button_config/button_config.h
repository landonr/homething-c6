#pragma once

#include "esphome/components/web_server_base/web_server_base.h"
#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

#include <atomic>
#include <cstdint>

namespace esphome::button_config {

// One row per assignable slot. Slot numbers are frozen by the NVS key layout in
// ir_learning.h, so the table is ordered by slot and not by physical position.
struct SlotInfo {
  uint8_t slot;
  bool voice;  // false where push-to-talk has no usable release edge
};

class ButtonConfig final : public AsyncWebHandler, public Component {
 public:
  ButtonConfig(web_server_base::WebServerBase *base) : base_(base) {}

  void setup() override;
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

 protected:
  void handle_page_(AsyncWebServerRequest *request);
  void handle_state_(AsyncWebServerRequest *request);
  void handle_code_(AsyncWebServerRequest *request);
  void handle_action_(AsyncWebServerRequest *request);
  void complete_action_(uint32_t id, bool ok);
  void load_ha_pref_();
  bool save_ha_pref_();

  // 'HAP1' record under key 'HAPI'. Missing or corrupt means expected=true.
  static constexpr uint32_t HA_PREF_KEY = 0x48415049U;
  static constexpr uint32_t HA_PREF_MAGIC = 0x48415031U;
  struct HaPref {
    uint32_t magic;
    uint8_t expected;
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
  ESPPreferenceObject ha_pref_;
};

}  // namespace esphome::button_config
