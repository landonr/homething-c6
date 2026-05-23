# Prototype Board Todo

Current PCB state moved past old checklist. `C2`, `R2`, `D2`, routed nets, battery connector placement, and prior board-level DRC blockers are fixed. Latest validation state below comes from fresh checks against current KiCad sources:

- Board size: `37.4 mm x 130.4 mm`
- ERC on `2026-05-23`: `10 warnings, 0 errors`
- DRC on `2026-05-23`: `16 warnings, 0 errors, 0 unconnected pads`
- Remaining DRC warnings are all `lib_footprint_mismatch`
- Fab outputs in `c6remote-kicad/export/` are still stale relative to current board + schematic edits

## Pre-Order Blockers

1. **Regenerate fabrication outputs**
   Re-export Gerbers and drill files into `c6remote-kicad/export/` after final validation. Current export files were generated before latest PCB/schematic edits.

## Should-Review Before Order

2. **Review or accept remaining footprint mismatch warnings**
   Fresh DRC still has `16` `lib_footprint_mismatch` warnings on `U1`, `J1`, and local testpoint footprints. If these are intentional local overrides, document/accept them before lock. If not, refresh footprints from source libraries and re-run DRC.

3. **Review duplicate local/global label warnings**
   Fresh ERC still reports `same_local_global_label` warnings for `scl`, `sda`, `sck`, `sd`, `ws`, `IR REC`, `IR EMIT`, `ano_enc1`, `ano_enc2`, and `led_1`. Usually not order-blocking if intentional, but clean them up or explicitly accept them before lock.

## Done Since Previous Checklist

- `J1` schematic missing-footprint ERC warning is gone
- `J1` clearance errors are gone
- `MK1` unconnected-pad error is gone
- Prior shorting, solder-mask, thermal, and silkscreen warnings still absent in fresh DRC

## Fast Validation Next Time

MCP-first flow:

1. Open `c6remote-kicad/c6remote.kicad_pro` in KiCad MCP first.
2. Run ERC on `c6remote-kicad/c6remote.kicad_sch`.
3. Run DRC and write report to `c6remote-kicad/DRC-mcp.rpt`.
4. Read `c6remote-kicad/c6remote_drc_violations.json` for machine-readable results.
5. If MCP says `No board is loaded`, project was not opened first. Re-open project, then re-run DRC.

## Validation Commands

CLI fallback. Run from `c6remote-kicad/`:

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc c6remote.kicad_sch --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export gerbers c6remote.kicad_pcb -o export --board-plot-params
```

## Order Sequence

`review-remaining-warnings` -> `regen-fab-files` -> `upload-order-package`
