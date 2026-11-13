# KiCad project

## Open the project

Open `c6remote.kicad_pro` in KiCad.
KiCad must resolve `../kicad lib/Library.pretty/` with the `Library` nickname.

The `sym-lib-table` file registers these symbol libraries:

- `dmm_4026_b_i2s_r`: The local `dmm_4026_b_i2s_r.kicad_sym` file contains the `MK1` microphone symbol.
- `Local`: The local `Local.kicad_sym` file contains the switch, IR receiver, XIAO ESP32-C6 module, and [Adafruit ANO rotary encoder](https://www.adafruit.com/product/5001) symbols.

### 3D models

The custom footprints reference their 3D models in `3dmodels/`.
This repository does not contain these models, because most are third-party files without a clear right to redistribute.
The models are in the private `c6remote-explode` repository.

Without the models, the KiCad 3D view shows bare pads for these parts.
The fabrication outputs, ERC, and DRC do not use the models.

If you have the `c6remote-explode` checkout, run `../scripts/link-3dmodels.sh` once for each clone or worktree.
The script links `3dmodels/` to the models in that checkout.
If the checkout is not at `~/dev/c6remote-explode`, set `EXPLODE` to its path.

## KiCad MCP

The repository uses the same KiCad MCP server with Codex and GitHub Copilot in VS Code:

- Codex workspace configuration: `../.mcp.json`
- VS Code workspace configuration: `../.vscode/mcp.json`

## Validation and fabrication

### Schematic-only agent workflow

Run this workflow from the repository root.
Use a unique session name for each schematic or custom-footprint edit loop.
The PCB must remain unchanged between `preflight` and `verify`.

```bash
./scripts/hw.py doctor
./scripts/hw.py preflight my-edit

# Inspect the baseline before an edit.
./scripts/hw.py inspect my-edit component U3
./scripts/hw.py inspect my-edit net sda
./scripts/hw.py inspect my-edit pin U3 14

# Run after every schematic or custom-footprint edit.
./scripts/hw.py quick my-edit

# Inspect the refreshed state and all baseline changes.
./scripts/hw.py inspect my-edit changes

# Run once before handoff.
./scripts/hw.py verify my-edit
./scripts/hw.py clean my-edit
```

Native KiCad ERC is authoritative.
Semantic analysis detects topology, BOM, metadata, findings, and custom-footprint regressions.

Use `--json` with `inspect` for stable structured output.
Use `--force` with `quick` or `inspect` to bypass reusable analysis.

Session artifacts stay in `.cache/hw/<session>/`.
The `preflight` command does not replace an existing session.
Reuse one session for repeated `inspect` and `quick` commands.
The session keeps its original baseline until you run `clean`.
If a session is old or incomplete, run `clean` and `preflight` again.

The tool refreshes stale inspection data before it prints results.
It reuses validated analysis and changed-footprint data when all fingerprints match.
It does not reuse failed or incomplete output.
It rejects simultaneous operations on one session.

The tool resolves `kicad-cli` from `KICAD_CLI`, `PATH`, or the macOS application bundle.
It resolves the analyzer from `KICAD_HAPPY_DIR`, shared, Codex, or Claude skill locations.
An invalid override stops discovery.
The `doctor` command prints each selected path.
The analyzer must emit schema 1.4.x.

If the analyzer is missing or incompatible, move or remove its existing destination.
Then install the pinned version:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" --repo aklofas/kicad-happy --ref v2.2.0 --path skills/kicad
```

Exit code `0` means pass.
Exit code `1` means a design regression.
Exit code `2` means a tooling or configuration failure.

A PCB change makes `quick` and `inspect` fail before analysis starts.
The message explains that the session cannot validate PCB edits.
The `quick` command blocks only new deterministic analyzer errors.
The `verify` command always runs fresh native checks and stores outputs in the session cache.

### Native checks

Run these commands from this directory:

```bash
# Schematic ERC
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli sch erc c6remote.kicad_sch --exit-code-violations

# Board DRC
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --exit-code-violations

# Full board DRC with schematic parity and zone refill
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations
```

### Fabrication outputs

Regenerate all Gerber, drill, position, and BOM files in `export/`:

```bash
../scripts/regen-fab.sh
```

Regenerate only the BOM after you edit symbol sourcing fields:

```bash
../scripts/export-bom.sh
```

Use this script instead of the KiCad MCP `export_bom` tool.
The MCP tool uses a different schema and removes the custom sourcing columns.

### Board renders

Render reusable 2D board views in `renders/<format>/`:

```bash
../scripts/render-2d.sh
../scripts/render-2d.sh --side top
../scripts/render-2d.sh --side bottom --format pdf
```

### Interactive BOM

Generate the interactive HTML BOM for the pre-fabrication pin-1 check:

```bash
../scripts/gen-ibom.sh
```

The command writes the ignored `ibom.html` file in this directory.
The pre-commit hook also updates it when you stage `c6remote.kicad_pcb`.

Complete the [pre-fabrication checklist](../docs/pre-fab-checklist.md) before you order a board.
