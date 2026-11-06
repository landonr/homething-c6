#!/usr/bin/env bash
#
# Export the board references the case model reads. Run after any board change
# that moves the outline, the mounting holes, or a component the case opens onto.
#
# Outputs (all into case/board/):
#   - c6remote-board-only.step  bare PCB solid, the case outline source (tracked)
#   - c6remote-outline.dxf      Edge.Cuts profile for other CAD tools (tracked)
#   - c6remote-board.step       full assembly, source of the keepout heights (untracked)
#   - c6remote-board.glb        mesh assembly for viewers (untracked)
#
# J1 uses the stock KiCad PicoBlade 53261-0271 model, so both assembly exports
# include the battery connector. D2-D7 use the checked-in
# 3dmodels/WS2812C-2020.step and are present. SW1-SW11 have only the
# 3dmodels/TL3315NF160Q.wrl model, so the STEP export omits them.
#
# Override the kicad-cli path on non-default installs:
#   KICAD_CLI=/path/to/kicad-cli scripts/export-case-refs.sh
#
set -euo pipefail

KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PCB="$REPO_ROOT/c6remote-kicad/c6remote.kicad_pcb"
OUT="$REPO_ROOT/case/board"

if [[ ! -x "$KICAD_CLI" ]]; then
	echo "error: kicad-cli not found at '$KICAD_CLI' (set KICAD_CLI env var)" >&2
	exit 1
fi

mkdir -p "$OUT"

# The STEP export exits 2 because a STEP file cannot use the VRML switch models.
# Check the output file, not the status.
export_assembly() {
	local out="$1"
	shift
	rm -f "$out"
	"$@" || true
	if [[ ! -s "$out" ]]; then
		echo "error: $out was not written" >&2
		exit 1
	fi
}

echo "==> Board-only STEP"
"$KICAD_CLI" pcb export step "$PCB" -o "$OUT/c6remote-board-only.step" --board-only --force

echo "==> Edge.Cuts DXF"
"$KICAD_CLI" pcb export dxf "$PCB" --mode-single -o "$OUT/c6remote-outline.dxf" \
	--layers Edge.Cuts --output-units mm --exclude-refdes --exclude-value

echo "==> Assembly STEP"
export_assembly "$OUT/c6remote-board.step" \
	"$KICAD_CLI" pcb export step "$PCB" -o "$OUT/c6remote-board.step" --subst-models --force

echo "==> Assembly GLB"
export_assembly "$OUT/c6remote-board.glb" \
	"$KICAD_CLI" pcb export glb "$PCB" -o "$OUT/c6remote-board.glb" --force --include-silkscreen

echo "==> Done. Case references written to $OUT"
