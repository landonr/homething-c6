#include "button_config.h"
#include "button_config_page.h"

#include "esphome/core/log.h"

#include "ir_learning.h"

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

namespace esphome::button_config {

static const char *const TAG = "button_config";

static const SlotInfo SLOTS[] = {
    {3, true},   {4, true},   {5, true},  {6, true},  {7, true},  {8, true},
    {9, true},   {10, true},  {11, true}, {12, true}, {13, true}, {14, true},
    {15, true},  {16, true},  {17, false},  // wheel clockwise
    {18, false},                            // wheel anticlockwise
    {19, false},                            // SW2 owns the receiver-mode hold
    {20, true},
};

static const SlotInfo *find_slot(long slot) {
  for (const auto &info : SLOTS) {
    if (info.slot == slot)
      return &info;
  }
  return nullptr;
}

static const SlotInfo *parse_slot(const std::string &text) {
  char *end = nullptr;
  const long slot = std::strtol(text.c_str(), &end, 10);
  if (text.empty() || end == text.c_str() || *end != '\0')
    return nullptr;
  return find_slot(slot);
}

// Accepts the text that /buttons/api/code prints: signed microsecond values in
// any bracket or separator style. A mark is positive and a space is negative,
// and the two must alternate from a mark, which rejects a truncated paste.
static bool parse_timings(const std::string &text, std::vector<int32_t> &raw) {
  raw.clear();
  const char *cursor = text.c_str();
  while (*cursor != '\0') {
    while (*cursor != '\0' && *cursor != '-' && *cursor != '+' && (*cursor < '0' || *cursor > '9'))
      cursor++;
    if (*cursor == '\0')
      break;
    char *end = nullptr;
    const long value = std::strtol(cursor, &end, 10);
    if (end == cursor)
      return false;
    cursor = end;
    if (value == 0 || value < -327670 || value > 327670)
      return false;
    if (raw.size() >= IrCodeStore::MAX_PULSES)
      return false;
    if ((raw.size() % 2 == 0) != (value > 0))
      return false;
    raw.push_back(static_cast<int32_t>(value));
  }
  return raw.size() >= 4 && raw.size() % 2 == 0;
}

static const char *state_name(uint8_t state) {
  switch (state) {
    case IrUi::READY:
      return "ready";
    case IrUi::READING:
      return "reading";
    case IrUi::SAVED:
      return "saved";
    case IrUi::ERROR:
      return "error";
    case IrUi::VOICE:
      return "voice";
    case IrUi::CLEARED:
      return "cleared";
    default:
      return "off";
  }
}

static const char *result_name(uint8_t result) {
  switch (result) {
    case IrUi::SAVED:
      return "saved";
    case IrUi::ERROR:
      return "error";
    default:
      return "none";
  }
}

void ButtonConfig::setup() {
  this->base_->init();
  this->base_->add_handler(this);
}

void ButtonConfig::dump_config() { ESP_LOGCONFIG(TAG, "Button config page at /buttons"); }

// init() starts the HTTP server, which asserts if it runs before the network is
// up. WebServer uses WIFI - 1.0f, so stay just behind it and reuse its server.
float ButtonConfig::get_setup_priority() const { return setup_priority::WIFI - 2.0f; }

bool ButtonConfig::canHandle(AsyncWebServerRequest *request) const {
  char url_buf[AsyncWebServerRequest::URL_BUF_SIZE];
  const StringRef url = request->url_to(url_buf);
  const http_method method = request->method();
  if (method == HTTP_GET)
    return url == "/buttons" || url == "/buttons/api/state" || url == "/buttons/api/code";
  if (method == HTTP_POST)
    return url == "/buttons/api/action";
  return false;
}

void ButtonConfig::handleRequest(AsyncWebServerRequest *request) {
  char url_buf[AsyncWebServerRequest::URL_BUF_SIZE];
  const StringRef url = request->url_to(url_buf);
  if (url == "/buttons/api/state") {
    this->handle_state_(request);
  } else if (url == "/buttons/api/code") {
    this->handle_code_(request);
  } else if (url == "/buttons/api/action") {
    this->handle_action_(request);
  } else {
    this->handle_page_(request);
  }
}

void ButtonConfig::handle_page_(AsyncWebServerRequest *request) {
  request->send(200, "text/html; charset=utf-8", PAGE_HTML);
}

// Reads only, so it runs on the httpd task without a defer.
void ButtonConfig::handle_state_(AsyncWebServerRequest *request) {
  const bool action_pending = this->action_pending_.load(std::memory_order_acquire);
  const bool busy = action_pending || ::ir_ui.state != IrUi::OFF;
  const char *owner = !busy ? "none" : (::ir_ui.web_owner() ? "web" : "device");
  const uint32_t completed_id = this->completed_action_id_.load(std::memory_order_acquire);

  AsyncResponseStream *stream = request->beginResponseStream("application/json");
  stream->printf(
      R"({"busy":%s,"owner":"%s","saves":%u,"op_slot":%u,"op_state":"%s","result_slot":%u,"result":"%s","action_id":%u,"action_ok":%s,"slots":[)",
      busy ? "true" : "false", owner, static_cast<unsigned>(::ir_code_store.saves()),
      static_cast<unsigned>(::ir_ui.target), state_name(::ir_ui.state),
      static_cast<unsigned>(::ir_ui.web_result_slot()), result_name(::ir_ui.web_result()),
      static_cast<unsigned>(completed_id), this->completed_action_ok_.load(std::memory_order_relaxed) ? "true" : "false");
  bool first = true;
  for (const auto &info : SLOTS) {
    const char *action = ::ir_code_store.is_voice(info.slot) ? "voice"
                         : ::ir_code_store.has_code(info.slot) ? "ir"
                                                               : "none";
    // Hex only, so it needs no JSON escape.
    char code[12] = "";
    uint32_t samsung = 0;
    if (::ir_code_store.code_samsung_data(info.slot, samsung))
      std::snprintf(code, sizeof(code), "0x%08X", static_cast<unsigned>(samsung));
    stream->printf(R"(%s{"slot":%u,"action":"%s","pulses":%u,"us":%u,"code":"%s"})",
                   first ? "" : ",", static_cast<unsigned>(info.slot), action,
                   static_cast<unsigned>(::ir_code_store.code_pulses(info.slot)),
                   static_cast<unsigned>(::ir_code_store.code_duration_us(info.slot)), code);
    first = false;
  }
  stream->print("]}");
  request->send(stream);
}

// Reads only, so it runs on the httpd task without a defer. The page prints
// these timings so a code can be copied to another board or edited by hand.
void ButtonConfig::handle_code_(AsyncWebServerRequest *request) {
  const SlotInfo *info = parse_slot(request->arg("slot"));
  if (info == nullptr) {
    request->send(400, "application/json", R"({"ok":false,"error":"invalid slot"})");
    return;
  }
  std::vector<int32_t> raw;
  const bool present = ::ir_code_store.code_timings(info->slot, raw);
  AsyncResponseStream *stream = request->beginResponseStream("application/json");
  stream->printf(R"({"slot":%u,"present":%s,"timings":[)", static_cast<unsigned>(info->slot),
                 present ? "true" : "false");
  for (size_t i = 0; i < raw.size(); i++)
    stream->printf(i == 0 ? "%d" : ",%d", static_cast<int>(raw[i]));
  stream->print("]}");
  request->send(stream);
}

// The store and the state machine are main-loop owned, so every mutation is
// deferred off the httpd task. NVS writes from the httpd task would race.
void ButtonConfig::handle_action_(AsyncWebServerRequest *request) {
  const std::string action = request->arg("action");
  if (action.empty()) {
    request->send(400, "application/json", R"({"ok":false,"error":"missing action"})");
    return;
  }

  if (action == "cancel") {
    if (this->action_pending_.load(std::memory_order_acquire) || ::ir_ui.state != IrUi::OFF)
      this->defer([]() { ::ir_ui.close(); });
    ESP_LOGI(TAG, "Web cancelled the assignment operation");
    request->send(200, "application/json", R"({"ok":true})");
    return;
  }

  const bool known = action == "record_ir" || action == "set_voice" || action == "set_ir_code" ||
                     action == "clear";
  if (!known) {
    request->send(400, "application/json", R"({"ok":false,"error":"unknown action"})");
    return;
  }

  const SlotInfo *info = parse_slot(request->arg("slot"));
  if (info == nullptr) {
    request->send(400, "application/json", R"({"ok":false,"error":"invalid slot"})");
    return;
  }
  if (action == "set_voice" && !info->voice) {
    request->send(400, "application/json", R"({"ok":false,"error":"slot has no voice action"})");
    return;
  }

  // The request dies before the defer runs, so the pasted text is parsed here.
  std::vector<int32_t> timings;
  if (action == "set_ir_code" && !parse_timings(request->arg("code"), timings)) {
    request->send(400, "application/json",
                  R"({"ok":false,"error":"a code is 4 to 512 alternating values in us, from a positive mark"})");
    return;
  }

  bool expected = false;
  if (::ir_ui.state != IrUi::OFF ||
      !this->action_pending_.compare_exchange_strong(expected, true, std::memory_order_acq_rel)) {
    request->send(409, "application/json", R"({"ok":false,"error":"busy"})");
    return;
  }
  if (::ir_ui.state != IrUi::OFF) {
    this->action_pending_.store(false, std::memory_order_release);
    request->send(409, "application/json", R"({"ok":false,"error":"busy"})");
    return;
  }

  const uint8_t button = info->slot;
  const uint32_t action_id = this->next_action_id_.fetch_add(1, std::memory_order_relaxed) + 1;
  if (action == "record_ir") {
    this->defer([this, button, action_id]() {
      ::ir_ui.open_from_web(button);
      this->complete_action_(action_id, true);
    });
  } else if (action == "set_voice") {
    this->defer([this, button, action_id]() {
      this->complete_action_(action_id, ::ir_code_store.set_voice(button));
    });
  } else if (action == "set_ir_code") {
    this->defer([this, button, action_id, timings]() {
      this->complete_action_(action_id, ::ir_code_store.save(button, timings));
    });
  } else {
    this->defer([this, button, action_id]() {
      this->complete_action_(action_id, ::ir_code_store.clear(button));
    });
  }
  ESP_LOGI(TAG, "Web action %s on slot %u", action.c_str(), static_cast<unsigned>(button));
  char response[32];
  std::snprintf(response, sizeof(response), R"({"ok":true,"id":%u})", static_cast<unsigned>(action_id));
  request->send(200, "application/json", response);
}

void ButtonConfig::complete_action_(uint32_t id, bool ok) {
  this->completed_action_ok_.store(ok, std::memory_order_relaxed);
  this->completed_action_id_.store(id, std::memory_order_release);
  this->action_pending_.store(false, std::memory_order_release);
}

}  // namespace esphome::button_config
