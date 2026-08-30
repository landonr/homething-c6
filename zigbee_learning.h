#pragma once

#include "ir_learning.h"

#include "esphome/components/mqtt/mqtt_client.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"
#include "esphome/core/preferences.h"

#include "esp_zigbee.h"

#include <ArduinoJson.h>

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

class ZigbeeAssignmentManager {
 public:
  static constexpr uint8_t FIRST_SLOT = 3;
  static constexpr uint8_t LAST_SLOT = 20;
  static constexpr size_t SLOT_COUNT = LAST_SLOT - FIRST_SLOT + 1;
  static constexpr uint8_t CLIENT_ENDPOINT = 1;
  // A wall switch target needs a walk to the switch, so 30 s expired first.
  static constexpr uint32_t TRAINING_TIMEOUT_MS = 60000;
  static constexpr uint32_t REQUEST_TIMEOUT_MS = 10000;

  void setup(const std::string &base_topic, const std::string &device_name, uint16_t group_base,
             const std::vector<std::string> &allowed_targets) {
    base_topic_ = base_topic;
    device_name_ = device_name;
    group_base_ = group_base;
    allowed_targets_.clear();
    for (const auto &target : allowed_targets) {
      if (!target.empty())
        allowed_targets_.insert(target);
    }
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
    ir_ui.set_zigbee_callbacks([this](uint8_t slot) { this->start_training(slot); },
                               [this](uint8_t slot) { return this->toggle(slot); },
                               [this]() { this->cancel_training(); });

    const auto handler =
        [this](const std::string &topic, const std::string &payload) { this->on_mqtt_message_(topic, payload); };
    for (const auto &target : allowed_targets_)
      esphome::mqtt::global_mqtt_client->subscribe(base_topic_ + "/" + target, handler, 1);
    esphome::mqtt::global_mqtt_client->subscribe(base_topic_ + "/bridge/groups", handler, 1);
    esphome::mqtt::global_mqtt_client->subscribe(base_topic_ + "/bridge/response/group/add", handler, 1);
    esphome::mqtt::global_mqtt_client->subscribe(base_topic_ + "/bridge/response/group/members/add", handler, 1);
    esphome::mqtt::global_mqtt_client->subscribe(base_topic_ + "/bridge/response/group/members/remove", handler, 1);
    ESP_LOGI("zigbee_learn", "Loaded Zigbee assignment mask 0x%05X with %u allowed targets",
             static_cast<unsigned>(record_.mask), static_cast<unsigned>(allowed_targets_.size()));
  }

  void start_training(uint8_t slot) {
    if (!slot_valid_(slot) || !esphome::mqtt::global_mqtt_client->is_connected()) {
      ESP_LOGW("zigbee_learn", "Cannot train button %u without MQTT", slot);
      ir_ui.zigbee_result(false);
      return;
    }
    if (!groups_ready_) {
      ESP_LOGW("zigbee_learn", "Cannot train button %u before the Zigbee2MQTT group snapshot", slot);
      ir_ui.zigbee_result(false);
      return;
    }
    pending_slot_ = slot;
    clear_candidate_();
    operation_ = Operation::WAIT_TRANSITION;
    deadline_ = esphome::millis() + TRAINING_TIMEOUT_MS;
    ESP_LOGI("zigbee_learn", "Button %u waits %u s for an allowed target transition", slot,
             static_cast<unsigned>(TRAINING_TIMEOUT_MS / 1000));
  }

  void tick() {
    if (operation_ == Operation::IDLE || !deadline_expired_())
      return;
    if (operation_ == Operation::WAIT_TRANSITION) {
      ESP_LOGW("zigbee_learn", "No allowed target transition received for button %u", pending_slot_);
      finish_error_();
      return;
    }
    ESP_LOGE("zigbee_learn", "Zigbee2MQTT request timed out for button %u", pending_slot_);
    if (operation_ == Operation::WAIT_NEW_DEVICE_CLEANUP)
      restore_old_or_finish_();
    else if (operation_ == Operation::WAIT_OLD_DEVICE_RESTORE)
      finish_error_();
    else
      begin_rollback_();
  }

