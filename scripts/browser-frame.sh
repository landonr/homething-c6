#!/usr/bin/env bash
#
# Draw a plain browser window around a web page screenshot, to match the .browser frame on
# the site. GitHub cannot style README images, so the frame goes into the image itself.
#
#   scripts/browser-frame.sh <in.png> <out.png> [address]
#
# Needs ImageMagick. Set FONT to override the address font.
set -euo pipefail

IN="${1:?usage: scripts/browser-frame.sh <in.png> <out.png> [address]}"
OUT="${2:?usage: scripts/browser-frame.sh <in.png> <out.png> [address]}"
URL="${3:-homething-c6-13f498.local}"
FONT="${FONT:-/System/Library/Fonts/SFNS.ttf}"

W=$(magick identify -format %w "$IN")
H=$(magick identify -format %h "$IN")
# Sizes are the site's CSS pixels times the capture scale. The screenshots are 1100 CSS px wide.
S=$(( W / 1100 ))
(( S >= 1 )) || S=1

BAR=$(( 45 * S ))
PAD=$(( 14 * S ))
R=$(( 5 * S ))
STEP=$(( 16 * S ))
CY=$(( BAR / 2 ))
X1=$(( PAD + R ))
X2=$(( X1 + STEP ))
X3=$(( X2 + STEP ))
# The address field starts after the dots and keeps a right margin as wide as the dots, so it
# sits in the middle of the bar.
PX0=$(( X3 + R + 12 * S ))
PX1=$(( W - PAD - 42 * S ))
PY0=$(( 10 * S ))
PY1=$(( BAR - 10 * S ))
TEXT_X=$(( (PX0 + PX1) / 2 - W / 2 ))
CORNER=$(( 12 * S ))

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

magick -size "${W}x${BAR}" xc:'#e8e8ec' \
	-fill '#ff5f57' -draw "circle $X1,$CY $(( X1 + R )),$CY" \
	-fill '#febc2e' -draw "circle $X2,$CY $(( X2 + R )),$CY" \
	-fill '#28c840' -draw "circle $X3,$CY $(( X3 + R )),$CY" \
	-fill white -draw "roundrectangle $PX0,$PY0 $PX1,$PY1 $(( 6 * S )),$(( 6 * S ))" \
	-font "$FONT" -pointsize $(( 12 * S )) -fill '#6e6e73' -gravity center -annotate "+${TEXT_X}+0" "$URL" \
	\( -size "${W}x${S}" xc:'#d9d9de' \) -append \
	"$IN" -append "$TMP/window.png"

WH=$(( BAR + S + H ))
magick -size "${W}x${WH}" xc:none -fill white \
	-draw "roundrectangle 0,0 $(( W - 1 )),$(( WH - 1 )) $CORNER,$CORNER" "$TMP/mask.png"
magick "$TMP/window.png" "$TMP/mask.png" -alpha off -compose CopyOpacity -composite \
	-fill none -stroke 'rgba(0,0,0,0.12)' -strokewidth "$S" \
	-draw "roundrectangle 0,0 $(( W - 1 )),$(( WH - 1 )) $CORNER,$CORNER" "$TMP/rounded.png"

# A soft shadow on a transparent margin, like the box-shadow on the site.
magick "$TMP/rounded.png" \
	\( +clone -background black -shadow "18x$(( 16 * S ))+0+$(( 8 * S ))" \) \
	+swap -background none -layers merge +repage "$OUT"
