# c6homeThing

A handheld remote for TV, Sonos, zigbee lights, and Home Assistant. No touchscreen, no digging through apps, no device that has to live on a charger. Physical buttons, a rotary control, fast access, and long idle life.

This repo is the hardware side of that project. The source of truth lives in `c6remote-kicad/`. Current design is a KiCad prototype built around a Seeed Studio XIAO ESP32-C6.

| View | Top | Bottom |
| --- | --- | --- |
| 3D | ![3D top preview of current board prototype](docs/readme-assets/board-3d-top.png) | ![3D bottom preview of current board prototype](docs/readme-assets/board-3d-bottom.png) |
| Flat SVG | ![Flat top SVG preview of current board prototype](docs/readme-assets/board-flat-top.svg) | ![Flat bottom SVG preview of current board prototype](docs/readme-assets/board-flat-bottom.svg) |

## What this remote is meant to do

- Control a TV through on-board IR receive and transmit hardware
- Handle Sonos and other music controls once firmware and Home Assistant integration land
- Use the ESP32-C6 for Zigbee, Thread, or Matter-adjacent control work
- Map Home Assistant actions to physical buttons instead of app screens
- Last longer than the usual "charge it every week" gadget

This is not a finished product yet. Right now this repo is about the hardware prototype. Firmware, battery tuning, UX, and the full integration story still come later.

## Current hardware

Board in `c6remote-kicad/` currently includes:

- Seeed Studio XIAO ESP32-C6 (`U1`)
- I2S microphone (`MK1`)
- TSOP45xx-style IR receiver (`U2`) and IR LED transmitter (`D1`) through `Q1`
- PCF8575 I2C GPIO expander (`U3`)
- Discrete switches `sw1` through `sw11`
- Custom "Ano Rotary" part (`ENC1`) with encoder channels and five switch signals
- SK6812 mini addressable status LED (`D2`)

In practice, that gives the board a lot of physical input options plus IR and wireless paths for mixed home gear.

## Repo layout

```text
.
├── c6remote-kicad/          Main KiCad project
│   ├── c6remote.kicad_sch   Schematic
│   ├── c6remote.kicad_pcb   PCB layout
│   ├── c6remote.kicad_pro   Project settings
│   └── export/              Generated fabrication outputs
├── kicad lib/Library.pretty Custom footprints used by board
└── ano rotary.kicad_sym     Project-local custom symbol library
```

## Open project

Open `c6remote-kicad/c6remote.kicad_pro` in KiCad.

Project uses local custom footprints under `kicad lib/Library.pretty/`. KiCad needs that footprint library to resolve under nickname `Library`.

Symbol libraries are registered in `c6remote-kicad/sym-lib-table`:

- `ano rotary` — project-local custom rotary symbol (`ano rotary.kicad_sym`), sourced from [Adafruit ANO Rotary Navigation Encoder](https://github.com/adafruit/Adafruit-ANO-Rotary-Navigation-Encoder-Breakout-PCB)
- `Seeed_Studio_XIAO_Series` — XIAO module symbols (`Seeed_Studio_XIAO_Series.kicad_sym`), sourced from [Seeed-Studio/OPL_Kicad_Library](https://github.com/Seeed-Studio/OPL_Kicad_Library/tree/master/Seeed%20Studio%20XIAO%20Series%20Library)

## KiCad MCP

This repo is set up to use same KiCad MCP server with Codex, Claude Desktop, and GitHub Copilot / VS Code.

- Codex workspace config: `.mcp.json`
- VS Code / Copilot workspace config: `.vscode/mcp.json`
- Claude Desktop example config: `docs/claude-desktop-config.example.json`

Full setup notes live in [docs/mcp-setup.md](docs/mcp-setup.md).

## Validation

Run from `c6remote-kicad/`:

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc c6remote.kicad_sch --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations
```

To regenerate fabrication outputs:

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export gerbers c6remote.kicad_pcb -o export --board-plot-params
```

To render reusable 2D board views:

```bash
./scripts/render-2d.sh
./scripts/render-2d.sh --side top
./scripts/render-2d.sh --side bottom --format pdf
```

Default output goes to `c6remote-kicad/renders/<format>/`.

To regenerate README preview assets in one shot:

```bash
./scripts/render-readme-assets.sh
```

Default output goes to `docs/readme-assets/`.

## Current status

- Prototype board, not finished remote
- KiCad source of truth lives in `c6remote-kicad/`
- Generated fabrication outputs live in `c6remote-kicad/export/`
- Current baseline still has known ERC and DRC issues
- Firmware and runtime integrations are not in this repo yet

## Why this lives separately from homeThing

Original inspiration came from [homeThing](https://github.com/landonr/homeThing).

This repo has a narrower job:

- Less "general smart display"
- More "grab remote, hit button, control house"
- Custom PCB around ESP32-C6
- Easier to own and iterate in KiCad

If question is "why build this at all?", answer is still pretty straightforward: one remote for TV, music, lights, and Home Assistant, without a charger becoming part of the routine.
