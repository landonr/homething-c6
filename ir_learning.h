#pragma once

#include "esphome/core/hal.h"
#include "esphome/core/preferences.h"
#include "esphome/core/log.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdint>
#include <functional>
#include <vector>

class IrCodeStore {
 public:
  static constexpr uint8_t FIRST_BUTTON = 3;
  // 3..11 are SW3..SW11. 12..16 are the ANO directions. 17 and 18 are wheel
  // rotation. 19 is SW2 and 20 is SW1. Slots are contiguous because each one
  // keys its own NVS record. SW1 and SW2 sit at the top rather than at 1 and 2
  // because the NVS key is 0x49524330 + (button - FIRST_BUTTON): moving
  // FIRST_BUTTON would shift every existing key by one slot and hand each
  // button its neighbour's code.
  static constexpr uint8_t LAST_BUTTON = 20;
  static constexpr uint8_t VOICE_BUTTON = 20;
  static constexpr size_t SLOT_COUNT = LAST_BUTTON - FIRST_BUTTON + 1;
  static constexpr size_t MAX_PULSES = 512;
  // Flipper .ir names are short words such as Power or Vol_up.
  static constexpr size_t NAME_LEN = 24;

  void setup() {
    size_t loaded_count = 0;
    for (size_t i = 0; i < SLOT_COUNT; i++) {
      prefs_[i] = esphome::global_preferences->make_preference<Record>(0x49524330U + i, true);
      Record loaded{};
      if (prefs_[i].load(&loaded) && valid_(loaded)) {
        records_[i] = loaded;
        loaded_count++;
        ESP_LOGI("ir_learn", "Loaded button %u: %u pulses", static_cast<unsigned>(i + FIRST_BUTTON),
                 static_cast<unsigned>(loaded.count));
      }
    }

    // Names live in their own record, so adding them leaves every stored code
    // readable by the unchanged Record layout.
    name_pref_ = esphome::global_preferences->make_preference<NameBook>(NAME_KEY, true);
    NameBook book{};
    if (name_pref_.load(&book) && book.magic == NAME_MAGIC && book.version == VERSION &&
        book.checksum == checksum_of_(&book, sizeof(book) - sizeof(book.checksum)))
      names_ = book;

    voice_pref_ = esphome::global_preferences->make_preference<uint32_t>(VOICE_KEY, true);
    uint32_t mask = 0;
    if (voice_pref_.load(&mask)) {
      voice_mask_ = mask;
    } else {
      // First boot after this feature. Seed SW1 so the board still has an Assist
      // button before anyone opens receiver mode. A clear writes the mask, so a
      // cleared SW1 stays cleared.
      voice_mask_ = slot_bit_(VOICE_BUTTON);
      voice_pref_.save(&voice_mask_);
    }

    ESP_LOGI("ir_learn", "IR store ready: %u/%u codes, voice mask 0x%05X",
             static_cast<unsigned>(loaded_count), static_cast<unsigned>(SLOT_COUNT),
             static_cast<unsigned>(voice_mask_));
  }

  bool is_voice(uint8_t button) const {
    return button_valid_(button) && (voice_mask_ & slot_bit_(button)) != 0;
  }

  bool has_code(uint8_t button) const {
    return button_valid_(button) && valid_(records_[button - FIRST_BUTTON]);
  }

  uint16_t code_pulses(uint8_t button) const {
    if (!has_code(button))
      return 0;
    return records_[button - FIRST_BUTTON].count;
  }

  // Stored pulses are 10 us ticks, so the frame length needs the scale back.
  uint32_t code_duration_us(uint8_t button) const {
    if (!has_code(button))
      return 0;
    const Record &record = records_[button - FIRST_BUTTON];
    uint32_t total = 0;
    for (size_t i = 0; i < record.count; i++) {
      const int16_t pulse = record.pulses[i];
      total += static_cast<uint32_t>(pulse < 0 ? -pulse : pulse) * 10U;
    }
    return total;
  }

  // load() logs the whole frame, which is too loud for a page view.
  bool code_timings(uint8_t button, std::vector<int32_t> &raw) const {
    raw.clear();
    if (!has_code(button))
      return false;
    const Record &record = records_[button - FIRST_BUTTON];
    raw.reserve(record.count);
    for (size_t i = 0; i < record.count; i++)
      raw.push_back(static_cast<int32_t>(record.pulses[i]) * 10);
    return true;
  }

