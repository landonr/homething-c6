#!/usr/bin/env bash
#
# Regenerate the BOM from the KiCad schematic (source of truth).
# Run this after editing any symbol sourcing field (Datasheet, Manufacturer,
# MPN, Digikey, Mouser, Adafruit, LCSC) so export/c6remote-bom.csv stays in sync.
#
# The LCSC column holds a product URL like the other distributor columns, not a
# bare C-number. JLCPCB's assembly upload matches on the bare part number, so
# read it out of the URL when filling their template.
#
# Use kicad-cli, NOT the KiCad MCP export_bom tool: the MCP tool emits a
# different schema (regrouped rows, drops the custom sourcing columns, lists
# test points) and silently clobbers the curated CSV.
#
# Output: c6remote-kicad/export/c6remote-bom.csv
#   (grouped by Value+Footprint, custom sourcing fields, ", " ref delimiter)
#
# Override the kicad-cli path on non-default installs:
#   KICAD_CLI=/path/to/kicad-cli scripts/export-bom.sh
#
set -euo pipefail

KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KI="$REPO_ROOT/c6remote-kicad"
SCH="$KI/c6remote.kicad_sch"
OUT="$KI/export/c6remote-bom.csv"

if [[ ! -x "$KICAD_CLI" ]]; then
	echo "error: kicad-cli not found at '$KICAD_CLI' (set KICAD_CLI env var)" >&2
	exit 1
fi

echo "==> BOM"
"$KICAD_CLI" sch export bom "$SCH" -o "$OUT" \
	--fields "Reference,QUANTITY,Value,Footprint,Datasheet,Description,Manufacturer,MPN,Digikey,Mouser,Adafruit,LCSC" \
	--labels "Reference,Qty,Value,Footprint,Datasheet,Description,Manufacturer,MPN,Digikey,Mouser,Adafruit,LCSC" \
	--group-by "Value,Footprint" \
	--ref-delimiter ", " --ref-range-delimiter ""

echo "==> Done. BOM written to $OUT"
