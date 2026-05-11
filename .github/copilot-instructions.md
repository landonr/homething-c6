# Repository instructions

This repository is a KiCad hardware project, not a software application. The source of truth lives under `c6remote-kicad/`, with the main design split across:

- `c6remote.kicad_sch` - single-sheet schematic
- `c6remote.kicad_pcb` - board layout
- `c6remote.kicad_pro` - ERC/DRC settings, BOM settings, and project metadata
- `ano rotary.kicad_sym` - project-local custom symbol library
- `../kicad lib/Library.pretty/` - custom footprints used by the board
- `export/` - generated Gerbers and drill files

## Validation and fabrication commands

Use KiCad CLI from `c6remote-kicad/`. On this machine the app-bundled binary is:

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
```

Common commands:

```bash
cd c6remote-kicad

# Scoped schematic validation
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc c6remote.kicad_sch --exit-code-violations

# Scoped board validation
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --exit-code-violations

# Full board validation with schematic parity and zone refill
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations

# Regenerate fabrication outputs into the checked-in export directory
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export gerbers c6remote.kicad_pcb -o export --board-plot-params
```

There is no finer-grained single-test harness in this repo; the closest scoped checks are ERC for the schematic and DRC for the PCB run separately.

Current baseline is not clean. `kicad-cli sch erc` currently reports 23 violations, and `kicad-cli pcb drc` currently reports 50 violations plus 3 unconnected items. Treat those as pre-existing unless the task is specifically about fixing electrical or layout issues.

## High-level architecture

The board is centered on a **Seeed Studio XIAO ESP32-C6** module (`U1`). The project is a single-sheet KiCad design with heavy use of global labels, so understanding behavior usually means following named nets across the sheet and then checking the matching PCB nets and footprints.

Key functional blocks:

- **Audio input:** `M1` is an ICS-43434 / INMP441-style I2S microphone wired with `sck`, `ws`, and `sd`.
- **IR subsystem:** `U2` is a TSOP45xx IR receiver on `IR REC`. `D1` is the IR LED transmitter, driven through `Q1` and `R1` from `IR EMIT`.
- **User input expansion:** `U3` is a `PCF8575DBR` I2C GPIO expander on `sda` / `scl`. It fans out the discrete pushbutton signals `sw1` through `sw11` and also carries the custom rotary assembly switch signals `ano_sw1` through `ano_sw5`.
- **Custom rotary assembly:** `U4` is the project-specific "Ano Rotary" part. It exposes encoder outputs `ano_enc1` / `ano_enc2` plus switch nets `ano_sw1` through `ano_sw5`.
- **Status lighting:** `D2` is an addressable `SK6812MINI` LED on `led_1`.

The signal split matters: the rotary encoder channels `ano_enc1` / `ano_enc2` go straight from `U4` to `U1`, while the rotary push-switch nets and the eleven discrete switches go through `U3`. Power is also split between **`+3.3V`** and **`VCC`**. Most logic parts sit on `+3.3V`, while `VCC` is kept as a separate rail in the schematic and on `U1` / `D2`. Do not collapse or rename those rails casually.

## Key repository conventions

- The schematic is a **single sheet** that relies on **global labels** for most interconnects. For cross-cutting changes, search label names such as `sw*`, `ano_*`, `IR EMIT`, `IR REC`, `led_1`, `sda`, `scl`, `sck`, `ws`, and `sd`.
- The live design files are `c6remote.kicad_sch`, `c6remote.kicad_pcb`, and `c6remote.kicad_pro`. Files such as `*.bak`, `*-bak`, and `c6remote-backups/` are archival backups, not the normal edit targets.
- `export/` contains **generated fabrication artifacts**. Update it only when intentionally regenerating manufacturing outputs; do not hand-edit Gerbers or drill files.
- The project-local symbol library is already wired through `c6remote-kicad/sym-lib-table`, but the board footprints use the library nickname **`Library`** and there is **no checked-in `fp-lib-table`**. To resolve custom footprints in KiCad, map `Library` to `kicad lib/Library.pretty`.
- Custom footprints under `kicad lib/Library.pretty/` are part of the design, especially `XIAO-ESP32C6-DIP.kicad_mod`, `SW_TL3315NF160Q.kicad_mod`, and `Ano Rotary.kicad_mod`. Changes to those parts affect both schematic-footprint linking and PCB geometry, so verify both the schematic symbol properties and the PCB footprint instances after editing them.
- `ano rotary.kicad_sym` defines the custom rotary symbol used as `U4`. Its pin electrical types are not modeled cleanly for ERC today, so changing that symbol can shift the existing ERC baseline.
- The stored plot settings in the KiCad files point at a Windows path. For automated exports, always pass an explicit output directory such as `-o export` instead of relying on the saved project path.
- `kicad-cli` writes report files such as `c6remote-erc.rpt` and `c6remote-drc.rpt` in `c6remote-kicad/` when you run validation. Treat them as generated scratch output unless a task explicitly asks you to keep or inspect them.
- `.vscode/mcp.json` already contains a working KiCad MCP server definition for this workspace. Keep using KiCad's bundled Python from the `.app` bundle; do not switch MCP operations to Homebrew or system Python.
- The local MCP server checkout at `/Users/landonrohatensky/dev/KiCAD-MCP-Server` is valid on this machine, and `bash setup-macos.sh --verify` currently passes there. If MCP stops working, rerun that command before changing paths by hand.
- The macOS platform guide examples use Claude Desktop's `mcpServers` format, but this repo's workspace file is `.vscode/mcp.json` with a `servers` object. Do not "normalize" one format into the other unless you are intentionally editing the target client config.
