#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/render-readme-assets.sh [options]

Render README board preview assets:
  - 3D top PNG
  - 3D bottom PNG
  - flat top SVG
  - flat bottom SVG
  - schematic SVG

Options:
  --project-dir <dir>        KiCad project directory. Default: c6remote-kicad
  --output-dir <dir>         Asset output directory. Default: docs/readme-assets
  --kicad-cli <path>         KiCad CLI path. Default: bundled macOS KiCad path
  --width <px>               3D render width. Default: 1800
  --height <px>              3D render height. Default: 1200
  --quality <basic|high|user|job_settings>
                             3D render quality. Default: high
  --top-rotate <x,y,z>       Top render rotation. Default: 315,0,35
  --bottom-rotate <x,y,z>    Bottom render rotation. Default: 315,0,35
  --top-camera-side <side>   Camera side for top output. Default: bottom
  --bottom-camera-side <side>
                             Camera side for bottom output. Default: top
  --flat-sides <top|bottom|both>
                             Flat SVG sides to render. Default: both
  -h, --help                 Show this help
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_DIR="${REPO_ROOT}/c6remote-kicad"
OUTPUT_DIR="${REPO_ROOT}/docs/readme-assets"
KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
WIDTH="1800"
HEIGHT="1200"
QUALITY="high"
TOP_ROTATE="-45,0,45"
BOTTOM_ROTATE="-45,0,-45"
TOP_CAMERA_SIDE="top"
BOTTOM_CAMERA_SIDE="bottom"
FLAT_SIDES="both"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --kicad-cli)
      KICAD_CLI="${2:-}"
      shift 2
      ;;
    --width)
      WIDTH="${2:-}"
      shift 2
      ;;
    --height)
      HEIGHT="${2:-}"
      shift 2
      ;;
    --quality)
      QUALITY="${2:-}"
      shift 2
      ;;
    --top-rotate)
      TOP_ROTATE="${2:-}"
      shift 2
      ;;
    --bottom-rotate)
      BOTTOM_ROTATE="${2:-}"
      shift 2
      ;;
    --top-camera-side)
      TOP_CAMERA_SIDE="${2:-}"
      shift 2
      ;;
    --bottom-camera-side)
      BOTTOM_CAMERA_SIDE="${2:-}"
      shift 2
      ;;
    --flat-sides)
      FLAT_SIDES="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

case "${FLAT_SIDES}" in
  top|bottom|both) ;;
  *)
    echo "Invalid flat sides value: ${FLAT_SIDES}" >&2
    exit 1
    ;;
esac

case "${QUALITY}" in
  basic|high|user|job_settings) ;;
  *)
    echo "Invalid quality: ${QUALITY}" >&2
    exit 1
    ;;
esac

case "${TOP_CAMERA_SIDE}" in
  top|bottom|left|right|front|back) ;;
  *)
    echo "Invalid top camera side: ${TOP_CAMERA_SIDE}" >&2
    exit 1
    ;;
esac

case "${BOTTOM_CAMERA_SIDE}" in
  top|bottom|left|right|front|back) ;;
  *)
    echo "Invalid bottom camera side: ${BOTTOM_CAMERA_SIDE}" >&2
    exit 1
    ;;
esac

if [[ ! -x "${KICAD_CLI}" ]]; then
  echo "KiCad CLI not executable: ${KICAD_CLI}" >&2
  exit 1
fi

PCB_FILE="${PROJECT_DIR}/c6remote.kicad_pcb"
if [[ ! -f "${PCB_FILE}" ]]; then
  echo "PCB file not found: ${PCB_FILE}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}"

render_3d() {
  local side="$1"
  local camera_side="$2"
  local rotate="$3"
  local output_file="${OUTPUT_DIR}/board-3d-${side}.png"

  "${KICAD_CLI}" pcb render "${PCB_FILE}" \
    --output "${output_file}" \
    --side "${camera_side}" \
    --width "${WIDTH}" \
    --height "${HEIGHT}" \
    --quality "${QUALITY}" \
    --background transparent \
    --rotate "${rotate}"

  echo "Wrote ${output_file}"
}

render_3d top "${TOP_CAMERA_SIDE}" "${TOP_ROTATE}"
render_3d bottom "${BOTTOM_CAMERA_SIDE}" "${BOTTOM_ROTATE}"

render_flat() {
  local side="$1"

  "${SCRIPT_DIR}/render-2d.sh" \
    --project-dir "${PROJECT_DIR}" \
    --kicad-cli "${KICAD_CLI}" \
    --side "${side}" \
    --format svg \
    --output "${OUTPUT_DIR}"

  mv "${OUTPUT_DIR}/${side}.svg" "${OUTPUT_DIR}/board-flat-${side}.svg"
  echo "Wrote ${OUTPUT_DIR}/board-flat-${side}.svg"
}

render_schematic() {
  local schematic_file="${PROJECT_DIR}/c6remote.kicad_sch"

  if [[ ! -f "${schematic_file}" ]]; then
    echo "Schematic file not found: ${schematic_file}" >&2
    exit 1
  fi

  "${KICAD_CLI}" sch export svg "${schematic_file}" \
    --output "${OUTPUT_DIR}" \
    --exclude-drawing-sheet \
    --black-and-white \
    --no-background-color

  mv "${OUTPUT_DIR}/c6remote.svg" "${OUTPUT_DIR}/schematic.svg"
  echo "Wrote ${OUTPUT_DIR}/schematic.svg"
}

case "${FLAT_SIDES}" in
  both)
    render_flat top
    render_flat bottom
    ;;
  top|bottom)
    render_flat "${FLAT_SIDES}"
    ;;
esac

render_schematic
