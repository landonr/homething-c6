#pragma once

#include "esphome/core/preferences.h"
#include "esphome/core/log.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdint>
#include <vector>

class IrCodeStore {
 public:
  static constexpr uint8_t FIRST_BUTTON = 3;
  static constexpr uint8_t LAST_BUTTON = 11;
  static constexpr size_t SLOT_COUNT = LAST_BUTTON - FIRST_BUTTON + 1;
  static constexpr size_t MAX_PULSES = 512;

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
    ESP_LOGI("ir_learn", "IR store ready: %u/%u buttons assigned", static_cast<unsigned>(loaded_count),
             static_cast<unsigned>(SLOT_COUNT));
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
    records_[slot] = next;
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
  static constexpr uint16_t VERSION = 1;

  struct Record {
    uint32_t magic;
    uint16_t version;
    uint16_t count;
    int16_t pulses[MAX_PULSES];
    uint32_t checksum;
  };

  static bool button_valid_(uint8_t button) { return button >= FIRST_BUTTON && button <= LAST_BUTTON; }

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

    normalized.clear();
    normalized.reserve(68);
    normalized.push_back(4500);
    normalized.push_back(-4500);
    for (int bit = 31; bit >= 0; bit--) {
      normalized.push_back(560);
      normalized.push_back((data & (1UL << bit)) != 0 ? -1690 : -560);
    }
    normalized.push_back(560);
    normalized.push_back(-560);
    return true;
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

  static uint32_t checksum_(const Record &record) {
    uint32_t hash = 2166136261U;
    const auto *bytes = reinterpret_cast<const uint8_t *>(&record);
    const size_t length = sizeof(Record) - sizeof(record.checksum);
    for (size_t i = 0; i < length; i++) {
      hash ^= bytes[i];
      hash *= 16777619U;
    }
    return hash;
  }

  static bool valid_(const Record &record) {
    return record.magic == MAGIC && record.version == VERSION && record.count >= 4 &&
           record.count <= MAX_PULSES && record.checksum == checksum_(record);
  }

  std::array<Record, SLOT_COUNT> records_{};
  std::array<esphome::ESPPreferenceObject, SLOT_COUNT> prefs_{};
};

inline IrCodeStore ir_code_store;
