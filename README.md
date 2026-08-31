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

This repo contains the KiCad hardware and ESPHome bring-up configuration for a prototype built around a Seeed Studio XIAO ESP32-C6. The hardware source of truth lives in `c6remote-kicad/`.

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
- Assign every button from a web page on the remote itself
- Run for a long time between charges

Open `http://homething-c6.local/buttons` in a browser on the same network. The page draws the remote layout. Select an input, then record an IR code, assign the voice assistant, or clear the input. The on-device gesture does the same job: hold `SW2` for two seconds. [`RECEIVER.md`](RECEIVER.md) documents both routes. The page has no password, so use it on a trusted network only.

## Hardware

| Ref | Part | Role |
| --- | --- | --- |
| `U1` | [Seeed Studio XIAO ESP32-C6](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/8932/102010636.pdf) | Main module: Wi-Fi, BLE, Zigbee/Thread |
| `MK1` | [ICS-43434 I2S microphone](https://invensense.tdk.com/wp-content/uploads/2016/02/DS-000069-ICS-43434-v1.2.pdf) | Audio input |
| `U2` | [TSOP6136 IR receiver](https://www.vishay.com/docs/82457/tsop61.pdf) | IR receive: Vishay Panhead SMD part on the back copper, listening out the top end wall. AGC1, the most permissive of Vishay's settings, which is what lets `remote_receiver` learn arbitrary remotes. VDD sits on the switched `ir_vdd` rail rather than straight on `+3.3V`, gated by `Q3` below |
| `D1`, `Q1` | [INL-3AHIR30 IR LED](http://www.inolux-corp.com/datasheet/IR/Emitter/3mm%20Lamp/INL-3AHIR30_V1.0.pdf) driven by [MMBT2222A](https://assets.nexperia.com/documents/data-sheet/MMBT2222A.pdf) | IR transmit; D1 leads hand-bent 90° to fire through the top-edge notch (see `BEND 90°` silk mark) |
| `U3` | [PCF8575DBR I2C GPIO expander](https://www.ti.com/lit/ds/symlink/pcf8575.pdf) | Button input fan-out |
| `SW1`–`SW11` | [TL3315NF160Q tactile switches](https://www.e-switch.com/wp-content/uploads/2022/06/TL3315.pdf) | Discrete buttons |
| `ENC1` | [Adafruit ANO rotary encoder](https://cdn-learn.adafruit.com/assets/assets/000/104/942/original/tsw.pdf) | Scroll wheel: encoder channels plus five switch signals |
| `D2`–`D5` | [XL-2020RGBC-WS2812B addressable LEDs](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/8903/5962_XL-2020RGBC-WS2812B.pdf) | Status light chain of 4, WS2812B protocol: `GPIO17` drives `D2` DIN, DOUT cascades to `D5`. VDD sits on the switched `led_vdd` rail rather than straight on `+3.3V`, gated by `Q2` below, with `C4` as the only bulk cap on the chain (see [`docs/timeline.md`](docs/timeline.md)) |
| `Q2`, `R10`, `C4` | [AO3401A P-channel MOSFET](https://www.aosmd.com/res/datasheets/AO3401A.pdf), 1M 0603 pull-up, 1µF X7R 0805 cap | LED rail load switch: high-side `Q2` gates `+3.3V` (source) onto `led_vdd` (drain) for `D2`–`D5`, gate net `led_en` on `U1` pad 11 (`GPIO18`/`D10`), driven low for rail on. `R10` pulls the gate to the source so the rail is off by default at boot while `GPIO18` floats as an input; `C4` is the mid-chain bulk cap on `led_vdd`. Cuts the ~2.0mA the LEDs burned when dark to tens of µA (calculated, not yet measured). Firmware must hold `GPIO17` low or high-impedance whenever the rail is down, or DIN pushes current into the dead rail |
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

3D models for the board view live in `c6remote-kicad/3dmodels/`; every file's source is cited in [`c6remote-kicad/3dmodels/README.md`](c6remote-kicad/3dmodels/README.md).

## KiCad MCP

The repo is set up to use the same KiCad MCP server with Codex and GitHub Copilot / VS Code:

- Codex workspace config: `.mcp.json`
- VS Code / Copilot workspace config: `.vscode/mcp.json`

## Validation and fabrication

### Fast agent schematic loop

Use a unique session name for one schematic or custom-footprint edit loop. The PCB is excluded from this workflow and must remain byte-for-byte unchanged between `preflight` and `verify`. Native KiCad ERC is authoritative; semantic analysis detects topology, BOM, metadata, findings, and custom-footprint regressions.

```bash
./scripts/hw.py doctor
./scripts/hw.py preflight my-edit

# Run after every schematic or custom-footprint edit.
./scripts/hw.py quick my-edit

# Run once before handoff.
./scripts/hw.py verify my-edit
./scripts/hw.py clean my-edit
```

Session artifacts stay under `.cache/hw/<session>/`. `preflight` refuses to replace an existing session. Reuse the same session for repeated `quick` runs, then use `clean` before creating a fresh baseline. A failed new `preflight` may intentionally leave ERC or analyzer diagnostics in its session directory; inspect them, then run `clean` before retrying.

The analyzer resolves from `KICAD_HAPPY_DIR` first, then `${CODEX_HOME:-$HOME/.codex}/skills/kicad`. It must emit schema 1.4.x. `KICAD_CLI` overrides the default macOS application binary. `doctor` may report the installed analyzer package version as unknown because this runtime has no package-version metadata; a compatible schema 1.4.x still passes.

If the analyzer is missing or incompatible, move or remove its existing destination before reinstalling the pinned version:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" --repo aklofas/kicad-happy --ref v2.2.0 --path skills/kicad
```

Exit codes are `0` for pass, `1` for a design regression, and `2` for missing tools, incompatible configuration, parser failure, process abort, or missing output. `quick` blocks only newly introduced analyzer findings whose severity is `error` and confidence is `deterministic`; warnings are reported without blocking. `verify` also runs native ERC, netlist and curated BOM export, full custom-footprint parsing, changed-footprint SVG export, PCB hash comparison, and `git diff --check`, with all outputs kept inside the session cache.

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

Regenerate just the BOM after editing symbol sourcing fields (Datasheet, MPN, vendor links). Use this, not the KiCad MCP `export_bom` tool, which emits a different schema and drops the custom sourcing columns:

```bash
scripts/export-bom.sh
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

Generate the interactive HTML BOM used for the pre-fab pin-1 orientation walk. Output is `c6remote-kicad/ibom.html`, a gitignored review artifact that the pre-commit hook also refreshes whenever `c6remote.kicad_pcb` is staged:

```bash
./scripts/gen-ibom.sh
```

Everything that has to happen before a board order, including the orientation and pinout checks ERC and DRC cannot do, is in [`docs/pre-fab-checklist.md`](docs/pre-fab-checklist.md).

## Status

The fabrication and bring-up history, the rev-B delivery, and the unit 1 versus current design comparison are in [`docs/timeline.md`](docs/timeline.md). Open work is in [`ROADMAP.md`](ROADMAP.md). The power budget is in [`docs/power-budget.md`](docs/power-budget.md).

## Relationship to homeThing

This project grew out of [homeThing](https://github.com/landonr/homeThing) but has a narrower job: instead of a general smart display, it is a simple dedicated remote. It has no screen and more buttons, and is built on a custom PCB that is easy to build.