  // save() canonicalizes a Samsung frame, so the 32 data bits read back out of
  // the record. Ticks are 10 us: a 4.5 ms header is 450, a one space is 169.
  bool code_samsung_data(uint8_t button, uint32_t &data) const {
    if (!has_code(button))
      return false;
    const Record &record = records_[button - FIRST_BUTTON];
    if (record.count != 68)
      return false;
    if (record.pulses[0] < 400 || record.pulses[0] > 500)
      return false;
    if (record.pulses[1] > -400 || record.pulses[1] < -500)
      return false;
    uint32_t value = 0;
    for (size_t bit = 0; bit < 32; bit++) {
      const int16_t space = record.pulses[3 + 2 * bit];
      if (space >= 0)
        return false;
      value = (value << 1) | (-space > 100 ? 1U : 0U);
    }
    data = value;
    return true;
  }

  // Samsung32 carries the address twice and the command with its inverse, both
  // LSB first. A frame that breaks either rule is raw to every decoder.
  bool code_samsung_fields(uint8_t button, uint8_t &address, uint8_t &command) const {
    uint32_t data = 0;
    if (!code_samsung_data(button, data))
      return false;
    const uint8_t first = reverse_bits_((data >> 24) & 0xFFU);
    const uint8_t second = reverse_bits_((data >> 16) & 0xFFU);
    const uint8_t value = reverse_bits_((data >> 8) & 0xFFU);
    const uint8_t inverse = reverse_bits_(data & 0xFFU);
    if (first != second || value != static_cast<uint8_t>(~inverse))
      return false;
    address = first;
    command = value;
    return true;
  }

  // The 68 pulse frame that code_samsung_fields() reads back.
  static void samsung_timings(uint8_t address, uint8_t command, std::vector<int32_t> &raw) {
    const uint32_t data = (static_cast<uint32_t>(reverse_bits_(address)) << 24) |
                          (static_cast<uint32_t>(reverse_bits_(address)) << 16) |
                          (static_cast<uint32_t>(reverse_bits_(command)) << 8) |
                          static_cast<uint32_t>(reverse_bits_(static_cast<uint8_t>(~command)));
    samsung_frame_(data, raw);
  }

  const char *name(uint8_t button) const {
    if (!button_valid_(button))
      return "";
    return names_.names[button - FIRST_BUTTON];
  }

  // Only printable ASCII is kept, so a name needs no JSON escape on the page.
  bool set_name(uint8_t button, const char *text) {
    if (!button_valid_(button))
      return false;
    char clean[NAME_LEN] = "";
    size_t used = 0;
    for (const char *cursor = text; *cursor != '\0' && used + 1 < NAME_LEN; cursor++) {
      const char value = *cursor;
      if (value < 0x20 || value > 0x7E || value == '"' || value == '\\')
        continue;
      clean[used++] = value;
    }
    while (used > 0 && clean[used - 1] == ' ')
      clean[--used] = '\0';
    return write_name_(button, clean);
  }

  // Counts successful captures only. A re-record of the same remote button
  // often keeps the pulse count, so a watcher cannot tell from the slot row
  // alone that a new code landed.
  uint32_t saves() const { return saves_; }

  // The voice assignment replaces whatever the button held, so drop the code.
  bool set_voice(uint8_t button) {
    if (!button_valid_(button))
      return false;
    const bool erased = erase_code_(button) && write_name_(button, "");
    const uint32_t next_mask = voice_mask_ | slot_bit_(button);
    const bool written = voice_pref_.save(&next_mask);
    if (written)
      voice_mask_ = next_mask;
    if (assignment_clear_callback_)
      assignment_clear_callback_(button);
    ESP_LOGI("ir_learn", "Button %u assigned to the voice assistant%s", button,
             erased && written ? "" : " (flash write failed)");
    return erased && written;
  }

  bool clear(uint8_t button) {
    if (!button_valid_(button))
      return false;
    const bool erased = erase_code_(button) && write_name_(button, "");
    const uint32_t next_mask = voice_mask_ & ~slot_bit_(button);
    const bool written = voice_pref_.save(&next_mask);
    if (written)
      voice_mask_ = next_mask;
    if (assignment_clear_callback_)
      assignment_clear_callback_(button);
    ESP_LOGI("ir_learn", "Button %u cleared%s", button,
             erased && written ? "" : " (flash write failed)");
    return erased && written;
  }

