#pragma once

#include "esphome/core/component.h"
#include "esphome/core/preferences.h"

#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <mutex>
#include <string>

namespace esphome::ha_action {

// One Home Assistant action for each assignable slot. A press queues the action,
// asks for Wi-Fi, and sends it over the native API once Home Assistant has
// subscribed to actions. Home Assistant needs "Allow the device to perform Home
// Assistant actions" on the ESPHome integration, or it ignores the request.
class HaAction final : public Component {
 public:
  static constexpr uint8_t FIRST_SLOT = 3;
  static constexpr uint8_t LAST_SLOT = 20;
  static constexpr size_t SLOT_COUNT = LAST_SLOT - FIRST_SLOT + 1;
  static constexpr size_t ENTITY_MAX = 64;
  static constexpr size_t QUEUE_MAX = 8;
  static constexpr size_t ERROR_MAX = 96;
  // A press that finds no subscribed client for this long is dropped.
  static constexpr uint32_t QUEUE_TIMEOUT_MS = 20000;
  // Old Home Assistant versions, and an integration that does not allow actions,
  // send no reply.
  static constexpr uint32_t REPLY_TIMEOUT_MS = 5000;
  static constexpr uint32_t FAIL_SHOW_MS = 2000;
  // Registered reply callbacks that no reply has removed. Past this a send registers none.
  static constexpr size_t STALE_MAX = 8;

  enum Result : uint8_t {
    RESULT_NONE = 0,
    RESULT_QUEUED,
    RESULT_SENT,
    RESULT_OK,
    RESULT_ERROR,
    RESULT_UNCONFIRMED,
    RESULT_TIMEOUT,
    RESULT_DROPPED,
  };

  enum class Check : uint8_t { OK, BAD_ACTION, BAD_ENTITY, BAD_STEP };

  struct Assignment {
    bool assigned{false};
    const char *kind{""};
    const char *act{""};
    uint8_t val{0};
    std::string entity;
  };

  void setup() override;
  void loop() override;
  void dump_config() override;

  // The token tables are the contract with the /buttons page. val is -1 when the
  // page sent something that is not an integer.
  static Check validate(const std::string &kind, const std::string &act, int val,
                        const std::string &entity);
  static bool slot_valid(uint8_t slot) { return slot >= FIRST_SLOT && slot <= LAST_SLOT; }
  static const char *result_name(uint8_t result);

  // Main loop only.
  bool assign(uint8_t slot, const std::string &kind, const std::string &act, int val,
              const std::string &entity);
  void clear(uint8_t slot);
  bool play(uint8_t slot);

  // The HTTP task reads these while the main loop writes.
  Assignment assignment(uint8_t slot) const;
  bool has_assignment(uint8_t slot) const;
  size_t pending() const { return this->pending_.load(std::memory_order_relaxed); }
  uint8_t last_slot() const { return this->last_slot_.load(std::memory_order_relaxed); }
  uint8_t last_result() const { return this->last_result_.load(std::memory_order_relaxed); }
  void last_error(std::string &text) const;
  bool busy() const { return this->pending() != 0; }
  bool failed_recently() const;

  // The Wi-Fi owner registers this. It must enable Wi-Fi and extend its lease.
  void set_wifi_hold(std::function<void()> hold) { this->wifi_hold_ = std::move(hold); }

 protected:
  static constexpr uint32_t MAGIC = 0x48414131U;
  static constexpr uint16_t VERSION = 1;
  // 'HAA1' record under key 'HAAC'.
  static constexpr uint32_t PREFERENCE_KEY = 0x48414143U;
  static constexpr size_t ENTITY_SIZE = ENTITY_MAX + 2;
  // Keeps the ids clear of the ones ESPHome's own homeassistant.action hands out.
  static constexpr uint32_t CALL_ID_BASE = 0x48410000U;

  struct Entry {
    uint8_t kind;
    uint8_t act;
    uint8_t val;
    uint8_t reserved;
    char entity[ENTITY_SIZE];
  };

  struct Record {
    uint32_t magic;
    uint16_t version;
    uint16_t reserved;
    uint32_t mask;
    Entry entries[SLOT_COUNT];
    uint32_t checksum;
  };
  static_assert(sizeof(Record) == 12 + SLOT_COUNT * sizeof(Entry) + 4,
                "the checksum covers the record, so it must have no padding");

  struct Pending {
    uint8_t slot;
    uint8_t kind;
    uint8_t act;
    uint8_t val;
    bool sent;
    uint32_t call_id;
    uint32_t queued_ms;
    uint32_t sent_ms;
    char entity[ENTITY_SIZE];
  };

  static uint32_t checksum_(const Record &record);
  static bool valid_(const Record &record);
  bool store_(const Record &next);
  bool send_(Pending &entry);
  void finish_(size_t index, Result result, const char *error);
  void on_response_(uint32_t call_id, bool success, const char *error);
  void set_result_(uint8_t slot, Result result, const char *error);
  void request_wifi_();

  ESPPreferenceObject pref_;
  Record record_{};
  mutable std::mutex record_mutex_;
  std::array<Pending, QUEUE_MAX> queue_{};
  size_t count_{0};
  uint32_t next_call_id_{CALL_ID_BASE};
  size_t stale_callbacks_{0};
  std::atomic<size_t> pending_{0};
  std::atomic<uint8_t> last_slot_{0};
  std::atomic<uint8_t> last_result_{RESULT_NONE};
  std::atomic<uint32_t> failed_at_ms_{0};
  std::atomic<bool> failed_{false};
  mutable std::mutex error_mutex_;
  char error_[ERROR_MAX + 1]{};
  std::function<void()> wifi_hold_{};
};

}  // namespace esphome::ha_action
