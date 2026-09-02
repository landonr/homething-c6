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

// Stores one Zigbee target and one command per assignable input, and sends that
// command from the radio.
//
// A target is a group or one device. The remote holds no MQTT client. The
// /buttons page reads the Zigbee2MQTT inventory over the frontend websocket in
// the browser and posts only the resolved address here, so a button keeps
// working with Zigbee2MQTT and Home Assistant both down.
//
// A group command is an unacknowledged groupcast, and group membership lives in
// the group table of the light. A device command is a unicast to the 16-bit
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

  // One press sends one ZCL command. The /buttons page reads the cluster list of
  // the target from Zigbee2MQTT and offers only the actions that list carries,
  // so a pair such as brighter and dimmer costs two inputs.
  enum Action : uint8_t {
    ACT_TOGGLE = 0,
    ACT_ON = 1,
    ACT_OFF = 2,
    ACT_LEVEL_UP = 3,
    ACT_LEVEL_DOWN = 4,
    ACT_WHITE_WARMER = 5,
    ACT_WHITE_COOLER = 6,
    ACT_SCENE = 7,
    ACT_COVER_OPEN = 8,
    ACT_COVER_CLOSE = 9,
    ACT_COVER_STOP = 10,
    ACT_TEMP_UP = 11,
    ACT_TEMP_DOWN = 12,
    ACT_LOCK = 13,
    ACT_UNLOCK = 14,
    ACT_ALARM = 15,
    ACT_SQUAWK = 16,
    ACTION_COUNT,
  };

  struct Assignment {
    bool assigned{false};
    Kind kind{KIND_GROUP};
    uint16_t group_id{0};
    uint8_t endpoint{0};
    uint8_t action{ACT_TOGGLE};
    int16_t param{0};
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
    } else if (load_version_4_(record_) || load_version_3_(record_)) {
      if (preference_.save(&record_)) {
        ESP_LOGI("zigbee_learn", "Migrated the Zigbee assignments to record version 5");
      } else {
        ESP_LOGE("zigbee_learn", "Failed to save the migrated Zigbee assignments");
      }
    } else {
      reset_record_(record_);
      if (!preference_.save(&record_))
        ESP_LOGE("zigbee_learn", "Failed to invalidate old Zigbee assignments");
    }

    ir_code_store.set_assignment_clear_callback([this](uint8_t slot) { this->clear(slot); });
    ir_ui.set_zigbee_play_callback([this](uint8_t slot) { return this->play(slot); });
    ESP_LOGI("zigbee_learn", "Loaded Zigbee assignment mask 0x%05X",
             static_cast<unsigned>(record_.mask));
  }

  // Runs on the main loop from a deferred web action, so the flash write cannot
  // block the httpd task. A group target needs no network round trip, so the
  // result is known before this returns.
  bool assign_from_web(uint8_t slot, uint16_t group_id, uint8_t action, int16_t param,
                       const std::string &name) {
    if (!slot_valid_(slot) || group_id == 0 || group_id > MAX_GROUP_ID)
      return false;
    if (!action_valid_(action, param) || name.size() >= TARGET_SIZE)
      return false;

    Entry entry;
    std::memset(&entry, 0, sizeof(entry));
    entry.kind = KIND_GROUP;
    entry.group_id = group_id;
    entry.action = action;
    entry.param = param;
    std::strncpy(entry.friendly_name, name.c_str(), TARGET_SIZE - 1);
    if (!store_(slot, entry))
      return false;

    nwk_cache_[slot - FIRST_SLOT].store(EZB_NWK_ADDR_UNKNOWN, std::memory_order_relaxed);
    ESP_LOGI("zigbee_learn", "Button %u sends action %u to group 0x%04X (%s)", slot,
             static_cast<unsigned>(action), static_cast<unsigned>(group_id), entry.friendly_name);
    return true;
  }

  // The IEEE address arrives as the little endian bytes of the EUI-64, which is
  // the order the radio wants, so it goes to flash without a swap.
  bool assign_device_from_web(uint8_t slot, const uint8_t (&ieee)[8], uint8_t endpoint,
                              uint8_t action, int16_t param, const std::string &name) {
    if (!slot_valid_(slot) || endpoint < MIN_ENDPOINT || endpoint > MAX_ENDPOINT)
      return false;
    if (!ieee_valid_(ieee) || !action_valid_(action, param) || name.size() >= TARGET_SIZE)
      return false;

    Entry entry;
    std::memset(&entry, 0, sizeof(entry));
    entry.kind = KIND_DEVICE;
    entry.endpoint = endpoint;
    entry.action = action;
    entry.param = param;
    std::memcpy(entry.ieee, ieee, sizeof(entry.ieee));
    std::strncpy(entry.friendly_name, name.c_str(), TARGET_SIZE - 1);
    if (!store_(slot, entry))
      return false;

    const size_t index = slot - FIRST_SLOT;
    nwk_cache_[index].store(EZB_NWK_ADDR_UNKNOWN, std::memory_order_relaxed);
    last_resolve_ms_[index] = 0;
    warm_mask_ |= 1UL << index;
    ESP_LOGI("zigbee_learn", "Button %u sends action %u to device %s endpoint %u", slot,
             static_cast<unsigned>(action), entry.friendly_name, static_cast<unsigned>(endpoint));
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
    result.action = entry.action;
    result.param = entry.param;
    std::memcpy(result.ieee, entry.ieee, sizeof(result.ieee));
    result.name = entry.friendly_name;
    return result;
  }

  bool play(uint8_t slot) {
    if (!has_assignment_(slot))
      return false;
    const Entry &entry = entry_(slot);
    if (entry.kind == KIND_DEVICE)
      play_device_(slot, entry);
    else
      send_command_(slot, entry, false, 0);
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
      send_command_(slot, entry, true, nwk_cache_[slot - FIRST_SLOT].load(std::memory_order_relaxed));
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
  // Version 5 carries the action and its value, because the target alone no
  // longer says what a press sends.
  static constexpr uint16_t VERSION = 5;
  static constexpr uint16_t VERSION_V4 = 4;
  static constexpr uint16_t VERSION_V3 = 3;
  static constexpr uint32_t PREFERENCE_KEY = 0x5A424731U;
  static constexpr size_t TARGET_SIZE = 65;
  // 0xFFFD reaches every device that keeps its radio on when idle.
  static constexpr uint16_t RESOLVE_BROADCAST = 0xFFFD;
  static constexpr uint32_t RESOLVE_TIMEOUT_MS = 5000;
  // A NWK_addr_req floods the mesh, so a stuck button cannot repeat it faster.
  static constexpr uint32_t RESOLVE_GAP_MS = 10000;
  static constexpr uint32_t WARM_GAP_MS = 1000;
  // Tenths of a second. A step that lands instantly reads as a jump, and one
  // that takes longer than the next press queues behind it.
  static constexpr uint16_t STEP_TRANSITION_DS = 3;
  static constexpr uint8_t STROBE_DUTY_PERCENT = 40;
  static constexpr uint8_t MAX_LEVEL_STEP = 254;
  static constexpr int16_t MAX_MIRED_STEP = 2000;
  static constexpr int16_t MAX_SCENE_ID = 255;
  // The ZCL amount field is a signed 0.1 C step, so a press moves 12.7 C at most.
  static constexpr int16_t MAX_TENTH_DEGREES = 127;
  static constexpr int16_t MAX_ALARM_SECONDS = 600;

  enum Pending : uint8_t { PENDING_NONE = 0, PENDING_RESOLVE = 1, PENDING_RESEND = 2 };

  struct Entry {
    uint8_t kind;
    uint8_t endpoint;
    uint16_t group_id;
    uint8_t action;
    uint8_t reserved;
    int16_t param;
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

  struct EntryV4 {
    uint8_t kind;
    uint8_t endpoint;
    uint16_t group_id;
    uint8_t ieee[8];
    char friendly_name[TARGET_SIZE];
  };

  struct RecordV4 {
    uint32_t magic;
    uint16_t version;
    uint16_t reserved;
    uint32_t mask;
    EntryV4 entries[SLOT_COUNT];
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

  // Each record differs in length, so a newer load fails on the NVS length check
  // before the older one runs. A version 3 target is always a group, and a
  // version 4 target always toggles.
  static_assert(sizeof(Record) != sizeof(RecordV4), "The version 5 record must not match version 4");
  static_assert(sizeof(Record) != sizeof(RecordV3), "The version 5 record must not match version 3");
  static_assert(sizeof(RecordV4) != sizeof(RecordV3),
                "The version 4 record must not match version 3");

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

  void play_device_(uint8_t slot, const Entry &entry) {
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
    send_command_(slot, entry, true, nwk);
  }

  // Every action shares this control block, so only the payload and the request
  // function below change. A groupcast carries no confirm callback, because it
  // gets no acknowledgement to drive one.
  void send_command_(uint8_t slot, const Entry &entry, bool device, uint16_t nwk) {
    ezb_zcl_cluster_cmd_ctrl_t ctrl{};
    if (device) {
      if (nwk == EZB_NWK_ADDR_UNKNOWN)
        return;
      ctrl.dst_addr.addr_mode = EZB_ADDR_MODE_SHORT;
      ctrl.dst_addr.u.short_addr = nwk;
      ctrl.dst_ep = entry.endpoint;
      ctrl.cnf_ctx.cb = on_confirm_;
      ctrl.cnf_ctx.user_ctx = slot_context_(slot);
    } else {
      ctrl.dst_addr.addr_mode = EZB_ADDR_MODE_GROUP;
      ctrl.dst_addr.u.group_addr.group = entry.group_id;
      ctrl.dst_addr.u.group_addr.bcast = RESOLVE_BROADCAST;
    }
    ctrl.src_ep = CLIENT_ENDPOINT;

    esp_zigbee_lock_acquire(portMAX_DELAY);
    const ezb_err_t result = dispatch_(ctrl, entry);
    esp_zigbee_lock_release();
    if (result != EZB_ERR_NONE) {
      ESP_LOGE("zigbee_tx", "Action %u failed for button %u, target 0x%04X: %d",
               static_cast<unsigned>(entry.action), slot,
               static_cast<unsigned>(device ? nwk : entry.group_id), result);
      return;
    }
    ESP_LOGI("zigbee_tx", "Action %u from button %u to target 0x%04X endpoint %u",
             static_cast<unsigned>(entry.action), slot,
             static_cast<unsigned>(device ? nwk : entry.group_id),
             static_cast<unsigned>(entry.endpoint));
  }

  // The SDK gives each cluster its own request function and payload, so the
  // action picks both. Nothing here reads a target state, which keeps a press
  // to one frame with no round trip.
  static ezb_err_t dispatch_(const ezb_zcl_cluster_cmd_ctrl_t &ctrl, const Entry &entry) {
    switch (entry.action) {
      case ACT_TOGGLE:
      case ACT_ON:
      case ACT_OFF: {
        ezb_zcl_on_off_cmd_t request{};
        request.cmd_ctrl = ctrl;
        if (entry.action == ACT_ON)
          return ezb_zcl_on_off_on_cmd_req(&request);
        if (entry.action == ACT_OFF)
          return ezb_zcl_on_off_off_cmd_req(&request);
        return ezb_zcl_on_off_toggle_cmd_req(&request);
      }
      case ACT_LEVEL_UP:
      case ACT_LEVEL_DOWN: {
        // WithOnOff, so a step up wakes a light that is off and a step to zero
        // turns it off, which is what a dimmer pair has to do.
        ezb_zcl_level_step_with_on_off_cmd_t request{};
        request.cmd_ctrl = ctrl;
        request.payload.step_mode = entry.action == ACT_LEVEL_UP ? EZB_ZCL_LEVEL_FADE_MODE_UP
                                                                 : EZB_ZCL_LEVEL_FADE_MODE_DOWN;
        request.payload.step_size = static_cast<uint8_t>(entry.param);
        request.payload.transition_time = STEP_TRANSITION_DS;
        return ezb_zcl_level_step_with_on_off_cmd_req(&request);
      }
      case ACT_WHITE_WARMER:
      case ACT_WHITE_COOLER: {
        // Mireds rise as the white gets warmer, so warmer steps up.
        ezb_zcl_color_control_step_color_temperature_cmd_t request{};
        request.cmd_ctrl = ctrl;
        request.payload.step_mode = entry.action == ACT_WHITE_WARMER
                                        ? EZB_ZCL_COLOR_CONTROL_STEP_MODE_UP
                                        : EZB_ZCL_COLOR_CONTROL_STEP_MODE_DOWN;
        request.payload.step_size = static_cast<uint16_t>(entry.param);
        request.payload.color_temperature_min_mireds =
            EZB_ZCL_COLOR_CONTROL_COLOR_TEMP_PHYSICAL_MIN_MIREDS_DEFAULT_VALUE;
        request.payload.color_temperature_max_mireds =
            EZB_ZCL_COLOR_CONTROL_COLOR_TEMP_PHYSICAL_MAX_MIREDS_DEFAULT_VALUE;
        request.payload.transition_time = STEP_TRANSITION_DS;
        return ezb_zcl_color_control_step_color_temperature_cmd_req(&request);
      }
      case ACT_SCENE: {
        // RecallScene carries its own group id. A device target stores 0 there,
        // which is the group Zigbee2MQTT uses for a scene on one device.
        ezb_zcl_scenes_recall_scene_cmd_t request{};
        request.cmd_ctrl = ctrl;
        request.payload.group_id = entry.group_id;
        request.payload.scene_id = static_cast<uint8_t>(entry.param);
        return ezb_zcl_scenes_recall_scene_cmd_req(&request);
      }
      case ACT_COVER_OPEN:
      case ACT_COVER_CLOSE:
      case ACT_COVER_STOP: {
        ezb_zcl_window_covering_movement_cmd_t request{};
        request.cmd_ctrl = ctrl;
        request.cmd_id = entry.action == ACT_COVER_OPEN
                             ? EZB_ZCL_CMD_WINDOW_COVERING_UP_OPEN_ID
                             : (entry.action == ACT_COVER_CLOSE
                                    ? EZB_ZCL_CMD_WINDOW_COVERING_DOWN_CLOSE_ID
                                    : EZB_ZCL_CMD_WINDOW_COVERING_STOP_ID);
        return ezb_zcl_window_covering_movement_cmd_req(&request);
      }
      case ACT_TEMP_UP:
      case ACT_TEMP_DOWN: {
        // A relative change needs no attribute read, so a press stays one frame.
        // BOTH moves the heating and the cooling setpoint together.
        ezb_zcl_thermostat_setpoint_raise_or_lower_cmd_t request{};
        request.cmd_ctrl = ctrl;
        request.payload.mode = EZB_ZCL_THERMOSTAT_SETPOINT_MODE_BOTH;
        request.payload.amount = entry.action == ACT_TEMP_UP
                                     ? static_cast<int8_t>(entry.param)
                                     : static_cast<int8_t>(-entry.param);
        return ezb_zcl_thermostat_setpoint_raise_or_lower_cmd_req(&request);
      }
      case ACT_LOCK:
      case ACT_UNLOCK: {
        // A lock refuses an unsecured frame, so this asks for APS security. A
        // lock that was never bound to this remote still refuses it.
        ezb_zcl_door_lock_lock_door_cmd_t request{};
        request.cmd_ctrl = ctrl;
        request.aps_secur_enabled = true;
        return entry.action == ACT_LOCK ? ezb_zcl_door_lock_lock_door_cmd_req(&request)
                                        : ezb_zcl_door_lock_unlock_door_cmd_req(&request);
      }
      case ACT_ALARM: {
        ezb_zcl_ias_wd_start_warning_cmd_t request{};
        request.cmd_ctrl = ctrl;
        request.payload.warning_mode = EZB_ZCL_IAS_WD_WARNING_MODE_BURGLAR;
        request.payload.strobe = 1;
        request.payload.siren_level = EZB_ZCL_IAS_WD_SIREN_LEVEL_HIGH;
        request.payload.duration = static_cast<uint16_t>(entry.param);
        request.payload.strobe_duty_cycle = STROBE_DUTY_PERCENT;
        request.payload.strobe_level = 1;
        return ezb_zcl_ias_wd_start_warning_cmd_req(&request);
      }
      case ACT_SQUAWK: {
        ezb_zcl_ias_wd_squawk_cmd_t request{};
        request.cmd_ctrl = ctrl;
        request.payload.squawk_mode = EZB_ZCL_IAS_WD_SQUAWK_MODE_ARMED;
        request.payload.strobe = EZB_ZCL_IAS_WD_SQUAWK_STROBE_USE_STROBE;
        request.payload.squawk_level = EZB_ZCL_IAS_WD_SQUAWK_LEVEL_HIGH;
        return ezb_zcl_ias_wd_squawk_cmd_req(&request);
      }
      default:
        return EZB_ERR_INV_ARG;
    }
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

  // The value an action carries is the one field the page cannot be trusted to
  // bound, because an import block reaches this path unread by any picker.
  static bool action_valid_(uint8_t action, int16_t param) {
    switch (action) {
      case ACT_LEVEL_UP:
      case ACT_LEVEL_DOWN:
        return param >= 1 && param <= MAX_LEVEL_STEP;
      case ACT_WHITE_WARMER:
      case ACT_WHITE_COOLER:
        return param >= 1 && param <= MAX_MIRED_STEP;
      case ACT_SCENE:
        return param >= 0 && param <= MAX_SCENE_ID;
      case ACT_TEMP_UP:
      case ACT_TEMP_DOWN:
        return param >= 1 && param <= MAX_TENTH_DEGREES;
      case ACT_ALARM:
        return param >= 1 && param <= MAX_ALARM_SECONDS;
      case ACT_TOGGLE:
      case ACT_ON:
      case ACT_OFF:
      case ACT_COVER_OPEN:
      case ACT_COVER_CLOSE:
      case ACT_COVER_STOP:
      case ACT_LOCK:
      case ACT_UNLOCK:
      case ACT_SQUAWK:
        return param == 0;
      default:
        return false;
    }
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
      if (entry.reserved != 0 || !action_valid_(entry.action, entry.param))
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

  static bool valid_v4_(const RecordV4 &record) {
    if (record.magic != MAGIC || record.version != VERSION_V4 ||
        (record.mask & ~((1UL << SLOT_COUNT) - 1)) != 0 || record.checksum != checksum_(record))
      return false;
    for (size_t index = 0; index < SLOT_COUNT; index++) {
      if ((record.mask & (1UL << index)) == 0)
        continue;
      const EntryV4 &entry = record.entries[index];
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

  static bool load_version_4_(Record &out) {
    auto old_preference = esphome::global_preferences->make_preference<RecordV4>(PREFERENCE_KEY, true);
    RecordV4 old{};
    if (!old_preference.load(&old) || !valid_v4_(old))
      return false;

    reset_record_(out);
    out.mask = old.mask;
    for (size_t index = 0; index < SLOT_COUNT; index++) {
      if ((old.mask & (1UL << index)) == 0)
        continue;
      Entry &entry = out.entries[index];
      entry.kind = old.entries[index].kind;
      entry.endpoint = old.entries[index].endpoint;
      entry.group_id = old.entries[index].group_id;
      entry.action = ACT_TOGGLE;
      std::memcpy(entry.ieee, old.entries[index].ieee, sizeof(entry.ieee));
      std::memcpy(entry.friendly_name, old.entries[index].friendly_name, TARGET_SIZE);
    }
    out.checksum = checksum_(out);
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
      entry.action = ACT_TOGGLE;
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
