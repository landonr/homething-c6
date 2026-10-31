#!/usr/bin/env bash
#
# Make the C6 page video clips in site/assets/c6/.
#
#   scripts/site-media.sh <IMG_7480_clicks.mp4>
#
# The feature clips come from the living room demo video. The explode clip comes from
# docs/readme-assets/case-explode-loop.webp. Needs ffmpeg and ImageMagick.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${1:?usage: scripts/site-media.sh <IMG_7480_clicks.mp4>}"
OUT="$REPO_ROOT/site/assets/c6"
# H.264 has no alpha, so the explode frames are flattened onto a white card. The browser
# draws video colours a little differently from CSS colours, so an exact band match shows a box.
CARD="#ffffff"

mkdir -p "$OUT"

# name start end crop-y poster-time
CLIPS=(
	"tv 13.2 16.8 200 16.4"
	"lights 27.8 32.3 200 28.2"
	"fireplace 33.2 36.2 250 35.3"
	"sleep 44.0 46.3 360 45.2"
)

for clip in "${CLIPS[@]}"; do
	read -r name start end y poster <<<"$clip"
	crop="crop=1080:1440:0:$y,scale=480:640"
	ffmpeg -v error -y -ss "$start" -to "$end" -i "$SRC" -an -vf "$crop" \
		-c:v libx264 -profile:v high -preset slow -crf 26 -pix_fmt yuv420p -movflags +faststart \
		"$OUT/clip-$name.mp4"
	ffmpeg -v error -y -ss "$poster" -i "$SRC" -frames:v 1 -vf "$crop" -q:v 4 "$OUT/clip-$name.jpg"
done

FRAMES="$(mktemp -d)"
trap 'rm -rf "$FRAMES"' EXIT
magick "$REPO_ROOT/docs/readme-assets/case-explode-loop.webp" -coalesce \
	-background "$CARD" -alpha remove -alpha off "$FRAMES/f_%04d.png"
# The WebP frames are 33 ms each.
ffmpeg -v error -y -framerate 1000/33 -i "$FRAMES/f_%04d.png" \
	-vf "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p" \
	-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
	-c:v libx264 -profile:v high -preset slow -crf 26 -movflags +faststart \
	"$OUT/explode.mp4"
magick "$FRAMES/f_0106.png" -quality 85 "$OUT/explode.jpg"

# The remote drawing and the edge of the Button 7 actions from the Buttons page, for the
# "No flashing needed" card.
magick "$REPO_ROOT/docs/readme-assets/buttons-page-assign.png" -crop 900x1020+20+420 +repage \
	-resize 600x -strip -quality 82 "$OUT/feature-web-page.jpg"

ls -la "$OUT"
