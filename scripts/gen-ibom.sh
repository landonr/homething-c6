#!/usr/bin/env bash
#
# Generate an InteractiveHtmlBom review page for the board.
# Run this before a fab order for a visual pin-1 / placement walk that DRC
# cannot do (see docs/pre-fab-checklist.md).
#
# Output: c6remote-kicad/ibom.html (generated review artifact, gitignored,
# never commit it: source of truth is the schematic/board, not this file).
#
# Clones openscopeproject/InteractiveHtmlBom into a cache dir on first run
# (shallow clone), then invokes it with KiCad's bundled Python, which has
# the pcbnew module the generator needs.
#
# Override the cache dir or the KiCad Python on non-default installs:
#   IBOM_CACHE_DIR=/path/to/cache KICAD_PYTHON=/path/to/python3 scripts/gen-ibom.sh
#
set -euo pipefail

IBOM_REPO_URL="${IBOM_REPO_URL:-https://github.com/openscopeproject/InteractiveHtmlBom}"
IBOM_CACHE_DIR="${IBOM_CACHE_DIR:-$HOME/.cache/InteractiveHtmlBom}"
KICAD_PYTHON="${KICAD_PYTHON:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KI="$REPO_ROOT/c6remote-kicad"
PCB="$KI/c6remote.kicad_pcb"

if [[ ! -x "$KICAD_PYTHON" ]]; then
	echo "error: KiCad bundled python3 not found at '$KICAD_PYTHON' (set KICAD_PYTHON env var)" >&2
	exit 1
fi

if [[ ! -f "$IBOM_CACHE_DIR/InteractiveHtmlBom/generate_interactive_bom.py" ]]; then
	echo "==> Cloning InteractiveHtmlBom into $IBOM_CACHE_DIR"
	rm -rf "$IBOM_CACHE_DIR"
	git clone --depth 1 "$IBOM_REPO_URL" "$IBOM_CACHE_DIR"
fi

GENERATOR="$IBOM_CACHE_DIR/InteractiveHtmlBom/generate_interactive_bom.py"

echo "==> Generating IBOM"
"$KICAD_PYTHON" "$GENERATOR" "$PCB" --no-browser --dest-dir "$KI" --name-format ibom

echo "==> Done. Review artifact written to $KI/ibom.html (not committed)"
