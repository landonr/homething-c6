#include "button_config.h"
#include "button_config_page.h"

#include "esphome/core/log.h"

#include "ir_learning.h"

#include <algorithm>
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

// Accepts a bare list of signed microsecond values in any bracket or separator
// style. A mark is positive and a space is negative, and the two must alternate
// from a mark, which rejects a truncated paste.
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

static std::string trim(const std::string &text) {
  size_t start = 0;
  size_t end = text.size();
  while (start < end && (text[start] == ' ' || text[start] == '\t' || text[start] == '\r'))
    start++;
  while (end > start && (text[end - 1] == ' ' || text[end - 1] == '\t' || text[end - 1] == '\r'))
    end--;
  return text.substr(start, end - start);
}

static bool lower_equals(const std::string &text, const char *want) {
  size_t i = 0;
  for (; i < text.size() && want[i] != '\0'; i++) {
    char value = text[i];
    if (value >= 'A' && value <= 'Z')
      value = static_cast<char>(value + ('a' - 'A'));
    char other = want[i];
    if (other >= 'A' && other <= 'Z')
      other = static_cast<char>(other + ('a' - 'A'));
    if (value != other)
      return false;
  }
  return i == text.size() && want[i] == '\0';
}

// A Flipper field holds four little endian bytes, of which Samsung32 uses one.
static bool parse_leading_byte(const std::string &text, uint8_t &value) {
  const std::string field = trim(text);
  if (field.size() < 2)
    return false;
  char *end = nullptr;
  const long parsed = std::strtol(field.substr(0, 2).c_str(), &end, 16);
  if (end == nullptr || *end != '\0' || parsed < 0 || parsed > 0xFF)
    return false;
  value = static_cast<uint8_t>(parsed);
  return true;
}

// A Flipper raw line holds unsigned durations that alternate from a mark. The
// last value is a mark, so the count is odd in every Flipper-IRDB file.
static bool parse_raw_data(const std::string &text, std::vector<int32_t> &raw) {
  raw.clear();
  const char *cursor = text.c_str();
  while (*cursor != '\0') {
    while (*cursor == ' ' || *cursor == '\t' || *cursor == '\r')
      cursor++;
    if (*cursor == '\0')
      break;
    char *end = nullptr;
    const long value = std::strtol(cursor, &end, 10);
    if (end == cursor)
      return false;
    cursor = end;
    if (value < 1 || value > 327670)
      return false;
    if (raw.size() >= IrCodeStore::MAX_PULSES)
      return false;
    raw.push_back(raw.size() % 2 == 0 ? static_cast<int32_t>(value) : -static_cast<int32_t>(value));
  }
  return raw.size() >= 4;
}

