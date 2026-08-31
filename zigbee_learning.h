#pragma once

#include "ir_learning.h"

#include "esphome/components/mqtt/mqtt_client.h"
#include "esphome/core/helpers.h"
#include "esphome/core/log.h"
#include "esphome/core/preferences.h"

#include "esp_zigbee.h"

#include <ArduinoJson.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <functional>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
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
  // The bridge inventory of a large network does not fit in RAM, so the cache
  // keeps the first entries only. The free-text field covers the rest.
  static constexpr size_t MAX_DEVICES = 64;

  struct Device {
    std::string name;
    std::string ieee;
  };

  struct Targets {
    bool ready{false};
    std::vector<std::pair<uint16_t, std::string>> groups;
    std::vector<Device> devices;
  };

  struct Assignment {
    bool assigned{false};
    uint16_t group_id{0};
    std::string name;
  };

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
    esphome::mqtt::global_mqtt_client->subscribe(base_topic_ + "/bridge/devices", handler, 1);
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
    // A web assignment leaves the receiver mode closed, so its operation is the
    // only thing that can already own the candidate fields here.
    if (operation_ != Operation::IDLE) {
      ESP_LOGW("zigbee_learn", "Cannot train button %u during another Zigbee operation", slot);
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

  bool busy() const { return operation_ != Operation::IDLE; }

  void set_web_result_callback(std::function<void(bool)> callback) {
    web_result_callback_ = std::move(callback);
  }

  // The /buttons page names its target instead of waiting for a state
  // transition. This runs on the main loop from a deferred web action.
  //
  // A false result means that nothing started, so the caller reports the
  // failure itself. A true result reports through the web result callback,
  // which can fire before this call returns for a direct group target.
  bool assign_from_web(uint8_t slot, const std::string &target) {
    if (!slot_valid_(slot) || operation_ != Operation::IDLE)
      return false;
    const std::string name = trimmed_(target);
    if (name.empty() || name.size() >= TARGET_SIZE)
      return false;

    pending_slot_ = slot;
    clear_candidate_();
    candidate_name_ = name;

    uint16_t group_id = 0;
    if (parse_group_id_(name, group_id)) {
      candidate_kind_ = TargetKind::GROUP;
      candidate_group_id_ = group_id;
    } else {
      const auto group = groups_by_name_.find(name);
      if (group != groups_by_name_.end()) {
        candidate_kind_ = TargetKind::GROUP;
        candidate_group_id_ = group->second;
      } else {
        candidate_kind_ = TargetKind::DEVICE;
      }
    }

    // A device target needs the private group. An old device target needs a
    // member removal. A plain group target needs neither, so it can be stored
    // while MQTT is down.
    const bool old_is_device = has_assignment_(slot) && kind_(entry_(slot)) == TargetKind::DEVICE;
    const bool needs_mqtt = candidate_kind_ == TargetKind::DEVICE || old_is_device;
    if (needs_mqtt && !esphome::mqtt::global_mqtt_client->is_connected()) {
      ESP_LOGW("zigbee_learn", "Cannot assign button %u to %s without MQTT", slot, name.c_str());
      clear_candidate_();
      return false;
    }
    if (candidate_kind_ == TargetKind::DEVICE && !groups_ready_) {
      ESP_LOGW("zigbee_learn", "Cannot assign button %u before the Zigbee2MQTT group snapshot", slot);
      clear_candidate_();
      return false;
    }

    web_pending_ = true;
    deadline_ = esphome::millis() + REQUEST_TIMEOUT_MS;
    ESP_LOGI("zigbee_learn", "Web assigns button %u to %s", slot, name.c_str());
    if (candidate_kind_ == TargetKind::GROUP)
      continue_after_private_group_();
    else
      start_device_candidate_();
    return true;
  }

  // The HTTP task reads this while the main loop can write it.
  Targets targets() const {
    Targets snapshot;
    const std::lock_guard<std::mutex> lock(cache_mutex_);
    snapshot.ready =
        groups_ready_ && devices_ready_ && esphome::mqtt::global_mqtt_client->is_connected();
    snapshot.groups.reserve(groups_by_name_.size());
    for (const auto &group : groups_by_name_)
      snapshot.groups.emplace_back(group.second, group.first);
    std::sort(snapshot.groups.begin(), snapshot.groups.end(),
              [](const std::pair<uint16_t, std::string> &left,
                 const std::pair<uint16_t, std::string> &right) { return left.second < right.second; });
    snapshot.devices = devices_;
    return snapshot;
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
    {
      const std::lock_guard<std::mutex> lock(cache_mutex_);
      record_ = next;
    }
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

    // The retained device inventory carries a full definition for each device,
    // so it is parsed with a filter before any full document exists.
    if (relative == "bridge/devices") {
      cache_devices_(payload);
      return;
    }

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
    const std::lock_guard<std::mutex> lock(cache_mutex_);
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

  // The bridge device list feeds the /buttons target picker only. Training from
  // the remote still resolves a device through its state transition.
  //
  // The filter keeps three fields for each device. Without it the definition and
  // exposes blocks of a real network exhaust the heap.
  void cache_devices_(const std::string &payload) {
    JsonDocument filter;
    JsonObject fields = filter.add<JsonObject>();
    fields["friendly_name"] = true;
    fields["ieee_address"] = true;
    fields["type"] = true;

    JsonDocument document;
    if (deserializeJson(document, payload, DeserializationOption::Filter(filter)) !=
        DeserializationError::Ok)
      return;
    const JsonVariantConst root = document.as<JsonVariantConst>();
    if (!root.is<JsonArrayConst>())
      return;
    std::vector<Device> devices;
    for (JsonObjectConst device : root.as<JsonArrayConst>()) {
      if (devices.size() >= MAX_DEVICES)
        break;
      if (!device["friendly_name"].is<const char *>() || !device["ieee_address"].is<const char *>())
        continue;
      const char *type = device["type"] | "";
      if (std::strcmp(type, "Coordinator") == 0)
        continue;
      Device entry;
      entry.name = device["friendly_name"].as<const char *>();
      entry.ieee = device["ieee_address"].as<const char *>();
      if (entry.name.empty() || entry.ieee.empty() || entry.name.size() >= TARGET_SIZE)
        continue;
      devices.push_back(std::move(entry));
    }
    std::sort(devices.begin(), devices.end(),
              [](const Device &left, const Device &right) { return left.name < right.name; });
    const std::lock_guard<std::mutex> lock(cache_mutex_);
    devices_ = std::move(devices);
    devices_ready_ = true;
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
    start_device_candidate_();
  }

  // Puts the candidate device in the slot's reserved group. The caller has
  // already stored the device name or IEEE address in candidate_name_.
  void start_device_candidate_() {
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
      case Operation::WAIT_PRIVATE_GROUP_ADD: {
        const std::string private_name = private_group_name_(pending_slot_);
        {
          const std::lock_guard<std::mutex> lock(cache_mutex_);
          groups_by_name_[private_name] = candidate_group_id_;
          group_names_by_id_[candidate_group_id_] = private_name;
        }
        if (cancel_requested_)
          finish_error_();
        else
          continue_after_private_group_();
        break;
      }
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
    {
      const std::lock_guard<std::mutex> lock(cache_mutex_);
      record_ = next;
    }
    ESP_LOGI("zigbee_learn", "Button %u assigned to %s as Zigbee Toggle group 0x%04X", pending_slot_,
             candidate_name_.c_str(), candidate_group_id_);
    operation_ = Operation::IDLE;
    clear_candidate_();
    report_result_(true);
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
    report_result_(false);
  }

  // The remote gesture reads the result from the LED state machine. A web
  // assignment has no receiver mode open, so it answers the pending HTTP action.
  void report_result_(bool saved) {
    if (web_pending_) {
      web_pending_ = false;
      if (web_result_callback_)
        web_result_callback_(saved);
      return;
    }
    ir_ui.zigbee_result(saved);
  }

  static std::string trimmed_(const std::string &value) {
    const size_t begin = value.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos)
      return {};
    return value.substr(begin, value.find_last_not_of(" \t\r\n") - begin + 1);
  }

  // Accepts a decimal group ID, or "0x" and up to four hex digits. A longer hex
  // string is an IEEE address, so it stays a device target.
  static bool parse_group_id_(const std::string &target, uint16_t &group_id) {
    const bool hex = target.size() > 2 && target[0] == '0' && (target[1] == 'x' || target[1] == 'X');
    const std::string digits = hex ? target.substr(2) : target;
    if (digits.empty() || digits.size() > (hex ? 4u : 5u))
      return false;
    uint32_t value = 0;
    for (const char character : digits) {
      uint32_t digit;
      if (character >= '0' && character <= '9')
        digit = static_cast<uint32_t>(character - '0');
      else if (hex && character >= 'a' && character <= 'f')
        digit = static_cast<uint32_t>(character - 'a') + 10;
      else if (hex && character >= 'A' && character <= 'F')
        digit = static_cast<uint32_t>(character - 'A') + 10;
      else
        return false;
      value = value * (hex ? 16u : 10u) + digit;
    }
    if (value == 0 || value > UINT16_MAX)
      return false;
    group_id = static_cast<uint16_t>(value);
    return true;
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
  std::vector<Device> devices_;
  // The main loop owns every write. The HTTP task of the /buttons page reads the
  // caches and the record, so both sides hold this lock.
  mutable std::mutex cache_mutex_;
  std::function<void(bool)> web_result_callback_{};
  Operation operation_{Operation::IDLE};
  TargetKind candidate_kind_{TargetKind::NONE};
  uint8_t pending_slot_{0};
  std::string candidate_name_;
  uint16_t candidate_group_id_{0};
  uint32_t deadline_{0};
  uint32_t transaction_{0};
  uint32_t transaction_counter_{1000};
  bool groups_ready_{false};
  bool devices_ready_{false};
  bool candidate_member_added_{false};
  bool old_member_removed_{false};
  bool cancel_requested_{false};
  bool web_pending_{false};
};

inline ZigbeeAssignmentManager zigbee_assignments;
