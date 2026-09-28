#include "idle_sleep.h"
#include "wake_stub.h"

#include "esphome/core/application.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "esphome/core/preferences.h"

#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "esp_attr.h"
#include "esp_private/esp_clk.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "soc/rtc.h"

#include <cstring>

namespace esphome::idle_sleep {

static const char *const TAG = "idle_sleep";

static constexpr gpio_num_t WAKE_PIN = GPIO_NUM_5;
// Held through deep sleep. 6 and 18 float so R11 and R10 keep both rails off,
// and 16 floats so U2 sees no pull. 15 floats so the active-low XIAO user LED
// is dark. 17 keeps the on_shutdown pulldown on DIN.
// 0 and 2 are driven low so MK1 sees a stopped clock.
static constexpr gpio_num_t HELD_FLOATING[] = {GPIO_NUM_6, GPIO_NUM_15, GPIO_NUM_16, GPIO_NUM_18};
static constexpr gpio_num_t HELD_PULLDOWN = GPIO_NUM_17;
static constexpr gpio_num_t HELD_LOW[] = {GPIO_NUM_0, GPIO_NUM_2};

static constexpr uint32_t POLL_MS = 100;
static constexpr int64_t REPLAY_TIMEOUT_US = 3000000;
// Same budget as the stock deep_sleep component.
static constexpr uint32_t TEARDOWN_MS = 5000;

static constexpr uint32_t RING_MAGIC = 0x534C5031u;
static constexpr size_t RING_SIZE = 20;
static constexpr int32_t NONE = -1;
static constexpr uint8_t NO_BIT = 0xFF;

struct WakeRecord {
  uint32_t seq;
  uint8_t cause;
  uint8_t reset;
  uint8_t stub_flags;
  uint8_t replay_bit;
  uint16_t stub_down;
  uint16_t first_down;
  uint32_t stub_us;
  uint32_t boot_us;
  uint32_t setup_us;
  int32_t read_us;
  int32_t link_ms;
  int32_t replay_ms;
  uint32_t awake_ms;
};

struct WakeRing {
  uint32_t magic;
  uint32_t seq;
  uint32_t head;
  uint32_t count;
  WakeRecord records[RING_SIZE];
};

// NOINIT keeps the history through a panic or software reset as well as deep
// sleep. The magic tells a power-on from a valid ring.
static RTC_NOINIT_ATTR WakeRing s_ring;
static WakeRecord *s_current = nullptr;

// Set by the INT falling-edge ISR and cleared by loop().
static volatile bool s_int_edge = false;

static void IRAM_ATTR int_edge_isr(void * /*arg*/) { s_int_edge = true; }

static const char *stub_name(uint8_t flags) {
  if (flags == 0)
    return "none";
  if (flags & IDLE_SLEEP_STUB_SKIPPED)
    return "skip";
  if ((flags & IDLE_SLEEP_STUB_ACK) == 0)
    return "nack";
  return "ok";
}

static void log_record(const char *label, const WakeRecord &r) {
  // Wake to link and wake to replay are only known when the stub stamped the LP timer.
  const int32_t base_ms = r.stub_flags != 0 ? static_cast<int32_t>((r.stub_us + r.boot_us) / 1000) : NONE;
  const int32_t to_link = base_ms >= 0 && r.link_ms >= 0 ? base_ms + r.link_ms : NONE;
  const int32_t to_replay = base_ms >= 0 && r.replay_ms >= 0 ? base_ms + r.replay_ms : NONE;
  ESP_LOGI(TAG,
           "%s #%" PRIu32 " cause=%u rst=%u stub=%s stub_down=0x%04X first_down=0x%04X stub_us=%" PRIu32
           " boot_us=%" PRIu32 " setup_us=%" PRIu32 " read_us=%" PRId32 " link_ms=%" PRId32 " replay_ms=%" PRId32
           " bit=%d to_link_ms=%" PRId32 " to_replay_ms=%" PRId32 " awake_ms=%" PRIu32,
           label, r.seq, r.cause, r.reset, stub_name(r.stub_flags), r.stub_down, r.first_down, r.stub_us, r.boot_us,
           r.setup_us, r.read_us, r.link_ms, r.replay_ms, r.replay_bit == NO_BIT ? -1 : r.replay_bit, to_link,
           to_replay, r.awake_ms);
}

bool IdleSleep::read_port_(uint16_t *port) {
  uint8_t data[2];
  if (this->read(data, sizeof(data)) != i2c::ERROR_OK)
    return false;
  *port = static_cast<uint16_t>(data[0] | (data[1] << 8));
  return true;
}

void IdleSleep::set_pressed_(uint16_t pressed, uint32_t now) {
  if (pressed != 0 && this->pressed_ == 0) {
    ESP_LOGI(TAG, "Press 0x%04X at %" PRIu32 " ms restarts the idle window", pressed, now);
  } else if (pressed == 0 && this->pressed_ != 0) {
    ESP_LOGI(TAG, "Release at %" PRIu32 " ms, idle window from %" PRIu32 " ms", now, this->last_activity_ms_);
  }
  this->pressed_ = pressed;
  if (pressed != 0)
    this->last_activity_ms_ = now;
}

void IdleSleep::track_hold_(uint16_t pressed, uint32_t now) {
  if (this->sleep_hold_bit_ == NO_BIT || this->forced_sleep_)
    return;
  if ((pressed & (1u << this->sleep_hold_bit_)) == 0) {
    this->hold_down_ = false;
    return;
  }
  if (!this->hold_down_) {
    this->hold_down_ = true;
    this->hold_since_ms_ = now;
  } else if (now - this->hold_since_ms_ >= this->sleep_hold_time_ms_) {
    this->forced_sleep_ = true;
    ESP_LOGI(TAG, "SW hold on bit %u, sleeping on release", this->sleep_hold_bit_);
  }
}

void IdleSleep::setup() {
  // First: a held pad ignores every configuration written while it is held.
  for (gpio_num_t pin : HELD_FLOATING)
    gpio_hold_dis(pin);
  gpio_hold_dis(HELD_PULLDOWN);
  for (gpio_num_t pin : HELD_LOW)
    gpio_hold_dis(pin);
  // ext1 leaves the wake pad on the LP mux, where the HP GPIO reads nothing.
  rtc_gpio_deinit(WAKE_PIN);

  this->setup_us_ = esp_timer_get_time();
  const uint64_t setup_ticks = rtc_time_get();
  const esp_sleep_wakeup_cause_t cause = esp_sleep_get_wakeup_cause();
  const esp_reset_reason_t reset = esp_reset_reason();
  this->cold_boot_ = reset != ESP_RST_DEEPSLEEP;

  const idle_sleep_latch_t latch = idle_sleep_latch;
  idle_sleep_latch.magic = 0;
  const bool latched = !this->cold_boot_ && latch.magic == IDLE_SLEEP_LATCH_MAGIC;

  uint16_t port = 0xFFFF;
  const bool read_ok = this->read_port_(&port);
  const int64_t read_us = esp_timer_get_time();
  const uint16_t first_down = read_ok ? static_cast<uint16_t>(~port) : 0;

  if (s_ring.magic != RING_MAGIC || s_ring.head >= RING_SIZE || s_ring.count > RING_SIZE) {
    std::memset(&s_ring, 0, sizeof(s_ring));
    s_ring.magic = RING_MAGIC;
    s_ring.head = RING_SIZE - 1;
  }
  s_ring.head = (s_ring.head + 1) % RING_SIZE;
  if (s_ring.count < RING_SIZE)
    s_ring.count++;
  WakeRecord &rec = s_ring.records[s_ring.head];
  std::memset(&rec, 0, sizeof(rec));
  rec.seq = ++s_ring.seq;
  rec.cause = static_cast<uint8_t>(cause);
  rec.reset = static_cast<uint8_t>(reset);
  rec.replay_bit = NO_BIT;
  rec.setup_us = static_cast<uint32_t>(this->setup_us_);
  rec.read_us = read_ok ? static_cast<int32_t>(read_us - this->setup_us_) : NONE;
  rec.first_down = first_down;
  rec.link_ms = NONE;
  rec.replay_ms = NONE;
  if (latched) {
    rec.stub_flags = static_cast<uint8_t>(latch.flags);
    if (latch.flags & IDLE_SLEEP_STUB_ACK)
      rec.stub_down = static_cast<uint16_t>(~latch.port);
    if (latch.ticks_per_us != 0)
      rec.stub_us = latch.cycles / latch.ticks_per_us;
    const uint64_t stub_ticks = (static_cast<uint64_t>(latch.lp_ticks_hi) << 32) | latch.lp_ticks_lo;
    if (setup_ticks > stub_ticks)
      rec.boot_us = static_cast<uint32_t>(rtc_time_slowclk_to_us(setup_ticks - stub_ticks, esp_clk_slowclk_cal_get()));
  }
  s_current = &rec;

  // The binary sensors do not fire on_press for their first state, so a bit
  // still down here reaches no on_press at all. The replay hook decides.
  this->replay_mask_ = rec.stub_down;
  this->held_mask_ = rec.stub_down & first_down;
  this->replay_pending_ = this->replay_mask_ != 0 && static_cast<bool>(this->replay_);
  this->pressed_ = first_down;
  this->last_activity_ms_ = millis();
  this->last_poll_ms_ = this->last_activity_ms_;

  this->load_settings_();
}

void IdleSleep::load_settings_() {
  this->settings_pref_ = global_preferences->make_preference<SettingsPref>(SETTINGS_KEY, true);
  SettingsPref loaded{};
  const bool valid = this->settings_pref_.load(&loaded) && loaded.magic == SETTINGS_MAGIC && loaded.enabled <= 1 &&
                     (loaded.stored_after_s == 0 ||
                      (loaded.stored_after_s >= MIN_SLEEP_AFTER_S && loaded.stored_after_s <= MAX_SLEEP_AFTER_S));
  this->stored_after_s_ = valid ? loaded.stored_after_s : 0;
  this->enabled_.store(!valid || loaded.enabled == 1, std::memory_order_relaxed);
  this->sleep_after_s_.store(this->stored_after_s_ != 0 ? this->stored_after_s_ : this->default_sleep_after_s_,
                             std::memory_order_relaxed);
}

bool IdleSleep::save_settings_(bool enabled, uint32_t stored_after_s) {
  SettingsPref next{SETTINGS_MAGIC, stored_after_s, enabled ? uint8_t{1} : uint8_t{0}, {0, 0, 0}};
  if (!this->settings_pref_.save(&next)) {
    ESP_LOGE(TAG, "Failed to save the sleep settings");
    return false;
  }
  return true;
}

bool IdleSleep::set_enabled(bool enabled) {
  if (!this->save_settings_(enabled, this->stored_after_s_))
    return false;
  this->enabled_.store(enabled, std::memory_order_relaxed);
  this->last_activity_ms_ = millis();
  ESP_LOGI(TAG, "Idle sleep %s, idle window restarted", enabled ? "on" : "off");
  return true;
}

bool IdleSleep::set_sleep_after_s(uint32_t seconds) {
  if (seconds < MIN_SLEEP_AFTER_S || seconds > MAX_SLEEP_AFTER_S)
    return false;
  if (!this->save_settings_(this->enabled(), seconds))
    return false;
  this->stored_after_s_ = seconds;
  this->sleep_after_s_.store(seconds, std::memory_order_relaxed);
  this->last_activity_ms_ = millis();
  ESP_LOGI(TAG, "Sleep after %" PRIu32 " s, idle window restarted", seconds);
  return true;
}

// Runs from the first loop(), after every setup(). ESPHome installs the ISR
// service on its first attach_interrupt() and fails that attach when the service
// already exists, so this must not install it first.
void IdleSleep::attach_int_isr_() {
  this->int_isr_tried_ = true;
  const esp_err_t service = gpio_install_isr_service(ESP_INTR_FLAG_LEVEL3);
  if (service != ESP_OK && service != ESP_ERR_INVALID_STATE) {
    ESP_LOGW(TAG, "GPIO ISR service failed: %s. Only the poll counts as activity", esp_err_to_name(service));
    return;
  }
  gpio_input_enable(WAKE_PIN);
  gpio_set_intr_type(WAKE_PIN, GPIO_INTR_NEGEDGE);
  const esp_err_t added = gpio_isr_handler_add(WAKE_PIN, int_edge_isr, nullptr);
  if (added != ESP_OK) {
    gpio_set_intr_type(WAKE_PIN, GPIO_INTR_DISABLE);
    ESP_LOGW(TAG, "GPIO5 ISR failed: %s. Only the poll counts as activity", esp_err_to_name(added));
    return;
  }
  this->int_isr_attached_ = true;
  ESP_LOGI(TAG, "INT falling-edge ISR on GPIO5");
}

void IdleSleep::detach_int_isr_() {
  if (!this->int_isr_attached_)
    return;
  this->int_isr_attached_ = false;
  gpio_isr_handler_remove(WAKE_PIN);
  gpio_set_intr_type(WAKE_PIN, GPIO_INTR_DISABLE);
}

void IdleSleep::dump_config() {
  ESP_LOGCONFIG(TAG,
                "Idle sleep:\n"
                "  Enabled: %s\n"
                "  Sleep after: %" PRIu32 " s (%s, YAML default %" PRIu32 " s)\n"
                "  Cold boot grace: %" PRIu32 " ms",
                YESNO(this->enabled()), this->sleep_after_s(), this->stored_after_s_ != 0 ? "stored" : "default",
                this->default_sleep_after_s_, this->cold_boot_grace_ms_);
  if (this->sleep_hold_bit_ != NO_BIT) {
    ESP_LOGCONFIG(TAG, "  Sleep hold: bit %u for %" PRIu32 " ms", this->sleep_hold_bit_, this->sleep_hold_time_ms_);
  } else {
    ESP_LOGCONFIG(TAG, "  Sleep hold: off");
  }
#ifdef USE_IDLE_SLEEP_WAKE_STUB
  ESP_LOGCONFIG(TAG, "  Wake stub: PCF8575 read on GPIO22/23");
#else
  ESP_LOGCONFIG(TAG, "  Wake stub: off");
#endif
  LOG_I2C_DEVICE(this);
}

void IdleSleep::loop() {
  const uint32_t now = millis();

  if (!this->int_isr_tried_)
    this->attach_int_isr_();
  // The poll can miss a tap shorter than POLL_MS, but INT cannot.
  if (s_int_edge) {
    s_int_edge = false;
    ESP_LOGD(TAG, "INT edge at %" PRIu32 " ms restarts the idle window", now);
    this->last_activity_ms_ = now;
  }

  if (!this->link_seen_ && this->link_probe_ && this->link_probe_()) {
    this->link_seen_ = true;
    if (s_current != nullptr)
      s_current->link_ms = static_cast<int32_t>((esp_timer_get_time() - this->setup_us_) / 1000);
  }

  if (this->replay_pending_) {
    if (this->link_seen_) {
      this->replay_pending_ = false;
      bool sent = false;
      for (uint8_t bit = 0; bit < 16; bit++) {
        if ((this->replay_mask_ & (1u << bit)) == 0)
          continue;
        const bool held = (this->held_mask_ & (1u << bit)) != 0;
        const bool this_sent = this->replay_(bit, held);
        ESP_LOGI(TAG, "Replay bit %u, held at first read: %s, sent: %s", bit, YESNO(held), YESNO(this_sent));
        if (this_sent && s_current != nullptr && s_current->replay_bit == NO_BIT)
          s_current->replay_bit = bit;
        sent = sent || this_sent;
      }
      if (sent) {
        if (s_current != nullptr)
          s_current->replay_ms = static_cast<int32_t>((esp_timer_get_time() - this->setup_us_) / 1000);
        this->last_activity_ms_ = now;
      }
    } else if (esp_timer_get_time() - this->setup_us_ > REPLAY_TIMEOUT_US) {
      this->replay_pending_ = false;
      ESP_LOGW(TAG, "Replay dropped: no link 3 s after setup");
    }
  }

  if (now - this->last_poll_ms_ >= POLL_MS) {
    this->last_poll_ms_ = now;
    uint16_t port;
    if (this->read_port_(&port)) {
      const uint16_t pressed = static_cast<uint16_t>(~port);
      this->set_pressed_(pressed, now);
      this->track_hold_(pressed, now);
    }
  }

  this->try_sleep_();
}

void IdleSleep::try_sleep_() {
  const uint32_t now = millis();
  if (this->forced_sleep_) {
    // A bit still down wakes ext1 at once on its release.
    if (this->pressed_ != 0)
      return;
    if (this->replay_pending_) {
      this->replay_pending_ = false;
      ESP_LOGI(TAG, "Replay dropped: forced sleep");
    }
  } else {
    if (!this->enabled())
      return;
    // A blocked remote counts as active, so the full window follows the block.
    if (this->block_probe_ && this->block_probe_()) {
      this->last_activity_ms_ = now;
      return;
    }
    if (this->replay_pending_ || this->pressed_ != 0)
      return;
    if (this->cold_boot_ && now < this->cold_boot_grace_ms_)
      return;
    if (now - this->last_activity_ms_ < this->sleep_after_s() * 1000U)
      return;
  }

  // The read releases INT. INT low after it means an input moved since.
  uint16_t port;
  if (this->read_port_(&port) && static_cast<uint16_t>(~port) != 0) {
    this->set_pressed_(static_cast<uint16_t>(~port), now);
    return;
  }
  if (gpio_get_level(WAKE_PIN) == 0) {
    if (this->forced_sleep_) {
      ESP_LOGD(TAG, "INT low before forced sleep at %" PRIu32 " ms, retry next loop", now);
      return;
    }
    ESP_LOGI(TAG, "INT low before sleep at %" PRIu32 " ms, idle window restarted", now);
    this->last_activity_ms_ = now;
    return;
  }
  this->enter_sleep_();
}

void IdleSleep::enter_sleep_() {
  if (s_current != nullptr) {
    s_current->awake_ms = static_cast<uint32_t>((esp_timer_get_time() - this->setup_us_) / 1000);
    log_record("WAKE_TIMING", *s_current);
  }
  const uint32_t now = millis();
  ESP_LOGI(TAG,
           "Entering deep sleep at %" PRIu32 " ms, idle %" PRIu32 " ms since %" PRIu32
           " ms, reason: %s, INT on GPIO5 wakes",
           now, now - this->last_activity_ms_, this->last_activity_ms_,
           this->forced_sleep_ ? "forced by hold" : "idle window");

  App.run_safe_shutdown_hooks();
  App.teardown_components(TEARDOWN_MS);
  App.run_powerdown_hooks();

  // ext1 takes the pad below, so the edge ISR goes first.
  this->detach_int_isr_();

  gpio_config_t floating{};
  floating.mode = GPIO_MODE_INPUT;
  for (gpio_num_t pin : HELD_FLOATING)
    floating.pin_bit_mask |= BIT64(pin);
  gpio_config(&floating);

  gpio_config_t pulldown{};
  pulldown.mode = GPIO_MODE_INPUT;
  pulldown.pull_down_en = GPIO_PULLDOWN_ENABLE;
  pulldown.pin_bit_mask = BIT64(HELD_PULLDOWN);
  gpio_config(&pulldown);

  gpio_config_t low{};
  low.mode = GPIO_MODE_OUTPUT;
  for (gpio_num_t pin : HELD_LOW) {
    gpio_set_level(pin, 0);
    low.pin_bit_mask |= BIT64(pin);
  }
  gpio_config(&low);
  for (gpio_num_t pin : HELD_LOW)
    gpio_set_level(pin, 0);

  for (gpio_num_t pin : HELD_FLOATING)
    gpio_hold_en(pin);
  gpio_hold_en(HELD_PULLDOWN);
  for (gpio_num_t pin : HELD_LOW)
    gpio_hold_en(pin);

  // try_sleep_() already saw INT high. After the hooks there is no way back, so
  // an input that moved since wakes ext1 at once and the stub latches it.
  uint16_t port;
  this->read_port_(&port);
  if (gpio_get_level(WAKE_PIN) == 0)
    ESP_LOGW(TAG, "INT low at sleep entry, ext1 wakes at once");

  // R9 is the pull-up. The HP and LP pads each carry their own pull bits.
  gpio_pullup_dis(WAKE_PIN);
  gpio_pulldown_dis(WAKE_PIN);
  rtc_gpio_pullup_dis(WAKE_PIN);
  rtc_gpio_pulldown_dis(WAKE_PIN);
  esp_sleep_enable_ext1_wakeup_io(BIT64(WAKE_PIN), ESP_EXT1_WAKEUP_ANY_LOW);
  esp_deep_sleep_start();
}

}  // namespace esphome::idle_sleep
