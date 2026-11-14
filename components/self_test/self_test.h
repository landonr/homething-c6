#pragma once

#include "esphome/core/defines.h"

#include "esphome/components/light/addressable_light.h"
#include "esphome/components/idle_sleep/idle_sleep.h"
#include "esphome/components/light/light_state.h"
#include "esphome/components/microphone/microphone.h"
#include "esphome/components/remote_transmitter/remote_transmitter.h"
#include "esphome/core/component.h"
#include "esphome/core/gpio.h"

#ifdef USE_OTA_STATE_LISTENER
#include "esphome/components/ota/ota_backend.h"
#endif

#include <atomic>
#include <cstdint>
#include <functional>
#include <vector>

namespace esphome::self_test {

class SelfTest : public Component
#ifdef USE_OTA_STATE_LISTENER
    ,
                 public ota::OTAGlobalStateListener
#endif
{
 public:
  void setup() override;
  void loop() override;
  void dump_config() override;
  // After every other setup, because the I2S queue must exist before the mic starts.
  float get_setup_priority() const override { return setup_priority::LATE; }

  void set_light(light::LightState *light) { this->light_ = light; }
  void set_microphone(microphone::Microphone *mic) { this->mic_ = mic; }
  void set_transmitter(remote_transmitter::RemoteTransmitterComponent *tx) { this->tx_ = tx; }
  void set_usb_present_pin(InternalGPIOPin *pin) { this->usb_pin_ = pin; }
  void set_idle_sleep(idle_sleep::IdleSleep *idle) { this->idle_ = idle; }
  // The probe names the condition that blocks sleep, or returns nullptr.
  void set_sleep_blocked_by(std::function<const char *()> probe) { this->sleep_blocked_by_ = std::move(probe); }

  // bit is the expander pin, 0 to 15.
  void input(uint8_t bit, bool pressed);
  void encoder_step(bool clockwise);
  void ir_frame(const std::vector<int32_t> &raw);
  void battery_sample(float volts);
  // The addressable_lambda effect calls this for each frame.
  void render(light::AddressableLight &it);

  bool usb_present() const { return this->v3_ && this->usb_known_ && this->usb_present_; }
  bool installing() const { return this->installing_; }
  // idle_sleep sees only the expander, so a wheel turn, an IR frame or a USB
  // change reports here.
  bool recently_active(uint32_t now) const {
    return this->active_ && now - this->active_ms_ < ACTIVE_HOLD_MS;
  }

#ifdef USE_OTA_STATE_LISTENER
  void on_ota_global_state(ota::OTAState state, float progress, uint8_t error, ota::OTAComponent *component) override;
#endif

  // SW1, the power key.
  static constexpr uint8_t TRANSMIT_BIT = 0;
  // ENC1 centre.
  static constexpr uint8_t VU_BIT = 13;
  static constexpr uint8_t PAGE_BIT = 1;
  static constexpr uint8_t SLEEP_BIT = 2;
  static constexpr uint32_t LONG_PRESS_MS = 2000;
  // The sleep hold works on every display mode, so it is longer than the other
  // holds. A button that an operator holds during the buttons step cannot sleep
  // the board in this time.
  static constexpr uint32_t SLEEP_HOLD_MS = 3000;

  // A flash is long enough for a phone camera to show it. The AGC of U2 gives
  // up on a mark of that length, so a flash goes out as a train of short
  // bursts. The 600 us burst and gap are the NEC zero bit, which every
  // receiver accepts, and the camera sees the train as one flash.
  static constexpr uint32_t TX_CARRIER_HZ = 38000;
  static constexpr uint32_t TX_MARK_US = 50000;
  static constexpr uint32_t TX_SPACE_US = 150000;
  static constexpr uint32_t TX_BURSTS = 15;
  static constexpr uint32_t TX_CHOP_MARK_US = 600;
  static constexpr uint32_t TX_CHOP_SPACE_US = 600;
  static constexpr uint32_t TX_CHOP_PERIOD_US = TX_CHOP_MARK_US + TX_CHOP_SPACE_US;
  static constexpr uint32_t TX_CHOPS = TX_MARK_US / TX_CHOP_PERIOD_US;
  // The last gap of a flash carries the rounding, so a flash period stays exact.
  static constexpr uint32_t TX_GAP_US = TX_MARK_US + TX_SPACE_US - (TX_CHOPS * TX_CHOP_PERIOD_US - TX_CHOP_SPACE_US);
  static constexpr uint32_t TX_PERIOD_MS = (TX_MARK_US + TX_SPACE_US) / 1000;
  static constexpr uint32_t TX_TOTAL_MS = TX_BURSTS * TX_PERIOD_MS;
  static constexpr uint32_t ACTIVE_HOLD_MS = 1000;

 protected:
  void mark_active_(uint32_t now) {
    this->active_ = true;
    this->active_ms_ = now;
  }
  void mic_block_(const std::vector<uint8_t> &data);
  void update_mic_(uint32_t now);
  void update_usb_(uint32_t now);
  void update_long_presses_(uint32_t now);
  void update_sleep_();
  const char *sleep_block_();
  bool allow_sleep_();
  void start_transmit_(uint32_t now);
  bool transmitting_(uint32_t now) const { return this->tx_started_ && now - this->tx_start_ms_ < TX_TOTAL_MS; }
  bool inputs_passed_() const { return this->seen_mask_ == 0xFFFF && this->cw_seen_ && this->ccw_seen_; }
  bool usb_passed_() const { return this->usb_plugged_seen_ && this->usb_unplugged_seen_; }
  void note_inputs_();
  void draw_chase_(light::AddressableLight &it, uint32_t t) const;
  void draw_overview_(light::AddressableLight &it) const;
  void draw_second_page_(light::AddressableLight &it) const;
  void draw_input_(light::AddressableLight &it, uint8_t bit) const;
  void draw_vu_(light::AddressableLight &it) const;
  void draw_install_(float percent);

  light::LightState *light_{nullptr};
  microphone::Microphone *mic_{nullptr};
  remote_transmitter::RemoteTransmitterComponent *tx_{nullptr};
  InternalGPIOPin *usb_pin_{nullptr};
  idle_sleep::IdleSleep *idle_{nullptr};
  std::function<const char *()> sleep_blocked_by_{};
  bool second_page_{false};
  bool sleep_requested_{false};
  bool sleep_wake_passed_{false};
  uint32_t sleep_armed_until_ms_{0};
  uint32_t sleep_refused_until_ms_{0};

  int32_t led_count_{4};
  bool v3_{false};

  // The intro is the boot chase. A wake from deep sleep plays it again.
  bool intro_started_{false};
  uint32_t intro_start_ms_{0};

  uint16_t seen_mask_{0};
  uint16_t held_mask_{0};
  uint16_t long_fired_mask_{0};
  uint32_t pressed_at_ms_[16]{};
  // 0xFF when no input is held.
  uint8_t shown_bit_{0xFF};
  bool cw_seen_{false};
  bool ccw_seen_{false};
  bool inputs_logged_{false};
  int32_t encoder_pos_{0};
  bool encoder_moved_{false};
  uint32_t encoder_ms_{0};

  bool ir_rx_passed_{false};
  uint32_t ir_flash_until_ms_{0};

  bool tx_started_{false};
  bool tx_done_{false};
  uint32_t tx_start_ms_{0};

  // Written by the mic task, read and cleared by the main loop.
  std::atomic<uint32_t> mic_peak_{0};
  std::atomic<uint32_t> mic_blocks_{0};
  uint32_t mic_window_ms_{0};
  uint32_t mic_windows_{0};
  uint32_t mic_floor_{UINT32_MAX};
  bool mic_passed_{false};
  bool vu_mode_{false};
  float vu_level_{0.0f};

  bool battery_passed_{false};
  uint8_t battery_count_{0};
  float battery_first_v_{0.0f};

  bool usb_raw_{false};
  uint32_t usb_raw_since_ms_{0};
  bool usb_known_{false};
  bool usb_present_{false};
  bool usb_plugged_seen_{false};
  bool usb_unplugged_seen_{false};
  bool usb_flash_plug_{false};
  uint32_t usb_flash_until_ms_{0};

  bool installing_{false};
  uint32_t install_step_{0};

  bool active_{false};
  uint32_t active_ms_{0};
};

}  // namespace esphome::self_test
