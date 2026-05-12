# Prototype Board Todo

1. **Add missing PCB parts**  
   Sync the board with the schematic so `C2`, `R2`, and `D2` exist on the PCB with correct footprints and placement for the `led_1` status LED path.

2. **Route open nets**  
   Complete the three remaining board hookups: `IR REC` from `U2` to `U1`, `sd` from `M1` to `U1`, and the missing `GND` connection at `M1`.

3. **Fix mic edge clearance**  
   Adjust the `M1` footprint placement and/or nearby `Edge.Cuts` geometry so the microphone `GND` pad no longer violates board-edge clearance.

4. **Resolve local library mapping**  
   Make sure the project can resolve the local `Library` footprint nickname so custom footprints stop showing as missing in KiCad on this machine/project.

5. **Rerun KiCad validation**  
   Run ERC/DRC again after the board changes and confirm only accepted baseline warnings remain.

6. **Regenerate fabrication outputs**  
   Re-export Gerbers and drill files into `c6remote-kicad/export` after the board is updated and validation is acceptable.

## Dependency Order

`add-missing-parts` -> `finish-open-nets` -> `rerun-validation` -> `regenerate-fab-files`

`fix-mic-clearance` should be handled alongside the board edits before validation.