  void cancel_training() {
    if (operation_ == Operation::IDLE)
      return;
    if (operation_ == Operation::WAIT_TRANSITION) {
      finish_error_();
      ESP_LOGI("zigbee_learn", "Cancelled Zigbee training");
      return;
    }
    cancel_requested_ = true;
    ESP_LOGI("zigbee_learn", "Cancelling Zigbee training after the pending request");
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

  void clear(uint8_t slot) {
    if (!has_assignment_(slot))
      return;
    const Entry old = entry_(slot);
    Record next = record_;
    const size_t index = slot - FIRST_SLOT;
    next.mask &= ~(1UL << index);
    std::memset(&next.entries[index], 0, sizeof(next.entries[index]));
    next.checksum = checksum_(next);

    // Disable playback before flash or MQTT work.
    record_ = next;
    if (!preference_.save(&record_))
      ESP_LOGE("zigbee_learn", "Failed to save cleared Zigbee button %u", slot);

    if (kind_(old) == TargetKind::DEVICE && esphome::mqtt::global_mqtt_client->is_connected()) {
      const uint32_t transaction = next_transaction_();
      if (!publish_member_request_("remove", slot, target_name_(old), transaction))
        ESP_LOGE("zigbee_learn", "Failed to request member removal for cleared button %u", slot);
    }
    ESP_LOGI("zigbee_learn", "Cleared Zigbee button %u", slot);
  }

 private:
  static constexpr uint32_t MAGIC = 0x5A424731U;
  static constexpr uint16_t VERSION = 2;
  static constexpr uint32_t PREFERENCE_KEY = 0x5A424731U;
  static constexpr size_t TARGET_SIZE = 65;

  enum class TargetKind : uint8_t { NONE = 0, GROUP = 1, DEVICE = 2 };

  struct Entry {
    uint8_t kind;
    uint8_t reserved;
    uint16_t group_id;
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

  enum class Operation : uint8_t {
    IDLE,
    WAIT_TRANSITION,
    WAIT_PRIVATE_GROUP_ADD,
    WAIT_OLD_DEVICE_REMOVE,
    WAIT_NEW_DEVICE_ADD,
    WAIT_NEW_DEVICE_CLEANUP,
    WAIT_OLD_DEVICE_RESTORE,
  };

  static bool slot_valid_(uint8_t slot) { return slot >= FIRST_SLOT && slot <= LAST_SLOT; }

  bool has_assignment_(uint8_t slot) const {
    return slot_valid_(slot) && (record_.mask & (1UL << (slot - FIRST_SLOT))) != 0;
  }

  const Entry &entry_(uint8_t slot) const { return record_.entries[slot - FIRST_SLOT]; }

  static TargetKind kind_(const Entry &entry) { return static_cast<TargetKind>(entry.kind); }

  static std::string target_name_(const Entry &entry) { return std::string(entry.friendly_name); }

  uint16_t private_group_id_(uint8_t slot) const { return group_base_ + (slot - FIRST_SLOT); }

  std::string private_group_name_(uint8_t slot) const {
    char name[96];
    std::snprintf(name, sizeof(name), "%s-button-%u", device_name_.c_str(), slot);
    return name;
  }

  bool deadline_expired_() const {
    return static_cast<int32_t>(esphome::millis() - deadline_) >= 0;
  }

  uint32_t next_transaction_() {
    transaction_counter_++;
    if (transaction_counter_ == 0)
      transaction_counter_ = 1;
    return transaction_counter_;
  }

  void on_mqtt_message_(const std::string &topic, const std::string &payload) {
    const std::string prefix = base_topic_ + "/";
    if (topic.rfind(prefix, 0) != 0)
      return;
    const std::string relative = topic.substr(prefix.size());

    JsonDocument document;
    if (deserializeJson(document, payload) != DeserializationError::Ok)
      return;

    if (relative == "bridge/groups") {
      cache_groups_(document.as<JsonVariantConst>());
      return;
    }
    if (relative.rfind("bridge/response/group/", 0) == 0) {
      handle_response_(document.as<JsonObjectConst>());
      return;
    }
    if (allowed_targets_.count(relative) == 0 || relative.find('/') != std::string::npos)
      return;

    const JsonObjectConst object = document.as<JsonObjectConst>();
    if (object.isNull() || !object["state"].is<const char *>())
      return;
    const std::string value = object["state"].as<const char *>();
    if (value != "ON" && value != "OFF")
      return;
    const bool state = value == "ON";
    const auto previous = target_states_.find(relative);
    if (previous == target_states_.end()) {
      target_states_[relative] = state;
      return;
    }
    if (previous->second == state)
      return;
    previous->second = state;
    if (operation_ == Operation::WAIT_TRANSITION)
      resolve_candidate_(relative);
  }

  void cache_groups_(JsonVariantConst root) {
    if (!root.is<JsonArrayConst>())
      return;
    groups_by_name_.clear();
    group_names_by_id_.clear();
    for (JsonObjectConst group : root.as<JsonArrayConst>()) {
      if (!group["friendly_name"].is<const char *>() || !group["id"].is<uint32_t>())
        continue;
      const uint32_t id = group["id"].as<uint32_t>();
      if (id == 0 || id > UINT16_MAX)
        continue;
      const std::string name = group["friendly_name"].as<const char *>();
      groups_by_name_[name] = static_cast<uint16_t>(id);
      group_names_by_id_[static_cast<uint16_t>(id)] = name;
    }
    groups_ready_ = true;
  }

  void resolve_candidate_(const std::string &target) {
    candidate_name_ = target;
    const auto group = groups_by_name_.find(target);
    if (group != groups_by_name_.end()) {
      candidate_kind_ = TargetKind::GROUP;
      candidate_group_id_ = group->second;
      continue_after_private_group_();
      return;
    }

    candidate_kind_ = TargetKind::DEVICE;
    candidate_group_id_ = private_group_id_(pending_slot_);
    const std::string private_name = private_group_name_(pending_slot_);
    const auto existing_name = groups_by_name_.find(private_name);
    if (existing_name != groups_by_name_.end()) {
      if (existing_name->second != candidate_group_id_) {
        ESP_LOGE("zigbee_learn", "Private group %s has unexpected ID 0x%04X", private_name.c_str(),
                 existing_name->second);
        finish_error_();
        return;
      }
      continue_after_private_group_();
      return;
    }
    const auto existing_id = group_names_by_id_.find(candidate_group_id_);
    if (existing_id != group_names_by_id_.end()) {
      ESP_LOGE("zigbee_learn", "Private group ID 0x%04X belongs to %s", candidate_group_id_,
               existing_id->second.c_str());
      finish_error_();
      return;
    }

    transaction_ = next_transaction_();
    if (!publish_group_add_(pending_slot_, transaction_)) {
      finish_error_();
      return;
    }
    operation_ = Operation::WAIT_PRIVATE_GROUP_ADD;
    deadline_ = esphome::millis() + REQUEST_TIMEOUT_MS;
  }

  void continue_after_private_group_() {
    if (has_assignment_(pending_slot_)) {
      const Entry &old = entry_(pending_slot_);
      const bool same_target = kind_(old) == candidate_kind_ && old.group_id == candidate_group_id_ &&
                               target_name_(old) == candidate_name_;
      if (same_target) {
        commit_assignment_();
        return;
      }
      if (kind_(old) == TargetKind::DEVICE) {
        transaction_ = next_transaction_();
        if (!publish_member_request_("remove", pending_slot_, target_name_(old), transaction_)) {
          finish_error_();
          return;
        }
        operation_ = Operation::WAIT_OLD_DEVICE_REMOVE;
        deadline_ = esphome::millis() + REQUEST_TIMEOUT_MS;
        return;
      }
    }
    add_candidate_or_commit_();
  }

  void add_candidate_or_commit_() {
    if (candidate_kind_ == TargetKind::GROUP) {
      commit_assignment_();
      return;
    }
    transaction_ = next_transaction_();
    if (!publish_member_request_("add", pending_slot_, candidate_name_, transaction_)) {
      begin_rollback_();
      return;
    }
    operation_ = Operation::WAIT_NEW_DEVICE_ADD;
    deadline_ = esphome::millis() + REQUEST_TIMEOUT_MS;
  }

  void handle_response_(JsonObjectConst response) {
    if (operation_ == Operation::IDLE || operation_ == Operation::WAIT_TRANSITION || response.isNull() ||
        response["transaction"].as<uint32_t>() != transaction_)
      return;
    const bool ok = response["status"].is<const char *>() &&
                    std::strcmp(response["status"].as<const char *>(), "ok") == 0;
    if (!ok) {
      const char *error = response["error"] | "unknown error";
      ESP_LOGE("zigbee_learn", "Zigbee2MQTT request failed for button %u: %s", pending_slot_, error);
      if (operation_ == Operation::WAIT_NEW_DEVICE_CLEANUP)
        restore_old_or_finish_();
      else if (operation_ == Operation::WAIT_OLD_DEVICE_RESTORE)
        finish_error_();
      else
        begin_rollback_();
      return;
    }

    switch (operation_) {
      case Operation::WAIT_PRIVATE_GROUP_ADD:
        groups_by_name_[private_group_name_(pending_slot_)] = candidate_group_id_;
        group_names_by_id_[candidate_group_id_] = private_group_name_(pending_slot_);
        if (cancel_requested_)
          finish_error_();
        else
          continue_after_private_group_();
        break;
      case Operation::WAIT_OLD_DEVICE_REMOVE:
        old_member_removed_ = true;
        if (cancel_requested_)
          begin_rollback_();
        else
          add_candidate_or_commit_();
        break;
      case Operation::WAIT_NEW_DEVICE_ADD:
        candidate_member_added_ = true;
        if (cancel_requested_)
          begin_rollback_();
        else
          commit_assignment_();
        break;
      case Operation::WAIT_NEW_DEVICE_CLEANUP:
        candidate_member_added_ = false;
        restore_old_or_finish_();
        break;
      case Operation::WAIT_OLD_DEVICE_RESTORE:
        old_member_removed_ = false;
        finish_error_();
        break;
      default:
        break;
    }
  }

  void commit_assignment_() {
    if (cancel_requested_) {
      begin_rollback_();
      return;
    }
    Record next = record_;
    const size_t index = pending_slot_ - FIRST_SLOT;
    next.mask |= 1UL << index;
    Entry &entry = next.entries[index];
    std::memset(&entry, 0, sizeof(entry));
    entry.kind = static_cast<uint8_t>(candidate_kind_);
    entry.group_id = candidate_group_id_;
    std::snprintf(entry.friendly_name, TARGET_SIZE, "%s", candidate_name_.c_str());
    next.checksum = checksum_(next);
    if (!preference_.save(&next)) {
      ESP_LOGE("zigbee_learn", "Failed to save Zigbee button %u", pending_slot_);
      begin_rollback_();
      return;
    }
    if (!ir_code_store.clear_for_zigbee(pending_slot_)) {
      preference_.save(&record_);
      ESP_LOGE("zigbee_learn", "Failed to clear the previous button %u action", pending_slot_);
      begin_rollback_();
      return;
    }
    record_ = next;
    ESP_LOGI("zigbee_learn", "Button %u assigned to %s as Zigbee Toggle group 0x%04X", pending_slot_,
             candidate_name_.c_str(), candidate_group_id_);
    operation_ = Operation::IDLE;
    clear_candidate_();
    ir_ui.zigbee_result(true);
  }

  void begin_rollback_() {
    if (candidate_member_added_ && esphome::mqtt::global_mqtt_client->is_connected()) {
      transaction_ = next_transaction_();
      if (publish_member_request_("remove", pending_slot_, candidate_name_, transaction_)) {
        operation_ = Operation::WAIT_NEW_DEVICE_CLEANUP;
        deadline_ = esphome::millis() + REQUEST_TIMEOUT_MS;
        return;
      }
    }
    restore_old_or_finish_();
  }

  void restore_old_or_finish_() {
    if (old_member_removed_ && has_assignment_(pending_slot_) &&
        kind_(entry_(pending_slot_)) == TargetKind::DEVICE && esphome::mqtt::global_mqtt_client->is_connected()) {
      transaction_ = next_transaction_();
      if (publish_member_request_("add", pending_slot_, target_name_(entry_(pending_slot_)), transaction_)) {
        operation_ = Operation::WAIT_OLD_DEVICE_RESTORE;
        deadline_ = esphome::millis() + REQUEST_TIMEOUT_MS;
        return;
      }
    }
    finish_error_();
  }

  void finish_error_() {
    operation_ = Operation::IDLE;
    clear_candidate_();
    ir_ui.zigbee_result(false);
  }

  void clear_candidate_() {
    candidate_kind_ = TargetKind::NONE;
    candidate_name_.clear();
    candidate_group_id_ = 0;
    candidate_member_added_ = false;
    old_member_removed_ = false;
    cancel_requested_ = false;
  }

  bool publish_group_add_(uint8_t slot, uint32_t transaction) const {
    const std::string topic = base_topic_ + "/bridge/request/group/add";
    const std::string name = private_group_name_(slot);
    const uint16_t id = private_group_id_(slot);
    return esphome::mqtt::global_mqtt_client->publish_json(
        topic, [name, id, transaction](JsonObject root) {
          root["friendly_name"] = name;
          root["id"] = id;
          root["transaction"] = transaction;
        }, 1, false);
  }

  bool publish_member_request_(const char *action, uint8_t slot, const std::string &target,
                               uint32_t transaction) const {
    const std::string topic = base_topic_ + "/bridge/request/group/members/" + action;
    const std::string group = private_group_name_(slot);
    return esphome::mqtt::global_mqtt_client->publish_json(
        topic, [group, target, transaction](JsonObject root) {
          root["group"] = group;
          root["device"] = target;
          root["transaction"] = transaction;
        }, 1, false);
  }

  static void reset_record_(Record &record) {
    std::memset(&record, 0, sizeof(record));
    record.magic = MAGIC;
    record.version = VERSION;
    record.checksum = checksum_(record);
  }

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
      const TargetKind kind = kind_(entry);
      if ((kind != TargetKind::GROUP && kind != TargetKind::DEVICE) || entry.group_id == 0 ||
          std::memchr(entry.friendly_name, '\0', TARGET_SIZE) == nullptr || entry.friendly_name[0] == '\0')
        return false;
    }
    return true;
  }

  esphome::ESPPreferenceObject preference_{};
  Record record_{};
  std::string base_topic_;
  std::string device_name_;
  uint16_t group_base_{0xC600};
  std::unordered_set<std::string> allowed_targets_;
  std::unordered_map<std::string, bool> target_states_;
  std::unordered_map<std::string, uint16_t> groups_by_name_;
  std::unordered_map<uint16_t, std::string> group_names_by_id_;
  Operation operation_{Operation::IDLE};
  TargetKind candidate_kind_{TargetKind::NONE};
  uint8_t pending_slot_{0};
  std::string candidate_name_;
  uint16_t candidate_group_id_{0};
  uint32_t deadline_{0};
  uint32_t transaction_{0};
  uint32_t transaction_counter_{1000};
  bool groups_ready_{false};
  bool candidate_member_added_{false};
  bool old_member_removed_{false};
  bool cancel_requested_{false};
};

inline ZigbeeAssignmentManager zigbee_assignments;