  bool save(uint8_t button, const std::vector<int32_t> &raw) {
    if (!button_valid_(button)) {
      ESP_LOGW("ir_learn", "Reject capture: invalid target button %u", button);
      return false;
    }
    if (raw.size() < 4 || raw.size() > MAX_PULSES) {
      ESP_LOGW("ir_learn", "Reject button %u: pulse count %u outside 4..%u", button,
               static_cast<unsigned>(raw.size()), static_cast<unsigned>(MAX_PULSES));
      return false;
    }

    std::vector<int32_t> normalized;
    const std::vector<int32_t> *capture = &raw;
    uint32_t samsung_data = 0;
    if (normalize_samsung_(raw, normalized, samsung_data)) {
      capture = &normalized;
      ESP_LOGI("ir_learn", "Canonicalized Samsung button %u: data=0x%08X", button,
               static_cast<unsigned>(samsung_data));
    }

    Record next{};
    next.magic = MAGIC;
    next.version = VERSION;
    next.count = capture->size();
    uint32_t total_us = 0;
    for (size_t i = 0; i < capture->size(); i++) {
      const int32_t pulse = (*capture)[i];
      const int64_t duration = pulse < 0 ? -static_cast<int64_t>(pulse) : pulse;
      if (duration < 80 || duration > 327670) {
        ESP_LOGW("ir_learn", "Reject button %u: pulse %u duration %lld us", button,
                 static_cast<unsigned>(i), static_cast<long long>(duration));
        return false;
      }
      total_us += duration;
      if (total_us > 250000) {
        ESP_LOGW("ir_learn", "Reject button %u: frame duration %u us", button,
                 static_cast<unsigned>(total_us));
        return false;
      }
      int32_t ticks = static_cast<int32_t>((duration + 5) / 10);
      if (ticks > 32767)
        return false;
      next.pulses[i] = pulse < 0 ? -ticks : ticks;
    }
    next.checksum = checksum_(next);

    const size_t slot = button - FIRST_BUTTON;
    if (!prefs_[slot].save(&next)) {
      ESP_LOGE("ir_learn", "Flash write failed for button %u", button);
      return false;
    }
    if ((voice_mask_ & slot_bit_(button)) != 0) {
      const uint32_t next_mask = voice_mask_ & ~slot_bit_(button);
      if (!voice_pref_.save(&next_mask)) {
        ESP_LOGE("ir_learn", "Flash write failed while removing voice from button %u", button);
        return false;
      }
      voice_mask_ = next_mask;
    }
    records_[slot] = next;
    saves_++;
    // A capture replaces the code, so the name of the old code no longer fits.
    // A paste names the slot again after this call.
    if (names_.names[slot][0] != '\0')
      write_name_(button, "");
    if (assignment_clear_callback_)
      assignment_clear_callback_(button);
    ESP_LOGI("ir_learn", "Saved button %u: %u pulses, %u us", button,
             static_cast<unsigned>(next.count), static_cast<unsigned>(total_us));
    return true;
  }

  bool load(uint8_t button, std::vector<int32_t> &raw) const {
    raw.clear();
    if (!button_valid_(button))
      return false;
    const Record &record = records_[button - FIRST_BUTTON];
    if (!valid_(record)) {
      ESP_LOGW("ir_learn", "Button %u has no stored IR code", button);
      return false;
    }
    raw.reserve(record.count);
    for (size_t i = 0; i < record.count; i++)
      raw.push_back(static_cast<int32_t>(record.pulses[i]) * 10);
    ESP_LOGI("ir_learn", "Playback button %u: %u pulses", button, static_cast<unsigned>(record.count));
    log_output_(button, raw);
    return true;
  }

  void set_assignment_clear_callback(std::function<void(uint8_t)> callback) {
    assignment_clear_callback_ = std::move(callback);
  }

  bool clear_for_zigbee(uint8_t button) {
    if (!button_valid_(button))
      return false;
    erase_code_(button);
    // The name belongs to the erased code. Leaving it orphans a label on a slot
    // that the Zigbee record later stops describing.
    write_name_(button, "");
    voice_mask_ &= ~slot_bit_(button);
    return voice_pref_.save(&voice_mask_);
  }

