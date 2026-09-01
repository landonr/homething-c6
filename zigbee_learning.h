#pragma once

#include "ir_learning.h"

#include "esphome/core/helpers.h"
#include "esphome/core/log.h"
#include "esphome/core/preferences.h"

#include "esp_zigbee.h"

#include <atomic>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <string>

// Stores one Zigbee target per assignable input and toggles it from the radio.
//
// A target is a group or one device. The remote holds no MQTT client. The
// /buttons page reads the Zigbee2MQTT inventory over the frontend websocket in
// the browser and posts only the resolved address here, so a button keeps
// working with Zigbee2MQTT and Home Assistant both down.
//
// A group toggle is an unacknowledged groupcast, and group membership lives in
// the group table of the light. A device toggle is a unicast to the 16-bit
// network address behind the stored IEEE address. That address is a lease the
// device gives up when it rejoins, so it never reaches flash, and the APS
// confirm drives one NWK_addr_req and one resend when it goes stale.
class ZigbeeAssignmentManager {
 public:
  static constexpr uint8_t FIRST_SLOT = 3;
  static constexpr uint8_t LAST_SLOT = 20;
  static constexpr size_t SLOT_COUNT = LAST_SLOT - FIRST_SLOT + 1;
  static constexpr uint8_t CLIENT_ENDPOINT = 1;
  // 0xFFF8 and above are the reserved broadcast addresses.
  static constexpr uint16_t MAX_GROUP_ID = 0xFFF7;
  static constexpr uint8_t MIN_ENDPOINT = 1;
  static constexpr uint8_t MAX_ENDPOINT = 240;

  enum Kind : uint8_t { KIND_GROUP = 0, KIND_DEVICE = 1 };

  struct Assignment {
    bool assigned{false};
    Kind kind{KIND_GROUP};
    uint16_t group_id{0};
    uint8_t endpoint{0};
    uint8_t ieee[8]{};
    std::string name;
  };

