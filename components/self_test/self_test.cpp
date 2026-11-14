#include "self_test.h"

#include "esphome/core/hal.h"
#include "esphome/core/log.h"

#include "esp_attr.h"
#include "esp_sleep.h"
#include "esp_system.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstring>

namespace esphome::self_test {

static const char *const TAG = "self_test";

static constexpr uint8_t NO_BIT = 0xFF;
static const char *const INPUT_NAME[16] = {
    "SW1",  "SW2", "SW3",  "SW4",         "SW5",      "SW6",          "SW7",        "SW8",
    "SW10", "SW9", "SW11", "wheel right", "wheel up", "wheel centre", "wheel down", "wheel left",
};

// Strip index of each LED. D2 and D3 are 0 and 1 on both boards.
static constexpr int32_t LED_D2 = 0;
static constexpr int32_t LED_D3 = 1;
static constexpr int32_t LED_D6 = 2;
static constexpr int32_t LED_D7 = 5;

// Boot chase, copied from the Status Indicators effect of c6remote.yaml so that a
// new unit looks like the finished product. A lap takes CHASE_LAP_MS at any LED
// count, so four LEDs keep the original 150 ms step.
static constexpr uint32_t CHASE_LAP_MS = 600;
static constexpr uint32_t CHASE_LAPS = 2;
// The strip is linear at full brightness here, so this peak reads brighter than
// it does in the production firmware.
static constexpr float CHASE_PEAK = 160.0f;
// The wake fill adds one LED at a time and keeps it lit, so it cannot look like
// the travelling pulse of a cold boot.
static constexpr uint32_t WAKE_STEP_MS = 160;
static constexpr uint32_t WAKE_HOLD_MS = 900;
static constexpr uint8_t WAKE_LEVEL = 140;

static constexpr uint32_t ENCODER_SHOW_MS = 1500;
static constexpr uint32_t IR_FLASH_MS = 300;
static constexpr uint32_t USB_FLASH_MS = 500;
static constexpr uint32_t USB_DEBOUNCE_MS = 50;
static constexpr uint32_t SLEEP_ARMED_FLASH_MS = 500;
static constexpr uint32_t SLEEP_REFUSED_MS = 1500;

// The receiver idle is 10 ms, so a frame from a remote has no longer entry.
static constexpr size_t IR_MIN_ENTRIES = 8;
static constexpr uint32_t IR_ECHO_MS = 500;

// Levels are window peaks in the 16-bit domain, full scale 32768. -25 dBFS is
// above the -35 dBFS knock that a key press puts into MK1 through the board.
static constexpr uint32_t MIC_WINDOW_MS = 50;
static constexpr uint32_t MIC_SETTLE_WINDOWS = 20;
static constexpr uint32_t MIC_LOUD = 1843;
static constexpr uint32_t MIC_SWING = 10;
static constexpr float VU_FLOOR_DB = -60.0f;
static constexpr float VU_SPAN_DB = 40.0f;

static constexpr float BATTERY_MIN_V = 3.3f;
static constexpr float BATTERY_MAX_V = 4.4f;
static constexpr float BATTERY_SPREAD_V = 0.15f;
static constexpr uint8_t BATTERY_SAMPLES = 3;

// gamma_correct is 1.0 on this strip, so each value is the PWM level.
// One colour for each LED of the chase, the README render palette in chain order:
// D2 red, D3 azure, D6 magenta, D4 green, D5 blue, D7 cyan.
static const Color CHASE_COLOUR[6] = {Color(255, 0, 0), Color(0, 112, 255), Color(170, 0, 171),
                                      Color(0, 255, 0), Color(0, 0, 255),   Color(0, 171, 170)};
// The ring rests here, so it stays dim enough to read a flash over it.
static const Color IDLE(10, 10, 10);
static const Color ENCODER_DOT(96, 96, 96);
static const Color IR_FLASH(96, 96, 96);
static const Color USB_PLUG(0, 64, 64);
static const Color USB_UNPLUG(96, 16, 0);
// A phone camera checks this step, so the ring must not flash or wash out D1.
// One dim LED holds steady instead, which lets the exposure settle on the emitter.
static const Color TRANSMIT(24, 0, 24);
static const Color VU_BAR(0, 48, 0);
static const Color VU_TOP(96, 0, 0);
static const Color VU_EMPTY(0, 0, 6);
static const Color INSTALL_DONE(0, 0, 64);
static const Color INSTALL_LEFT(0, 0, 6);
static const Color INSTALL_HEAD(64, 64, 96);
static const Color FAILED(64, 0, 0);
// Both sleep results cover the whole ring, so each one reads over the VU meter
// and over the resting glow. Dark blue stays apart from the dim VU blue.
static const Color SLEEP_ARMED_FLASH(0, 0, 64);
// Five bases that stay apart at this brightness. A held input shows one on the
// top half of the ring and another on the bottom half, so the pair names the bit.
// Magenta has no green, the brightest channel here, so it reads apart from white.
static const Color BASE_COLOUR[5] = {
    Color(96, 0, 0),    // red
    Color(0, 96, 0),    // green
    Color(0, 0, 96),    // blue
    Color(80, 80, 80),  // white
    Color(96, 0, 96),   // magenta
};
// Top and bottom base of each expander bit. site/factory-self-test.html lists
// the same pairs. Each group of four bits shares a top colour, and the bottom runs
// through the other bases in table order. No bit uses one base on both halves.
static const uint8_t INPUT_PAIR[16][2] = {
    {0, 1},  // SW1 red green
    {0, 2},  // SW2 red blue
    {0, 3},  // SW3 red white
    {0, 4},  // SW4 red magenta
    {1, 0},  // SW5 green red
    {1, 2},  // SW6 green blue
    {1, 3},  // SW7 green white
    {1, 4},  // SW8 green magenta
    {2, 0},  // SW10 blue red
    {2, 1},  // SW9 blue green
    {2, 3},  // SW11 blue white
    {2, 4},  // wheel right blue magenta
    {3, 0},  // wheel up white red
    {3, 1},  // wheel centre white green
    {3, 2},  // wheel down white blue
    {3, 4},  // wheel left white magenta
};

// Two laps of pulses, and two more steps for the tail of the last pulse.
static uint32_t chase_ms(uint32_t n) { return (CHASE_LAPS * n + 2) * (CHASE_LAP_MS / n); }

// The fill takes one step for each LED, then holds the full ring.
static uint32_t wake_ms(uint32_t n) { return n * WAKE_STEP_MS + WAKE_HOLD_MS; }

// D6 and D7 sit at the ends of the chain, so a six-LED ring skips the swap that
// a four-LED ring needs.
static Color chase_colour(uint32_t n, uint32_t led) {
  return CHASE_COLOUR[n >= 6 ? led % 6 : (led >= 2 ? led + 1 : led)];
}

static Color scaled(const Color &c, float f) {
  f = std::min(std::max(f, 0.0f), 1.0f);
  return c * static_cast<uint8_t>(f * 255.0f);
}

void SelfTest::setup() {
  auto *out = static_cast<light::AddressableLight *>(this->light_->get_output());
  this->led_count_ = std::max<int32_t>(out->size(), 1);
  this->v3_ = this->led_count_ >= 6;
  // GPIO7 has no connection on a V2 board, so only V3 configures it.
  if (this->v3_ && this->usb_pin_ != nullptr) {
    this->usb_pin_->setup();
    this->usb_raw_ = this->usb_pin_->digital_read();
    this->usb_raw_since_ms_ = millis();
  }
  this->mic_->add_data_callback([this](const std::vector<uint8_t> &data) { this->mic_block_(data); });
  this->mic_->start();
#ifdef USE_OTA_STATE_LISTENER
  ota::get_global_ota_callback()->add_global_state_listener(this);
#endif
}

void SelfTest::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Self-test:\n"
                "  Board: %s, %" PRId32 " status LEDs\n"
                "  USB detector: %s\n"
                "  IR transmit: hold %s for %" PRIu32 " ms\n"
                "  VU meter: hold %s for %" PRIu32 " ms\n"
                "  Sleep test: hold %s for %" PRIu32 " ms",
                this->v3_ ? "V3" : "V2", this->led_count_, this->v3_ ? "GPIO7" : "none", INPUT_NAME[TRANSMIT_BIT],
                LONG_PRESS_MS, INPUT_NAME[VU_BIT], LONG_PRESS_MS, INPUT_NAME[SLEEP_BIT], SLEEP_HOLD_MS);
}

