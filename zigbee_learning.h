#pragma once

#include "ir_learning.h"

#include "esphome/core/helpers.h"
#include "esphome/core/log.h"
#include "esphome/core/preferences.h"

#include "esp_zigbee.h"

#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>

// Stores one Zigbee group per assignable input and toggles it from the radio.
//
// The remote holds no MQTT client. The /buttons page reads the Zigbee2MQTT
// inventory over the frontend websocket in the browser, creates or picks the
// group there, and posts the finished group id here. Playback is a groupcast,
// and group membership lives in the light's own group table, so a button keeps
// working with Zigbee2MQTT and Home Assistant both down.
class ZigbeeAssignmentManager {
 public:
  static constexpr uint8_t FIRST_SLOT = 3;
  static constexpr uint8_t LAST_SLOT = 20;
  static constexpr size_t SLOT_COUNT = LAST_SLOT - FIRST_SLOT + 1;
  static constexpr uint8_t CLIENT_ENDPOINT = 1;
  // 0xFFF8 and above are the reserved broadcast addresses.
  static constexpr uint16_t MAX_GROUP_ID = 0xFFF7;

  struct Assignment {
    bool assigned{false};
    uint16_t group_id{0};
    std::string name;
  };

  void setup() {
    preference_ = esphome::global_preferences->make_preference<Record>(PREFERENCE_KEY, true);

    Record loaded{};
    if (preference_.load(&loaded) && valid_(loaded)) {
      record_ = loaded;
    } else {
      reset_record_(record_);
      if (!preference_.save(&record_))
        ESP_LOGE("zigbee_learn", "Failed to invalidate old Zigbee assignments");
    }

    ir_code_store.set_assignment_clear_callback([this](uint8_t slot) { this->clear(slot); });
    ir_ui.set_zigbee_play_callback([this](uint8_t slot) { return this->toggle(slot); });
    ESP_LOGI("zigbee_learn", "Loaded Zigbee assignment mask 0x%05X",
             static_cast<unsigned>(record_.mask));
  }

  // Runs on the main loop from a deferred web action, so the flash write cannot
  // block the httpd task. A group target needs no network round trip, so the
  // result is known before this returns.
  bool assign_from_web(uint8_t slot, uint16_t group_id, const std::string &name) {
    if (!slot_valid_(slot) || group_id == 0 || group_id > MAX_GROUP_ID)
      return false;
    if (name.size() >= TARGET_SIZE)
      return false;
    if (!ir_code_store.clear_for_zigbee(slot)) {
      ESP_LOGE("zigbee_learn", "Failed to clear the old action on button %u", slot);
      return false;
    }

    Record next = record_;
    const size_t index = slot - FIRST_SLOT;
    next.mask |= 1UL << index;
    Entry &entry = next.entries[index];
    std::memset(&entry, 0, sizeof(entry));
    entry.group_id = group_id;
    std::strncpy(entry.friendly_name, name.c_str(), TARGET_SIZE - 1);
    next.checksum = checksum_(next);

    {
      const std::lock_guard<std::mutex> lock(cache_mutex_);
      record_ = next;
    }
    if (!preference_.save(&record_)) {
      ESP_LOGE("zigbee_learn", "Failed to save Zigbee button %u", slot);
      return false;
    }
    ESP_LOGI("zigbee_learn", "Button %u toggles group 0x%04X (%s)", slot,
             static_cast<unsigned>(group_id), entry.friendly_name);
    return true;
  }

  // The HTTP task reads this while the main loop can write it.
  Assignment assignment(uint8_t slot) const {
    Assignment result;
    const std::lock_guard<std::mutex> lock(cache_mutex_);
    if (!has_assignment_(slot))
      return result;
    const Entry &entry = record_.entries[slot - FIRST_SLOT];
    result.assigned = true;
    result.group_id = entry.group_id;
    result.name = entry.friendly_name;
    return result;
  }