  void log_received(const std::vector<int32_t> &raw) const {
    if (raw.empty()) {
      ESP_LOGW("ir_rx", "Received empty raw frame");
      return;
    }

    uint32_t total_us = 0;
    uint32_t min_us = UINT32_MAX;
    uint32_t max_us = 0;
    uint32_t hash = 2166136261U;
    size_t marks = 0;
    size_t spaces = 0;
    for (const int32_t pulse : raw) {
      const uint32_t duration = pulse < 0 ? static_cast<uint32_t>(-static_cast<int64_t>(pulse))
                                          : static_cast<uint32_t>(pulse);
      total_us += duration;
      min_us = std::min(min_us, duration);
      max_us = std::max(max_us, duration);
      marks += pulse > 0;
      spaces += pulse < 0;
      const uint32_t encoded = static_cast<uint32_t>(pulse);
      for (size_t byte = 0; byte < sizeof(encoded); byte++) {
        hash ^= (encoded >> (byte * 8)) & 0xFFU;
        hash *= 16777619U;
      }
    }

    ESP_LOGI("ir_rx",
             "Raw frame: pulses=%u, marks=%u, spaces=%u, total=%u us, min=%u us, max=%u us, hash=0x%08X",
             static_cast<unsigned>(raw.size()), static_cast<unsigned>(marks), static_cast<unsigned>(spaces),
             static_cast<unsigned>(total_us), static_cast<unsigned>(min_us), static_cast<unsigned>(max_us),
             static_cast<unsigned>(hash));
    log_pulses_("ir_rx", "Raw frame", raw);
  }

 private:
  static constexpr uint32_t MAGIC = 0x49524336U;
  static constexpr uint32_t VOICE_KEY = 0x49524356U;
  static constexpr uint32_t NAME_KEY = 0x4952434EU;
  static constexpr uint32_t NAME_MAGIC = 0x4952434FU;
  static constexpr uint16_t VERSION = 1;

  struct Record {
    uint32_t magic;
    uint16_t version;
    uint16_t count;
    int16_t pulses[MAX_PULSES];
    uint32_t checksum;
  };

  struct NameBook {
    uint32_t magic;
    uint16_t version;
    uint16_t reserved;
    char names[SLOT_COUNT][NAME_LEN];
    uint32_t checksum;
  };

  static bool button_valid_(uint8_t button) { return button >= FIRST_BUTTON && button <= LAST_BUTTON; }

  static uint32_t slot_bit_(uint8_t button) { return 1UL << (button - FIRST_BUTTON); }

  // A zeroed record fails valid_(), so the slot reads as unassigned after a reboot.
  bool erase_code_(uint8_t button) {
    const size_t slot = button - FIRST_BUTTON;
    Record empty{};
    if (!prefs_[slot].save(&empty))
      return false;
    records_[slot] = empty;
    return true;
  }

  static uint8_t reverse_bits_(uint8_t value) {
    uint8_t out = 0;
    for (size_t bit = 0; bit < 8; bit++)
      out = static_cast<uint8_t>((out << 1) | ((value >> bit) & 1U));
    return out;
  }

  bool write_name_(uint8_t button, const char *clean) {
    NameBook book = names_;
    book.magic = NAME_MAGIC;
    book.version = VERSION;
    book.reserved = 0;
    char *row = book.names[button - FIRST_BUTTON];
    // snprintf leaves the tail bytes alone, and stale bytes would move the checksum.
    for (size_t i = 0; i < NAME_LEN; i++)
      row[i] = '\0';
    std::snprintf(row, NAME_LEN, "%s", clean);
    book.checksum = checksum_of_(&book, sizeof(book) - sizeof(book.checksum));
    if (!name_pref_.save(&book)) {
      ESP_LOGE("ir_learn", "Flash write failed for the name of button %u", button);
      return false;
    }
    names_ = book;
    return true;
  }

  static bool in_range_(int32_t value, int32_t low, int32_t high) {
    const int32_t duration = value < 0 ? -value : value;
    return duration >= low && duration <= high;
  }

  static bool normalize_samsung_(const std::vector<int32_t> &raw, std::vector<int32_t> &normalized,
                                 uint32_t &data) {
    if (raw.size() < 67 || raw[0] <= 0 || raw[1] >= 0 || !in_range_(raw[0], 3500, 5500) ||
        !in_range_(raw[1], 3500, 5500))
      return false;

    data = 0;
    for (size_t bit = 0; bit < 32; bit++) {
      const int32_t mark = raw[2 + bit * 2];
      const int32_t space = raw[3 + bit * 2];
      if (mark <= 0 || space >= 0 || !in_range_(mark, 350, 800) || !in_range_(space, 350, 2100))
        return false;
      data = (data << 1) | (in_range_(space, 1100, 2100) ? 1U : 0U);
    }
    if (raw[66] <= 0 || !in_range_(raw[66], 350, 800))
      return false;

    samsung_frame_(data, normalized);
    return true;
  }