void SelfTest::loop() {
  const uint32_t now = millis();
  this->update_mic_(now);
  this->update_usb_(now);
  this->update_long_presses_(now);
  this->update_sleep_();
  if (this->tx_started_ && !this->tx_done_ && !this->transmitting_(now)) {
    this->tx_done_ = true;
    ESP_LOGI(TAG, "IR transmit ended");
  }
}

void SelfTest::input(uint8_t bit, bool pressed) {
  if (bit >= 16)
    return;
  const uint16_t mask = 1u << bit;
  if (pressed) {
    this->held_mask_ |= mask;
    this->long_fired_mask_ &= ~mask;
    this->pressed_at_ms_[bit] = millis();
    this->shown_bit_ = bit;
    if ((this->seen_mask_ & mask) == 0) {
      this->seen_mask_ |= mask;
      ESP_LOGI(TAG, "Input %s seen, missing inputs 0x%04X", INPUT_NAME[bit], static_cast<uint16_t>(~this->seen_mask_));
      this->note_inputs_();
    }
    return;
  }
  this->held_mask_ &= ~mask;
  if (this->shown_bit_ == bit)
    this->shown_bit_ = this->held_mask_ != 0 ? static_cast<uint8_t>(__builtin_ctz(this->held_mask_)) : NO_BIT;
}

