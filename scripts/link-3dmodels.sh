#!/usr/bin/env bash
# Link c6remote-kicad/3dmodels to the KiCad 3D models in the private c6remote-explode
# checkout. Run once for each clone or worktree. EXPLODE overrides the checkout path.
set -euo pipefail

EXPLODE="${EXPLODE:-$HOME/dev/c6remote-explode}"
ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
LINK="$ROOT/c6remote-kicad/3dmodels"

if [[ ! -d "$EXPLODE/3dmodels" ]]; then
	echo "error: no 3dmodels directory in '$EXPLODE'." >&2
	echo "Clone c6remote-explode to that path, or set EXPLODE to its checkout." >&2
	exit 1
fi
TARGET="$(cd "$EXPLODE/3dmodels" && pwd)"

if [[ -L "$LINK" ]]; then
	if [[ "$(readlink "$LINK")" == "$TARGET" ]]; then
		echo "$LINK already links to $TARGET"
		exit 0
	fi
	echo "replacing the old link to $(readlink "$LINK")"
	rm "$LINK"
elif [[ -e "$LINK" ]]; then
	echo "error: $LINK is a real file or directory, not a link. Move it away first." >&2
	exit 1
fi

ln -s "$TARGET" "$LINK"
echo "linked $LINK -> $TARGET"
