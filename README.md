<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/readme-assets/homeThingLogoWhite.svg">
    <img alt="homeThing logo" src="docs/readme-assets/homeThingLogo.svg" width="120">
  </picture>
</p>

<h1 align="center">homeThing C6</h1>

<p align="center">
  A handheld remote for TV, Sonos, Zigbee lights, and Home Assistant.<br>
  Physical buttons, a rotary control, fast access, and long idle life. No touchscreen, no apps, no daily charging.
</p>

<p align="center">
  <a href="https://discord.gg/BX6ZtGKHTy"><img alt="Discord" src="https://img.shields.io/discord/1021434469917413498?style=for-the-badge&logo=discord&logoColor=white&label=Discord&color=5865F2"></a>
  <a href="https://www.instagram.com/homething.io/"><img alt="Instagram" src="https://img.shields.io/badge/Instagram-%40homething.io-E4405F?style=for-the-badge&logo=instagram&logoColor=white"></a>
  <a href="https://homething.io/"><img alt="Website" src="https://img.shields.io/badge/Website-homething.io-6E40C9?style=for-the-badge&logo=googlechrome&logoColor=white"></a>
  <a href="https://github.com/landonr/homeThing"><img alt="homeThing on GitHub" src="https://img.shields.io/github/stars/landonr/homeThing?style=for-the-badge&logo=github&logoColor=white&label=homeThing&color=181717"></a>
</p>

<p align="center">
  <sub>Prototype and fab costs sponsored by <a href="https://pcbway.com/g/Xymq6O">PCBWay</a>. Boards arrive fully assembled, no soldering required.</sub>
  <br>
  <a href="https://pcbway.com/g/Xymq6O"><img alt="PCBWay" src="https://freight.cargo.site/w/800/i/a931690205c27162476213b8bcc171585aad9d84d65cdc121ca425e813114121/0x0.png" width="140"></a>
</p>

This repo is the hardware side of the project: a KiCad prototype built around a Seeed Studio XIAO ESP32-C6. The source of truth lives in `c6remote-kicad/`. Firmware and runtime integrations are not in this repo yet.

<p align="center">
  <img alt="Raytraced 3D top view of the board" src="docs/readme-assets/board-3d-rotated-top.png" width="49%">
  <img alt="Raytraced 3D bottom view of the board" src="docs/readme-assets/board-3d-rotated-bottom.png" width="49%">
</p>
<p align="center"><sub>Raytraced renders, top and bottom</sub></p>

## Features

- Control a TV with on-board IR receive and transmit hardware
- Drive music playback over Wi-Fi and BLE
- Switch lights over Zigbee, Thread, or Matter
- Map Home Assistant actions to physical buttons instead of app screens
- Run for a long time between charges

## Hardware

