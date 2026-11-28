#include "improv_ble.h"

#include "esphome/core/application.h"
#include "esphome/core/log.h"
#include "esphome/core/version.h"

#include "../ble_hid/ble_hid.h"

#include "host/ble_gatt.h"
#include "host/ble_hs.h"
#include "host/ble_hs_mbuf.h"
#include "os/os_mbuf.h"

#include <cstring>

namespace esphome::improv_ble {

static const char *const TAG = "improv_ble";

// The Improv UUIDs differ in one byte only. A 128-bit UUID goes in reverse
// byte order, so the byte that differs is the first one here.
#define IMPROV_UUID(last) \
  BLE_UUID128_INIT((last), 0x80, 0x26, 0x78, 0x74, 0x27, 0x63, 0x46, 0x72, 0x22, 0x28, 0x62, 0x68, 0x77, 0x46, 0x00)

static const ble_uuid128_t SERVICE_UUID = IMPROV_UUID(0x00);
static const ble_uuid128_t STATE_UUID = IMPROV_UUID(0x01);
static const ble_uuid128_t ERROR_UUID = IMPROV_UUID(0x02);
static const ble_uuid128_t RPC_COMMAND_UUID = IMPROV_UUID(0x03);
static const ble_uuid128_t RPC_RESULT_UUID = IMPROV_UUID(0x04);
static const ble_uuid128_t CAPABILITIES_UUID = IMPROV_UUID(0x05);

// The remote has no way to identify itself that an installer could see, so the
// capability bitmask stays empty.
static constexpr uint8_t CAPABILITIES = 0x00;
// One RPC holds a one-byte command, a one-byte length, the payload and a
// checksum byte. An SSID and a password cap the payload.
static constexpr size_t RPC_MAX = 256;

static uint16_t state_handle = 0;
static uint16_t error_handle = 0;
static uint16_t result_handle = 0;
static std::atomic<uint16_t> client_connection{0xFFFF};
static std::vector<uint8_t> last_result;

static const ble_gatt_chr_def IMPROV_CHARACTERISTICS[] = {
    {
        .uuid = &CAPABILITIES_UUID.u,
        .access_cb = ImprovBle::access_,
        .flags = BLE_GATT_CHR_F_READ,
    },
    {
        .uuid = &STATE_UUID.u,
        .access_cb = ImprovBle::access_,
        .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY,
        .val_handle = &state_handle,
    },
    {
        .uuid = &ERROR_UUID.u,
        .access_cb = ImprovBle::access_,
        .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY,
        .val_handle = &error_handle,
    },
    {
        .uuid = &RPC_COMMAND_UUID.u,
        .access_cb = ImprovBle::access_,
        .flags = BLE_GATT_CHR_F_WRITE,
    },
    {
        .uuid = &RPC_RESULT_UUID.u,
        .access_cb = ImprovBle::access_,
        .flags = BLE_GATT_CHR_F_READ | BLE_GATT_CHR_F_NOTIFY,
        .val_handle = &result_handle,
    },
    {nullptr},
};

static const ble_gatt_svc_def IMPROV_SERVICES[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = &SERVICE_UUID.u,
        .characteristics = IMPROV_CHARACTERISTICS,
    },
    {0},
};

ImprovBle *ImprovBle::global_instance_ = nullptr;

ImprovBle::ImprovBle() {
  global_instance_ = this;
  // NimBLE closes the database before the host task starts, so the service has
  // to go in ahead of every setup().
  ble_hid::BleHid::add_gatt_services(IMPROV_SERVICES);
}

float ImprovBle::get_setup_priority() const { return setup_priority::AFTER_WIFI; }

void ImprovBle::setup() { this->incoming_.reserve(RPC_MAX); }

int ImprovBle::access_(uint16_t conn, uint16_t attr, ble_gatt_access_ctxt *ctxt, void *) {
  if (global_instance_ == nullptr)
    return BLE_ATT_ERR_UNLIKELY;
  return global_instance_->handle_access_(conn, attr, ctxt);
}