void SelfTest::encoder_step(bool clockwise) {
  const int32_t n = this->led_count_;
  this->encoder_pos_ = clockwise ? (this->encoder_pos_ + 1) % n : (this->encoder_pos_ + n - 1) % n;
  this->encoder_moved_ = true;
  this->encoder_ms_ = millis();
  this->mark_active_(this->encoder_ms_);
  bool &seen = clockwise ? this->cw_seen_ : this->ccw_seen_;
  if (!seen) {
    seen = true;
    ESP_LOGI(TAG, "Encoder %s step seen", clockwise ? "clockwise" : "anticlockwise");
    this->note_inputs_();
  }
}

void SelfTest::note_inputs_() {
  if (this->inputs_logged_ || !this->inputs_seen_())
    return;
  this->inputs_logged_ = true;
  ESP_LOGI(TAG, "Every input seen");
}

void SelfTest::update_long_presses_(uint32_t now) {
  for (const uint8_t bit : {TRANSMIT_BIT, VU_BIT, SLEEP_BIT}) {
    const uint16_t mask = 1u << bit;
    if ((this->held_mask_ & mask) == 0 || (this->long_fired_mask_ & mask) != 0)
      continue;
    if (now - this->pressed_at_ms_[bit] < (bit == SLEEP_BIT ? SLEEP_HOLD_MS : LONG_PRESS_MS))
      continue;
    this->long_fired_mask_ |= mask;
    if (bit == TRANSMIT_BIT) {
      this->start_transmit_(now);
    } else if (bit == VU_BIT) {
      this->vu_mode_ = !this->vu_mode_;
      ESP_LOGI(TAG, "VU meter %s", this->vu_mode_ ? "on" : "off");
    } else {
      // The hold works in the VU meter too, so no display mode makes it dead.
      // allow_sleep_() logs and shows a refusal.
      this->sleep_requested_ = this->allow_sleep_();
      if (this->sleep_requested_) {
        this->sleep_armed_until_ms_ = now + SLEEP_ARMED_FLASH_MS;
        ESP_LOGI(TAG, "Sleep test armed, release all buttons");
      }
    }
  }
}

// Names the first condition that blocks the sleep test, or returns nullptr.
const char *SelfTest::sleep_block_() {
  if (!this->sleep_blocked_by_)
    return "no sleep probe";
  if (this->installing_)
    return "an OTA install is running";
  if (this->transmitting_(millis()))
    return "IR transmit is running";
  return this->sleep_blocked_by_();
}

bool SelfTest::allow_sleep_() {
  const char *blocked = this->sleep_block_();
  if (blocked == nullptr)
    return true;
  this->sleep_requested_ = false;
  this->sleep_refused_until_ms_ = millis() + SLEEP_REFUSED_MS;
  ESP_LOGI(TAG, "Sleep test refused: %s", blocked);
  return false;
}

void SelfTest::update_sleep_() {
  if (!this->sleep_requested_ || this->held_mask_ != 0)
    return;
  if (!this->allow_sleep_())
    return;
  this->idle_->arm_sleep([this]() { return this->allow_sleep_(); });
}

