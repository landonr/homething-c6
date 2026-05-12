# c6homeThing

An ESP32-C6 remote board inspired by [homeThing](https://github.com/landonr/homeThing), but aimed at a simpler control scheme, easier fabrication, and a custom PCB built around newer wireless hardware.

This repository is primarily the **hardware project** for that follow-up. The current design is a KiCad-based prototype for a handheld smart-home remote with physical buttons, a rotary control, IR support, a microphone, and a Seeed Studio XIAO ESP32-C6 at the center.

![3D preview of the current board prototype](docs/board-preview-3d.png)

## Why this exists

The original homeThing project combines great software ideas with custom hardware for a smart-home remote. This repo is an attempt to carry that idea forward with a different hardware tradeoff:

- **Custom board that's easier to fab and assemble**
- **ESP32-C6-based platform** for Zigbee / Thread / Matter-class experimentation
- **Simpler physical controls** instead of leaning on a more complex device platform
- **Open KiCad sources** so the board can be iterated on directly

This is not a drop-in replacement for the original homeThing hardware or firmware. Think of it as a hardware-first branch of the idea.

## Hardware overview

The current board lives in `c6remote-kicad/` and is built around these blocks:

- **MCU:** Seeed Studio XIAO ESP32-C6 (`U1`)
- **Audio input:** I2S microphone (`M1`)
- **IR:** TSOP45xx-style receiver (`U2`) and IR LED transmitter (`D1`) driven through `Q1`
- **Input expansion:** PCF8575 I2C GPIO expander (`U3`)
- **Main controls:** discrete switches `sw1` through `sw11`
- **Rotary assembly:** custom "Ano Rotary" part (`U4`) with encoder channels and five switch signals
- **Status LED:** SK6812 mini addressable LED (`D2`)

At a high level, this board is trying to preserve the "smart-home remote with tactile controls" idea from homeThing while simplifying the hardware stack and moving to the ESP32-C6.

## Repository layout

```text
.
├── c6remote-kicad/          Main KiCad project
│   ├── c6remote.kicad_sch   Schematic
│   ├── c6remote.kicad_pcb   PCB layout
│   ├── c6remote.kicad_pro   Project settings
│   └── export/              Generated fabrication outputs
├── kicad lib/Library.pretty Custom footprints used by the board
└── ano rotary.kicad_sym     Project-local custom symbol library
```

## Working with the board

Open the project from `c6remote-kicad/c6remote.kicad_pro` in KiCad.

The project uses local custom footprints under `kicad lib/Library.pretty/`. The board expects the footprint library nickname **`Library`** to resolve to that directory.

## Validation

From `c6remote-kicad/`, the main checks are:

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc c6remote.kicad_sch --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations
```

To regenerate fabrication outputs:

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export gerbers c6remote.kicad_pcb -o export --board-plot-params
```

## Current status

This is still a **prototype board**, not a finished product release.

- The KiCad source of truth is in `c6remote-kicad/`
- `export/` contains generated fabrication artifacts
- There are known ERC/DRC issues in the current baseline
- The repo is focused on board design first; firmware and UI integration are follow-on work

## Relationship to homeThing

If you're here because of homeThing:

- See the original project for the broader vision, UI ideas, and prior hardware: <https://github.com/landonr/homeThing>
- This repo is the custom-board follow-up focused on a simpler, more fabrication-friendly ESP32-C6 design
- The long-term goal is to keep the spirit of homeThing while making the hardware platform easier to own and iterate on