int ImprovBle::handle_access_(uint16_t conn, uint16_t, ble_gatt_access_ctxt *ctxt) {
  client_connection.store(conn, std::memory_order_release);
  const ble_uuid_t *uuid = ctxt->chr->uuid;

  if (ctxt->op == BLE_GATT_ACCESS_OP_READ_CHR) {
    if (ble_uuid_cmp(uuid, &CAPABILITIES_UUID.u) == 0) {
      const uint8_t value = CAPABILITIES;
      return os_mbuf_append(ctxt->om, &value, 1) == 0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
    }
    if (ble_uuid_cmp(uuid, &STATE_UUID.u) == 0) {
      const uint8_t value = static_cast<uint8_t>(this->state_);
      return os_mbuf_append(ctxt->om, &value, 1) == 0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
    }
    if (ble_uuid_cmp(uuid, &ERROR_UUID.u) == 0) {
      const uint8_t value = static_cast<uint8_t>(this->error_);
      return os_mbuf_append(ctxt->om, &value, 1) == 0 ? 0 : BLE_ATT_ERR_INSUFFICIENT_RES;
    }
    if (ble_uuid_cmp(uuid, &RPC_RESULT_UUID.u) == 0) {
      if (last_result.empty())
        return 0;
      return os_mbuf_append(ctxt->om, last_result.data(), last_result.size()) == 0 ? 0
                                                                                   : BLE_ATT_ERR_INSUFFICIENT_RES;
    }
    return BLE_ATT_ERR_UNLIKELY;
  }

  if (ctxt->op == BLE_GATT_ACCESS_OP_WRITE_CHR && ble_uuid_cmp(uuid, &RPC_COMMAND_UUID.u) == 0) {
    // The main loop owns the parsing, so the NimBLE task only hands the bytes over.
    if (this->incoming_ready_.load(std::memory_order_acquire))
      return BLE_ATT_ERR_INSUFFICIENT_RES;
    uint8_t buffer[RPC_MAX];
    uint16_t length = 0;
    const int copied = ble_hs_mbuf_to_flat(ctxt->om, buffer, sizeof(buffer), &length);
    if (copied != 0)
      return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    this->incoming_.assign(buffer, buffer + length);
    this->incoming_ready_.store(true, std::memory_order_release);
    return 0;
  }
  return BLE_ATT_ERR_UNLIKELY;
}

void ImprovBle::notify_(uint16_t handle, const uint8_t *data, size_t length) {
  const uint16_t conn = client_connection.load(std::memory_order_acquire);
  if (conn == 0xFFFF || handle == 0)
    return;
  os_mbuf *om = ble_hs_mbuf_from_flat(data, length);
  if (om == nullptr)
    return;
  ble_gatts_notify_custom(conn, handle, om);
}

void ImprovBle::set_state_(improv::State state) {
  if (this->state_ == state)
    return;
  this->state_ = state;
  const uint8_t value = static_cast<uint8_t>(state);
  this->notify_(state_handle, &value, 1);
}

void ImprovBle::set_error_(improv::Error error) {
  if (this->error_ == error)
    return;
  this->error_ = error;
  const uint8_t value = static_cast<uint8_t>(error);
  this->notify_(error_handle, &value, 1);
}

void ImprovBle::send_response_(const std::vector<uint8_t> &response) {
  last_result = response;
  this->notify_(result_handle, response.data(), response.size());
}

void ImprovBle::start_() {
  if (this->running_)
    return;
  this->running_ = true;
  auto *hid = ble_hid::BleHid::instance();
  if (hid != nullptr) {
    hid->set_extra_service_uuid(&SERVICE_UUID);
    hid->refresh_advertising();
  }
  this->set_error_(improv::ERROR_NONE);
#ifdef USE_BINARY_SENSOR
  if (this->authorizer_ != nullptr) {
    this->set_state_(improv::STATE_AWAITING_AUTHORIZATION);
    ESP_LOGD(TAG, "Waiting for the authorizer");
    return;
  }
#endif
  this->set_state_(improv::STATE_AUTHORIZED);
  ESP_LOGD(TAG, "Provisioning is open");
}

