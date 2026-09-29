#include "button_config.h"

#include "esphome/core/application.h"
#include "esphome/core/log.h"

#include "ir_learning.h"
#include "zigbee_learning.h"
#include "esphome/components/api/api_server.h"
#include "esphome/components/ble_hid/ble_hid.h"
#include "esphome/components/wifi/wifi_component.h"

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace esphome::button_config {

static const char *const TAG = "button_config";

// The 400 check runs on the httpd task. IdleSleep checks the range again.
static constexpr uint32_t SLEEP_AFTER_MIN_S = 10;
static constexpr uint32_t SLEEP_AFTER_MAX_S = 3600;
// The reply leaves on the httpd task, so the reboot waits for it to clear the socket.
static constexpr uint32_t RESTART_DELAY_MS = 500;
#ifdef USE_BUTTON_CONFIG_IDLE_SLEEP
static_assert(SLEEP_AFTER_MIN_S == idle_sleep::IdleSleep::MIN_SLEEP_AFTER_S &&
                  SLEEP_AFTER_MAX_S == idle_sleep::IdleSleep::MAX_SLEEP_AFTER_S,
              "the page range must match IdleSleep");
#endif

static const SlotInfo SLOTS[] = {
    {3, true},   {4, true},   {5, true},  {6, true},  {7, true},  {8, true},
    {9, true},   {10, true},  {11, true}, {12, true}, {13, true}, {14, true},
    {15, true},  {16, true},  {17, false},  // wheel clockwise
    {18, false},                            // wheel anticlockwise
    {19, true},
    {20, false},                            // SW1 owns the receiver-mode hold
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

// Accepts a decimal or 0x hex group id. 0xFFF8 and above are the reserved
// Zigbee broadcast addresses, so the manager rejects them too.
static bool parse_group_id(const std::string &text, uint16_t &group_id) {
  if (text.empty() || text.size() > 6)
    return false;
  char *end = nullptr;
  const unsigned long value = std::strtoul(text.c_str(), &end, 0);
  if (end == text.c_str() || *end != '\0' || value == 0 ||
      value > ZigbeeAssignmentManager::MAX_GROUP_ID)
    return false;
  group_id = static_cast<uint16_t>(value);
  return true;
}

// Zigbee2MQTT prints an IEEE address with the most significant nibble first. The
// radio holds an EUI-64 as little endian bytes, so the parsed value copies whole
// and needs no swap on the way to flash.
static bool parse_ieee(const std::string &text, uint8_t (&ieee)[8]) {
  std::string digits = trim(text);
  if (digits.size() > 2 && digits[0] == '0' && (digits[1] == 'x' || digits[1] == 'X'))
    digits = digits.substr(2);
  if (digits.size() != 16)
    return false;
  for (const char digit : digits) {
    if (std::isxdigit(static_cast<unsigned char>(digit)) == 0)
      return false;
  }
  const uint64_t value = std::strtoull(digits.c_str(), nullptr, 16);
  std::memcpy(ieee, &value, sizeof(ieee));
  return true;
}

// The page names an action by its number, so the two tables have to agree. The
// manager bounds the value that goes with it.
static bool parse_action(const std::string &text, uint8_t &action) {
  if (text.empty()) {
    action = ZigbeeAssignmentManager::ACT_TOGGLE;
    return true;
  }
  if (text.size() > 3)
    return false;
  char *end = nullptr;
  const unsigned long value = std::strtoul(text.c_str(), &end, 10);
  if (end == text.c_str() || *end != '\0' || value >= ZigbeeAssignmentManager::ACTION_COUNT)
    return false;
  action = static_cast<uint8_t>(value);
  return true;
}

static bool parse_sleep_after(const std::string &text, uint32_t &seconds) {
  if (text.empty() || text.size() > 4 || std::isdigit(static_cast<unsigned char>(text[0])) == 0)
    return false;
  char *end = nullptr;
  const unsigned long value = std::strtoul(text.c_str(), &end, 10);
  if (*end != '\0' || value < SLEEP_AFTER_MIN_S || value > SLEEP_AFTER_MAX_S)
    return false;
  seconds = static_cast<uint32_t>(value);
  return true;
}

// Home Assistant reads the name as a protobuf string, which must be valid UTF-8.
// A long name is refused and never cut, so no multibyte sequence is split.
// ESPHome reserves the slash in a device name. An empty result means the YAML name.
static bool parse_friendly_name(const std::string &text, std::string &name) {
  size_t start = 0;
  size_t end = text.size();
  while (start < end && text[start] == ' ')
    start++;
  while (end > start && text[end - 1] == ' ')
    end--;
  name = text.substr(start, end - start);
  if (name.size() > ButtonConfig::FRIENDLY_NAME_MAX)
    return false;
  for (size_t i = 0; i < name.size();) {
    const auto lead = static_cast<unsigned char>(name[i]);
    if (lead < 0x20 || lead == 0x7F || lead == '/')
      return false;
    size_t extra = 0;
    unsigned char low = 0x80;
    unsigned char high = 0xBF;
    if (lead >= 0xC2 && lead <= 0xDF) {
      extra = 1;
    } else if (lead >= 0xE0 && lead <= 0xEF) {
      extra = 2;
      low = lead == 0xE0 ? 0xA0 : 0x80;   // overlong
      high = lead == 0xED ? 0x9F : 0xBF;  // UTF-16 surrogate
    } else if (lead >= 0xF0 && lead <= 0xF4) {
      extra = 3;
      low = lead == 0xF0 ? 0x90 : 0x80;   // overlong
      high = lead == 0xF4 ? 0x8F : 0xBF;  // above U+10FFFF
    } else if (lead >= 0x80) {
      return false;
    }
    if (i + extra >= name.size())
      return false;
    for (size_t k = 1; k <= extra; k++) {
      const auto next = static_cast<unsigned char>(name[i + k]);
      if (next < (k == 1 ? low : 0x80) || next > (k == 1 ? high : 0xBF))
        return false;
    }
    i += extra + 1;
  }
  return true;
}

static bool parse_param(const std::string &text, int16_t &param) {
  if (text.empty()) {
    param = 0;
    return true;
  }
  if (text.size() > 6)
    return false;
  char *end = nullptr;
  const long value = std::strtol(text.c_str(), &end, 10);
  if (end == text.c_str() || *end != '\0' || value < 0 || value > 32767)
    return false;
  param = static_cast<int16_t>(value);
  return true;
}

static bool parse_hid_kind(const std::string &text, esphome::ble_hid::BleHid::Kind &kind) {
  if (text == "keyboard")
    kind = esphome::ble_hid::BleHid::KEYBOARD;
  else if (text == "consumer")
    kind = esphome::ble_hid::BleHid::CONSUMER;
  else if (text == "gamepad_button")
    kind = esphome::ble_hid::BleHid::GAMEPAD_BUTTON;
  else if (text == "gamepad_dpad")
    kind = esphome::ble_hid::BleHid::GAMEPAD_DPAD;
  else
    return false;
  return true;
}

static bool parse_hid_number(const std::string &text, uint16_t max, uint16_t &value) {
  if (text.empty() || text.size() > 6)
    return false;
  char *end = nullptr;
  const unsigned long parsed = std::strtoul(text.c_str(), &end, 0);
  if (end == text.c_str() || *end != '\0' || parsed > max)
    return false;
  value = static_cast<uint16_t>(parsed);
  return true;
}

static const char *hid_kind_name(esphome::ble_hid::BleHid::Kind kind) {
  switch (kind) {
    case esphome::ble_hid::BleHid::KEYBOARD: return "keyboard";
    case esphome::ble_hid::BleHid::CONSUMER: return "consumer";
    case esphome::ble_hid::BleHid::GAMEPAD_BUTTON: return "gamepad_button";
    case esphome::ble_hid::BleHid::GAMEPAD_DPAD: return "gamepad_dpad";
    default: return "none";
  }
}

// Endpoint 0 is the ZDO and 0xF1 and above are reserved.
static bool parse_endpoint(const std::string &text, uint8_t &endpoint) {
  if (text.empty() || text.size() > 3)
    return false;
  char *end = nullptr;
  const unsigned long value = std::strtoul(text.c_str(), &end, 10);
  if (end == text.c_str() || *end != '\0' || value < ZigbeeAssignmentManager::MIN_ENDPOINT ||
      value > ZigbeeAssignmentManager::MAX_ENDPOINT)
    return false;
  endpoint = static_cast<uint8_t>(value);
  return true;
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

// Escapes a Zigbee2MQTT name into a JSON string body. The names come from the
// bridge, so they can hold a quote, a backslash, or a control character.
static void print_json_text(AsyncResponseStream *stream, const char *text) {
  char buffer[8];
  for (const char *cursor = text; *cursor != '\0'; cursor++) {
    const unsigned char value = static_cast<unsigned char>(*cursor);
    if (value == '"' || value == '\\') {
      buffer[0] = '\\';
      buffer[1] = static_cast<char>(value);
      buffer[2] = '\0';
    } else if (value < 0x20) {
      std::snprintf(buffer, sizeof(buffer), "\\u%04X", static_cast<unsigned>(value));
    } else {
      buffer[0] = static_cast<char>(value);
      buffer[1] = '\0';
    }
    stream->print(buffer);
  }
}

void ButtonConfig::setup() {
  // mDNS builds its TXT record at AFTER_CONNECTION, which runs after this, so
  // a saved name reaches it on every boot.
  this->default_name_ = App.get_friendly_name();
  this->current_name_.store(this->default_name_.c_str(), std::memory_order_release);
  this->load_name_pref_();
  this->load_ha_pref_();
  this->load_wifi_pref_();
  this->boot_wifi_always_on_ = this->wifi_always_on();
  if (this->boot_wifi_always_on_)
    wifi::global_wifi_component->enable();
  // Each pairing restart drops the page. ZigbeeAssignmentManager::setup() runs
  // first, from on_boot at priority 600, so pairing() already reads this boot.
  if (!this->boot_wifi_always_on_ && ::zigbee_assignments.pairing())
    this->open_temporary_wifi_("for Zigbee pairing");
  this->base_->init();
  this->base_->add_handler(this);
}

void ButtonConfig::loop() {
  if (!this->temporary_wifi_)
    return;
  const uint32_t idle_ms = millis() - this->last_activity_ms_.load(std::memory_order_acquire);
  if (idle_ms < WIFI_IDLE_MS)
    return;
  this->temporary_wifi_ = false;
  wifi::global_wifi_component->disable();
  ESP_LOGI(TAG, "Temporary Wi-Fi session closed after ten minutes idle");
}

void ButtonConfig::load_wifi_pref_() {
  this->wifi_pref_ = global_preferences->make_preference<WifiPref>(WIFI_PREF_KEY, true);
  WifiPref loaded{};
  const bool enabled = this->wifi_pref_.load(&loaded) && loaded.magic == WIFI_PREF_MAGIC &&
                       loaded.enabled <= 1 && loaded.reserved[0] == 0 &&
                       loaded.reserved[1] == 0 && loaded.reserved[2] == 0 && loaded.enabled == 1;
  this->wifi_always_on_.store(enabled, std::memory_order_release);
}

bool ButtonConfig::set_wifi_always_on_(bool enabled) {
  if (this->wifi_always_on() == enabled)
    return true;
  WifiPref next{WIFI_PREF_MAGIC, enabled ? uint8_t{1} : uint8_t{0}, {0, 0, 0}};
  if (!this->wifi_pref_.save(&next)) {
    ESP_LOGE(TAG, "Failed to save the Wi-Fi boot switch");
    return false;
  }
  this->wifi_always_on_.store(enabled, std::memory_order_release);
  ESP_LOGI(TAG, "Wi-Fi default on next boot: %s", enabled ? "on" : "off");
  return true;
}

ButtonConfig::SleepState ButtonConfig::sleep_state_() const {
#ifdef USE_BUTTON_CONFIG_IDLE_SLEEP
  if (this->idle_sleep_ != nullptr)
    return {true, this->idle_sleep_->enabled(), this->idle_sleep_->sleep_after_s()};
#endif
  return {false, false, 0};
}

// Main loop only. The IdleSleep setters save and restart its idle window.
bool ButtonConfig::set_sleep_enabled_(bool enabled) {
#ifdef USE_BUTTON_CONFIG_IDLE_SLEEP
  return this->idle_sleep_ != nullptr && this->idle_sleep_->set_enabled(enabled);
#else
  (void) enabled;
  return false;
#endif
}

bool ButtonConfig::set_sleep_after_(uint32_t seconds) {
#ifdef USE_BUTTON_CONFIG_IDLE_SLEEP
  return this->idle_sleep_ != nullptr && this->idle_sleep_->set_sleep_after_s(seconds);
#else
  (void) seconds;
  return false;
#endif
}

// A missing, corrupt, or empty record keeps the YAML name.
void ButtonConfig::load_name_pref_() {
  this->name_pref_ = global_preferences->make_preference<NamePref>(NAME_PREF_KEY, true);
  NamePref loaded{};
  if (!this->name_pref_.load(&loaded) || loaded.magic != NAME_PREF_MAGIC || loaded.length == 0 ||
      loaded.length > FRIENDLY_NAME_MAX)
    return;
  const std::string stored(loaded.name, loaded.length);
  std::string name;
  if (!parse_friendly_name(stored, name) || name != stored)
    return;
  this->apply_friendly_name_(name);
}

// Main loop only. An empty name saves a length 0 record, which means the YAML name.
bool ButtonConfig::set_friendly_name_(const std::string &name) {
  if (name.size() > FRIENDLY_NAME_MAX)
    return false;
  NamePref next{};
  next.magic = NAME_PREF_MAGIC;
  next.length = static_cast<uint8_t>(name.size());
  std::memcpy(next.name, name.data(), name.size());
  if (!this->name_pref_.save(&next)) {
    ESP_LOGE(TAG, "Failed to save the friendly name");
    return false;
  }
  this->apply_friendly_name_(name);
  ESP_LOGI(TAG, "Friendly name set to \"%s\"", this->current_name_.load(std::memory_order_relaxed));
  return true;
}

// Main loop only. App and its member are not const, so a write through the
// const getter is defined. pre_setup() cannot run again, because it reruns
// arch_init() and puts the MAC suffix back. App.get_name() stays unchanged.
void ButtonConfig::apply_friendly_name_(const std::string &name) {
  if (name.size() > FRIENDLY_NAME_MAX)
    return;
  if (name.empty()) {
    this->current_name_.store(this->default_name_.c_str(), std::memory_order_release);
    const_cast<StringRef &>(App.get_friendly_name()) = this->default_name_;
    return;
  }
  char *buffer =
      this->current_name_.load(std::memory_order_relaxed) == this->names_[0] ? this->names_[1] : this->names_[0];
  std::memcpy(buffer, name.data(), name.size());
  buffer[name.size()] = '\0';
  this->current_name_.store(buffer, std::memory_order_release);
  const_cast<StringRef &>(App.get_friendly_name()) = StringRef(buffer, name.size());
}

void ButtonConfig::note_activity_() {
  this->last_activity_ms_.store(millis(), std::memory_order_release);
}

void ButtonConfig::open_temporary_wifi_(const char *reason) {
  this->note_activity_();
  this->temporary_wifi_ = true;
  wifi::global_wifi_component->enable();
  ESP_LOGI(TAG, "Temporary Wi-Fi session opened %s", reason);
}

void ButtonConfig::toggle_temporary_wifi() {
  if (this->boot_wifi_always_on_)
    return;
  if (wifi::global_wifi_component->is_disabled()) {
    this->open_temporary_wifi_("by SW9");
  } else {
    this->temporary_wifi_ = false;
    wifi::global_wifi_component->disable();
    ESP_LOGI(TAG, "Temporary Wi-Fi session closed by SW9");
  }
}

void ButtonConfig::load_ha_pref_() {
  this->ha_pref_ = global_preferences->make_preference<HaPref>(HA_PREF_KEY, true);
  HaPref loaded{};
  if (this->ha_pref_.load(&loaded) && loaded.magic == HA_PREF_MAGIC) {
    this->ha_api_expected_.store(loaded.expected != 0, std::memory_order_release);
  } else {
    this->ha_api_expected_.store(true, std::memory_order_release);
  }
}

bool ButtonConfig::save_ha_pref_() {
  HaPref next{HA_PREF_MAGIC, this->ha_api_expected() ? uint8_t{1} : uint8_t{0}, {0, 0, 0}};
  if (!this->ha_pref_.save(&next)) {
    ESP_LOGE(TAG, "Failed to save the Home Assistant API switch");
    return false;
  }
  return true;
}

bool ButtonConfig::set_ha_api_expected(bool expected) {
  if (this->ha_api_expected() == expected)
    return true;
  this->ha_api_expected_.store(expected, std::memory_order_release);
  if (!this->save_ha_pref_())
    return false;
  ESP_LOGI(TAG, "Home Assistant API expected %s", expected ? "on" : "off");
  return true;
}

void ButtonConfig::dump_config() {
  ESP_LOGCONFIG(TAG, "Button config page at /buttons");
  ESP_LOGCONFIG(TAG, "  Friendly name: %s", this->current_name_.load(std::memory_order_acquire));
  ESP_LOGCONFIG(TAG, "  Home Assistant API expected: %s", YESNO(this->ha_api_expected()));
  ESP_LOGCONFIG(TAG, "  Wi-Fi always on: %s", YESNO(this->wifi_always_on()));
  ESP_LOGCONFIG(TAG, "  Sleep settings: %s", this->sleep_state_().available ? "idle_sleep" : "not configured");
}

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
    return url == "/buttons/api/action" || url == "/buttons/api/activity";
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
  } else if (url == "/buttons/api/activity") {
    this->handle_activity_(request);
  } else {
    this->handle_page_(request);
  }
}

void ButtonConfig::handle_page_(AsyncWebServerRequest *request) {
  this->note_activity_();
  AsyncWebServerResponse *response =
      request->beginResponse(200, "text/html; charset=utf-8", this->page_, this->page_size_);
  response->addHeader("Content-Encoding", "gzip");
  request->send(response);
}

void ButtonConfig::handle_activity_(AsyncWebServerRequest *request) {
  this->note_activity_();
  request->send(200, "application/json", R"({"ok":true})");
}

// Reads only, so it runs on the httpd task without a defer.
void ButtonConfig::handle_state_(AsyncWebServerRequest *request) {
  const bool action_pending = this->action_pending_.load(std::memory_order_acquire);
  const bool busy = action_pending || ::ir_ui.state != IrUi::OFF;
  // A web Zigbee assignment keeps the receiver mode closed, so the reserved
  // action, not the LED state machine, marks the page as the owner.
  const char *owner = !busy ? "none" : ((action_pending || ::ir_ui.web_owner()) ? "web" : "device");
  const uint32_t completed_id = this->completed_action_id_.load(std::memory_order_acquire);
  char ip[network::IP_ADDRESS_BUFFER_SIZE] = "";
  for (const auto &address : wifi::global_wifi_component->get_ip_addresses()) {
    if (address.is_ip4() && address.is_set()) {
      address.str_to(ip);
      break;
    }
  }
  char mac[MAC_ADDRESS_PRETTY_BUFFER_SIZE];
  get_mac_address_pretty_into_buffer(mac);
  const SleepState sleep = this->sleep_state_();

  AsyncResponseStream *stream = request->beginResponseStream("application/json");
  stream->printf(
      R"({"busy":%s,"owner":"%s","saves":%u,"op_slot":%u,"op_state":"%s","result_slot":%u,"result":"%s","action_id":%u,"action_ok":%s,"network":{"wifi":%s,"wifi_enabled":%s,"wifi_always_on":%s,"home_assistant":%s,"ip":"%s","mac":"%s"},"sleep":{"available":%s,"enabled":%s,"after_s":%u},"radios":{"zigbee":%s,"ble":%s,"home_assistant":%s},"zigbee":{"started":%s,"paired":%s,"new":%s,"gated":%s,"pairing":%s,"pair_left":%u,"pair_failed":%s,"reach":"%s"},"ble":{"connected":%s,"bonded":%s,"pairing":%s,"host":")",
      busy ? "true" : "false", owner, static_cast<unsigned>(::ir_code_store.saves()),
      static_cast<unsigned>(::ir_ui.target), state_name(::ir_ui.state),
      static_cast<unsigned>(::ir_ui.web_result_slot()), result_name(::ir_ui.web_result()),
      static_cast<unsigned>(completed_id), this->completed_action_ok_.load(std::memory_order_relaxed) ? "true" : "false",
      wifi::global_wifi_component->is_connected() ? "true" : "false",
      wifi::global_wifi_component->is_disabled() ? "false" : "true",
      this->wifi_always_on() ? "true" : "false",
      api::global_api_server->is_connected() ? "true" : "false",
      ip, mac,
      sleep.available ? "true" : "false", sleep.enabled ? "true" : "false",
      static_cast<unsigned>(sleep.after_s),
      ::zigbee_assignments.radio_enabled() ? "true" : "false",
      esphome::ble_hid::BleHid::instance()->radio_enabled() ? "true" : "false",
      this->ha_api_expected() ? "true" : "false",
      ::zigbee_assignments.link_started() ? "true" : "false",
      ::zigbee_assignments.link_paired() ? "true" : "false",
      ::zigbee_assignments.link_factory_new() ? "true" : "false",
      ::zigbee_assignments.boot_gated() ? "true" : "false",
      ::zigbee_assignments.pairing() ? "true" : "false",
      static_cast<unsigned>(::zigbee_assignments.pairing_seconds_left()),
      ::zigbee_assignments.pair_failed() ? "true" : "false",
      ZigbeeAssignmentManager::reach_name(::zigbee_assignments.reach()),
      esphome::ble_hid::BleHid::instance()->connected() ? "true" : "false",
      esphome::ble_hid::BleHid::instance()->bonded() ? "true" : "false",
      esphome::ble_hid::BleHid::instance()->pairing() ? "true" : "false");
  print_json_text(stream, esphome::ble_hid::BleHid::instance()->host_name().c_str());
  stream->print(R"("},"slots":[)");
  bool first = true;
  for (const auto &info : SLOTS) {
    const auto zigbee = ::zigbee_assignments.assignment(info.slot);
    const auto hid = esphome::ble_hid::BleHid::instance()->assignment(info.slot);
    const char *action = hid.assigned                           ? "hid"
                         : zigbee.assigned                      ? "zigbee"
                         : ::ir_code_store.is_voice(info.slot)  ? "voice"
                         : ::ir_code_store.has_code(info.slot) ? "ir"
                                                               : "none";
    // Hex only, so it needs no JSON escape. A Zigbee slot shows its target name,
    // and an IR slot shows the code name that set_name() cleaned.
    char code[12] = "";
    char fields[8] = "";
    uint32_t samsung = 0;
    uint8_t address = 0;
    uint8_t command = 0;
    if (::ir_code_store.code_samsung_data(info.slot, samsung))
      std::snprintf(code, sizeof(code), "0x%08X", static_cast<unsigned>(samsung));
    if (::ir_code_store.code_samsung_fields(info.slot, address, command))
      std::snprintf(fields, sizeof(fields), "%02X %02X", address, command);
    // The stored bytes are the little endian EUI-64, so this prints the value
    // that Zigbee2MQTT shows rather than the byte order on the wire.
    char ieee_text[20] = "";
    if (zigbee.assigned && zigbee.kind == ZigbeeAssignmentManager::KIND_DEVICE) {
      uint64_t value = 0;
      std::memcpy(&value, zigbee.ieee, sizeof(value));
      std::snprintf(ieee_text, sizeof(ieee_text), "0x%016llx",
                    static_cast<unsigned long long>(value));
    }
    stream->printf(
        R"(%s{"slot":%u,"action":"%s","pulses":%u,"us":%u,"code":"%s","fields":"%s","group":%u,"ieee":"%s","ep":%u,"act":%u,"val":%d,"hid_kind":"%s","hid_usage":%u,"hid_mod":%u,"name":")",
        first ? "" : ",", static_cast<unsigned>(info.slot), action,
        static_cast<unsigned>(::ir_code_store.code_pulses(info.slot)),
        static_cast<unsigned>(::ir_code_store.code_duration_us(info.slot)), code, fields,
        static_cast<unsigned>(zigbee.group_id), ieee_text,
        static_cast<unsigned>(zigbee.endpoint), static_cast<unsigned>(zigbee.action),
        static_cast<int>(zigbee.param), hid_kind_name(hid.kind), static_cast<unsigned>(hid.usage),
        static_cast<unsigned>(hid.modifiers));
    print_json_text(stream, zigbee.assigned ? zigbee.name.c_str() : ::ir_code_store.name(info.slot));
    stream->print("\"}");
    first = false;
  }
  stream->print(R"(],"name":")");
  print_json_text(stream, this->current_name_.load(std::memory_order_acquire));
  stream->print(R"(","default_name":")");
  print_json_text(stream, this->default_name_.c_str());
  stream->print("\"}");
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
  this->note_activity_();
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
                     action == "set_zigbee" || action == "set_zigbee_device" ||
                     action == "set_hid" || action == "forget_ble" || action == "set_radio" ||
                     action == "set_wifi_always_on" || action == "set_sleep_enabled" ||
                     action == "set_sleep_after" || action == "pair" || action == "restart" ||
                     action == "set_name" || action == "clear";
  if (!known) {
    request->send(400, "application/json", R"({"ok":false,"error":"unknown action"})");
    return;
  }

  // The switch covers every button at once, so it carries a radio name and a
  // state instead of a slot.
  const std::string radio = request->arg("radio");
  bool radio_on = false;
  if (action == "set_radio") {
    const std::string on = request->arg("on");
    if ((radio != "zigbee" && radio != "ble" && radio != "home_assistant") ||
        (on != "0" && on != "1")) {
      request->send(400, "application/json", R"({"ok":false,"error":"invalid radio switch"})");
      return;
    }
    radio_on = on == "1";
  }

  bool wifi_default_on = false;
  if (action == "set_wifi_always_on") {
    const std::string enabled = request->arg("enabled");
    if (enabled != "0" && enabled != "1") {
      request->send(400, "application/json", R"({"ok":false,"error":"invalid Wi-Fi default"})");
      return;
    }
    wifi_default_on = enabled == "1";
  }

  const bool sleep_action = action == "set_sleep_enabled" || action == "set_sleep_after";
  if (sleep_action && !this->sleep_state_().available) {
    request->send(400, "application/json", R"({"ok":false,"error":"sleep is not configured"})");
    return;
  }
  bool sleep_on = false;
  if (action == "set_sleep_enabled") {
    const std::string enabled = request->arg("enabled");
    if (enabled != "0" && enabled != "1") {
      request->send(400, "application/json", R"({"ok":false,"error":"invalid sleep switch"})");
      return;
    }
    sleep_on = enabled == "1";
  }
  uint32_t sleep_after_s = 0;
  if (action == "set_sleep_after" && !parse_sleep_after(request->arg("seconds"), sleep_after_s)) {
    request->send(400, "application/json", R"({"ok":false,"error":"sleep after is 10 to 3600 seconds"})");
    return;
  }

  // Pairing carries the same on flag, so one control can start and stop it.
  bool pair_on = false;
  if (action == "pair") {
    const std::string on = request->arg("on");
    if (on != "0" && on != "1") {
      request->send(400, "application/json", R"({"ok":false,"error":"invalid pairing state"})");
      return;
    }
    pair_on = on == "1";
  }

  // The request dies before the defer runs, so the name is checked and copied
  // here. An empty name restores the YAML name.
  std::string friendly_name;
  if (action == "set_name" && !parse_friendly_name(request->arg("name"), friendly_name)) {
    request->send(400, "application/json",
                  R"({"ok":false,"error":"a name is up to 40 bytes, with no slash or control character"})");
    return;
  }

  const bool needs_slot = action != "forget_ble" && action != "set_radio" &&
                          action != "set_wifi_always_on" && !sleep_action && action != "pair" &&
                          action != "restart" && action != "set_name";
  const SlotInfo *info = needs_slot ? parse_slot(request->arg("slot")) : nullptr;
  if (needs_slot && info == nullptr) {
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

  // Every slot accepts a Zigbee target, because playback rides the same path as
  // IR. The page resolves the name to a group id against Zigbee2MQTT, so the
  // remote stores the id and never needs the broker itself.
  uint16_t group_id = 0;
  uint8_t ieee[8] = {};
  uint8_t endpoint = 0;
  uint8_t zb_action = ZigbeeAssignmentManager::ACT_TOGGLE;
  int16_t zb_param = 0;
  std::string target_name;
  if (action == "set_zigbee" || action == "set_zigbee_device") {
    if (action == "set_zigbee" && !parse_group_id(request->arg("group"), group_id)) {
      request->send(400, "application/json",
                    R"({"ok":false,"error":"a group is 1 to 65527, in decimal or 0x hex"})");
      return;
    }
    if (action == "set_zigbee_device" && !parse_ieee(request->arg("ieee"), ieee)) {
      request->send(400, "application/json",
                    R"({"ok":false,"error":"an IEEE address is 16 hex digits"})");
      return;
    }
    if (action == "set_zigbee_device" && !parse_endpoint(request->arg("ep"), endpoint)) {
      request->send(400, "application/json", R"({"ok":false,"error":"an endpoint is 1 to 240"})");
      return;
    }
    if (!parse_action(request->arg("act"), zb_action)) {
      request->send(400, "application/json", R"({"ok":false,"error":"unknown Zigbee action"})");
      return;
    }
    if (!parse_param(request->arg("val"), zb_param)) {
      request->send(400, "application/json",
                    R"({"ok":false,"error":"an action value is 0 to 32767"})");
      return;
    }
    target_name = request->arg("name");
    if (target_name.size() > 64) {
      request->send(400, "application/json", R"({"ok":false,"error":"target name too long"})");
      return;
    }
  }

  esphome::ble_hid::BleHid::Kind hid_kind = esphome::ble_hid::BleHid::NONE;
  uint16_t hid_usage = 0;
  uint16_t hid_mod = 0;
  if (action == "set_hid") {
    if (!parse_hid_kind(request->arg("kind"), hid_kind) ||
        !parse_hid_number(request->arg("usage"), 0x03FF, hid_usage) ||
        !parse_hid_number(request->arg("mod"), 0x00FF, hid_mod)) {
      request->send(400, "application/json", R"({"ok":false,"error":"invalid HID assignment"})");
      return;
    }
    const bool valid = (hid_kind == esphome::ble_hid::BleHid::KEYBOARD && hid_usage <= 0xE7 &&
                        (hid_usage != 0 || hid_mod != 0)) ||
                       (hid_kind == esphome::ble_hid::BleHid::CONSUMER && hid_usage > 0 && hid_mod == 0) ||
                       (hid_kind == esphome::ble_hid::BleHid::GAMEPAD_BUTTON && hid_usage >= 1 &&
                        hid_usage <= 16 && hid_mod == 0) ||
                       (hid_kind == esphome::ble_hid::BleHid::GAMEPAD_DPAD && hid_usage <= 7 && hid_mod == 0);
    if (!valid) {
      request->send(400, "application/json", R"({"ok":false,"error":"HID value is outside its range"})");
      return;
    }
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

  const uint8_t button = info == nullptr ? 0 : info->slot;
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
  } else if (action == "set_zigbee") {
    this->defer([this, button, action_id, group_id, zb_action, zb_param, target_name]() {
      this->complete_action_(action_id, ::zigbee_assignments.assign_from_web(
                                            button, group_id, zb_action, zb_param, target_name));
    });
  } else if (action == "set_zigbee_device") {
    // The array decays in a lambda capture, so it rides along as a struct.
    struct Target {
      uint8_t ieee[8];
    } target{};
    std::memcpy(target.ieee, ieee, sizeof(target.ieee));
    this->defer([this, button, action_id, target, endpoint, zb_action, zb_param, target_name]() {
      this->complete_action_(action_id,
                             ::zigbee_assignments.assign_device_from_web(
                                 button, target.ieee, endpoint, zb_action, zb_param, target_name));
    });
  } else if (action == "set_hid") {
    this->defer([this, button, action_id, hid_kind, hid_usage, hid_mod]() {
      this->complete_action_(action_id, esphome::ble_hid::BleHid::instance()->assign(
                                            button, hid_kind, hid_usage, static_cast<uint8_t>(hid_mod)));
    });
  } else if (action == "forget_ble") {
    this->defer([this, action_id]() {
      this->complete_action_(action_id, esphome::ble_hid::BleHid::instance()->forget_bond());
    });
  } else if (action == "pair") {
    // A call that reaches the restart never returns, so the action id it was
    // given is never completed and the page watches its own poll fail instead.
    // A false return means no restart happened, and then the id has to be
    // completed or every later action answers 409.
    this->defer([this, action_id, pair_on]() {
      const bool ok = pair_on ? ::zigbee_assignments.begin_pairing()
                              : ::zigbee_assignments.cancel_pairing();
      this->complete_action_(action_id, ok);
    });
  } else if (action == "set_radio") {
    this->defer([this, action_id, radio, radio_on]() {
      bool ok = false;
      if (radio == "zigbee")
        ok = ::zigbee_assignments.set_radio_enabled(radio_on);
      else if (radio == "ble")
        ok = esphome::ble_hid::BleHid::instance()->set_radio_enabled(radio_on);
      else
        ok = this->set_ha_api_expected(radio_on);
      this->complete_action_(action_id, ok);
    });
  } else if (action == "set_wifi_always_on") {
    this->defer([this, action_id, wifi_default_on]() {
      this->complete_action_(action_id, this->set_wifi_always_on_(wifi_default_on));
    });
  } else if (action == "set_sleep_enabled") {
    this->defer([this, action_id, sleep_on]() {
      this->complete_action_(action_id, this->set_sleep_enabled_(sleep_on));
    });
  } else if (action == "set_sleep_after") {
    this->defer([this, action_id, sleep_after_s]() {
      this->complete_action_(action_id, this->set_sleep_after_(sleep_after_s));
    });
  } else if (action == "set_name") {
    this->defer([this, action_id, friendly_name]() {
      this->complete_action_(action_id, this->set_friendly_name_(friendly_name));
    });
  } else if (action == "restart") {
    this->defer([this, action_id]() {
      ESP_LOGI(TAG, "Restart requested from the page");
      this->complete_action_(action_id, true);
      this->set_timeout("restart", RESTART_DELAY_MS, []() { App.safe_reboot(); });
    });
  } else {
    this->defer([this, button, action_id]() {
      this->complete_action_(action_id, ::ir_code_store.clear(button));
    });
  }
  if (needs_slot)
    ESP_LOGI(TAG, "Web action %s on slot %u", action.c_str(), static_cast<unsigned>(button));
  else
    ESP_LOGI(TAG, "Web action %s", action.c_str());
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