void SelfTest::start_transmit_(uint32_t now) {
  if (this->tx_ == nullptr || this->transmitting_(now))
    return;
  auto call = this->tx_->transmit();
  auto *data = call.get_data();
  data->set_carrier_frequency(TX_CARRIER_HZ);
  data->reserve(2 * TX_BURSTS * TX_CHOPS);
  for (uint32_t i = 0; i < TX_BURSTS; i++) {
    for (uint32_t j = 0; j + 1 < TX_CHOPS; j++)
      data->item(TX_CHOP_MARK_US, TX_CHOP_SPACE_US);
    data->item(TX_CHOP_MARK_US, TX_GAP_US);
  }
  call.perform();
  this->tx_started_ = true;
  this->tx_start_ms_ = now;
  ESP_LOGI(TAG, "IR transmit: %" PRIu32 " flashes of %" PRIu32 " ms at %" PRIu32 " Hz, %" PRIu32 " bursts each",
           TX_BURSTS, TX_MARK_US / 1000, TX_CARRIER_HZ, TX_CHOPS);
}

void SelfTest::ir_frame(const std::vector<int32_t> &raw) {
  const uint32_t now = millis();
  // U2 can see the reflection of the board's own bursts.
  if (this->tx_started_ && now - this->tx_start_ms_ < TX_TOTAL_MS + IR_ECHO_MS)
    return;
  if (raw.size() < IR_MIN_ENTRIES)
    return;
  this->ir_flash_until_ms_ = now + IR_FLASH_MS;
  this->mark_active_(now);
  if (!this->ir_rx_passed_) {
    this->ir_rx_passed_ = true;
    ESP_LOGI(TAG, "IR receive check passed: frame of %u entries", static_cast<unsigned>(raw.size()));
  }
}

void SelfTest::battery_sample(float volts) {
  if (this->battery_passed_)
    return;
  // With USB present, the charger output can read in range without a cell, so
  // V3 counts only samples on battery power.
  const bool on_battery = !this->v3_ || (this->usb_known_ && !this->usb_present_);
  if (std::isnan(volts) || volts < BATTERY_MIN_V || volts > BATTERY_MAX_V || !on_battery) {
    this->battery_count_ = 0;
    return;
  }
  if (this->battery_count_ == 0 || std::fabs(volts - this->battery_first_v_) > BATTERY_SPREAD_V) {
    this->battery_first_v_ = volts;
    this->battery_count_ = 1;
    return;
  }
  if (++this->battery_count_ < BATTERY_SAMPLES)
    return;
  this->battery_passed_ = true;
  ESP_LOGI(TAG, "Battery check passed at %.2f V", volts);
}

// Runs in the mic task.
void SelfTest::mic_block_(const std::vector<uint8_t> &data) {
  const size_t n = data.size() / sizeof(int32_t);
  if (n == 0)
    return;
  int64_t sum = 0;
  for (size_t i = 0; i < n; i++) {
    int32_t sample;
    std::memcpy(&sample, &data[i * sizeof(int32_t)], sizeof(sample));
    sum += sample >> 8;
  }
  const int32_t mean = static_cast<int32_t>(sum / static_cast<int64_t>(n));
  uint32_t peak = 0;
  for (size_t i = 0; i < n; i++) {
    int32_t sample;
    std::memcpy(&sample, &data[i * sizeof(int32_t)], sizeof(sample));
    const int32_t value = (sample >> 8) - mean;
    const uint32_t magnitude = static_cast<uint32_t>(value < 0 ? -value : value);
    peak = std::max(peak, magnitude);
  }
  // 24-bit payload to the 16-bit domain.
  peak >>= 8;
  uint32_t prev = this->mic_peak_.load(std::memory_order_relaxed);
  while (peak > prev && !this->mic_peak_.compare_exchange_weak(prev, peak, std::memory_order_relaxed)) {
  }
  this->mic_blocks_.fetch_add(1, std::memory_order_relaxed);
}