  static void samsung_frame_(uint32_t data, std::vector<int32_t> &frame) {
    frame.clear();
    frame.reserve(68);
    frame.push_back(4500);
    frame.push_back(-4500);
    for (int bit = 31; bit >= 0; bit--) {
      frame.push_back(560);
      frame.push_back((data & (1UL << bit)) != 0 ? -1690 : -560);
    }
    frame.push_back(560);
    frame.push_back(-560);
  }

  static void log_output_(uint8_t button, const std::vector<int32_t> &raw) {
    uint32_t total_us = 0;
    for (const int32_t pulse : raw)
      total_us += pulse < 0 ? -pulse : pulse;
    ESP_LOGI("ir_tx", "Output button %u: carrier=38000 Hz, duty=50%%, pulses=%u, total=%u us", button,
             static_cast<unsigned>(raw.size()), static_cast<unsigned>(total_us));

    char label[32];
    std::snprintf(label, sizeof(label), "Output button %u", button);
    log_pulses_("ir_tx", label, raw);
  }

  static void log_pulses_(const char *tag, const char *label, const std::vector<int32_t> &raw) {
    constexpr size_t PULSES_PER_LINE = 12;
    for (size_t start = 0; start < raw.size(); start += PULSES_PER_LINE) {
      const size_t end = std::min(start + PULSES_PER_LINE, raw.size());
      char line[192];
      size_t used = 0;
      for (size_t i = start; i < end; i++) {
        const int written = std::snprintf(line + used, sizeof(line) - used, "%s%ld", i == start ? "" : ",",
                                          static_cast<long>(raw[i]));
        if (written < 0 || static_cast<size_t>(written) >= sizeof(line) - used)
          break;
        used += static_cast<size_t>(written);
      }
      ESP_LOGI(tag, "%s [%u..%u]: %s", label, static_cast<unsigned>(start),
               static_cast<unsigned>(end - 1), line);
    }
  }

  static uint32_t checksum_of_(const void *data, size_t length) {
    uint32_t hash = 2166136261U;
    const auto *bytes = static_cast<const uint8_t *>(data);
    for (size_t i = 0; i < length; i++) {
      hash ^= bytes[i];
      hash *= 16777619U;
    }
    return hash;
  }

  static uint32_t checksum_(const Record &record) {
    return checksum_of_(&record, sizeof(Record) - sizeof(record.checksum));
  }

  static bool valid_(const Record &record) {
    return record.magic == MAGIC && record.version == VERSION && record.count >= 4 &&
           record.count <= MAX_PULSES && record.checksum == checksum_(record);
  }

  std::array<Record, SLOT_COUNT> records_{};
  std::array<esphome::ESPPreferenceObject, SLOT_COUNT> prefs_{};
  NameBook names_{};
  esphome::ESPPreferenceObject name_pref_{};
  esphome::ESPPreferenceObject voice_pref_{};
  uint32_t voice_mask_ = 0;
  uint32_t saves_ = 0;
  std::function<void(uint8_t)> assignment_clear_callback_{};
};

inline IrCodeStore ir_code_store;

// Receiver-mode state machine and per-button assignment cycle. This lives here
// rather than in YAML globals so that eighteen inputs share one call each.
class IrUi {
 public:
  enum : uint8_t {
    OFF = 0,
    READY = 1,
    READING = 2,
    SAVED = 3,
    ERROR = 4,
    VOICE = 5,
    CLEARED = 6,
  };

  // FULL cycles IR, voice, clear. NO_VOICE omits voice. ARM_ONLY always
  // arms IR capture for wheel rotation, which has no release edge.
  enum class Tap : uint8_t { FULL, NO_VOICE, ARM_ONLY };

  uint8_t state = OFF;
  uint8_t target = 0;
  uint8_t stage = 0;
  bool sw2_consumed = false;

  void open() {
    state = READY;
    target = 0;
    stage = 0;
    web_owner_ = false;
    web_result_ = OFF;
    web_result_slot_ = 0;
    mark_();
    ESP_LOGI("ir_learn", "Receiver mode READY; hold SW2 or wait 5 s to leave");
  }

  void close() {
    state = OFF;
    target = 0;
    stage = 0;
    web_owner_ = false;
    closed_ = true;
    mark_();
    ESP_LOGI("ir_learn", "Receiver mode OFF; passive IR logging remains active");
  }

