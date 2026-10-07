#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/render-readme-assets.sh [options]

Render README board preview assets:
  - top, bottom, rotated top and rotated bottom PNGs, rendered with
    Blender by scripts/render-board-blender.py
  - flat top SVG
  - flat bottom SVG
  - schematic SVG

Options:
  --project-dir <dir>        KiCad project directory. Default: c6remote-kicad
  --output-dir <dir>         Asset output directory. Default: docs/readme-assets
  --kicad-cli <path>         KiCad CLI path. Default: bundled macOS KiCad path
  --flat-sides <top|bottom|both>
                             Flat SVG sides to render. Default: both
  --only <board|schematic|all>
                             Subset of assets to render: board = 3D + flat board
                             views, schematic = schematic SVG only. Default: all
  --samples <n>              Cycles samples for the 3D PNGs. Default: 1600
  -h, --help                 Show this help

The PNGs are rendered from a board GLB exported from the PCB on every run, with
Blender by scripts/render-board-blender.py. BLENDER overrides the Blender binary.
If BLENDER is not set, the script uses blender on PATH, then the macOS app path.
If magick is on PATH, the script trims each PNG.
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_DIR="${REPO_ROOT}/c6remote-kicad"
OUTPUT_DIR="${REPO_ROOT}/docs/readme-assets"
KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
SAMPLES=1600
FLAT_SIDES="both"
ONLY="all"

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
    --flat-sides)
      FLAT_SIDES="${2:-}"
      shift 2
      ;;
    --only)
      ONLY="${2:-}"
      shift 2
      ;;
    --samples)
      SAMPLES="${2:-}"
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

case "${ONLY}" in
  board|schematic|all) ;;
  *)
    echo "Invalid --only value: ${ONLY}" >&2
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

if [[ "${ONLY}" != "schematic" ]]; then
  BLENDER_BIN="${BLENDER:-}"
  if [[ -z "${BLENDER_BIN}" ]]; then
    BLENDER_BIN="$(command -v blender || true)"
  fi
  if [[ -z "${BLENDER_BIN}" ]]; then
    BLENDER_BIN="/Applications/Blender.app/Contents/MacOS/Blender"
  fi
  if [[ ! -x "${BLENDER_BIN}" ]]; then
    echo "Blender not executable: ${BLENDER_BIN} (set BLENDER, or put blender on PATH)" >&2
    exit 1
  fi
  BOARD_DIR="$(mktemp -d)"
  trap 'rm -rf "${BOARD_DIR}"' EXIT
  # The export exits non-zero when a footprint names a 3D model that is not installed
  # (see export-case-refs.sh), so check the file rather than the status.
  "${KICAD_CLI}" pcb export glb "${PCB_FILE}" -o "${BOARD_DIR}/c6remote-board.glb" \
    --force --include-silkscreen >/dev/null 2>&1 || true
  if [[ ! -s "${BOARD_DIR}/c6remote-board.glb" ]]; then
    echo "Board GLB export failed: ${PCB_FILE}" >&2
    exit 1
  fi
  "${BLENDER_BIN}" -b --factory-startup -noaudio --python-exit-code 1 \
    -P "${SCRIPT_DIR}/render-board-blender.py" -- \
    --glb "${BOARD_DIR}/c6remote-board.glb" \
    --hdr "${SCRIPT_DIR}/assets/env-studio.hdr" \
    --out-dir "${OUTPUT_DIR}" \
    --samples "${SAMPLES}"
  if command -v magick >/dev/null 2>&1; then
    for f in board-3d-top board-3d-bottom board-3d-rotated-top board-3d-rotated-bottom; do
      magick "${OUTPUT_DIR}/${f}.png" -trim +repage "${OUTPUT_DIR}/${f}.png"
    done
  fi
  for f in board-3d-top board-3d-bottom board-3d-rotated-top board-3d-rotated-bottom; do
    echo "Wrote ${OUTPUT_DIR}/${f}.png"
  done
fi

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
    --black-and-white

  mv "${OUTPUT_DIR}/c6remote.svg" "${OUTPUT_DIR}/schematic.svg"
  echo "Wrote ${OUTPUT_DIR}/schematic.svg"
}

if [[ "${ONLY}" != "schematic" ]]; then
  case "${FLAT_SIDES}" in
    both)
      render_flat top
      render_flat bottom
      ;;
    top|bottom)
      render_flat "${FLAT_SIDES}"
      ;;
  esac
fi

if [[ "${ONLY}" != "board" ]]; then
  render_schematic
fi