void SelfTest::update_mic_(uint32_t now) {
  if (now - this->mic_window_ms_ < MIC_WINDOW_MS)
    return;
  this->mic_window_ms_ = now;
  const uint32_t blocks = this->mic_blocks_.exchange(0, std::memory_order_relaxed);
  const uint32_t peak = this->mic_peak_.exchange(0, std::memory_order_relaxed);
  if (blocks == 0) {
    this->vu_level_ *= 0.8f;
    return;
  }
  // The first windows after the clock starts can hold the start-up output of MK1.
  if (this->mic_windows_ < MIC_SETTLE_WINDOWS) {
    this->mic_windows_++;
    return;
  }
  const float db = peak > 0 ? 20.0f * log10f(static_cast<float>(peak) / 32768.0f) : -120.0f;
  const float target = std::min(std::max((db - VU_FLOOR_DB) / VU_SPAN_DB, 0.0f), 1.0f);
  this->vu_level_ += (target - this->vu_level_) * (target > this->vu_level_ ? 0.6f : 0.1f);

  if (peak > 0)
    this->mic_floor_ = std::min(this->mic_floor_, peak);
  // A loud peak alone does not pass. A stream of noise has no quiet floor 20 dB under it.
  if (!this->mic_passed_ && peak >= MIC_LOUD && this->mic_floor_ != UINT32_MAX &&
      peak >= MIC_SWING * this->mic_floor_) {
    this->mic_passed_ = true;
    ESP_LOGI(TAG, "Microphone check passed: peak %.1f dBFS, floor %.1f dBFS", db,
             20.0f * log10f(static_cast<float>(this->mic_floor_) / 32768.0f));
  }
}

void SelfTest::update_usb_(uint32_t now) {
  if (!this->v3_ || this->usb_pin_ == nullptr)
    return;
  const bool raw = this->usb_pin_->digital_read();
  if (raw != this->usb_raw_) {
    this->usb_raw_ = raw;
    this->usb_raw_since_ms_ = now;
    return;
  }
  if (now - this->usb_raw_since_ms_ < USB_DEBOUNCE_MS)
    return;
  if (this->usb_known_ && raw == this->usb_present_)
    return;
  const bool first = !this->usb_known_;
  this->usb_known_ = true;
  this->usb_present_ = raw;
  if (raw) {
    this->usb_plugged_seen_ = true;
  } else {
    this->usb_unplugged_seen_ = true;
  }
  ESP_LOGI(TAG, "USB power %s", raw ? "present" : "absent");
  this->mark_active_(now);
  if (!first) {
    this->usb_flash_plug_ = raw;
    this->usb_flash_until_ms_ = now + USB_FLASH_MS;
    if (this->usb_seen_())
      ESP_LOGI(TAG, "USB seen present and absent");
  }
}

void SelfTest::render(light::AddressableLight &it) {
  const int32_t n = it.size();
  // The buffer keeps the last install frame.
  if (n <= 0 || this->installing_)
    return;
  const uint32_t now = millis();
  if (!this->intro_started_) {
    this->intro_started_ = true;
    this->intro_wake_ = this->idle_ != nullptr && this->idle_->woke_from_sleep();
    this->intro_start_ms_ = now;
  }
  const uint32_t since = now - this->intro_start_ms_;
  const auto un = static_cast<uint32_t>(n);
  if (since < (this->intro_wake_ ? wake_ms(un) : chase_ms(un))) {
    if (this->intro_wake_)
      this->draw_wake_(it, since);
    else
      this->draw_chase_(it, since);
    return;
  }

  // The operator keeps the record, so the ring reports no result of its own.
  // A dim ring only shows that the board is awake and that every LED lights.
  if (this->vu_mode_) {
    this->draw_vu_(it);
  } else {
    it.all() = IDLE;
  }

  if (now < this->usb_flash_until_ms_)
    it.all() = this->usb_flash_plug_ ? USB_PLUG : USB_UNPLUG;
  if (now < this->ir_flash_until_ms_)
    it.all() = IR_FLASH;
  if (this->encoder_moved_ && now - this->encoder_ms_ < ENCODER_SHOW_MS) {
    it.all() = Color::BLACK;
    it[this->encoder_pos_ % n] = ENCODER_DOT;
  }
  // After a hold fires, that action owns the ring instead of the key colour.
  if (this->shown_bit_ != NO_BIT && (this->long_fired_mask_ & (1u << this->shown_bit_)) == 0)
    this->draw_input_(it, this->shown_bit_);
  if (this->transmitting_(now)) {
    it.all() = Color::BLACK;
    it[LED_D6] = TRANSMIT;
  }
  // Last, so the sleep hold answers on every display mode and over a held input.
  if (static_cast<int32_t>(this->sleep_armed_until_ms_ - now) > 0)
    it.all() = SLEEP_ARMED_FLASH;
  if (static_cast<int32_t>(this->sleep_refused_until_ms_ - now) > 0)
    it.all() = FAILED;
}

