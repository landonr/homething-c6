#pragma once

#include "esphome/core/component.h"
#include "esphome/core/hal.h"
#include "esphome/components/wifi/wifi_component.h"

#ifdef USE_BINARY_SENSOR
#include "esphome/components/binary_sensor/binary_sensor.h"
#endif

#include <improv.h>

#include <atomic>
#include <cstdint>
#include <string>
#include <vector>

struct ble_gatt_access_ctxt;

namespace esphome::improv_ble {

// Improv over BLE on the NimBLE server that ble_hid runs. ESPHome's own
// component needs Bluedroid, and the remote cannot have it, because the BLE
// keyboard needs NimBLE and only one host can run at a time.
class ImprovBle final : public Component {
 public:
  ImprovBle();

  void setup() override;
  void loop() override;
  void dump_config() override;
  float get_setup_priority() const override;

  void set_next_url(const std::string &url) { this->next_url_ = url; }
  void set_authorized_duration(uint32_t duration) { this->authorized_duration_ = duration; }
  void set_wifi_timeout(uint32_t timeout) { this->wifi_timeout_ = timeout; }
#ifdef USE_BINARY_SENSOR
  void set_authorizer(binary_sensor::BinarySensor *authorizer) { this->authorizer_ = authorizer; }
#endif

  improv::State state() const { return this->state_; }

  static ImprovBle *instance() { return global_instance_; }

  // The NimBLE task calls this from its own context. The service table names
  // it, so it cannot be protected.
  static int access_(uint16_t conn, uint16_t attr, ble_gatt_access_ctxt *ctxt, void *arg);

 protected:
  int handle_access_(uint16_t conn, uint16_t attr, ble_gatt_access_ctxt *ctxt);

  void set_state_(improv::State state);
  void set_error_(improv::Error error);
  void send_response_(const std::vector<uint8_t> &response);
  void notify_(uint16_t handle, const uint8_t *data, size_t length);
  void process_incoming_();
  void check_wifi_();
  void on_wifi_timeout_();
  void start_();
  void stop_();
  std::string formatted_next_url_() const;

  improv::State state_{improv::STATE_STOPPED};
  improv::Error error_{improv::ERROR_NONE};
  bool running_{false};
  uint32_t authorized_start_{0};
  uint32_t provisioning_start_{0};
  uint32_t authorized_duration_{60000};
  uint32_t wifi_timeout_{30000};
  std::string next_url_;
  wifi::WiFiAP connecting_sta_{};
#ifdef USE_BINARY_SENSOR
  binary_sensor::BinarySensor *authorizer_{nullptr};
#endif

  // The NimBLE task fills this and the main loop drains it.
  std::vector<uint8_t> incoming_;
  std::atomic<bool> incoming_ready_{false};

  static ImprovBle *global_instance_;
};

}  // namespace esphome::improv_ble
