#pragma once

#include "esphome/components/web_server_base/web_server_base.h"
#include "esphome/core/component.h"

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

 protected:
  void handle_page_(AsyncWebServerRequest *request);
  void handle_state_(AsyncWebServerRequest *request);
  void handle_code_(AsyncWebServerRequest *request);
  void handle_targets_(AsyncWebServerRequest *request);
  void handle_action_(AsyncWebServerRequest *request);
  void complete_action_(uint32_t id, bool ok);

  web_server_base::WebServerBase *base_;
  std::atomic<bool> action_pending_{false};
  std::atomic<uint32_t> next_action_id_{0};
  std::atomic<uint32_t> completed_action_id_{0};
  std::atomic<bool> completed_action_ok_{false};
  // A Zigbee assignment finishes on an MQTT round trip, so the manager reports
  // it back later. Zero means that no Zigbee action waits for a result.
  std::atomic<uint32_t> zigbee_action_id_{0};
};

}  // namespace esphome::button_config