  void setup() {
    instance_ = this;
    for (size_t index = 0; index < SLOT_COUNT; index++) {
      nwk_cache_[index].store(EZB_NWK_ADDR_UNKNOWN, std::memory_order_relaxed);
      last_resolve_ms_[index] = 0;
    }
    preference_ = esphome::global_preferences->make_preference<Record>(PREFERENCE_KEY, true);

    Record loaded{};
    if (preference_.load(&loaded) && valid_(loaded)) {
      record_ = loaded;
    } else if (load_version_3_(record_)) {
      if (preference_.save(&record_)) {
        ESP_LOGI("zigbee_learn", "Migrated the Zigbee assignments from record version 3");
      } else {
        ESP_LOGE("zigbee_learn", "Failed to save the migrated Zigbee assignments");
      }
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

    Entry entry;
    std::memset(&entry, 0, sizeof(entry));
    entry.kind = KIND_GROUP;
    entry.group_id = group_id;
    std::strncpy(entry.friendly_name, name.c_str(), TARGET_SIZE - 1);
    if (!store_(slot, entry))
      return false;

    nwk_cache_[slot - FIRST_SLOT].store(EZB_NWK_ADDR_UNKNOWN, std::memory_order_relaxed);
    ESP_LOGI("zigbee_learn", "Button %u toggles group 0x%04X (%s)", slot,
             static_cast<unsigned>(group_id), entry.friendly_name);
    return true;
  }

  // The IEEE address arrives as the little endian bytes of the EUI-64, which is
  // the order the radio wants, so it goes to flash without a swap.
  bool assign_device_from_web(uint8_t slot, const uint8_t (&ieee)[8], uint8_t endpoint,
                              const std::string &name) {
    if (!slot_valid_(slot) || endpoint < MIN_ENDPOINT || endpoint > MAX_ENDPOINT)
      return false;
    if (!ieee_valid_(ieee) || name.size() >= TARGET_SIZE)
      return false;

    Entry entry;
    std::memset(&entry, 0, sizeof(entry));
    entry.kind = KIND_DEVICE;
    entry.endpoint = endpoint;
    std::memcpy(entry.ieee, ieee, sizeof(entry.ieee));
    std::strncpy(entry.friendly_name, name.c_str(), TARGET_SIZE - 1);
    if (!store_(slot, entry))
      return false;

    const size_t index = slot - FIRST_SLOT;
    nwk_cache_[index].store(EZB_NWK_ADDR_UNKNOWN, std::memory_order_relaxed);
    last_resolve_ms_[index] = 0;
    warm_mask_ |= 1UL << index;
    ESP_LOGI("zigbee_learn", "Button %u toggles device %s endpoint %u", slot, entry.friendly_name,
             static_cast<unsigned>(endpoint));
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
    result.kind = static_cast<Kind>(entry.kind);
    result.group_id = entry.group_id;
    result.endpoint = entry.endpoint;
    std::memcpy(result.ieee, entry.ieee, sizeof(result.ieee));
    result.name = entry.friendly_name;
    return result;
  }

  bool toggle(uint8_t slot) {
    if (!has_assignment_(slot))
      return false;
    const Entry &entry = entry_(slot);
    if (entry.kind == KIND_DEVICE)
      toggle_device_(slot, entry);
    else
      toggle_group_(slot, entry);
    return true;
  }

  // Runs on the main loop. Every radio request that a callback asks for starts
  // here, so a Zigbee task callback never sends and never touches flash.
  void tick() {
    const uint32_t now = esphome::millis();
    if (resolve_in_flight_.load(std::memory_order_acquire)) {
      if (now - resolve_started_ms_ < RESOLVE_TIMEOUT_MS)
        return;
      // A later answer belongs to a request this timeout already abandoned.
      resolve_seq_.fetch_add(1, std::memory_order_acq_rel);
      resolve_in_flight_.store(false, std::memory_order_release);
      pending_state_.store(PENDING_NONE, std::memory_order_relaxed);
      ESP_LOGE("zigbee_tx", "No answer to the network address request for button %u",
               static_cast<unsigned>(resolve_slot_));
      return;
    }

    const uint8_t state = pending_state_.exchange(PENDING_NONE, std::memory_order_acq_rel);
    if (state == PENDING_NONE) {
      warm_step_(now);
      return;
    }

    const uint8_t slot = pending_slot_.load(std::memory_order_relaxed);
    if (!has_assignment_(slot))
      return;
    const Entry &entry = entry_(slot);
    if (entry.kind != KIND_DEVICE)
      return;

    if (state == PENDING_RESEND) {
      // The one resend a press gets, so a second failure stops here.
      retry_armed_.store(false, std::memory_order_relaxed);
      send_device_toggle_(slot, entry, nwk_cache_[slot - FIRST_SLOT].load(std::memory_order_relaxed));
      return;
    }
    start_resolve_(slot, entry, true, now);
  }

  // The address map is cold after a join, so this fills what it can for free and
  // asks the mesh for the rest. Each slot is warmed at most once for each join,
  // which bounds the broadcasts a boot can cause.
  void on_network_up() {
    warm_mask_ = 0;
    for (size_t index = 0; index < SLOT_COUNT; index++) {
      if ((record_.mask & (1UL << index)) == 0)
        continue;
      if (record_.entries[index].kind == KIND_DEVICE)
        warm_mask_ |= 1UL << index;
    }
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
    nwk_cache_[index].store(EZB_NWK_ADDR_UNKNOWN, std::memory_order_relaxed);
    warm_mask_ &= ~(1UL << index);
    if (!preference_.save(&record_))
      ESP_LOGE("zigbee_learn", "Failed to save cleared Zigbee button %u", slot);
    ESP_LOGI("zigbee_learn", "Cleared Zigbee button %u", slot);
  }

 private:
  static constexpr uint32_t MAGIC = 0x5A424731U;
  // Version 4 returned the target kind, because a direct device target needs an
  // IEEE address and an endpoint that a group id cannot carry.
  static constexpr uint16_t VERSION = 4;
  static constexpr uint16_t VERSION_V3 = 3;
  static constexpr uint32_t PREFERENCE_KEY = 0x5A424731U;
  static constexpr size_t TARGET_SIZE = 65;
  // 0xFFFD reaches every device that keeps its radio on when idle.
  static constexpr uint16_t RESOLVE_BROADCAST = 0xFFFD;
  static constexpr uint32_t RESOLVE_TIMEOUT_MS = 5000;
  // A NWK_addr_req floods the mesh, so a stuck button cannot repeat it faster.
  static constexpr uint32_t RESOLVE_GAP_MS = 10000;
  static constexpr uint32_t WARM_GAP_MS = 1000;

  enum Pending : uint8_t { PENDING_NONE = 0, PENDING_RESOLVE = 1, PENDING_RESEND = 2 };

  struct Entry {
    uint8_t kind;
    uint8_t endpoint;
    uint16_t group_id;
    uint8_t ieee[8];
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

  struct EntryV3 {
    uint16_t group_id;
    uint16_t reserved;
    char friendly_name[TARGET_SIZE];
  };

  struct RecordV3 {
    uint32_t magic;
    uint16_t version;
    uint16_t reserved;
    uint32_t mask;
    EntryV3 entries[SLOT_COUNT];
    uint32_t checksum;
  };

  // The two records differ in length, so the version 4 load fails on the NVS
  // length check before this runs. A version 3 target is always a group.
  static_assert(sizeof(Record) != sizeof(RecordV3), "The version 4 record must not match version 3");

  static bool slot_valid_(uint8_t slot) { return slot >= FIRST_SLOT && slot <= LAST_SLOT; }

  bool has_assignment_(uint8_t slot) const {
    return slot_valid_(slot) && (record_.mask & (1UL << (slot - FIRST_SLOT))) != 0;
  }

  const Entry &entry_(uint8_t slot) const { return record_.entries[slot - FIRST_SLOT]; }

  // The caller must memset the entry first, because the checksum hashes padding.
  bool store_(uint8_t slot, const Entry &entry) {
    if (!ir_code_store.clear_for_zigbee(slot)) {
      ESP_LOGE("zigbee_learn", "Failed to clear the old action on button %u", slot);
      return false;
    }

    Record next = record_;
    const size_t index = slot - FIRST_SLOT;
    next.mask |= 1UL << index;
    std::memcpy(&next.entries[index], &entry, sizeof(entry));
    next.checksum = checksum_(next);

    {
      const std::lock_guard<std::mutex> lock(cache_mutex_);
      record_ = next;
    }
    if (!preference_.save(&record_)) {
      ESP_LOGE("zigbee_learn", "Failed to save Zigbee button %u", slot);
      return false;
    }
    return true;
  }

  void toggle_group_(uint8_t slot, const Entry &entry) {
    ezb_zcl_on_off_cmd_t request{};
    request.cmd_ctrl.dst_addr.addr_mode = EZB_ADDR_MODE_GROUP;
    request.cmd_ctrl.dst_addr.u.group_addr.group = entry.group_id;
    request.cmd_ctrl.dst_addr.u.group_addr.bcast = RESOLVE_BROADCAST;
    request.cmd_ctrl.src_ep = CLIENT_ENDPOINT;

    esp_zigbee_lock_acquire(portMAX_DELAY);
    const ezb_err_t result = ezb_zcl_on_off_toggle_cmd_req(&request);
    esp_zigbee_lock_release();
    if (result != EZB_ERR_NONE) {
      ESP_LOGE("zigbee_tx", "Toggle failed for button %u, group 0x%04X: %d", slot, entry.group_id,
               result);
      return;
    }
    ESP_LOGI("zigbee_tx", "Toggle button %u, group 0x%04X", slot, entry.group_id);
  }

  void toggle_device_(uint8_t slot, const Entry &entry) {
    const size_t index = slot - FIRST_SLOT;
    uint16_t nwk = nwk_cache_[index].load(std::memory_order_relaxed);
    if (nwk == EZB_NWK_ADDR_UNKNOWN)
      nwk = short_by_ieee_(entry.ieee);
    if (nwk == EZB_NWK_ADDR_UNKNOWN) {
      ESP_LOGI("zigbee_tx", "Button %u needs the network address of %s", slot, entry.friendly_name);
      request_resolve_(slot);
      return;
    }
    nwk_cache_[index].store(nwk, std::memory_order_relaxed);
    // A fresh press earns one retry. The resend clears this before it sends.
    retry_armed_.store(true, std::memory_order_relaxed);
    send_device_toggle_(slot, entry, nwk);
  }

  void send_device_toggle_(uint8_t slot, const Entry &entry, uint16_t nwk) {
    if (nwk == EZB_NWK_ADDR_UNKNOWN)
      return;
    ezb_zcl_on_off_cmd_t request{};
    request.cmd_ctrl.dst_addr.addr_mode = EZB_ADDR_MODE_SHORT;
    request.cmd_ctrl.dst_addr.u.short_addr = nwk;
    request.cmd_ctrl.dst_ep = entry.endpoint;
    request.cmd_ctrl.src_ep = CLIENT_ENDPOINT;
    request.cmd_ctrl.cnf_ctx.cb = on_confirm_;
    request.cmd_ctrl.cnf_ctx.user_ctx = slot_context_(slot);

    esp_zigbee_lock_acquire(portMAX_DELAY);
    const ezb_err_t result = ezb_zcl_on_off_toggle_cmd_req(&request);
    esp_zigbee_lock_release();
    if (result != EZB_ERR_NONE) {
      ESP_LOGE("zigbee_tx", "Toggle failed for button %u, device 0x%04X: %d", slot,
               static_cast<unsigned>(nwk), result);
      return;
    }
    ESP_LOGI("zigbee_tx", "Toggle button %u, device 0x%04X endpoint %u", slot,
             static_cast<unsigned>(nwk), static_cast<unsigned>(entry.endpoint));
  }

  // Runs on the Zigbee task. It parks the slot for the next tick instead of
  // sending, because that task must not block on the flash or the record mutex.
  static void on_confirm_(ezb_af_user_cnf_t *cnf, void *user_ctx) {
    if (cnf == nullptr || cnf->status == 0 || instance_ == nullptr)
      return;
    if (!instance_->retry_armed_.exchange(false, std::memory_order_relaxed))
      return;
    instance_->request_resolve_(context_slot_(user_ctx));
  }

  static void on_resolved_(const ezb_zdo_nwk_addr_req_result_t *result, void *user_ctx) {
    if (instance_ == nullptr)
      return;
    const uintptr_t packed = reinterpret_cast<uintptr_t>(user_ctx);
    instance_->finish_resolve_(static_cast<uint8_t>(packed & 0xFF),
                               static_cast<uint32_t>(packed >> 8), result);
  }

  void finish_resolve_(uint8_t slot, uint32_t seq,
                       const ezb_zdo_nwk_addr_req_result_t *result) {
    // An answer that arrives after its timeout must not clear the resolve that
    // replaced it, or resend a Toggle the press no longer wants.
    if (seq != resolve_seq_.load(std::memory_order_acquire))
      return;
    resolve_in_flight_.store(false, std::memory_order_release);
    if (result == nullptr || result->error != EZB_ERR_NONE || result->rsp == nullptr ||
        result->rsp->status != EZB_ZDP_STATUS_SUCCESS) {
      ESP_LOGE("zigbee_tx", "The mesh has no network address for button %u",
               static_cast<unsigned>(slot));
      return;
    }
    if (!slot_valid_(slot))
      return;
    nwk_cache_[slot - FIRST_SLOT].store(result->rsp->nwk_addr_remote_dev, std::memory_order_relaxed);
    if (!resolve_send_.load(std::memory_order_relaxed))
      return;
    pending_slot_.store(slot, std::memory_order_relaxed);
    pending_state_.store(PENDING_RESEND, std::memory_order_release);
  }

  // Called from the main loop and from the Zigbee task, so it only writes
  // atomics. The newest request wins, because one is enough to unstick a slot.
  void request_resolve_(uint8_t slot) {
    if (!slot_valid_(slot))
      return;
    nwk_cache_[slot - FIRST_SLOT].store(EZB_NWK_ADDR_UNKNOWN, std::memory_order_relaxed);
    pending_slot_.store(slot, std::memory_order_relaxed);
    pending_state_.store(PENDING_RESOLVE, std::memory_order_release);
  }

  void start_resolve_(uint8_t slot, const Entry &entry, bool send_after, uint32_t now) {
    const size_t index = slot - FIRST_SLOT;
    if (last_resolve_ms_[index] != 0 && now - last_resolve_ms_[index] < RESOLVE_GAP_MS)
      return;
    last_resolve_ms_[index] = now;
    const uint32_t seq = resolve_seq_.load(std::memory_order_relaxed) + 1;
    resolve_seq_.store(seq, std::memory_order_release);

    ezb_zdo_nwk_addr_req_t request{};
    request.dst_nwk_addr = RESOLVE_BROADCAST;
    std::memcpy(&request.field.ieee_addr_of_interest, entry.ieee, sizeof(entry.ieee));
    request.field.request_type = ZDO_ADDR_REQUEST_TYPE_SINGLE_DEVICE;
    request.field.start_index = 0;
    request.cb = on_resolved_;
    request.user_ctx = resolve_context_(slot, seq);

    resolve_slot_ = slot;
    resolve_send_.store(send_after, std::memory_order_relaxed);
    resolve_started_ms_ = now;
    resolve_in_flight_.store(true, std::memory_order_release);

    esp_zigbee_lock_acquire(portMAX_DELAY);
    const ezb_err_t result = ezb_zdo_nwk_addr_req(&request);
    esp_zigbee_lock_release();
    if (result != EZB_ERR_NONE) {
      resolve_in_flight_.store(false, std::memory_order_release);
      ESP_LOGE("zigbee_tx", "The network address request for button %u failed: %d", slot, result);
    }
  }

  void warm_step_(uint32_t now) {
    if (warm_mask_ == 0 || now - last_warm_ms_ < WARM_GAP_MS)
      return;
    for (size_t index = 0; index < SLOT_COUNT; index++) {
      if ((warm_mask_ & (1UL << index)) == 0)
        continue;
      warm_mask_ &= ~(1UL << index);
      last_warm_ms_ = now;
      const uint8_t slot = static_cast<uint8_t>(FIRST_SLOT + index);
      if (!has_assignment_(slot))
        return;
      const Entry &entry = entry_(slot);
      const uint16_t nwk = short_by_ieee_(entry.ieee);
      if (nwk != EZB_NWK_ADDR_UNKNOWN) {
        nwk_cache_[index].store(nwk, std::memory_order_relaxed);
        return;
      }
      start_resolve_(slot, entry, false, now);
      return;
    }
  }

  static uint16_t short_by_ieee_(const uint8_t (&ieee)[8]) {
    ezb_extaddr_t extended{};
    std::memcpy(&extended, ieee, sizeof(ieee));
    ezb_shortaddr_t nwk = EZB_NWK_ADDR_UNKNOWN;
    esp_zigbee_lock_acquire(portMAX_DELAY);
    const ezb_err_t result = ezb_address_short_by_extended(&extended, &nwk);
    esp_zigbee_lock_release();
    return result == EZB_ERR_NONE ? nwk : EZB_NWK_ADDR_UNKNOWN;
  }

  static void *slot_context_(uint8_t slot) {
    return reinterpret_cast<void *>(static_cast<uintptr_t>(slot));
  }

  // One resolve is in flight at a time, so the sequence tells a live answer from
  // one that belongs to an abandoned request.
  static void *resolve_context_(uint8_t slot, uint32_t seq) {
    return reinterpret_cast<void *>(static_cast<uintptr_t>((seq << 8) | slot));
  }

  static uint8_t context_slot_(void *user_ctx) {
    return static_cast<uint8_t>(reinterpret_cast<uintptr_t>(user_ctx));
  }

  // Hashes the padding too, so every writer must memset a record or an entry
  // before it fills the fields.
  template<typename T> static uint32_t checksum_(const T &record) {
    uint32_t hash = 2166136261U;
    const auto *bytes = reinterpret_cast<const uint8_t *>(&record);
    for (size_t i = 0; i < sizeof(record) - sizeof(record.checksum); i++) {
      hash ^= bytes[i];
      hash *= 16777619U;
    }
    return hash;
  }

  static bool ieee_all_zero_(const uint8_t (&ieee)[8]) {
    for (uint8_t byte : ieee) {
      if (byte != 0)
        return false;
    }
    return true;
  }

  // All zeros and all ones are the two reserved EUI-64 values.
  static bool ieee_valid_(const uint8_t (&ieee)[8]) {
    bool all_ones = true;
    for (uint8_t byte : ieee) {
      if (byte != 0xFF) {
        all_ones = false;
        break;
      }
    }
    return !all_ones && !ieee_all_zero_(ieee);
  }

  static bool valid_(const Record &record) {
    if (record.magic != MAGIC || record.version != VERSION ||
        (record.mask & ~((1UL << SLOT_COUNT) - 1)) != 0 || record.checksum != checksum_(record))
      return false;
    for (size_t index = 0; index < SLOT_COUNT; index++) {
      if ((record.mask & (1UL << index)) == 0)
        continue;
      const Entry &entry = record.entries[index];
      if (std::memchr(entry.friendly_name, '\0', TARGET_SIZE) == nullptr)
        return false;
      if (entry.kind == KIND_GROUP) {
        if (entry.group_id == 0 || entry.group_id > MAX_GROUP_ID || entry.endpoint != 0 ||
            !ieee_all_zero_(entry.ieee))
          return false;
      } else if (entry.kind == KIND_DEVICE) {
        if (entry.group_id != 0 || entry.endpoint < MIN_ENDPOINT || entry.endpoint > MAX_ENDPOINT ||
            !ieee_valid_(entry.ieee))
          return false;
      } else {
        return false;
      }
    }
    return true;
  }

  static bool valid_v3_(const RecordV3 &record) {
    if (record.magic != MAGIC || record.version != VERSION_V3 ||
        (record.mask & ~((1UL << SLOT_COUNT) - 1)) != 0 || record.checksum != checksum_(record))
      return false;
    for (size_t index = 0; index < SLOT_COUNT; index++) {
      if ((record.mask & (1UL << index)) == 0)
        continue;
      const EntryV3 &entry = record.entries[index];
      if (entry.group_id == 0 || entry.group_id > MAX_GROUP_ID ||
          std::memchr(entry.friendly_name, '\0', TARGET_SIZE) == nullptr)
        return false;
    }
    return true;
  }

  static bool load_version_3_(Record &out) {
    auto old_preference = esphome::global_preferences->make_preference<RecordV3>(PREFERENCE_KEY, true);
    RecordV3 old{};
    if (!old_preference.load(&old) || !valid_v3_(old))
      return false;

    reset_record_(out);
    out.mask = old.mask;
    for (size_t index = 0; index < SLOT_COUNT; index++) {
      if ((old.mask & (1UL << index)) == 0)
        continue;
      Entry &entry = out.entries[index];
      entry.kind = KIND_GROUP;
      entry.group_id = old.entries[index].group_id;
      std::memcpy(entry.friendly_name, old.entries[index].friendly_name, TARGET_SIZE);
    }
    out.checksum = checksum_(out);
    return true;
  }

  static void reset_record_(Record &record) {
    std::memset(&record, 0, sizeof(record));
    record.magic = MAGIC;
    record.version = VERSION;
    record.checksum = checksum_(record);
  }

  static inline ZigbeeAssignmentManager *instance_{nullptr};

  mutable std::mutex cache_mutex_;
  esphome::ESPPreferenceObject preference_;
  Record record_{};

  // A short address is a lease the device drops when it rejoins, so it stays in
  // RAM. The Zigbee task writes it from a callback while the loop reads it.
  std::atomic<uint16_t> nwk_cache_[SLOT_COUNT];
  std::atomic<uint8_t> pending_state_{PENDING_NONE};
  std::atomic<uint8_t> pending_slot_{0};
  std::atomic<bool> resolve_in_flight_{false};
  std::atomic<bool> resolve_send_{false};
  std::atomic<uint32_t> resolve_seq_{0};
  std::atomic<bool> retry_armed_{false};
  uint32_t last_resolve_ms_[SLOT_COUNT]{};
  uint32_t resolve_started_ms_{0};
  uint32_t last_warm_ms_{0};
  uint32_t warm_mask_{0};
  uint8_t resolve_slot_{0};
};

inline ZigbeeAssignmentManager zigbee_assignments;