void ImprovBle::stop_() {
  if (!this->running_)
    return;
  this->running_ = false;
  auto *hid = ble_hid::BleHid::instance();
  if (hid != nullptr) {
    hid->set_extra_service_uuid(nullptr);
    hid->refresh_advertising();
  }
  this->incoming_.clear();
  this->incoming_ready_.store(false, std::memory_order_release);
}

std::string ImprovBle::formatted_next_url_() const {
  if (this->next_url_.empty())
    return {};
  std::string url = this->next_url_;
  const std::string name{App.get_name().c_str()};
  size_t at = url.find("{{device_name}}");
  if (at != std::string::npos)
    url.replace(at, std::strlen("{{device_name}}"), name);
  at = url.find("{{ip_address}}");
  if (at != std::string::npos) {
    const auto addresses = wifi::global_wifi_component->wifi_sta_ip_addresses();
    for (const auto &address : addresses) {
      if (address.is_ip4()) {
        char text[network::IP_ADDRESS_BUFFER_SIZE];
        address.str_to(text);
        url.replace(at, std::strlen("{{ip_address}}"), text);
        break;
      }
    }
  }
  return url;
}

void ImprovBle::process_incoming_() {
  if (this->incoming_.size() < 3) {
    this->incoming_.clear();
    this->incoming_ready_.store(false, std::memory_order_release);
    return;
  }
  const uint8_t length = this->incoming_[1];
  if (this->incoming_.size() - 3 != length) {
    ESP_LOGW(TAG, "An RPC arrived with the wrong length");
    this->set_error_(improv::ERROR_INVALID_RPC);
    this->incoming_.clear();
    this->incoming_ready_.store(false, std::memory_order_release);
    return;
  }

  const improv::ImprovCommand command = improv::parse_improv_data(this->incoming_);
  this->incoming_.clear();
  this->incoming_ready_.store(false, std::memory_order_release);

  switch (command.command) {
    case improv::BAD_CHECKSUM:
      ESP_LOGW(TAG, "An RPC arrived with a bad checksum");
      this->set_error_(improv::ERROR_INVALID_RPC);
      return;
    case improv::WIFI_SETTINGS: {
      if (this->state_ != improv::STATE_AUTHORIZED) {
        ESP_LOGW(TAG, "Wi-Fi settings arrived before authorization");
        this->set_error_(improv::ERROR_NOT_AUTHORIZED);
        return;
      }
      if (wifi::global_wifi_component->is_disabled()) {
        ESP_LOGW(TAG, "Wi-Fi is off, so the remote cannot take the settings");
        this->set_error_(improv::ERROR_UNABLE_TO_CONNECT);
        return;
      }
      wifi::WiFiAP sta{};
      sta.set_ssid(command.ssid.c_str());
      sta.set_password(command.password.c_str());
      this->connecting_sta_ = sta;
      wifi::global_wifi_component->set_sta(sta);
      wifi::global_wifi_component->start_connecting(sta);
      this->set_error_(improv::ERROR_NONE);
      this->set_state_(improv::STATE_PROVISIONING);
      this->provisioning_start_ = millis();
      ESP_LOGD(TAG, "Joining %s", command.ssid.c_str());
      return;
    }
    case improv::GET_DEVICE_INFO: {
      const std::vector<std::string> info{"ESPHome", ESPHOME_VERSION, "ESP32-C6", std::string{App.get_name().c_str()}};
      this->send_response_(improv::build_rpc_response(improv::GET_DEVICE_INFO, info));
      return;
    }
    case improv::IDENTIFY:
      // Also GET_CURRENT_STATE on the serial transport. Over BLE the state
      // characteristic answers a read, so there is nothing to send back.
      return;
    default:
      ESP_LOGW(TAG, "An RPC arrived that the remote does not know");
      this->set_error_(improv::ERROR_UNKNOWN_RPC);
      return;
  }
}