  bool toggle(uint8_t slot) const {
    if (!has_assignment_(slot))
      return false;
    const Entry &entry = entry_(slot);
    ezb_zcl_on_off_cmd_t request{};
    request.cmd_ctrl.dst_addr.addr_mode = EZB_ADDR_MODE_GROUP;
    request.cmd_ctrl.dst_addr.u.group_addr.group = entry.group_id;
    request.cmd_ctrl.dst_addr.u.group_addr.bcast = 0xFFFD;
    request.cmd_ctrl.src_ep = CLIENT_ENDPOINT;

    esp_zigbee_lock_acquire(portMAX_DELAY);
    const ezb_err_t result = ezb_zcl_on_off_toggle_cmd_req(&request);
    esp_zigbee_lock_release();
    if (result != EZB_ERR_NONE) {
      ESP_LOGE("zigbee_tx", "Toggle failed for button %u, group 0x%04X: %d", slot, entry.group_id, result);
      return true;
    }
    ESP_LOGI("zigbee_tx", "Toggle button %u, group 0x%04X", slot, entry.group_id);
    return true;
  }

  // Membership stays in Zigbee2MQTT, so clearing a button only drops the local
  // record. A group the page created for one button outlives it.
  void clear(uint8_t slot) {
    if (!has_assignment_(slot))
      return;
    Record next = record_;
    const size_t index = slot - FIRST_SLOT;
    next.mask &= ~(1UL << index);
    std::memset(&next.entries[index], 0, sizeof(next.entries[index]));
    next.checksum = checksum_(next);

    {
      const std::lock_guard<std::mutex> lock(cache_mutex_);
      record_ = next;
    }
    if (!preference_.save(&record_))
      ESP_LOGE("zigbee_learn", "Failed to save cleared Zigbee button %u", slot);
    ESP_LOGI("zigbee_learn", "Cleared Zigbee button %u", slot);
  }

 private:
  static constexpr uint32_t MAGIC = 0x5A424731U;
  // Version 3 dropped the target kind, because every target is now a group.
  static constexpr uint16_t VERSION = 3;
  static constexpr uint32_t PREFERENCE_KEY = 0x5A424731U;
  static constexpr size_t TARGET_SIZE = 65;

  struct Entry {
    uint16_t group_id;
    uint16_t reserved;
    char friendly_name[TARGET_SIZE];
  };

  struct Record {
    uint32_t magic;
    uint16_t version;
    uint16_t reserved;
    uint32_t mask;
    Entry entries[SLOT_COUNT];
    uint32_t checksum;
  };

  static bool slot_valid_(uint8_t slot) { return slot >= FIRST_SLOT && slot <= LAST_SLOT; }

  bool has_assignment_(uint8_t slot) const {
    return slot_valid_(slot) && (record_.mask & (1UL << (slot - FIRST_SLOT))) != 0;
  }

  const Entry &entry_(uint8_t slot) const { return record_.entries[slot - FIRST_SLOT]; }

  static uint32_t checksum_(const Record &record) {
    uint32_t hash = 2166136261U;
    const auto *bytes = reinterpret_cast<const uint8_t *>(&record);
    for (size_t i = 0; i < sizeof(record) - sizeof(record.checksum); i++) {
      hash ^= bytes[i];
      hash *= 16777619U;
    }
    return hash;
  }

  static bool valid_(const Record &record) {
    if (record.magic != MAGIC || record.version != VERSION ||
        (record.mask & ~((1UL << SLOT_COUNT) - 1)) != 0 || record.checksum != checksum_(record))
      return false;
    for (size_t index = 0; index < SLOT_COUNT; index++) {
      if ((record.mask & (1UL << index)) == 0)
        continue;
      const Entry &entry = record.entries[index];
      if (entry.group_id == 0 || entry.group_id > MAX_GROUP_ID ||
          std::memchr(entry.friendly_name, '\0', TARGET_SIZE) == nullptr)
        return false;
    }
    return true;
  }

  static void reset_record_(Record &record) {
    std::memset(&record, 0, sizeof(record));
    record.magic = MAGIC;
    record.version = VERSION;
    record.checksum = checksum_(record);
  }

  mutable std::mutex cache_mutex_;
  esphome::ESPPreferenceObject preference_;
  Record record_{};
};

inline ZigbeeAssignmentManager zigbee_assignments;