  bool web_owner() const { return web_owner_; }
  uint8_t web_result() const { return web_result_; }
  uint8_t web_result_slot() const { return web_result_slot_; }

  // Opens receiver mode from the web page and arms the slot in one step. The
  // rail and LED work needs YAML ids, so it is flagged for the 250 ms interval.
  void open_from_web(uint8_t button) {
    open();
    web_owner_ = true;
    open_requested_ = true;
    tap(button, Tap::ARM_ONLY);
  }

  bool take_open_request() {
    const bool pending = open_requested_;
    open_requested_ = false;
    return pending;
  }

  void tap(uint8_t button, Tap mode) {
    if (state == OFF) {
      play_(button);
      if (mode == Tap::ARM_ONLY && hid_play_callback_)
        hid_play_callback_(button, false);
      return;
    }
    if (button != target || mode == Tap::ARM_ONLY || stage == 0) {
      arm_(button);
      return;
    }
    if (stage == 1 && mode == Tap::FULL) {
      ir_code_store.set_voice(button);
      stage = 2;
      state = VOICE;
      mark_();
      return;
    }
    ir_code_store.clear(button);
    target = 0;
    stage = 0;
    state = CLEARED;
    mark_();
  }

  void captured(const std::vector<int32_t> &raw) {
    if (state != READING)
      return;
    ESP_LOGI("ir_learn", "Capture candidate for button %u: %u pulses", target,
             static_cast<unsigned>(raw.size()));
    const bool saved = ir_code_store.save(target, raw);
    state = saved ? SAVED : ERROR;
    if (web_owner_) {
      web_result_ = state;
      web_result_slot_ = target;
    }
    mark_();
  }

  // True when the mode closed since the last tick, so the caller restores idle
  // status. A close from the web page reports here too, not only a timeout.
  bool tick() {
    if (state == OFF) {
      const bool restore = closed_;
      closed_ = false;
      return restore;
    }
    const uint32_t elapsed = esphome::millis() - since_;
    if (state == READY) {
      if (elapsed < 5000)
        return false;
      ESP_LOGI("ir_learn", "Receiver mode OFF after 5 s idle");
      close();
      closed_ = false;
      return true;
    }
    const uint32_t hold = (state == READING || state == VOICE) ? 10000 : 1000;
    if (elapsed >= hold) {
      // Keep target and stage so the next tap on the same button still advances.
      state = READY;
      mark_();
    }
    return false;
  }

  bool take_transmit() {
    const bool pending = pending_transmit_;
    pending_transmit_ = false;
    return pending;
  }

  bool take_voice_start() {
    const bool pending = pending_voice_;
    pending_voice_ = false;
    return pending;
  }

  // Stop Assist only when the released input started it.
  bool release(uint8_t button) {
    if (hid_play_callback_)
      hid_play_callback_(button, false);
    if (voice_active_ != button)
      return false;
    voice_active_ = 0;
    return true;
  }

  const std::vector<int32_t> &code() const { return code_; }

  void set_zigbee_play_callback(std::function<bool(uint8_t)> play) {
    zigbee_play_callback_ = std::move(play);
  }

  void set_hid_play_callback(std::function<bool(uint8_t, bool)> play) {
    hid_play_callback_ = std::move(play);
  }

 private:
  void mark_() { since_ = esphome::millis(); }

  void arm_(uint8_t button) {
    target = button;
    stage = 1;
    state = READING;
    mark_();
    ESP_LOGI("ir_learn", "Button %u armed for capture", button);
  }

  void play_(uint8_t button) {
    pending_transmit_ = false;
    pending_voice_ = false;
    if (ir_code_store.is_voice(button)) {
      pending_voice_ = true;
      voice_active_ = button;
      return;
    }
    if (hid_play_callback_ && hid_play_callback_(button, true))
      return;
    if (zigbee_play_callback_ && zigbee_play_callback_(button))
      return;
    pending_transmit_ = ir_code_store.load(button, code_);
  }

  std::vector<int32_t> code_;
  uint32_t since_ = 0;
  bool pending_transmit_ = false;
  bool pending_voice_ = false;
  bool web_owner_ = false;
  uint8_t web_result_ = OFF;
  uint8_t web_result_slot_ = 0;
  bool open_requested_ = false;
  bool closed_ = false;
  uint8_t voice_active_ = 0;
  std::function<bool(uint8_t)> zigbee_play_callback_{};
  std::function<bool(uint8_t, bool)> hid_play_callback_{};
};

inline IrUi ir_ui;