void ImprovBle::on_wifi_timeout_() {
  ESP_LOGW(TAG, "The network did not accept the remote in time");
  this->set_error_(improv::ERROR_UNABLE_TO_CONNECT);
  this->set_state_(improv::STATE_AUTHORIZED);
  wifi::global_wifi_component->clear_sta();
#ifdef USE_BINARY_SENSOR
  if (this->authorizer_ != nullptr)
    this->authorized_start_ = millis();
#endif
}

void ImprovBle::check_wifi_() {
  if (!wifi::global_wifi_component->is_connected())
    return;
  if (this->state_ != improv::STATE_PROVISIONING)
    return;
  wifi::global_wifi_component->save_wifi_sta(this->connecting_sta_.get_ssid(), this->connecting_sta_.get_password());
  this->connecting_sta_ = {};
  std::vector<std::string> urls;
  const std::string next = this->formatted_next_url_();
  if (!next.empty())
    urls.push_back(next);
  urls.push_back("http://" + std::string{App.get_name().c_str()} + ".local/");
  this->send_response_(improv::build_rpc_response(improv::WIFI_SETTINGS, urls));
  this->set_state_(improv::STATE_PROVISIONED);
  ESP_LOGI(TAG, "The remote joined the network");
}

void ImprovBle::loop() {
  // Provisioning is open while Wi-Fi is on and the remote has no network. The
  // firmware opens that window itself on a cold boot with nothing saved.
  const bool wanted = !wifi::global_wifi_component->is_disabled() &&
                      this->state_ != improv::STATE_PROVISIONED &&
                      !wifi::global_wifi_component->is_connected();
  if (!wanted) {
    if (this->running_ && this->state_ != improv::STATE_PROVISIONING) {
      this->check_wifi_();
      if (this->state_ != improv::STATE_PROVISIONING)
        this->stop_();
    }
    if (!this->running_)
      return;
  } else if (!this->running_) {
    this->start_();
  }

  if (this->incoming_ready_.load(std::memory_order_acquire))
    this->process_incoming_();

  const uint32_t now = millis();
  switch (this->state_) {
    case improv::STATE_AWAITING_AUTHORIZATION:
#ifdef USE_BINARY_SENSOR
      if (this->authorizer_ == nullptr || this->authorizer_->state) {
        this->authorized_start_ = now;
        this->set_state_(improv::STATE_AUTHORIZED);
      }
#else
      this->set_state_(improv::STATE_AUTHORIZED);
#endif
      break;
    case improv::STATE_AUTHORIZED:
#ifdef USE_BINARY_SENSOR
      if (this->authorizer_ != nullptr && now - this->authorized_start_ > this->authorized_duration_) {
        ESP_LOGD(TAG, "Authorization ran out");
        this->set_state_(improv::STATE_AWAITING_AUTHORIZATION);
      }
#endif
      break;
    case improv::STATE_PROVISIONING:
      this->check_wifi_();
      if (this->state_ == improv::STATE_PROVISIONING && now - this->provisioning_start_ > this->wifi_timeout_)
        this->on_wifi_timeout_();
      break;
    case improv::STATE_PROVISIONED:
      this->stop_();
      break;
    default:
      break;
  }
}

void ImprovBle::dump_config() {
  ESP_LOGCONFIG(TAG, "Improv BLE:");
  ESP_LOGCONFIG(TAG, "  Transport: the NimBLE server of ble_hid");
  // NimBLE fills the handles while it registers the service, so a handle of
  // zero is the one sign that the service never reached the database.
  if (state_handle == 0 || error_handle == 0 || result_handle == 0) {
    ESP_LOGW(TAG, "The Improv service is not in the GATT database, so no installer can reach it");
  } else {
    ESP_LOGCONFIG(TAG, "  Handles: state %u, error %u, result %u", state_handle, error_handle, result_handle);
  }
#ifdef USE_BINARY_SENSOR
  ESP_LOGCONFIG(TAG, "  Authorizer: %s", this->authorizer_ == nullptr ? "none" : "a binary sensor");
#endif
  if (!this->next_url_.empty())
    ESP_LOGCONFIG(TAG, "  Next URL: %s", this->next_url_.c_str());
}

}  // namespace esphome::improv_ble