// Reads one signal of a Flipper .ir file, so a code from Flipper-IRDB pastes in
// unchanged. A file holds many signals, and only the first one is taken. A bare
// list of signed values still parses, which keeps an older copy usable.
static bool parse_ir_text(const std::string &text, std::string &name, std::vector<int32_t> &raw) {
  name.clear();
  raw.clear();
  std::string type;
  std::string protocol;
  std::string data;
  bool have_address = false;
  bool have_command = false;
  uint8_t address = 0;
  uint8_t command = 0;
  bool keyed = false;
  bool named = false;

  size_t line_start = 0;
  while (line_start <= text.size()) {
    const size_t line_end = std::min(text.find('\n', line_start), text.size());
    const std::string line = trim(text.substr(line_start, line_end - line_start));
    line_start = line_end + 1;
    if (line.empty() || line[0] == '#')
      continue;
    const size_t colon = line.find(':');
    if (colon == std::string::npos)
      continue;
    const std::string key = trim(line.substr(0, colon));
    const std::string value = trim(line.substr(colon + 1));
    if (lower_equals(key, "filetype") || lower_equals(key, "version"))
      continue;
    if (lower_equals(key, "name")) {
      // The next name line starts the next signal of the file.
      if (named)
        break;
      name = value;
      named = true;
      keyed = true;
    } else if (lower_equals(key, "type")) {
      type = value;
      keyed = true;
    } else if (lower_equals(key, "protocol")) {
      protocol = value;
      keyed = true;
    } else if (lower_equals(key, "address")) {
      have_address = parse_leading_byte(value, address);
      keyed = true;
    } else if (lower_equals(key, "command")) {
      have_command = parse_leading_byte(value, command);
      keyed = true;
    } else if (lower_equals(key, "data")) {
      data = value;
      keyed = true;
    }
  }

  if (!keyed)
    return parse_timings(text, raw);
  if (lower_equals(type, "parsed")) {
    if (!lower_equals(protocol, "samsung32") || !have_address || !have_command)
      return false;
    IrCodeStore::samsung_timings(address, command, raw);
    return true;
  }
  if (lower_equals(type, "raw"))
    return parse_raw_data(data, raw);
  return false;
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
    // Hex only, so it needs no JSON escape. set_name() keeps a name printable.
    char code[12] = "";
    char fields[8] = "";
    uint32_t samsung = 0;
    uint8_t address = 0;
    uint8_t command = 0;
    if (::ir_code_store.code_samsung_data(info.slot, samsung))
      std::snprintf(code, sizeof(code), "0x%08X", static_cast<unsigned>(samsung));
    if (::ir_code_store.code_samsung_fields(info.slot, address, command))
      std::snprintf(fields, sizeof(fields), "%02X %02X", address, command);
    stream->printf(R"(%s{"slot":%u,"action":"%s","name":"%s","pulses":%u,"us":%u,"code":"%s","fields":"%s"})",
                   first ? "" : ",", static_cast<unsigned>(info.slot), action,
                   ::ir_code_store.name(info.slot),
                   static_cast<unsigned>(::ir_code_store.code_pulses(info.slot)),
                   static_cast<unsigned>(::ir_code_store.code_duration_us(info.slot)), code, fields);
    first = false;
  }
  stream->print("]}");
  request->send(stream);
}

// Reads only, so it runs on the httpd task without a defer. The block is the
// Flipper .ir signal syntax, so a code moves between this board, a Flipper, and
// the Flipper-IRDB files without a converter. Every printed value is a name
// that set_name() cleaned, a hex byte, or a digit, so none of it needs a JSON
// escape. The newline is the one exception.
void ButtonConfig::handle_code_(AsyncWebServerRequest *request) {
  const SlotInfo *info = parse_slot(request->arg("slot"));
  if (info == nullptr) {
    request->send(400, "application/json", R"({"ok":false,"error":"invalid slot"})");
    return;
  }
  std::vector<int32_t> raw;
  const bool present = ::ir_code_store.code_timings(info->slot, raw);
  const char *name = ::ir_code_store.name(info->slot);
  uint8_t address = 0;
  uint8_t command = 0;
  const bool parsed = ::ir_code_store.code_samsung_fields(info->slot, address, command);

  AsyncResponseStream *stream = request->beginResponseStream("application/json");
  stream->printf(R"({"slot":%u,"present":%s,"text":")", static_cast<unsigned>(info->slot),
                 present ? "true" : "false");
  if (present) {
    if (name[0] != '\0')
      stream->printf("name: %s\\n", name);
    else
      stream->printf("name: Slot%u\\n", static_cast<unsigned>(info->slot));
    if (parsed) {
      stream->print("type: parsed\\nprotocol: Samsung32\\n");
      stream->printf("address: %02X 00 00 00\\ncommand: %02X 00 00 00", address, command);
    } else {
      stream->print("type: raw\\nfrequency: 38000\\nduty_cycle: 0.500000\\ndata:");
      for (const int32_t pulse : raw)
        stream->printf(" %d", static_cast<int>(pulse < 0 ? -pulse : pulse));
    }
  }
  stream->print(R"("})");
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
  std::string name;
  if (action == "set_ir_code" && !parse_ir_text(request->arg("code"), name, timings)) {
    request->send(400, "application/json",
                  R"({"ok":false,"error":"a code is a Flipper signal block, or 4 to 512 alternating values in us"})");
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
    this->defer([this, button, action_id, timings, name]() {
      const bool saved = ::ir_code_store.save(button, timings);
      this->complete_action_(action_id, saved && ::ir_code_store.set_name(button, name.c_str()));
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
