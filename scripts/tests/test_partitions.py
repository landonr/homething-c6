"""Checks partitions.csv with the offset rules of ESP-IDF gen_esp32part.py.

An OTA cannot change the partition table, so a layout change reaches a unit
only through a USB flash. These checks pin the layout that the build makes.
"""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).parents[2]
PARTITIONS = ROOT / "partitions.csv"
FIRMWARE_WORKFLOW = ROOT / ".github" / "workflows" / "firmware.yml"

# CONFIG_PARTITION_TABLE_OFFSET is 0x8000, and the table takes one 0x1000 sector.
FIRST_OFFSET = 0x8000 + 0x1000
# gen_esp32part.py ALIGNMENT: an app partition starts on 64 KB, data on 4 KB.
ALIGNMENT = {"app": 0x10000, "data": 0x1000}
# A no-secure-boot app partition size must be a multiple of the 4 KB erase sector.
APP_SIZE_ALIGNMENT = 0x1000
FLASH_SIZE = 4 * 1024 * 1024
NVS_MIN_SIZE = 0x3000

EXPECTED = [
    ("otadata", "data", "ota", 0x9000, 0x2000),
    ("phy_init", "data", "phy", 0xB000, 0x1000),
    ("zb_fct", "data", "fat", 0xC000, 0x1000),
    ("app0", "app", "ota_0", 0x10000, 0x1F0000),
    ("app1", "app", "ota_1", 0x200000, 0x1F0000),
    ("nvs", "data", "nvs", 0x3F0000, 0x10000),
]


def parse_size(text: str) -> int:
    text = text.strip()
    match = re.fullmatch(r"(\d+)([KM])", text, re.IGNORECASE)
    if match:
        return int(match.group(1)) * (1024 if match.group(2).upper() == "K" else 1024 * 1024)
    return int(text, 0)


def layout() -> list[tuple[str, str, str, int, int]]:
    """Returns (name, type, subtype, offset, size) rows with the offsets that
    gen_esp32part.py fills in for empty offset fields."""
    rows = []
    last_end = FIRST_OFFSET
    for line in PARTITIONS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = [field.strip() for field in line.split(",")]
        name, ptype, subtype, offset, size = fields[:5]
        size_value = parse_size(size)
        if offset:
            offset_value = parse_size(offset)
        else:
            align = ALIGNMENT[ptype]
            offset_value = last_end + (-last_end % align)
        rows.append((name, ptype, subtype, offset_value, size_value))
        last_end = offset_value + size_value
    return rows


class PartitionTableTest(unittest.TestCase):
    def test_the_auto_offsets_give_the_expected_layout(self) -> None:
        self.assertEqual(layout(), EXPECTED)

    def test_each_partition_follows_the_idf_alignment_rules(self) -> None:
        for name, ptype, _subtype, offset, size in layout():
            with self.subTest(partition=name):
                self.assertEqual(offset % ALIGNMENT[ptype], 0)
                if ptype == "app":
                    self.assertEqual(size % APP_SIZE_ALIGNMENT, 0)

    def test_the_table_fills_4_mb_flash_without_overlap(self) -> None:
        rows = sorted(layout(), key=lambda row: row[3])
        self.assertGreaterEqual(rows[0][3], FIRST_OFFSET)
        for before, after in zip(rows, rows[1:]):
            self.assertLessEqual(before[3] + before[4], after[3], f"{before[0]} overlaps {after[0]}")
        self.assertEqual(rows[-1][3] + rows[-1][4], FLASH_SIZE)

    def test_the_fixed_partitions_keep_their_idf_and_zigbee_rules(self) -> None:
        rows = {row[0]: row for row in layout()}
        # gen_esp32part.py rejects any other otadata size.
        self.assertEqual(rows["otadata"][4], 0x2000)
        self.assertGreaterEqual(rows["nvs"][4], NVS_MIN_SIZE)
        # The Zigbee component checks for this name in a custom table.
        self.assertEqual(rows["zb_fct"][1:3], ("data", "fat"))
        self.assertEqual(rows["app0"][4], rows["app1"][4])

    def test_the_release_size_check_reads_the_app_slot_from_the_table(self) -> None:
        workflow = FIRMWARE_WORKFLOW.read_text()
        self.assertIn("awk -F, '$1 ~ /^app0/ { gsub(/[[:space:]]/, \"\", $5); print $5 }' partitions.csv", workflow)
        self.assertNotRegex(workflow, r"0x1E0000|1966080")


if __name__ == "__main__":
    unittest.main()
