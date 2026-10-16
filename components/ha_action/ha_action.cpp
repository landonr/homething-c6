#include "ha_action.h"

#include "esphome/components/api/api_connection.h"
#include "esphome/components/api/api_server.h"
#include "esphome/components/api/homeassistant_service.h"
#include "esphome/core/hal.h"
#include "esphome/core/log.h"
#include "esphome/core/string_ref.h"

#include "ir_learning.h"

#include <algorithm>
#include <cstdio>
#include <cstring>

namespace esphome::ha_action {

static const char *const TAG = "ha_action";

namespace {

struct KindDef {
  const char *name;
  uint8_t count;
  const char *acts[5];
};

const KindDef KINDS[] = {
    {"light", 5, {"toggle", "turn_on", "turn_off", "brightness_up", "brightness_down"}},
    {"switch", 3, {"toggle", "turn_on", "turn_off"}},
    {"input_boolean", 3, {"toggle", "turn_on", "turn_off"}},
    {"fan", 5, {"toggle", "turn_on", "turn_off", "increase_speed", "decrease_speed"}},
    {"cover", 4, {"toggle", "open_cover", "close_cover", "stop_cover"}},
    {"lock", 2, {"lock", "unlock"}},
    {"scene", 1, {"turn_on"}},
    {"script", 2, {"turn_on", "toggle"}},
    {"automation", 2, {"trigger", "toggle"}},
    {"button", 1, {"press"}},
    {"input_button", 1, {"press"}},
    {"media_player",
     5,
     {"media_play_pause", "volume_up", "volume_down", "media_next_track", "media_previous_track"}},
    {"homeassistant", 3, {"toggle", "turn_on", "turn_off"}},
};
constexpr size_t KIND_COUNT = sizeof(KINDS) / sizeof(KINDS[0]);
constexpr const char *ANY_DOMAIN_KIND = "homeassistant";

bool resolve(const std::string &kind, const std::string &act, uint8_t &kind_index, uint8_t &act_index) {
  for (size_t k = 0; k < KIND_COUNT; k++) {
    if (kind != KINDS[k].name)
      continue;
    for (uint8_t a = 0; a < KINDS[k].count; a++) {
      if (act == KINDS[k].acts[a]) {
        kind_index = static_cast<uint8_t>(k);
        act_index = a;
        return true;
      }
    }
    return false;
  }
  return false;
}

bool is_step(uint8_t kind_index, uint8_t act_index) {
  return std::strcmp(KINDS[kind_index].name, "light") == 0 &&
         std::strncmp(KINDS[kind_index].acts[act_index], "brightness_", 11) == 0;
}

bool object_char(char value) {
  return (value >= 'a' && value <= 'z') || (value >= '0' && value <= '9') || value == '_';
}

// domain.object_id, each part lower case letters, digits and underscores.
bool entity_valid(const char *text, size_t length, const char *domain_must_be) {
  if (length < 3 || length > HaAction::ENTITY_MAX)
    return false;
  size_t dot = length;
  for (size_t i = 0; i < length; i++) {
    if (text[i] == '.') {
      if (dot != length)
        return false;
      dot = i;
    } else if (!object_char(text[i])) {
      return false;
    }
  }
  if (dot == length || dot == 0 || dot == length - 1)
    return false;
  if (domain_must_be == nullptr)
    return true;
  return std::strlen(domain_must_be) == dot && std::strncmp(text, domain_must_be, dot) == 0;
}

}  // namespace

HaAction::Check HaAction::validate(const std::string &kind, const std::string &act, int val,
                                   const std::string &entity) {
  uint8_t kind_index = 0;
  uint8_t act_index = 0;
  if (!resolve(kind, act, kind_index, act_index))
    return Check::BAD_ACTION;
  const bool any_domain = kind == ANY_DOMAIN_KIND;
  if (!entity_valid(entity.c_str(), entity.size(), any_domain ? nullptr : KINDS[kind_index].name))
    return Check::BAD_ENTITY;
  if (val < 0 || val > 100 || (is_step(kind_index, act_index) && val < 1))
    return Check::BAD_STEP;
  return Check::OK;
}

const char *HaAction::result_name(uint8_t result) {
  switch (result) {
    case RESULT_QUEUED: return "queued";
    case RESULT_SENT: return "sent";
    case RESULT_OK: return "ok";
    case RESULT_ERROR: return "error";
    case RESULT_UNCONFIRMED: return "unconfirmed";
    case RESULT_TIMEOUT: return "timeout";
    case RESULT_DROPPED: return "dropped";
    default: return "none";
  }
}

uint32_t HaAction::checksum_(const Record &record) {
  const auto *bytes = reinterpret_cast<const uint8_t *>(&record);
  uint32_t hash = 2166136261U;
  for (size_t i = 0; i < sizeof(record) - sizeof(record.checksum); i++) {
    hash ^= bytes[i];
    hash *= 16777619U;
  }
  return hash;
}

bool HaAction::valid_(const Record &record) {
  if (record.magic != MAGIC || record.version != VERSION || record.checksum != checksum_(record))
    return false;
  if ((record.mask >> SLOT_COUNT) != 0)
    return false;
  for (size_t index = 0; index < SLOT_COUNT; index++) {
    if ((record.mask & (1UL << index)) == 0)
      continue;
    const Entry &entry = record.entries[index];
    if (entry.kind >= KIND_COUNT || entry.act >= KINDS[entry.kind].count || entry.val > 100 ||
        (is_step(entry.kind, entry.act) && entry.val < 1) || entry.entity[ENTITY_MAX + 1] != '\0')
      return false;
    if (!entity_valid(entry.entity, strnlen(entry.entity, ENTITY_SIZE),
                      std::strcmp(KINDS[entry.kind].name, ANY_DOMAIN_KIND) == 0 ? nullptr : KINDS[entry.kind].name))
      return false;
  }
  return true;
}

void HaAction::setup() {
  this->pref_ = global_preferences->make_preference<Record>(PREFERENCE_KEY, true);
  Record loaded{};
  if (this->pref_.load(&loaded) && valid_(loaded)) {
    this->record_ = loaded;
  } else {
    std::memset(&this->record_, 0, sizeof(this->record_));
    this->record_.magic = MAGIC;
    this->record_.version = VERSION;
    this->record_.checksum = checksum_(this->record_);
  }

  ::ir_code_store.add_assignment_clear_callback([this](uint8_t slot, IrCodeStore::Owner keep) {
    if (keep != IrCodeStore::OWNER_HA)
      this->clear(slot);
  });
  ::ir_ui.set_ha_play_callback([this](uint8_t slot) { return this->play(slot); });
  ESP_LOGI(TAG, "Loaded Home Assistant action mask 0x%05X", static_cast<unsigned>(this->record_.mask));
}

void HaAction::dump_config() {
  ESP_LOGCONFIG(TAG, "Home Assistant actions, mask 0x%05X", static_cast<unsigned>(this->record_.mask));
}

bool HaAction::has_assignment(uint8_t slot) const {
  if (!slot_valid(slot))
    return false;
  const std::lock_guard<std::mutex> lock(this->record_mutex_);
  return (this->record_.mask & (1UL << (slot - FIRST_SLOT))) != 0;
}

HaAction::Assignment HaAction::assignment(uint8_t slot) const {
  Assignment result;
  if (!slot_valid(slot))
    return result;
  const std::lock_guard<std::mutex> lock(this->record_mutex_);
  const size_t index = slot - FIRST_SLOT;
  if ((this->record_.mask & (1UL << index)) == 0)
    return result;
  const Entry &entry = this->record_.entries[index];
  result.assigned = true;
  result.kind = KINDS[entry.kind].name;
  result.act = KINDS[entry.kind].acts[entry.act];
  result.val = entry.val;
  result.entity = entry.entity;
  return result;
}

// The caller built next from record_, so the swap and the write stay together.
bool HaAction::store_(const Record &next) {
  {
    const std::lock_guard<std::mutex> lock(this->record_mutex_);
    this->record_ = next;
  }
  if (!this->pref_.save(&this->record_)) {
    ESP_LOGE(TAG, "Failed to save the Home Assistant actions");
    return false;
  }
  return true;
}

bool HaAction::assign(uint8_t slot, const std::string &kind, const std::string &act, int val,
                      const std::string &entity) {
  if (!slot_valid(slot) || validate(kind, act, val, entity) != Check::OK)
    return false;
  uint8_t kind_index = 0;
  uint8_t act_index = 0;
  resolve(kind, act, kind_index, act_index);

  if (!::ir_code_store.clear_for_zigbee(slot)) {
    ESP_LOGE(TAG, "Failed to clear the old action on button %u", slot);
    return false;
  }
  ::ir_code_store.release_others(slot, IrCodeStore::OWNER_HA);

  Record next = this->record_;
  const size_t index = slot - FIRST_SLOT;
  Entry &entry = next.entries[index];
  std::memset(&entry, 0, sizeof(entry));
  entry.kind = kind_index;
  entry.act = act_index;
  entry.val = static_cast<uint8_t>(val);
  std::memcpy(entry.entity, entity.data(), entity.size());
  next.mask |= 1UL << index;
  next.checksum = checksum_(next);
  ESP_LOGI(TAG, "Button %u sends %s.%s to %s", slot, KINDS[kind_index].name,
           KINDS[kind_index].acts[act_index], entity.c_str());
  return this->store_(next);
}

void HaAction::clear(uint8_t slot) {
  if (!this->has_assignment(slot))
    return;
  Record next = this->record_;
  const size_t index = slot - FIRST_SLOT;
  next.mask &= ~(1UL << index);
  std::memset(&next.entries[index], 0, sizeof(next.entries[index]));
  next.checksum = checksum_(next);
  this->store_(next);
  ESP_LOGI(TAG, "Cleared Home Assistant button %u", slot);
}

void HaAction::set_result_(uint8_t slot, Result result, const char *error) {
  {
    const std::lock_guard<std::mutex> lock(this->error_mutex_);
    size_t length = std::min(std::strlen(error), ERROR_MAX);
    // Do not cut a multibyte character in half.
    while (length > 0 && (static_cast<uint8_t>(error[length]) & 0xC0) == 0x80)
      length--;
    std::memcpy(this->error_, error, length);
    this->error_[length] = '\0';
  }
  this->last_slot_.store(slot, std::memory_order_relaxed);
  this->last_result_.store(result, std::memory_order_relaxed);
  if (result == RESULT_ERROR || result == RESULT_TIMEOUT) {
    this->failed_at_ms_.store(millis(), std::memory_order_relaxed);
    this->failed_.store(true, std::memory_order_relaxed);
  }
}

void HaAction::last_error(std::string &text) const {
  const std::lock_guard<std::mutex> lock(this->error_mutex_);
  text = this->error_;
}

bool HaAction::failed_recently() const {
  return this->failed_.load(std::memory_order_relaxed) &&
         millis() - this->failed_at_ms_.load(std::memory_order_relaxed) < FAIL_SHOW_MS;
}

void HaAction::request_wifi_() {
  if (this->wifi_hold_)
    this->wifi_hold_();
}

bool HaAction::play(uint8_t slot) {
  if (!this->has_assignment(slot))
    return false;
  if (this->count_ >= QUEUE_MAX) {
    ESP_LOGW(TAG, "Button %u dropped: %u actions already wait", slot, static_cast<unsigned>(this->count_));
    this->set_result_(slot, RESULT_DROPPED, "");
    return true;
  }
  const size_t index = slot - FIRST_SLOT;
  Pending &entry = this->queue_[this->count_];
  std::memset(&entry, 0, sizeof(entry));
  {
    const std::lock_guard<std::mutex> lock(this->record_mutex_);
    const Entry &stored = this->record_.entries[index];
    entry.kind = stored.kind;
    entry.act = stored.act;
    entry.val = stored.val;
    std::memcpy(entry.entity, stored.entity, sizeof(entry.entity));
  }
  entry.slot = slot;
  entry.queued_ms = millis();
  this->count_++;
  this->pending_.store(this->count_, std::memory_order_relaxed);
  this->set_result_(slot, RESULT_QUEUED, "");
  this->request_wifi_();
  ESP_LOGI(TAG, "Button %u queued %s.%s", slot, KINDS[entry.kind].name, KINDS[entry.kind].acts[entry.act]);
  return true;
}

void HaAction::finish_(size_t index, Result result, const char *error) {
  const uint8_t slot = this->queue_[index].slot;
  // Its callback stays registered until a late reply removes it.
  if (result == RESULT_UNCONFIRMED && this->queue_[index].call_id != 0)
    this->stale_callbacks_++;
  for (size_t i = index + 1; i < this->count_; i++)
    this->queue_[i - 1] = this->queue_[i];
  this->count_--;
  this->pending_.store(this->count_, std::memory_order_relaxed);
  this->set_result_(slot, result, error);
  ESP_LOGI(TAG, "Button %u finished: %s %s", slot, result_name(result), error);
  // The Wi-Fi lease counts from the last action that finished.
  this->request_wifi_();
}

void HaAction::on_response_(uint32_t call_id, bool success, const char *error) {
  for (size_t i = 0; i < this->count_; i++) {
    if (this->queue_[i].sent && this->queue_[i].call_id == call_id) {
      this->finish_(i, success ? RESULT_OK : RESULT_ERROR, success ? "" : error);
      return;
    }
  }
  // A late reply to a call that already finished as unconfirmed.
  if (this->stale_callbacks_ > 0)
    this->stale_callbacks_--;
}

bool HaAction::send_(Pending &entry) {
  api::APIServer *server = api::global_api_server;
  if (server == nullptr)
    return false;

  const KindDef &def = KINDS[entry.kind];
  const char *act = def.acts[entry.act];
  const bool step = is_step(entry.kind, entry.act);
  // A brightness step is light.turn_on with brightness_step_pct.
  char service[48];
  std::snprintf(service, sizeof(service), "%s.%s", def.name, step ? "turn_on" : act);
  char amount[8] = "";
  if (step)
    std::snprintf(amount, sizeof(amount), "%s%u", std::strcmp(act, "brightness_down") == 0 ? "-" : "",
                  static_cast<unsigned>(entry.val));

  // Call id 0 asks for no reply, so past STALE_MAX leaked callbacks a send
  // registers none. Home Assistant sends no reply for it.
  const bool untracked = this->stale_callbacks_ >= STALE_MAX;
  const uint32_t call_id = untracked ? 0 : this->next_call_id_;
  api::HomeassistantActionRequest request;
  request.service = StringRef(service);
  request.data.init(step ? 2 : 1);
  auto &target = request.data.emplace_back();
  target.key = StringRef::from_lit("entity_id");
  target.value = StringRef(entry.entity);
  if (step) {
    auto &brightness = request.data.emplace_back();
    brightness.key = StringRef::from_lit("brightness_step_pct");
    brightness.value = StringRef(amount);
  }
  request.call_id = call_id;

  bool sent = false;
  for (auto &client : server->active_clients())
    sent |= client->send_homeassistant_action(request);
  if (!sent)
    return false;
  if (untracked) {
    entry.sent = true;
    entry.call_id = 0;
    entry.sent_ms = millis();
    ESP_LOGI(TAG, "Button %u sent %s for %s without a reply callback", entry.slot, service, entry.entity);
    return true;
  }

  // Same loop turn as the send, so no reply can arrive before the callback
  // exists, and an unsent call never registers one.
  this->next_call_id_++;
  server->register_action_response_callback(call_id, [this, call_id](const api::ActionResponse &response) {
    // The reference points into the protobuf message and has no terminator.
    const StringRef &message = response.get_error_message();
    const size_t length = std::min(message.size(), ERROR_MAX);
    char error[ERROR_MAX + 1];
    std::memcpy(error, message.c_str(), length);
    error[length] = '\0';
    this->on_response_(call_id, response.is_success(), error);
  });
  entry.sent = true;
  entry.call_id = call_id;
  entry.sent_ms = millis();
  this->set_result_(entry.slot, RESULT_SENT, "");
  ESP_LOGI(TAG, "Button %u sent %s for %s", entry.slot, service, entry.entity);
  return true;
}

void HaAction::loop() {
  if (this->count_ == 0)
    return;
  const uint32_t now = millis();
  for (size_t i = 0; i < this->count_;) {
    const Pending &entry = this->queue_[i];
    if (!entry.sent && now - entry.queued_ms >= QUEUE_TIMEOUT_MS) {
      this->finish_(i, RESULT_TIMEOUT, "");
    } else if (entry.sent && now - entry.sent_ms >= REPLY_TIMEOUT_MS) {
      this->finish_(i, RESULT_UNCONFIRMED, "");
    } else {
      i++;
    }
  }
  // Entries go out in press order, so one that cannot go blocks the rest.
  for (size_t i = 0; i < this->count_;) {
    if (this->queue_[i].sent) {
      i++;
      continue;
    }
    if (!this->send_(this->queue_[i]))
      break;
    // An untracked call has no reply to wait for, so it finishes at once.
    if (this->queue_[i].call_id == 0)
      this->finish_(i, RESULT_UNCONFIRMED, "");
    else
      i++;
  }
  if (this->count_ != 0)
    this->request_wifi_();
}

}  // namespace esphome::ha_action
