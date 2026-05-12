#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/render-2d.sh [options]

Render 2D board view from KiCad CLI.

Options:
  --side <top|bottom|both>   Which side to render. Default: both
  --format <svg|pdf>         Output format. Default: svg
  --output <dir>             Output directory. Default: c6remote-kicad/renders/<format>
  --project-dir <dir>        KiCad project directory. Default: c6remote-kicad
  --kicad-cli <path>         KiCad CLI path. Default: bundled macOS KiCad path
  -h, --help                 Show this help
EOF
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SIDE="both"
FORMAT="svg"
PROJECT_DIR="${REPO_ROOT}/c6remote-kicad"
KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --side)
      SIDE="${2:-}"
      shift 2
      ;;
    --format)
      FORMAT="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --project-dir)
      PROJECT_DIR="${2:-}"
      shift 2
      ;;
    --kicad-cli)
      KICAD_CLI="${2:-}"
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

case "${SIDE}" in
  top|bottom|both) ;;
  *)
    echo "Invalid side: ${SIDE}" >&2
    exit 1
    ;;
esac

case "${FORMAT}" in
  svg|pdf) ;;
  *)
    echo "Invalid format: ${FORMAT}" >&2
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

if [[ -z "${OUTPUT_DIR}" ]]; then
  OUTPUT_DIR="${PROJECT_DIR}/renders/${FORMAT}"
fi

mkdir -p "${OUTPUT_DIR}"

render_side() {
  local side="$1"
  local layers output_file
  local -a cmd=()

  case "${side}" in
    top)
      layers="F.Cu,F.Mask,F.Silkscreen,Edge.Cuts"
      ;;
    bottom)
      layers="B.Cu,B.Mask,B.Silkscreen,Edge.Cuts"
      ;;
    *)
      echo "Unsupported side: ${side}" >&2
      exit 1
      ;;
  esac

  output_file="${OUTPUT_DIR}/${side}.${FORMAT}"

  if [[ "${FORMAT}" == "svg" ]]; then
    cmd=(
      "${KICAD_CLI}" pcb export svg "${PCB_FILE}"
      --output "${output_file}"
      --layers "${layers}"
      --mode-single
      --page-size-mode 2
      --exclude-drawing-sheet
      --check-zones
    )
  else
    cmd=(
      "${KICAD_CLI}" pcb export pdf "${PCB_FILE}"
      --output "${output_file}"
      --layers "${layers}"
      --mode-single
      --scale 0
      --check-zones
    )
  fi

  if [[ "${side}" == "bottom" ]]; then
    cmd+=(--mirror)
  fi

  "${cmd[@]}"
  echo "Wrote ${output_file}"
}

if [[ "${SIDE}" == "both" ]]; then
  render_side top
  render_side bottom
else
  render_side "${SIDE}"
fi
