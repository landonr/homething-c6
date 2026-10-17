"""Pattern checks for the Home Assistant assignment type on the /buttons page.

test_page_js.py runs the behaviour. These checks pin the contract strings that
the firmware and the preview share, so a rename shows up here first.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).parents[2]
PAGE = (ROOT / "components" / "button_config" / "button_config_page.h").read_text()
PREVIEW = (ROOT / "scripts" / "preview-buttons-page.py").read_text()

ERRORS = (
    "unknown Home Assistant kind or action",
    "an entity id is domain.object_id, up to 64 characters, and its domain must match the kind",
    "a brightness step is 1 to 100",
)


class HaPageTest(unittest.TestCase):
    def test_the_editor_lists_the_option_after_ble_hid(self) -> None:
        self.assertIn('opts.push(["ha","Home Assistant"]);', PAGE)
        self.assertIn("act===\"ha\"?haPanel(lock)", PAGE)

    def test_every_kind_and_action_token_is_on_the_page(self) -> None:
        for token in ("light", "switch", "input_boolean", "fan", "cover", "lock", "scene",
                      "script", "automation", "button", "input_button", "media_player",
                      "homeassistant", "brightness_up", "brightness_down", "increase_speed",
                      "decrease_speed", "open_cover", "close_cover", "stop_cover", "trigger",
                      "press", "media_play_pause", "volume_up", "volume_down",
                      "media_next_track", "media_previous_track"):
            self.assertRegex(PAGE, r"\b" + token + r"\b", token)

    def test_the_page_and_the_preview_share_the_firmware_error_text(self) -> None:
        for text in ERRORS:
            self.assertIn(text, PAGE)
            self.assertIn(text, PREVIEW)

    def test_the_save_and_test_paths_post_the_contract_fields(self) -> None:
        self.assertIn('go("set_ha",null,"&kind="+hkd+"&act="+hac+"&val="+v+"&entity="', PAGE)
        self.assertIn('post("test_ha",s)', PAGE)
        self.assertIn('post("set_ha",e.slot,null,undefined,', PAGE)

    def test_the_entity_box_switches_off_autocorrection(self) -> None:
        for text in ("placeholder=light.living_room", "autocapitalize=off", "autocorrect=off",
                     "spellcheck=false"):
            self.assertIn(text, PAGE)

    def test_the_panel_carries_the_integration_note(self) -> None:
        self.assertIn("Allow the device to perform Home Assistant actions", PAGE)
        self.assertIn("The first press after sleep waits a few seconds", PAGE)
        self.assertIn("<b>Allow the device to perform Home Assistant actions</b>", PAGE)

    def test_the_page_has_no_em_dash(self) -> None:
        self.assertNotIn("—", PAGE)

    def test_the_preview_serves_the_ha_state_fields(self) -> None:
        for field in ("ha_kind", "ha_act", "ha_val", "ha_entity"):
            self.assertIn('"%s"' % field, PREVIEW)
        self.assertRegex(PREVIEW, r'"ha": \{"pending": 0, "last_slot": 0, "last": "none", "error": ""\}')
        self.assertIn('action == "test_ha"', PREVIEW)
        self.assertIn('action == "set_ha"', PREVIEW)

    def test_the_preview_serves_the_api_gate_and_refuses_a_test_like_the_firmware(self) -> None:
        cpp = (ROOT / "components" / "button_config" / "button_config.cpp").read_text()
        self.assertIn('"api_gated": False,', PREVIEW)
        self.assertIn('STATE["network"]["api_gated"] = not STATE["radios"]["home_assistant"]', PREVIEW)
        for text in ("Home Assistant is off in Config", "Home Assistant API is off until the remote restarts"):
            self.assertIn(f'"error":"{text}"', cpp)
            self.assertIn(f'"error": "{text}"', PREVIEW)


if __name__ == "__main__":
    unittest.main()
