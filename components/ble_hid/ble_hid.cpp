#include "ble_hid.h"

#include "esphome/core/log.h"

#include "esp_hid_common.h"
#include "esp_bt.h"

#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "host/ble_gap.h"
#include "host/ble_gatt.h"
#include "host/ble_hs.h"
#include "host/ble_store.h"
#include "services/gap/ble_svc_gap.h"

#include "ir_learning.h"
#include "zigbee_learning.h"

#include <algorithm>
#include <cstring>

// The NimBLE key store lives in its own source file and has no public header.
extern "C" void ble_store_config_init(void);

namespace esphome::ble_hid {

static const char *const TAG = "ble_hid";
static const char *const DEVICE_NAME = "homeThing C6";
static constexpr uint16_t HID_SERVICE_UUID = 0x1812;
// The host carries its own name in the GAP service, 0x1800, as characteristic
// 0x2A00. That characteristic exists nowhere else, so one read by UUID over the
// whole handle range finds it without a service discovery first.
static constexpr uint16_t DEVICE_NAME_UUID = 0x2A00;
static constexpr uint32_t STORE_KEY = 0x424C4831U;
static constexpr uint32_t STORE_MAGIC = 0x424C4844U;
static constexpr uint8_t STORE_VERSION = 1;

static constexpr uint8_t REPORT_KEYBOARD = 1;
static constexpr uint8_t REPORT_CONSUMER = 2;
static constexpr uint8_t REPORT_GAMEPAD = 3;

// One report map keeps the device visible as one composite HID peripheral.
static const uint8_t REPORT_MAP[] = {
    0x05, 0x01, 0x09, 0x06, 0xA1, 0x01, 0x85, REPORT_KEYBOARD,
    0x05, 0x07, 0x19, 0xE0, 0x29, 0xE7, 0x15, 0x00, 0x25, 0x01,
    0x75, 0x01, 0x95, 0x08, 0x81, 0x02,
    0x05, 0x07, 0x19, 0x00, 0x29, 0xE7, 0x15, 0x00, 0x25, 0x01,
    0x75, 0x01, 0x96, 0xE8, 0x00, 0x81, 0x02, 0xC0,

    0x05, 0x0C, 0x09, 0x01, 0xA1, 0x01, 0x85, REPORT_CONSUMER,
    0x15, 0x00, 0x26, 0xFF, 0x03, 0x19, 0x00, 0x2A, 0xFF, 0x03,
    0x75, 0x10, 0x95, 0x01, 0x81, 0x00, 0xC0,

    0x05, 0x01, 0x09, 0x05, 0xA1, 0x01, 0x85, REPORT_GAMEPAD,
    0x05, 0x09, 0x19, 0x01, 0x29, 0x10, 0x15, 0x00, 0x25, 0x01,
    0x75, 0x01, 0x95, 0x10, 0x81, 0x02,
    0x05, 0x01, 0x09, 0x39, 0x15, 0x00, 0x25, 0x07,
    0x35, 0x00, 0x46, 0x3B, 0x01, 0x65, 0x14,
    0x75, 0x04, 0x95, 0x01, 0x81, 0x42,
    0x65, 0x00, 0x75, 0x04, 0x95, 0x01, 0x81, 0x01, 0xC0,
};

static esp_hid_raw_report_map_t REPORT_MAPS[] = {{REPORT_MAP, sizeof(REPORT_MAP)}};
static esp_hid_device_config_t DEVICE_CONFIG = {
    .vendor_id = 0x16C0,
    .product_id = 0x05DF,
    .version = 0x0100,
    .device_name = DEVICE_NAME,
    .manufacturer_name = "homeThing",
    .serial_number = "C6",
    .report_maps = REPORT_MAPS,
    .report_maps_len = 1,
};

BleHid *BleHid::global_instance_ = nullptr;

static int bond_count() {
  int count = 0;
  return ble_store_util_count(BLE_STORE_OBJ_TYPE_PEER_SEC, &count) == 0 ? count : 0;
}

// The build allows one bond, so the saved host is the first and only entry.
static bool bonded_peer(ble_addr_t *address) {
  int count = 0;
  return ble_store_util_bonded_peers(address, &count, 1) == 0 && count == 1;
}

static void host_task(void *param) {
  nimble_port_run();
  nimble_port_freertos_deinit();
  (void) param;
}

float BleHid::get_setup_priority() const { return setup_priority::BLUETOOTH - 1.0f; }

void BleHid::setup() {
  if (!this->init_stack_()) {
    this->mark_failed();
    return;
  }
  this->bonded_.store(bond_count() > 0, std::memory_order_release);
}

void BleHid::loop() {
  if (this->disconnect_pending_.exchange(false, std::memory_order_acq_rel))
    this->release_all_();
  if (this->report_sync_pending_.exchange(false, std::memory_order_acq_rel))
    this->send_reports_();
}

void BleHid::dump_config() {
  const std::string host = this->host_name();
  ESP_LOGCONFIG(TAG, "BLE HID:");
  ESP_LOGCONFIG(TAG, "  Name: %s", DEVICE_NAME);
  ESP_LOGCONFIG(TAG, "  Connected: %s", YESNO(this->connected()));
  ESP_LOGCONFIG(TAG, "  Connected to: %s", host.empty() ? "unknown" : host.c_str());
  ESP_LOGCONFIG(TAG, "  Bonded: %s", YESNO(this->bonded()));
}

std::string BleHid::host_name() const {
  const std::lock_guard<std::mutex> lock(this->host_name_mutex_);
  return std::string(this->host_name_.data());
}

void BleHid::set_host_name_(const char *name) {
  const std::lock_guard<std::mutex> lock(this->host_name_mutex_);
  this->host_name_.fill('\0');
  if (name != nullptr)
    std::strncpy(this->host_name_.data(), name, this->host_name_.size() - 1);
}

void BleHid::setup_assignments() {
  this->pref_ = esphome::global_preferences->make_preference<Record>(STORE_KEY, true);
  Record loaded{};
  if (this->pref_.load(&loaded) && valid_record_(loaded)) {
    this->record_ = loaded;
  } else {
    this->record_.magic = STORE_MAGIC;
    this->record_.version = STORE_VERSION;
    this->record_.checksum = checksum_(this->record_);
  }
  this->assignments_ready_ = true;

  ::ir_code_store.set_assignment_clear_callback([](uint8_t slot) {
    ::zigbee_assignments.clear(slot);
    if (BleHid::instance() != nullptr)
      BleHid::instance()->clear(slot);
  });
  ::zigbee_assignments.set_assignment_store_callback([](uint8_t slot) {
    if (BleHid::instance() != nullptr)
      BleHid::instance()->clear(slot);
  });
  ::ir_ui.set_hid_play_callback([](uint8_t slot, bool pressed) {
    return BleHid::instance() != nullptr && BleHid::instance()->set_pressed(slot, pressed);
  });
  ESP_LOGI(TAG, "Loaded BLE HID assignments");
}

BleHid::Assignment BleHid::assignment(uint8_t slot) const {
  if (!slot_valid_(slot) || !this->assignments_ready_)
    return {};
  const std::lock_guard<std::mutex> lock(this->record_mutex_);
  const Entry &entry = this->record_.entries[slot - FIRST_SLOT];
  const Kind kind = static_cast<Kind>(entry.kind);
  if (!valid_assignment_(kind, entry.usage, entry.modifiers))
    return {};
  return {true, kind, entry.usage, entry.modifiers};
}

bool BleHid::assign(uint8_t slot, Kind kind, uint16_t usage, uint8_t modifiers) {
  if (!slot_valid_(slot) || !this->assignments_ready_ || !valid_assignment_(kind, usage, modifiers))
    return false;
  const bool local_cleared = ::ir_code_store.clear_for_zigbee(slot);
  if (!local_cleared)
    return false;
  ::zigbee_assignments.clear(slot);
  bool stored;
  {
    const std::lock_guard<std::mutex> lock(this->record_mutex_);
    this->active_[slot - FIRST_SLOT] = false;
    Entry &entry = this->record_.entries[slot - FIRST_SLOT];
    entry = {static_cast<uint8_t>(kind), modifiers, usage};
    stored = this->save_();
  }
  ESP_LOGI(TAG, "Slot %u assigned HID kind %u usage 0x%04X modifiers 0x%02X", slot,
           static_cast<unsigned>(kind), usage, modifiers);
  if (this->connected())
    this->send_reports_();
  return stored;
}

void BleHid::clear(uint8_t slot) {
  if (!slot_valid_(slot) || !this->assignments_ready_)
    return;
  const size_t index = slot - FIRST_SLOT;
  {
    const std::lock_guard<std::mutex> lock(this->record_mutex_);
    if (this->record_.entries[index].kind == NONE)
      return;
    this->active_[index] = false;
    this->record_.entries[index] = {};
    this->save_();
  }
  if (this->connected())
    this->send_reports_();
}

bool BleHid::set_pressed(uint8_t slot, bool pressed) {
  const Assignment value = this->assignment(slot);
  if (!value.assigned)
    return false;
  const size_t index = slot - FIRST_SLOT;
  if (!this->connected()) {
    this->active_[index] = false;
    return true;
  }
  this->active_[index] = pressed;
  this->send_reports_();
  return true;
}

bool BleHid::slot_valid_(uint8_t slot) { return slot >= FIRST_SLOT && slot <= LAST_SLOT; }

uint32_t BleHid::checksum_(const Record &record) {
  const auto *bytes = reinterpret_cast<const uint8_t *>(&record);
  uint32_t hash = 2166136261U;
  for (size_t i = 0; i < sizeof(record) - sizeof(record.checksum); i++) {
    hash ^= bytes[i];
    hash *= 16777619U;
  }
  return hash;
}

bool BleHid::valid_record_(const Record &record) {
  if (record.magic != STORE_MAGIC || record.version != STORE_VERSION || record.checksum != checksum_(record))
    return false;
  for (const Entry &entry : record.entries) {
    if (entry.kind != NONE &&
        !valid_assignment_(static_cast<Kind>(entry.kind), entry.usage, entry.modifiers))
      return false;
  }
  return true;
}

bool BleHid::valid_assignment_(Kind kind, uint16_t usage, uint8_t modifiers) {
  switch (kind) {
    case KEYBOARD:
      return usage <= 0xE7 && (usage != 0 || modifiers != 0);
    case CONSUMER:
      return usage > 0 && usage <= 0x03FF && modifiers == 0;
    case GAMEPAD_BUTTON:
      return usage >= 1 && usage <= 16 && modifiers == 0;
    case GAMEPAD_DPAD:
      return usage <= 7 && modifiers == 0;
    default:
      return false;
  }
}

bool BleHid::save_() {
  this->record_.magic = STORE_MAGIC;
  this->record_.version = STORE_VERSION;
  this->record_.checksum = checksum_(this->record_);
  return this->pref_.save(&this->record_);
}

bool BleHid::forget_bond() {
  ble_addr_t peer{};
  if (!bonded_peer(&peer)) {
    this->bonded_.store(false, std::memory_order_release);
    this->pairing_.store(false, std::memory_order_release);
    this->start_advertising_();
    return true;
  }

  // ble_gap_unpair() closes the link before it drops the key, so the disconnect
  // event restarts advertising on its own.
  const int result = ble_gap_unpair(&peer);
  if (result != 0) {
    ESP_LOGE(TAG, "Could not remove the Bluetooth bond: %d", result);
    return false;
  }
  this->bonded_.store(bond_count() > 0, std::memory_order_release);
  this->pairing_.store(false, std::memory_order_release);
  ESP_LOGI(TAG, "Bluetooth host bond removed");
  this->start_advertising_();
  return true;
}

bool BleHid::init_stack_() {
  esp_err_t result;
  if (esp_bt_controller_get_status() == ESP_BT_CONTROLLER_STATUS_IDLE) {
    esp_bt_controller_config_t config = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    result = esp_bt_controller_init(&config);
    if (result != ESP_OK) {
      ESP_LOGE(TAG, "Bluetooth controller init failed: %s", esp_err_to_name(result));
      return false;
    }
  }
  if (esp_bt_controller_get_status() == ESP_BT_CONTROLLER_STATUS_INITED) {
    result = esp_bt_controller_enable(ESP_BT_MODE_BLE);
    if (result != ESP_OK) {
      ESP_LOGE(TAG, "Bluetooth controller enable failed: %s", esp_err_to_name(result));
      return false;
    }
  }
  result = esp_nimble_init();
  if (result != ESP_OK) {
    ESP_LOGE(TAG, "NimBLE init failed: %s", esp_err_to_name(result));
    return false;
  }

  // No display and no keypad, so the host pairs without a passkey. Secure
  // connections still give an encrypted and bonded link.
  ble_hs_cfg.sm_io_cap = BLE_SM_IO_CAP_NO_IO;
  ble_hs_cfg.sm_bonding = 1;
  ble_hs_cfg.sm_mitm = 0;
  ble_hs_cfg.sm_sc = 1;
  ble_hs_cfg.sm_our_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
  ble_hs_cfg.sm_their_key_dist = BLE_SM_PAIR_KEY_DIST_ENC | BLE_SM_PAIR_KEY_DIST_ID;
  ble_hs_cfg.store_status_cb = ble_store_util_status_rr;
  ble_store_config_init();

  // esp_hidd_dev_init() registers the GATT database and takes the host sync
  // callback, so it must run before the host task starts.
  this->init_hid_();
  if (this->is_failed())
    return false;
  ble_svc_gap_device_name_set(DEVICE_NAME);
  ble_svc_gap_device_appearance_set(ESP_HID_APPEARANCE_GAMEPAD);

  result = esp_nimble_enable(reinterpret_cast<void *>(host_task));
  if (result != ESP_OK) {
    ESP_LOGE(TAG, "NimBLE host task start failed: %s", esp_err_to_name(result));
    return false;
  }
  return true;
}

void BleHid::init_hid_() {
  const esp_err_t result = esp_hidd_dev_init(&DEVICE_CONFIG, ESP_HID_TRANSPORT_BLE,
                                              hidd_event_handler_, &this->device_);
  if (result != ESP_OK) {
    ESP_LOGE(TAG, "HID init failed: %s", esp_err_to_name(result));
    this->mark_failed();
    return;
  }
}

void BleHid::send_reports_() {
  if (!this->connected() || this->device_ == nullptr)
    return;

  uint8_t keyboard[30]{};
  uint16_t consumer = 0;
  uint16_t buttons = 0;
  int dpad_x = 0;
  int dpad_y = 0;
  for (size_t i = 0; i < SLOT_COUNT; i++) {
    if (!this->active_[i])
      continue;
    const Entry &entry = this->record_.entries[i];
    if (entry.kind == KEYBOARD) {
      keyboard[0] |= entry.modifiers;
      if (entry.usage != 0)
        keyboard[1 + entry.usage / 8] |= static_cast<uint8_t>(1U << (entry.usage % 8));
    } else if (entry.kind == CONSUMER && consumer == 0) {
      consumer = entry.usage;
    } else if (entry.kind == GAMEPAD_BUTTON) {
      buttons |= static_cast<uint16_t>(1U << (entry.usage - 1));
    } else if (entry.kind == GAMEPAD_DPAD) {
      static constexpr int8_t DX[8] = {0, 1, 1, 1, 0, -1, -1, -1};
      static constexpr int8_t DY[8] = {-1, -1, 0, 1, 1, 1, 0, -1};
      dpad_x += DX[entry.usage];
      dpad_y += DY[entry.usage];
    }
  }

  uint8_t consumer_report[2] = {static_cast<uint8_t>(consumer), static_cast<uint8_t>(consumer >> 8)};
  uint8_t hat = 8;
  const int x = (dpad_x > 0) - (dpad_x < 0);
  const int y = (dpad_y > 0) - (dpad_y < 0);
  if (x == 0 && y < 0) hat = 0;
  else if (x > 0 && y < 0) hat = 1;
  else if (x > 0 && y == 0) hat = 2;
  else if (x > 0 && y > 0) hat = 3;
  else if (x == 0 && y > 0) hat = 4;
  else if (x < 0 && y > 0) hat = 5;
  else if (x < 0 && y == 0) hat = 6;
  else if (x < 0 && y < 0) hat = 7;
  uint8_t gamepad[3] = {static_cast<uint8_t>(buttons), static_cast<uint8_t>(buttons >> 8), hat};

  esp_hidd_dev_input_set(this->device_, 0, REPORT_KEYBOARD, keyboard, sizeof(keyboard));
  esp_hidd_dev_input_set(this->device_, 0, REPORT_CONSUMER, consumer_report, sizeof(consumer_report));
  esp_hidd_dev_input_set(this->device_, 0, REPORT_GAMEPAD, gamepad, sizeof(gamepad));
}

void BleHid::release_all_() {
  this->active_.fill(false);
}

void BleHid::start_advertising_() {
  if (!this->hid_started_.load(std::memory_order_acquire) ||
      this->advertising_.load(std::memory_order_acquire) ||
      this->link_connected_.load(std::memory_order_acquire))
    return;

  const ble_uuid16_t hid_uuid = BLE_UUID16_INIT(HID_SERVICE_UUID);
  ble_hs_adv_fields fields{};
  fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
  fields.appearance = ESP_HID_APPEARANCE_GAMEPAD;
  fields.appearance_is_present = 1;
  fields.tx_pwr_lvl = BLE_HS_ADV_TX_PWR_LVL_AUTO;
  fields.tx_pwr_lvl_is_present = 1;
  fields.name = reinterpret_cast<const uint8_t *>(DEVICE_NAME);
  fields.name_len = std::strlen(DEVICE_NAME);
  fields.name_is_complete = 1;
  fields.uuids16 = &hid_uuid;
  fields.num_uuids16 = 1;
  fields.uuids16_is_complete = 1;
  int result = ble_gap_adv_set_fields(&fields);
  if (result != 0) {
    ESP_LOGE(TAG, "Advertising data setup failed: %d", result);
    return;
  }

  ble_gap_adv_params parameters{};
  parameters.conn_mode = BLE_GAP_CONN_MODE_UND;
  parameters.disc_mode = BLE_GAP_DISC_MODE_GEN;
  parameters.itvl_min = BLE_GAP_ADV_ITVL_MS(30);
  parameters.itvl_max = BLE_GAP_ADV_ITVL_MS(50);
  result = ble_gap_adv_start(BLE_OWN_ADDR_PUBLIC, nullptr, BLE_HS_FOREVER, &parameters,
                             &BleHid::gap_event_, this);
  if (result != 0) {
    ESP_LOGE(TAG, "Advertising start failed: %d", result);
    return;
  }
  this->advertising_.store(true, std::memory_order_release);
  ESP_LOGI(TAG, "Advertising as homeThing C6");
}

void BleHid::read_host_name_() {
  const uint16_t connection = this->connection_.load(std::memory_order_acquire);
  if (connection == NO_CONNECTION)
    return;
  const ble_uuid16_t name_uuid = BLE_UUID16_INIT(DEVICE_NAME_UUID);
  const int result =
      ble_gattc_read_by_uuid(connection, 1, 0xFFFF, &name_uuid.u, &BleHid::host_name_read_, this);
  if (result != 0)
    ESP_LOGD(TAG, "Host name read could not start: %d", result);
}

int BleHid::host_name_read_(uint16_t, const ble_gatt_error *error, ble_gatt_attr *attr, void *arg) {
  auto *self = static_cast<BleHid *>(arg);
  // The last callback of the procedure carries no attribute, so it ends here.
  if (self == nullptr || error == nullptr || error->status != 0 || attr == nullptr ||
      attr->om == nullptr)
    return 0;
  char name[HOST_NAME_SIZE]{};
  uint16_t length = 0;
  if (ble_hs_mbuf_to_flat(attr->om, name, sizeof(name) - 1, &length) != 0)
    return 0;
  name[length] = '\0';
  self->set_host_name_(name);
  ESP_LOGI(TAG, "Connected to %s", name);
  return 0;
}

void BleHid::hidd_event_handler_(void *, esp_event_base_t, int32_t id, void *data) {
  BleHid *self = instance();
  if (self == nullptr)
    return;
  if (static_cast<esp_hidd_event_t>(id) == ESP_HIDD_START_EVENT) {
    // The event follows every host sync, and a host reset drops advertising, so
    // the flag has to clear before the restart.
    self->hid_started_.store(true, std::memory_order_release);
    self->advertising_.store(false, std::memory_order_release);
    ESP_LOGI(TAG, "HID services ready");
    self->start_advertising_();
  }
  (void) data;
}

int BleHid::gap_event_(ble_gap_event *event, void *arg) {
  auto *self = static_cast<BleHid *>(arg);
  return self == nullptr ? 0 : self->handle_gap_event_(event);
}

int BleHid::handle_gap_event_(ble_gap_event *event) {
  switch (event->type) {
    case BLE_GAP_EVENT_CONNECT: {
      this->advertising_.store(false, std::memory_order_release);
      if (event->connect.status != 0) {
        this->start_advertising_();
        return 0;
      }
      this->connection_.store(event->connect.conn_handle, std::memory_order_release);
      this->link_connected_.store(true, std::memory_order_release);

      ble_addr_t peer{};
      ble_gap_conn_desc description{};
      const bool has_bond = bonded_peer(&peer);
      if (has_bond && ble_gap_conn_find(event->connect.conn_handle, &description) == 0 &&
          ble_addr_cmp(&description.peer_id_addr, &peer) != 0) {
        ESP_LOGW(TAG, "Rejected a second HID host");
        ble_gap_terminate(event->connect.conn_handle, BLE_ERR_REM_USER_CONN_TERM);
        return 0;
      }
      this->pairing_.store(!has_bond, std::memory_order_release);
      // The host waits for the peripheral to ask, so send the security request.
      ble_gap_security_initiate(event->connect.conn_handle);
      return 0;
    }
    case BLE_GAP_EVENT_ENC_CHANGE: {
      const bool ok = event->enc_change.status == 0;
      this->pairing_.store(false, std::memory_order_release);
      this->bonded_.store(bond_count() > 0, std::memory_order_release);
      this->connected_.store(ok, std::memory_order_release);
      if (ok) {
        this->report_sync_pending_.store(true, std::memory_order_release);
        this->read_host_name_();
      } else {
        ble_gap_terminate(event->enc_change.conn_handle, BLE_ERR_REM_USER_CONN_TERM);
      }
      return 0;
    }
    case BLE_GAP_EVENT_REPEAT_PAIRING: {
      // The host lost its key. Drop the stale bond so the retry can store a new one.
      ble_gap_conn_desc description{};
      if (ble_gap_conn_find(event->repeat_pairing.conn_handle, &description) == 0)
        ble_store_util_delete_peer(&description.peer_id_addr);
      return BLE_GAP_REPEAT_PAIRING_RETRY;
    }
    case BLE_GAP_EVENT_DISCONNECT:
      this->connected_.store(false, std::memory_order_release);
      this->link_connected_.store(false, std::memory_order_release);
      this->pairing_.store(false, std::memory_order_release);
      this->connection_.store(NO_CONNECTION, std::memory_order_release);
      this->disconnect_pending_.store(true, std::memory_order_release);
      this->set_host_name_(nullptr);
      this->start_advertising_();
      return 0;
    default:
      return 0;
  }
}

}  // namespace esphome::ble_hid
