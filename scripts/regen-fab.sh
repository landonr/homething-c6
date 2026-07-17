#!/usr/bin/env bash
#
# Regenerate all fabrication outputs from the KiCad source of truth.
# Run this after ANY schematic or board change so export/ stays in sync.
#
# Outputs (all into c6remote-kicad/export/):
#   - Gerbers (*.gbr) + job file (*.gbrjob)
#   - Excellon drill file (*.drl, PTH+NPTH merged)
#   - Pick-and-place / position file (c6remote-pos.csv, both sides, mm)
#   - BOM (c6remote-bom.csv, grouped by Value+Footprint, custom sourcing fields)
#
# Override the kicad-cli path on non-default installs:
#   KICAD_CLI=/path/to/kicad-cli scripts/regen-fab.sh
#
set -euo pipefail

KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KI="$REPO_ROOT/c6remote-kicad"
PCB="$KI/c6remote.kicad_pcb"
SCH="$KI/c6remote.kicad_sch"
OUT="$KI/export"

if [[ ! -x "$KICAD_CLI" ]]; then
	echo "error: kicad-cli not found at '$KICAD_CLI' (set KICAD_CLI env var)" >&2
	exit 1
fi

cd "$KI"

echo "==> Gerbers"
"$KICAD_CLI" pcb export gerbers "$PCB" -o "$OUT" --board-plot-params

echo "==> Drill"
"$KICAD_CLI" pcb export drill "$PCB" -o "$OUT/"

echo "==> Pick-and-place (position)"
"$KICAD_CLI" pcb export pos "$PCB" -o "$OUT/c6remote-pos.csv" --format csv --units mm --side both

echo "==> BOM"
"$KICAD_CLI" sch export bom "$SCH" -o "$OUT/c6remote-bom.csv" \
	--fields "Reference,QUANTITY,Value,Footprint,Datasheet,Description,Manufacturer,MPN,Digikey,Mouser,Adafruit" \
	--labels "Reference,Qty,Value,Footprint,Datasheet,Description,Manufacturer,MPN,Digikey,Mouser,Adafruit" \
	--group-by "Value,Footprint" \
	--ref-delimiter ", " --ref-range-delimiter ""

echo "==> Done. Fabrication outputs written to $OUT"