| Ref | Part | Role |
| --- | --- | --- |
| `U1` | [Seeed Studio XIAO ESP32-C6](https://www.digikey.ca/en/products/detail/seeed-technology-co-ltd/113991254/24613066) | Main module: Wi-Fi, BLE, Zigbee/Thread |
| `MK1` | [ICS-43434 I2S microphone](https://www.digikey.ca/en/products/detail/tdk-invensense/ICS-43434/6140298) | Audio input |
| `U2` | [TSOP4136 IR receiver](https://www.vishay.com/docs/82460/tsop45.pdf) | IR receive |
| `D1`, `Q1` | [INL-3AHIR30 IR LED](http://www.inolux-corp.com/datasheet/IR/Emitter/3mm%20Lamp/INL-3AHIR30_V1.0.pdf) driven by [MMBT2222A,215](https://www.digikey.ca/en/products/detail/nexperia-usa-inc/MMBT2222A-215/1156598) | IR transmit; D1 leads hand-bent 90° to fire through the top-edge notch (see `BEND 90°` silk mark) |
| `U3` | [PCF8575DBR I2C GPIO expander](https://www.digikey.com/en/products/detail/texas-instruments/PCF8575DBR/754551) | Button input fan-out |
| `SW1`–`SW11` | [TL3315NF160Q tactile switches](https://www.digikey.ca/en/products/detail/e-switch/TL3315NF160Q/1870395) | Discrete buttons |
| `ENC1` | [Adafruit ANO rotary encoder](https://www.adafruit.com/product/5001) | Scroll wheel: encoder channels plus five switch signals |
| `D2` | [SK6812MINI addressable LED](https://www.digikey.ca/en/products/detail/adafruit-industries-llc/2686/5804107) | Status light |
| `J1` | [JST S2B-PH-SM4-TB(LF)(SN)](https://www.jst-mfg.com/product/pdf/eng/ePH.pdf) | Battery connector, PH series right-angle SMD |

The auto-generated BOM lives at [c6remote-kicad/export/c6remote-bom.csv](c6remote-kicad/export/c6remote-bom.csv). It tracks the latest repo state and is not release-validated.

## Board views

<p align="center">
  <img alt="Basic 3D top view" src="docs/readme-assets/board-3d-top.png" width="180">
  &nbsp;&nbsp;
  <img alt="Flat copper top view" src="docs/readme-assets/board-flat-top.svg" width="180">
</p>
<p align="center"><sub>Top: basic 3D and flat copper</sub></p>

<p align="center">
  <img alt="Basic 3D bottom view" src="docs/readme-assets/board-3d-bottom.png" width="180">
  &nbsp;&nbsp;
  <img alt="Flat copper bottom view" src="docs/readme-assets/board-flat-bottom.svg" width="180">
</p>
<p align="center"><sub>Bottom: basic 3D and flat copper</sub></p>

## Schematic

![Current schematic](docs/readme-assets/schematic.svg)

## Repo layout

```text
.
├── c6remote-kicad/          Main KiCad project
│   ├── c6remote.kicad_sch   Schematic
│   ├── c6remote.kicad_pcb   PCB layout
│   ├── c6remote.kicad_pro   Project settings
│   ├── 3dmodels/            STEP models used for 3D board view
│   └── export/              Generated fabrication outputs
├── kicad lib/Library.pretty Custom PCB footprints used by board
└── ano rotary.kicad_sym     Project-local schematic symbol library
```

## Opening the project

Open `c6remote-kicad/c6remote.kicad_pro` in KiCad. The board uses local custom footprints under `kicad lib/Library.pretty/`, which KiCad must resolve under the library nickname `Library`.

Symbol libraries are registered in `c6remote-kicad/sym-lib-table`:

- `ano rotary`: project-local custom rotary symbol (`ano rotary.kicad_sym`) for the [Adafruit ANO rotary encoder](https://www.adafruit.com/product/5001)
- `Seeed_Studio_XIAO_Series`: XIAO module symbols from [Seeed-Studio/OPL_Kicad_Library](https://github.com/Seeed-Studio/OPL_Kicad_Library/tree/master/Seeed%20Studio%20XIAO%20Series%20Library)

STEP models for the 3D board view live in `c6remote-kicad/3dmodels/`:

- `5221 ANO Rotary Encoder.step`: [GrabCAD Adafruit 5001 ANO Rotary Encoder](https://grabcad.com/library/adafruit-5001-ano-rotary-encoder-1)
- `SW_SPST_PTS647Sx50_black.step`: local fork matching the [C&K PTS647 series](https://www.ckswitches.com/products/switches/product-details/Tactile/PTS647/)
- `Seeed Studio XIAO ESP32-C6.step`: [GrabCAD XIAO ESP32-C6 3D model](https://grabcad.com/library/seeed-studio-xiao-esp32-c6-1)

## KiCad MCP

The repo is set up to use the same KiCad MCP server with Codex, Claude Desktop, and GitHub Copilot / VS Code:

- Codex workspace config: `.mcp.json`
- VS Code / Copilot workspace config: `.vscode/mcp.json`
- Claude Desktop example config: `docs/claude-desktop-config.example.json`

Full setup notes live in [docs/mcp-setup.md](docs/mcp-setup.md).

## Validation and fabrication

Run from `c6remote-kicad/`:

```bash
# Schematic ERC
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc c6remote.kicad_sch --exit-code-violations

# Board DRC
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --exit-code-violations

# Full board DRC with schematic parity and zone refill
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations
```

Regenerate all fabrication outputs (gerbers, drill, position file, BOM) into `export/`:

```bash
scripts/regen-fab.sh
```

Render reusable 2D board views (default output: `c6remote-kicad/renders/<format>/`):

```bash
./scripts/render-2d.sh
./scripts/render-2d.sh --side top
./scripts/render-2d.sh --side bottom --format pdf
```

Regenerate the README preview assets in `docs/readme-assets/`:

```bash
./scripts/render-readme-assets.sh
```

## Status

Prototype fab and assembly are ordered from PCBWay (order YT1753739, PCB plus SMD assembly). Current baseline still has ERC and DRC warnings. Firmware and runtime integrations are not in this repo yet.

| Date | Milestone |
| --- | --- |
| 2026-06-16 | Quotation received for PCB and assembly, replied with updates |
| 2026-06-17 | Updated quotation approved; assembly order passed review |
| 2026-06-18 | Order confirmed, production queued |
| 2026-07-10 | Component engineering questions received from PCBWay |
| 2026-07-12 | Answers returned; PCBWay confirmed production is proceeding |
| 2026-07-14 | Assembled sample board photos received; PCBWay asked to confirm D1/U2 orientation before completing solder |
| 2026-07-15 | PCBWay adjusted D1 (90° lead bend firing through top-edge notch) and requested recheck |
| 2026-07-16 | D1 and full board orientation confirmed correct; assembly proceeding |

## Relationship to homeThing

This project grew out of [homeThing](https://github.com/landonr/homeThing) but has a narrower job: instead of a general smart display, it is a simple dedicated remote. It has no screen and more buttons, and is built on a custom PCB that is easy to build.