// Two clockwise laps. Each pulse lasts three steps and the next starts one step
// later, so each pulse overlaps the next two. A four-LED chain skips magenta and
// cyan, as the production index mapping does.
void SelfTest::draw_chase_(light::AddressableLight &it, uint32_t t) const {
  const auto n = static_cast<uint32_t>(it.size());
  const uint32_t step = CHASE_LAP_MS / n;
  const uint32_t pulses = CHASE_LAPS * n;
  it.all() = Color::BLACK;
  for (uint32_t i = 0; i < pulses; i++) {
    const uint32_t start = i * step;
    if (t < start || t >= start + 3 * step)
      continue;
    const float phase = static_cast<float>(t - start) / (3.0f * static_cast<float>(step));
    const auto level = static_cast<uint8_t>(CHASE_PEAK *
                                            (0.5f - 0.5f * cosf(2.0f * static_cast<float>(M_PI) * phase)));
    const uint32_t led = i % n;
    it[static_cast<int32_t>(led)] = chase_colour(n, led) * level;
  }
}

// A wake fills the ring one LED at a time and holds it. The operator sees a
// complete ring, not a moving pulse, so a reset cannot pass for a wake.
void SelfTest::draw_wake_(light::AddressableLight &it, uint32_t t) const {
  const auto n = static_cast<uint32_t>(it.size());
  const uint32_t lit = std::min(t / WAKE_STEP_MS + 1, n);
  it.all() = Color::BLACK;
  for (uint32_t led = 0; led < lit; led++)
    it[static_cast<int32_t>(led)] = chase_colour(n, led) * WAKE_LEVEL;
}

// The chain runs clockwise from D2 at the bottom left, so indices 1 to n / 2
// are the top arc on the four-LED ring and on the six-LED ring.
void SelfTest::draw_input_(light::AddressableLight &it, uint8_t bit) const {
  const int32_t n = it.size();
  for (int32_t i = 0; i < n; i++) {
    const bool top = i >= 1 && i <= n / 2;
    it[i] = BASE_COLOUR[INPUT_PAIR[bit][top ? 0 : 1]];
  }
}

void SelfTest::draw_vu_(light::AddressableLight &it) const {
  const int32_t n = it.size();
  const float lit = this->vu_level_ * static_cast<float>(n);
  for (int32_t i = 0; i < n; i++) {
    const float part = lit - static_cast<float>(i);
    if (part <= 0.0f) {
      it[i] = VU_EMPTY;
    } else {
      it[i] = scaled(i == n - 1 ? VU_TOP : VU_BAR, part);
    }
  }
}

// The http_request install blocks the main loop, so the light never runs its
// effect. This writes the strip from the OTA callback instead.
void SelfTest::draw_install_(float percent) {
  if (this->light_ == nullptr || !this->light_->remote_values.is_on())
    return;
  auto *out = static_cast<light::AddressableLight *>(this->light_->get_output());
  const int32_t n = out->size();
  if (n <= 0)
    return;
  const auto done = static_cast<int32_t>(std::lround(std::min(std::max(percent, 0.0f), 100.0f) * n / 100.0f));
  for (int32_t i = 0; i < n; i++)
    (*out)[i] = i < done ? INSTALL_DONE : INSTALL_LEFT;
  // One step for each callback, about one each second, so a slow block still moves.
  (*out)[static_cast<int32_t>(this->install_step_++ % static_cast<uint32_t>(n))] = INSTALL_HEAD;
  out->write_state(this->light_);
}

#ifdef USE_OTA_STATE_LISTENER
void SelfTest::on_ota_global_state(ota::OTAState state, float progress, uint8_t error,
                                   ota::OTAComponent *component) {
  switch (state) {
    case ota::OTA_STARTED:
      this->installing_ = true;
      this->install_step_ = 0;
      this->draw_install_(0.0f);
      break;
    case ota::OTA_IN_PROGRESS:
      this->installing_ = true;
      this->draw_install_(progress);
      break;
    case ota::OTA_COMPLETED:
      this->draw_install_(100.0f);
      this->installing_ = false;
      break;
    default:
      // An error or abort hands the strip back to the effect.
      this->installing_ = false;
      break;
  }
}
#endif

}  // namespace esphome::self_test
