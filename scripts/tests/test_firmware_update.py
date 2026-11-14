"""Regression checks for the firmware update path: provisioning, the update entity and the release."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[2]
CONFIG = (ROOT / "c6remote.yaml").read_text()
FACTORY = (ROOT / "c6remote-factory.yaml").read_text()
BUTTON_CPP = (ROOT / "components" / "button_config" / "button_config.cpp").read_text()
BUTTON_HEADER = (ROOT / "components" / "button_config" / "button_config.h").read_text()
FIRMWARE_WORKFLOW = (ROOT / ".github" / "workflows" / "firmware.yml").read_text()
PAGES_WORKFLOW = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
SECRETS_EXAMPLE = (ROOT / "secrets.example.yaml").read_text()

MANIFEST_URL = "https://landonr.github.io/homething-c6/firmware/manifest.json"
PROJECT_NAME = "landonr.homething-c6"


def top_level_block(text: str, key: str) -> str:
    """Returns the lines under one top-level key, up to the next top-level key.

    A top-level comment does not end the block, so a comment in front of the
    next key stays with the block above it.
    """
    lines = text.splitlines()
    try:
        start = lines.index(f"{key}:")
    except ValueError:
        raise AssertionError(f"no top-level {key}: block") from None
    body = []
    for line in lines[start + 1:]:
        if line and not line[0].isspace() and not line.startswith("#"):
            break
        body.append(line)
    return "\n".join(body) + "\n"


def without_comments(block: str) -> str:
    return "\n".join(line for line in block.splitlines() if not line.lstrip().startswith("#")) + "\n"


def substitution(text: str, name: str) -> str:
    match = re.search(rf"(?m)^  {re.escape(name)}: (.+)$", top_level_block(text, "substitutions"))
    if match is None:
        raise AssertionError(f"substitution {name} not found")
    return match.group(1).strip()


def project(text: str) -> tuple[str, str]:
    match = re.search(r"\n  project:\n    name: (\S+)\n    (?:#.*\n    )*version: (\S+)\n",
                      top_level_block(text, "esphome"))
    if match is None:
        raise AssertionError("esphome: project: not found")
    return match.group(1), match.group(2)


def http_update_source(text: str) -> str:
    block = top_level_block(text, "update")
    entry = block.split("  - platform: http_request\n", 1)
    if len(entry) != 2:
        raise AssertionError("no http_request update platform")
    match = re.search(r"(?m)^    source: (\S+)$", entry[1].split("\n  - platform:", 1)[0])
    if match is None:
        raise AssertionError("the http_request update platform has no source")
    return match.group(1)


class WifiCredentialTest(unittest.TestCase):
    """Improv saves a network under a fixed key only when the config has no networks,
    so a network saved on the factory image survives every later firmware."""

    def test_neither_config_holds_wifi_credentials(self) -> None:
        for name, text in (("c6remote.yaml", CONFIG), ("c6remote-factory.yaml", FACTORY)):
            with self.subTest(config=name):
                self.assertNotIn("!secret", text)
                wifi = without_comments(top_level_block(text, "wifi"))
                self.assertNotRegex(wifi, r"(?m)^\s+(?:-\s+)?(?:ssid|password|networks)\s*:")
                self.assertNotRegex(wifi, r"(?m)^  ap\s*:")

    def test_every_secret_a_bench_config_uses_is_in_the_example(self) -> None:
        """c6remote-test-mic-vu.yaml still reads secrets, so the example file must stay."""
        for path in sorted(ROOT.glob("*.yaml")):
            for key in re.findall(r"!secret (\w+)", path.read_text()):
                with self.subTest(config=path.name, secret=key):
                    self.assertRegex(SECRETS_EXAMPLE, rf"(?m)^{key}:")

    def test_the_production_config_keeps_wifi_off_at_boot_and_the_factory_turns_it_on(self) -> None:
        self.assertIn("  enable_on_boot: false\n", top_level_block(CONFIG, "wifi"))
        self.assertNotIn("enable_on_boot", top_level_block(FACTORY, "wifi"))


class ImprovTest(unittest.TestCase):
    def test_production_provisions_over_usb_only(self) -> None:
        """esp32_improv needs Bluedroid, but ble_hid forces NimBLE."""
        self.assertNotRegex(CONFIG, r"(?m)^esp32_improv:")
        self.assertRegex(CONFIG, r"(?m)^ble_hid:")
        self.assertIn("  id: improv_usb\n", top_level_block(CONFIG, "improv_serial"))

    def test_the_factory_image_has_both_improv_paths_and_no_nimble(self) -> None:
        self.assertNotRegex(FACTORY, r"(?m)^ble_hid:")
        self.assertIn("  authorizer: none\n", top_level_block(FACTORY, "esp32_improv"))
        self.assertIn("  id: improv_usb\n", top_level_block(FACTORY, "improv_serial"))
        # improv_serial needs the logger UART, so the logger must not set baud_rate 0.
        self.assertRegex(FACTORY, r"(?m)^logger:")
        self.assertNotRegex(FACTORY, r"baud_rate:\s*0\b")

    def test_an_unprovisioned_cold_boot_opens_wifi_for_improv(self) -> None:
        """Improv serial refuses Wi-Fi settings while Wi-Fi is disabled."""
        boot = CONFIG.split("    - priority: 225\n", 1)
        self.assertEqual(len(boot), 2, "no on_boot step at priority 225")
        step = boot[1].split("\n  on_shutdown:", 1)[0]
        # A deep-sleep wake returns before the NVS read and opens no session.
        wake = step.index("if (id(idle).woke_from_sleep())\n              return;")
        read = step.index("make_preference<wifi::SavedWifiSettings>(88491487UL, true).load(&saved)")
        self.assertLess(wake, read)
        self.assertIn("saved.ssid[0] == '\\0'", step)
        provision = step.index(
            'id(button_cfg).open_boot_wifi_session("for Improv provisioning, because no Wi-Fi network is saved");')
        self.assertLess(read, provision)
        # 225 sits between ButtonConfig::setup() at WIFI - 2 (248) and
        # improv_serial at AFTER_WIFI (200).
        self.assertIn("return setup_priority::WIFI - 2.0f;", BUTTON_CPP)

    def test_a_software_restart_opens_a_session_for_home_assistant(self) -> None:
        """Both OTA platforms and the factory install reboot through esp_restart(),
        so the new firmware comes up where Home Assistant can confirm it."""
        step = CONFIG.split("    - priority: 225\n", 1)[1].split("\n  on_shutdown:", 1)[0]
        restart = step.index("} else if (esp_reset_reason() == ESP_RST_SW) {")
        self.assertLess(step.index("if (id(idle).woke_from_sleep())\n              return;"), restart)
        self.assertLess(step.index("for Improv provisioning"), restart)
        self.assertIn('id(button_cfg).open_boot_wifi_session("after a software restart");', step[restart:])

    def test_boot_sessions_are_ordinary_temporary_sessions(self) -> None:
        """The ten-minute idle close and the wifi_session sleep block then cover them."""
        self.assertIn("  void open_boot_wifi_session(const char *reason);\n", BUTTON_HEADER)
        self.assertNotIn("open_wifi_for_provisioning", BUTTON_HEADER + BUTTON_CPP + CONFIG)
        start = BUTTON_CPP.index("void ButtonConfig::open_boot_wifi_session(const char *reason) {")
        body = BUTTON_CPP[start:BUTTON_CPP.index("\n}", start)]
        self.assertIn("if (wifi::global_wifi_component->is_disabled())", body)
        self.assertIn("this->open_temporary_wifi_(reason);", body)
        self.assertNotIn("->enable()", body)


class UpdateEntityTest(unittest.TestCase):
    def test_both_configs_share_the_project_and_the_partition_table(self) -> None:
        """An OTA cannot change the partition table, so the factory image must use the same one."""
        self.assertEqual(project(CONFIG), (PROJECT_NAME, "${fw_version}"))
        self.assertEqual(project(FACTORY), (PROJECT_NAME, "factory"))
        self.assertEqual(substitution(CONFIG, "fw_version"), "dev")
        for name, text in (("c6remote.yaml", CONFIG), ("c6remote-factory.yaml", FACTORY)):
            with self.subTest(config=name):
                esp32 = top_level_block(text, "esp32")
                self.assertIn("  board: seeed_xiao_esp32c6\n", esp32)
                self.assertIn("  partitions: partitions.csv\n", esp32)
                self.assertIn("    type: esp-idf\n", esp32)

    def test_both_configs_keep_one_hostname_and_home_assistant_identity(self) -> None:
        for key in ("device_name", "friendly_name"):
            self.assertEqual(substitution(FACTORY, key), substitution(CONFIG, key))
        for name, text in (("c6remote.yaml", CONFIG), ("c6remote-factory.yaml", FACTORY)):
            with self.subTest(config=name):
                esphome = top_level_block(text, "esphome")
                self.assertIn("  name: ${device_name}\n", esphome)
                self.assertIn("  friendly_name: ${friendly_name}\n", esphome)
                self.assertIn("  name_add_mac_suffix: true\n", esphome)
        # Both use one device name, so the factory build keeps its own directory.
        self.assertRegex(top_level_block(FACTORY, "esphome"), r"\n  build_path: build/\$\{device_name\}-factory\n")

    def test_both_configs_read_the_pages_manifest(self) -> None:
        for name, text in (("c6remote.yaml", CONFIG), ("c6remote-factory.yaml", FACTORY)):
            with self.subTest(config=name):
                self.assertEqual(http_update_source(text), MANIFEST_URL)
                update = top_level_block(text, "update")
                self.assertIn("    id: firmware_update\n", update)
                self.assertIn("    name: Firmware\n", update)
                ota = top_level_block(text, "ota")
                self.assertIn("  - platform: esphome\n", ota)
                self.assertIn("  - platform: http_request\n", ota)
                self.assertIn("  id: http_client\n", top_level_block(text, "http_request"))

    def test_each_wifi_connection_checks_for_firmware(self) -> None:
        """Wi-Fi is off most of the time, so the poll interval alone rarely runs."""
        on_connect = top_level_block(FACTORY, "wifi").split("  on_connect:\n", 1)[1]
        self.assertIn("    - component.update: firmware_update\n", on_connect.split("\n  on_", 1)[0] + "\n")

    def test_a_home_assistant_action_lease_skips_the_check(self) -> None:
        """A TLS fetch next to the action would take heap from Zigbee and NimBLE."""
        on_connect = top_level_block(CONFIG, "wifi").split("  on_connect:\n", 1)[1]
        on_connect = on_connect.split("\n  on_", 1)[0] + "\n"
        self.assertIn("    - script.execute: show_idle_status\n", on_connect)
        self.assertIn("    - if:\n        condition:\n"
                      "          lambda: return !id(button_cfg).wifi_for_action_only();\n"
                      "        then:\n          - component.update: firmware_update\n", on_connect)
        self.assertEqual(CONFIG.count("component.update: firmware_update"), 1)
        # Only the lease flag may be set. A page, hold, pairing or boot session
        # sets temporary_wifi_, and Always On at boot enables Wi-Fi without either flag.
        self.assertIn("bool wifi_for_action_only() const {\n"
                      "    return this->action_wifi_ && !this->temporary_wifi_ && !this->boot_wifi_always_on_;\n"
                      "  }", BUTTON_HEADER)
        # Wi-Fi turns on only in setup() for Always On, in open_temporary_wifi_()
        # and in hold_wifi_for_action(), so the three terms cover every enable.
        self.assertEqual(BUTTON_CPP.count("wifi::global_wifi_component->enable();"), 3)
        self.assertNotIn("global_wifi_component->enable()", CONFIG)

    def test_production_never_installs_on_its_own(self) -> None:
        update = top_level_block(CONFIG, "update")
        self.assertNotIn("on_update_available", update)
        self.assertNotIn("update.perform", CONFIG)

    def test_the_factory_image_installs_with_force_and_retries(self) -> None:
        update = top_level_block(FACTORY, "update")
        self.assertIn("    update_interval: never\n", update)
        self.assertIn("    on_update_available:\n      - update.perform:\n          id: firmware_update\n"
                      "          force_update: true\n", update)
        retry = top_level_block(FACTORY, "interval")
        self.assertIn("wifi.connected:", retry)
        self.assertIn("update.is_available: firmware_update", retry)
        self.assertIn("force_update: true", retry)
        self.assertIn("component.update: firmware_update", retry)

    def test_the_factory_image_has_no_api(self) -> None:
        self.assertNotRegex(FACTORY, r"(?m)^api:")


class FlashBudgetTest(unittest.TestCase):
    """mbedTLS and Wi-Fi features that the full firmware does not use. The
    factory image has room, so it keeps the ESP-IDF defaults."""

    OFF = (
        "CONFIG_MBEDTLS_TLS_SERVER_AND_CLIENT",
        "CONFIG_MBEDTLS_KEY_EXCHANGE_RSA",
        "CONFIG_MBEDTLS_KEY_EXCHANGE_ECDH_ECDSA",
        "CONFIG_MBEDTLS_KEY_EXCHANGE_ECDH_RSA",
        "CONFIG_MBEDTLS_ECP_DP_BP256R1_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_BP384R1_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_BP512R1_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_CURVE25519_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_SECP192K1_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_SECP192R1_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_SECP224K1_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_SECP224R1_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_SECP256K1_ENABLED",
        "CONFIG_MBEDTLS_SSL_RENEGOTIATION",
        "CONFIG_MBEDTLS_X509_CSR_PARSE_C",
        "CONFIG_MBEDTLS_PEM_WRITE_C",
        "CONFIG_MBEDTLS_GCM_SUPPORT_NON_AES_CIPHER",
        "CONFIG_ESP_WIFI_ENABLE_SAE_PK",
        "CONFIG_ESP_WIFI_ENABLE_WPA3_OWE_STA",
    )
    # WPA3-SAE uses P-256, PMF uses CMAC, Zigbee uses CCM, and the CA bundle has P-384 roots.
    KEEP = (
        "CONFIG_MBEDTLS_ECP_DP_SECP256R1_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_SECP384R1_ENABLED",
        "CONFIG_MBEDTLS_ECP_DP_SECP521R1_ENABLED",
        "CONFIG_MBEDTLS_KEY_EXCHANGE_ECDHE_ECDSA",
        "CONFIG_MBEDTLS_KEY_EXCHANGE_ECDHE_RSA",
        "CONFIG_MBEDTLS_CMAC_C",
        "CONFIG_MBEDTLS_CCM_C",
        "CONFIG_MBEDTLS_SHA512_C",
        # esp_http_client calls the ALPN setter without a guard, so the link needs it.
        "CONFIG_MBEDTLS_SSL_ALPN",
        "CONFIG_MBEDTLS_CERTIFICATE_BUNDLE",
        "CONFIG_ESP_WIFI_ENABLE_WPA3_SAE",
        "CONFIG_ESP_WIFI_ENABLE_SAE_H2E",
    )

    def test_the_full_firmware_turns_off_unused_tls_and_wifi_features(self) -> None:
        esp32 = top_level_block(CONFIG, "esp32")
        self.assertIn('      CONFIG_MBEDTLS_TLS_CLIENT_ONLY: "y"\n', esp32)
        for option in self.OFF:
            with self.subTest(option=option):
                self.assertIn(f'      {option}: "n"\n', esp32)
        for option in self.KEEP:
            with self.subTest(option=option):
                self.assertNotRegex(CONFIG, rf"{option}\w*:")

    def test_the_factory_image_keeps_the_defaults(self) -> None:
        self.assertNotIn("CONFIG_MBEDTLS", FACTORY)
        self.assertNotIn("CONFIG_ESP_WIFI", FACTORY)


class ReleaseWorkflowTest(unittest.TestCase):
    def test_firmware_tags_build_both_configs_at_the_tag_version(self) -> None:
        self.assertIn("    tags: ['fw-*']\n", FIRMWARE_WORKFLOW)
        self.assertIn(r"^fw-[0-9]{4}\.([1-9]|1[0-2])\.(0|[1-9][0-9]*)$", FIRMWARE_WORKFLOW)
        # Releases are for V3 boards, which have six status LEDs. The bench default stays at four.
        self.assertIn('esphome -s fw_version "${{ steps.ver.outputs.version }}" -s status_led_count 6 '
                      'compile c6remote.yaml', FIRMWARE_WORKFLOW)
        self.assertEqual(substitution(CONFIG, "status_led_count"), '"4"')
        self.assertIn("esphome -s status_led_count 6 compile c6remote-factory.yaml", FIRMWARE_WORKFLOW)
        self.assertIn('pip install "esphome==${ESPHOME_VERSION}"', FIRMWARE_WORKFLOW)
        self.assertRegex(FIRMWARE_WORKFLOW, r"\n  ESPHOME_VERSION: \d+\.\d+\.\d+\n")

    def test_the_manifest_matches_the_http_request_update_parser(self) -> None:
        for text in ('name: "homeThing C6"', "version: $version", 'chipFamily: "ESP32-C6"',
                     "parts: [{path: $factory, offset: 0}]",
                     "ota: {path: $ota, md5: $md5, summary: $summary, release_url: $release_url}"):
            self.assertIn(text, FIRMWARE_WORKFLOW)
        # Bare names resolve next to the manifest URL.
        self.assertIn('full_ota="homething-c6-${v}.ota.bin"', FIRMWARE_WORKFLOW)
        self.assertIn('full_factory="homething-c6-${v}.factory.bin"', FIRMWARE_WORKFLOW)

    def test_a_firmware_release_is_never_latest_and_starts_pages_on_develop(self) -> None:
        self.assertIn("--latest=false", FIRMWARE_WORKFLOW)
        self.assertIn("gh workflow run pages.yml", FIRMWARE_WORKFLOW)
        self.assertIn("--ref develop", FIRMWARE_WORKFLOW)
        self.assertIn("  contents: write\n  actions: write\n", FIRMWARE_WORKFLOW)
        self.assertIn("  cancel-in-progress: false\n", FIRMWARE_WORKFLOW)

    def test_pages_adds_the_newest_firmware_release_after_the_site_build(self) -> None:
        build = PAGES_WORKFLOW.index("run: scripts/build-site.sh _site")
        firmware = PAGES_WORKFLOW.index("out=_site/firmware")
        self.assertLess(build, firmware)
        self.assertLess(firmware, PAGES_WORKFLOW.index("actions/upload-pages-artifact"))
        step = PAGES_WORKFLOW[build:firmware]
        self.assertIn("GH_TOKEN: ${{ github.token }}", step)
        self.assertIn('--output "${out}/manifest.json"', PAGES_WORKFLOW)
        self.assertIn("::notice::", step)
        self.assertTrue(MANIFEST_URL.endswith("/firmware/manifest.json"))


if __name__ == "__main__":
    unittest.main()
