#!/usr/bin/env bash
#
# Make the C6 page video clips in site/assets/c6/.
#
#   scripts/site-media.sh <IMG_7480_clicks.mp4>
#
# The feature clips come from the living room demo video. The explode clip comes from
# docs/readme-assets/case-explode-loop.webp. Needs FFmpeg with animated WebP support and ImageMagick.
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${1:?usage: scripts/site-media.sh <IMG_7480_clicks.mp4>}"
OUT="$REPO_ROOT/site/assets/c6"
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

LOOP="$REPO_ROOT/docs/readme-assets/case-explode-loop.webp"
IFS=, read -r width height fps < <(ffprobe -v error -select_streams v:0 \
	-show_entries stream=width,height,r_frame_rate -of csv=p=0 "$LOOP")
ffmpeg -v error -y -i "$LOOP" \
	-filter_complex "color=c=white:s=${width}x${height}:r=${fps}[bg];[bg][0:v]overlay=shortest=1:format=auto,scale=out_color_matrix=bt709:out_range=tv,setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709,format=yuv420p[out]" \
	-map '[out]' -fps_mode passthrough \
	-colorspace bt709 -color_primaries bt709 -color_trc bt709 -color_range tv \
	-c:v libx264 -profile:v high -preset slow -crf 26 -movflags +faststart \
	"$OUT/explode.mp4"

# The remote drawing and the edge of the Button 7 actions from the Buttons page, for the
# "No flashing needed" card.
magick "$REPO_ROOT/docs/readme-assets/buttons-page-assign.png" -crop 900x1020+20+420 +repage \
	-resize 600x -strip -quality 82 "$OUT/feature-web-page.jpg"

ls -la "$OUT"
