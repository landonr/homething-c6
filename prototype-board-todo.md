# Prototype Board Todo

Current PCB state no longer matches old checklist. `C2`, `R2`, `D2`, and routed nets are present on board. Latest validation state below comes from fresh checks against current KiCad sources:

- Board size: `37.4 mm x 130.4 mm`
- ERC on `2026-05-23`: 11 warnings, 0 errors
- DRC: last known report still `49 warnings, 0 errors, 0 unconnected pads`
- Fab outputs in `c6remote-kicad/export/` are stale relative to board + schematic edits

## Pre-Order Blockers

1. **Run final ERC/DRC on order candidate**  
   Fresh ERC no longer shows `BAT` issue. Re-run full KiCad validation from `c6remote-kicad/` and confirm final board still has no DRC errors and no unconnected pads.

2. **Regenerate fabrication outputs**  
   Re-export Gerbers and drill files into `c6remote-kicad/export/` after final validation. Current export files were generated before latest PCB/schematic edits.

## Should-Fix Before Order

3. **Clean silkscreen around `U1`**  
   Current DRC includes repeated `silk_over_copper` warnings around XIAO pads. Text/outline will likely be clipped by solder mask.

4. **Clean edge-clipped silkscreen**  
   Current DRC includes `silk_edge_clearance` warnings near board edge. Trim or move silk that crosses `Edge.Cuts`.

5. **Increase undersized silkscreen text**  
   Current DRC includes `text_height` and `text_thickness` warnings. Increase text size/stroke if board markings need to survive fab limits.

## Project Hygiene / Reproducibility

6. **Resolve missing local footprint library entry for `J1`**  
   Fresh ERC reports missing `Local:WirePad_1x02_P2.54mm_Back` footprint for battery connector `J1`. Board still contains embedded footprint data, but local library should be fixed so future edits/exports stay reproducible.

7. **Review footprint mismatch warnings**  
   Current DRC includes multiple `lib_footprint_mismatch` warnings for overridden or locally edited footprints. Usually not order-blocking, but worth reviewing before locking revision.

8. **Review duplicate local/global label warnings**  
   Fresh ERC reports `same_local_global_label` warnings for `scl`, `sda`, `sck`, `sd`, `ws`, `IR REC`, `IR EMIT`, `ano_enc1`, `ano_enc2`, and `led_1`. Usually not order-blocking if intentional, but clean them up or explicitly accept them before lock.

## Validation Commands

Run from `c6remote-kicad/`:

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc c6remote.kicad_sch --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export gerbers c6remote.kicad_pcb -o export --board-plot-params
```

## Order Sequence

`final-erc-drc` -> `fix-order-relevant-warnings` -> `regen-fab-files` -> `upload-order-package`
