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
# D2-D5 and J1 are absent from both assembly exports: their footprints point at
# 3D model paths that do not exist. J1 is a battery connector, so its height is a
# real gap in the bottom-side keepout, not a cosmetic one.
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

# The assembly exports exit 2 because five footprints reference 3D models that are
# not installed, so check the output file rather than the status.
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
