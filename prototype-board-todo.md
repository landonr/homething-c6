# Prototype Board Todo

Current PCB state no longer matches old checklist. `C2`, `R2`, `D2`, and routed nets are present on board. Latest validation state below comes from live KiCad MCP checks against `c6remote.kicad_pro`:

- Board size: `37.4 mm x 130.4 mm`
- ERC: 11 warnings, 0 errors
- DRC: 49 warnings, 0 errors, 0 unconnected pads
- Fab outputs in `c6remote-kicad/export/` are stale relative to board + schematic edits

## Pre-Order Blockers

1. **Confirm `BAT` net is intentional**  
   ERC reports `Label connected to only one pin` on `BAT`. If battery input or measurement path should exist, fix schematic + board before ordering. If intentionally unused for this prototype, document and accept warning.

2. **Run final ERC/DRC on order candidate**  
   Re-run KiCad validation from `c6remote-kicad/` and confirm final board still has no DRC errors and no unconnected pads.

3. **Regenerate fabrication outputs**  
   Re-export Gerbers and drill files into `c6remote-kicad/export/` after final validation. Current export files were generated before latest PCB/schematic edits.

## Should-Fix Before Order

4. **Clean silkscreen around `U1`**  
   Current DRC includes repeated `silk_over_copper` warnings around XIAO pads. Text/outline will likely be clipped by solder mask.

5. **Clean edge-clipped silkscreen**  
   Current DRC includes `silk_edge_clearance` warnings near board edge. Trim or move silk that crosses `Edge.Cuts`.

6. **Increase undersized silkscreen text**  
   Current DRC includes `text_height` and `text_thickness` warnings. Increase text size/stroke if board markings need to survive fab limits.

## Project Hygiene / Reproducibility

7. **Resolve missing local footprint library entry**  
   DRC reports missing `Local:WirePad_1x02_P2.54mm_Back` library footprint. Board still contains embedded footprint data, but local library should be fixed so future edits/exports stay reproducible.

8. **Review footprint mismatch warnings**  
   Current DRC includes multiple `lib_footprint_mismatch` warnings for overridden or locally edited footprints. Usually not order-blocking, but worth reviewing before locking revision.

## Validation Commands

Run from `c6remote-kicad/`:

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc c6remote.kicad_sch --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export gerbers c6remote.kicad_pcb -o export --board-plot-params
```

## Order Sequence

`confirm-bat-intent` -> `final-erc-drc` -> `fix-order-relevant-warnings` -> `regen-fab-files` -> `upload-order-package`
