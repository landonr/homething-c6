#!/usr/bin/env bash
# Usage: scripts/check-3dmodels.sh <board.kicad_pcb>
# Exit 1 when a ${KIPRJMOD}/3dmodels/ model that the board names is not present.
# kicad-cli writes a 3D export without the missing bodies, and the callers ignore its status.
set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
	echo "usage: $0 <board.kicad_pcb>" >&2
	exit 2
fi

MODELS="$(cd "$(dirname "$1")" && pwd)/3dmodels"
missing=""
count=0
while IFS= read -r name; do
	if [[ ! -s "$MODELS/$name" ]]; then
		missing="$missing  $name"$'\n'
		count=$((count + 1))
	fi
done < <(grep -o 'model "${KIPRJMOD}/3dmodels/[^"]*"' "$1" \
	| sed -e 's|^model "${KIPRJMOD}/3dmodels/||' -e 's|"$||' | sort -u)

if [[ $count -gt 0 ]]; then
	if [[ ! -d "$MODELS" ]]; then
		echo "error: $MODELS is missing or is a broken link." >&2
	fi
	echo "error: $count 3D model(s) that $(basename "$1") names are not in $MODELS:" >&2
	printf '%s' "$missing" >&2
	echo "The models are in the private c6remote-explode repository." >&2
	echo "Run scripts/link-3dmodels.sh to link them, then run this command again." >&2
	exit 1
fi
