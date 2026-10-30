#!/usr/bin/env bash
#
# Assemble the static website into one directory for GitHub Pages or a local preview.
#
#   scripts/build-site.sh [out-dir]    (default: _site)
#
# The pages come from site/. The product images come from docs/readme-assets/ at
# build time, so git keeps one copy of each binary. If a page uses another image
# from docs/readme-assets/, add it to README_ASSETS below.
#
# Preview: scripts/build-site.sh && python3 -m http.server 8130 -d _site
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-_site}"

README_ASSETS=(
	homeThingLogo.svg
	remote-build-stages.jpg
	case-annotated-front.png
	case-annotated-back.png
	remote-controls-annotated.svg
	case-exploded.png
	case-front-iso-sls.png
	case-front-iso-fdm.png
	buttons-page-assign.png
)

mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

# The output directory is wiped, so refuse anything that holds real files.
case "$OUT" in
	/ | "$HOME" | "$REPO_ROOT" | "$REPO_ROOT/site" | "$REPO_ROOT/site/"* | "$REPO_ROOT/docs" | "$REPO_ROOT/docs/"*)
		echo "error: refusing to use '$OUT' as the output directory" >&2
		exit 1
		;;
esac

rm -rf "$OUT"
mkdir -p "$OUT/assets"

cp -R "$REPO_ROOT/site/." "$OUT/"
for f in "${README_ASSETS[@]}"; do
	cp "$REPO_ROOT/docs/readme-assets/$f" "$OUT/assets/$f"
done

find "$OUT" -name .DS_Store -delete
# GitHub Pages must serve the files as they are, without a Jekyll pass.
touch "$OUT/.nojekyll"

echo "==> Site written to $OUT"
