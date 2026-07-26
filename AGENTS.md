# Agent instructions

`AGENTS.md` is the real file. `CLAUDE.md` and `.github/copilot-instructions.md` are symlinks to it, so Claude Code, Codex, and Copilot all read the same text. Edit `AGENTS.md` only; never replace a symlink with a copy, or the three clients drift apart.

## Response style

Respond terse like smart caveman. All technical substance stay. Only fluff die.

Rules:
- Drop: articles (a/an/the), filler (just/really/basically), pleasantries, hedging
- Fragments OK. Short synonyms. Technical terms exact. Code unchanged.
- Pattern: [thing] [action] [reason]. [next step].
- Not: "Sure! I'd be happy to help you with that."
- Yes: "Bug in auth middleware. Fix:"

Switch level: /caveman lite|full|ultra|wenyan
Stop: "stop caveman" or "normal mode"

Auto-Clarity: drop caveman for security warnings, irreversible actions, user confused. Resume after.

Boundaries: code/commits/PRs written normal.

Response shape:
- Report what happened and what it proves. Every sentence carries new fact: result, number, file, next step. Stop when facts stop.
- Describe only actions taken and their outcomes. Skipped checks, unused alternatives, possible follow-ups: mention only when user must act on them.
- Yes: "ERC 0. Netlist matches board, parity 45. Committed fee23d4."
- Not: "ERC 0. Note I didn't re-run DRC since copper unchanged. Could also have used kicad-cli instead. Want me to check parity too, or update the README?"
- Exception: failures and blockers get full detail. What failed, exact error output, what was tried, what input is needed to unblock.

## Repository layout

This repository is a KiCad hardware project, not a software application. Source of truth lives under `c6remote-kicad/`:

- `c6remote.kicad_sch` - single-sheet schematic
- `c6remote.kicad_pcb` - board layout
- `c6remote.kicad_pro` - ERC/DRC settings, BOM settings, project metadata
- `ano rotary.kicad_sym` - project-local custom symbol library
- `../kicad lib/Library.pretty/` - custom footprints used by the board
- `export/` - generated Gerbers and drill files

For board status, validation history, or "what's left" work, read `ROADMAP.md` first.

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

# Regenerate ALL fabrication outputs (gerbers, drill, pick-and-place, BOM) into export/
# Run this after any schematic or board change so export/ stays in sync.
scripts/regen-fab.sh

# Or just the gerbers, directly:
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb export gerbers c6remote.kicad_pcb -o export --board-plot-params
```

`scripts/regen-fab.sh` wraps four `kicad-cli` exports (gerbers + drill + `c6remote-pos.csv` position file + `c6remote-bom.csv` BOM) with the project's established formats: position file is CSV/mm/both-sides; BOM is grouped by Value+Footprint with the custom sourcing columns (Reference, Qty, Value, Footprint, Datasheet, Description, Manufacturer, MPN, Digikey, Mouser, Adafruit) and ", "-joined references. Override the binary with `KICAD_CLI=/path/to/kicad-cli scripts/regen-fab.sh`.

BOM regen: run `scripts/export-bom.sh` (or `scripts/regen-fab.sh`, which calls it). NOT the MCP `export_bom` tool, which emits a different schema (regrouped rows, drops the custom sourcing columns, lists test points) and clobbers the curated CSV. Datasheet and sourcing fields live on the schematic symbols (source of truth); edit them there, then rerun the script.

A tracked pre-commit hook (`scripts/hooks/pre-commit`) runs `regen-fab.sh` and stages `export/` automatically whenever `c6remote.kicad_sch` or `c6remote.kicad_pcb` is part of a commit, so fabrication outputs never drift from the design. It also rerenders README assets via `scripts/render-readme-assets.sh` and stages `docs/readme-assets/`: a staged PCB rerenders the board views (`--only board`), a staged schematic rerenders `schematic.svg` (`--only schematic`), both staged rerenders everything (`--only all`). Activate it once per clone with `git config core.hooksPath scripts/hooks`; bypass a single commit with `git commit --no-verify`. Because gerber/drill headers embed a creation timestamp, any board-touching commit restages all of `export/` even when geometry is unchanged.

There is no finer-grained single-test harness in this repo; the closest scoped checks are ERC for the schematic and DRC for the PCB, run separately.

**Zone refill before commit:** `kicad-cli pcb drc --refill-zones` refills copper zones in memory only, it never saves the refill back into `c6remote.kicad_pcb`. After any board edit that can affect copper pours (moved/changed footprints, new tracks or vias, net changes), do NOT commit until Landon has refilled zones in the KiCad GUI (Edit → Fill All Zones, then save) and confirmed. Stage and commit the board file only after that confirmation.

Baseline as of 2026-07-26: `sch erc` 0 violations, `pcb drc` 0 errors and 0 unconnected items with 48 silkscreen/library warnings (24 `silk_over_copper`, 14 `lib_footprint_mismatch`, 7 `silk_edge_clearance`, 3 `silk_overlap`). Treat those 48 as pre-existing unless the task is specifically about them; 5 of the `silk_over_copper` are the ANO wheel outline crossing ENC1 pads, which is intentional. Schematic-vs-board parity is 13 issues, all `extra_footprint` for the board-only `TP_*` test points. The board now carries the D2 `WS2812B-2020` swap, the D3-D5 chain, and the SW1-11 terminal remap, so those no longer diverge.

## High-level architecture

The board is centered on a **Seeed Studio XIAO ESP32-C6** module (`U1`). Single-sheet KiCad design with heavy use of global labels, so understanding behavior usually means following named nets across the sheet and then checking the matching PCB nets and footprints.

Key functional blocks:

- **Audio input:** `MK1` is an ICS-43434 / INMP441-style I2S microphone wired with `sck`, `ws`, and `sd`.
- **IR subsystem:** `U2` is a TSOP45xx IR receiver on `IR REC`. `D1` is the IR LED transmitter, driven through `Q1` and `R1` from `IR EMIT`.
- **User input expansion:** `U3` is a `PCF8575DBR` I2C GPIO expander on `sda` / `scl`. It fans out the discrete pushbutton signals `sw1` through `sw11` and also carries the custom rotary assembly switch signals `ano_sw1` through `ano_sw5`. All 16 expander IO are used, and all 11 XIAO GPIO pads are used: there are no spare pins.
- **Custom rotary assembly:** `ENC1` is the project-specific "Ano Rotary" part. It exposes encoder outputs `ano_enc1` / `ano_enc2` plus switch nets `ano_sw1` through `ano_sw5`.
- **Status lighting:** `D2` through `D5` are addressable `WS2812B-2020` LEDs in a 4-long cascade. `U1` `GPIO17` drives `D2` DIN on `led_1` with no series resistor, then `led_2`, `led_3`, and `led_4` carry DOUT to the next DIN. `D5` DOUT is a no-connect. All four VDD sit on `+3.3V` and all four VSS on GND, with no decoupling caps: every VDD pad drops into the board-wide B.Cu `+3.3V` plane through a via 0.0 to 4.4mm away, and every VSS pad sits directly in the F.Cu GND pour, so the supply loop is a few nH and the WS2812B-2020 datasheet does not require external caps.

The signal split matters: the rotary encoder channels `ano_enc1` / `ano_enc2` go straight from `ENC1` to `U1`, while the rotary push-switch nets and the eleven discrete switches go through `U3`. Power is also split between **`+3.3V`** and **`VCC`**. Logic parts sit on `+3.3V`, including `D2` since the VBUS rewire; `VCC` is now only the dangling `U1`/14 VBUS node. Do not collapse or rename those rails casually.

## KiCad workflow

- For board/schematic inspection, validation, and edits: use KiCad MCP tools first (run tool discovery for deferred ones). Fall back to `kicad-cli` or manual file patching only when MCP lacks the operation or fails.
- For schematic parity work, use KiCad MCP schematic tools (not raw file patching) because labels and wire endpoints must snap to exact coordinates.
- After KiCad MCP connect/edit operations, re-run ERC/DRC immediately because some MCP tools may also mutate PCB-side metadata or parity-relevant state.
- KiCad tools may rewrite large file sections for small edits, sometimes collapsing the whole file to one line. Re-read the file before a second patch if a turn was interrupted, and run `kicad-cli sch upgrade <file> --force` to restore canonical formatting before committing.
- KiCad MCP schematic operations rewrite `c6remote-kicad/c6remote.kicad_pro` as a side effect, and the rewrite always drifts the same way: `min_copper_edge_clearance` 0.5 → 0.025, `pth_inside_courtyard` / `npth_inside_courtyard` ignore → error, unused `highpower` / `lowpower` netclasses re-added, `Default` netclass priority reset. It came back twice in one session. Run `git diff c6remote-kicad/c6remote.kicad_pro` before every commit and `git checkout --` it unless the rule change is deliberate; committing the 0.025 value silently disarms the edge-clearance check.
- `rotate_schematic_component` drags attached wire endpoints along with the symbol. After a delete + add + rotate swap, re-check every pin against `get_schematic_pin_locations` and re-run ERC: a rotated stub can silently land a power rail on a signal pin.
- Autorouting: use KiCadRoutingTools (Rust A* router, no Java) at `~/dev/KiCadRoutingTools`, NOT the MCP Freerouting autoroute (its jar needs Java 25, only 17/23 installed here). Run: `~/dev/KiCadRoutingTools/.venv/bin/python ~/dev/KiCadRoutingTools/route.py <board.kicad_pcb>`. Writes `<board>_routed.kicad_pcb` (non-destructive; add `--overwrite` to replace). Scope with `--nets "<glob>"`. Diff pairs: `route_diff.py`; planes: `route_planes.py`. Deps live in that venv (numpy/scipy/shapely + prebuilt `grid_router.so` from `build_router.py`). Sync board from schematic (update_from_schematic / MCP `sync_schematic_to_board`) BEFORE routing when the schematic changed, else the router routes stale board topology.
- Verify a footprint's pad numbering against the part datasheet before adopting it. KiCad's stock symbols and footprints for the same part family do not always agree: `LED_SK6812_EC15_1.5x1.5mm` numbers pads 1 DIN / 2 VDD / 3 DOUT / 4 GND while every stock SK68xx symbol numbers 1 DOUT / 2 VSS / 3 DIN / 4 VDD, and pairing them rotates all four functions. Same failure class as the ENC1 pad 6/8 fault.

## Key repository conventions

- **Never add `Co-Authored-By:` trailers to commit messages**, no Claude, no Copilot, none. Author identity in commits and docs is the git user only. Hooks `scripts/hooks/commit-msg` (message) and `scripts/hooks/pre-commit` (staged content) reject trailer-shaped lines and known AI-bot emails; install with `git config core.hooksPath scripts/hooks`.
- Punctuation for breaks: period, colon, comma, or parentheses. Applies everywhere: docs, README, commit messages, comments, chat. (Em dash banned.)
- For exploration/search/research subagent tasks, launch the Agent tool with `model: sonnet`. Keep the main-thread model for synthesis and edits.
- The schematic is a **single sheet** that relies on **global labels** for most interconnects. For cross-cutting changes, search label names such as `sw*`, `ano_*`, `IR EMIT`, `IR REC`, `led_1`, `sda`, `scl`, `sck`, `ws`, and `sd`.
- The live design files are `c6remote.kicad_sch`, `c6remote.kicad_pcb`, and `c6remote.kicad_pro`. Files such as `*.bak`, `*-bak`, and `c6remote-backups/` are archival backups, not normal edit targets.
- `export/` contains **generated fabrication artifacts**. Update it only when intentionally regenerating manufacturing outputs; do not hand-edit Gerbers or drill files.
- The project-local symbol library is already wired through `c6remote-kicad/sym-lib-table`, but the board footprints use the library nickname **`Library`** and there is **no checked-in `fp-lib-table`**. To resolve custom footprints in KiCad, map `Library` to `kicad lib/Library.pretty`.
- Custom footprints under `kicad lib/Library.pretty/` are part of the design, especially `XIAO-ESP32C6-DIP.kicad_mod`, `SW_TL3315NF160Q.kicad_mod`, and `Ano Rotary.kicad_mod`. Changes to those parts affect both schematic-footprint linking and PCB geometry, so verify both the schematic symbol properties and the PCB footprint instances after editing them.
- `ano rotary.kicad_sym` defines the custom rotary symbol used as `ENC1`. Its pin electrical types are not modeled cleanly for ERC today, so changing that symbol can shift the existing ERC baseline.
- The stored plot settings in the KiCad files point at a Windows path. For automated exports, always pass an explicit output directory such as `-o export` instead of relying on the saved project path.
- `kicad-cli` writes report files such as `c6remote-erc.rpt` and `c6remote-drc.rpt` in `c6remote-kicad/` when you run validation. Treat them as generated scratch output unless a task explicitly asks you to keep or inspect them.
- Before commit, check tracked vs untracked. Common untracked KiCad/editor artifacts here:
  `c6remote-kicad/.history/`, `c6remote-kicad/DRC.rpt`, `c6remote-kicad/renders/`,
  `.cursor/`, `.windsurf/`, `.opencode/`, `.clinerules/`
- Git write operations from Codex can fail with `.git/index.lock` errors because the sandbox blocks writes inside `.git`, not because a stale lock exists. If the lock file is absent, treat it as a permissions issue and rerun `git add`, `git commit`, or other Git write ops with escalation instead of chasing repo corruption.
- `.mcp.json` already contains a working KiCad MCP server definition for Codex in this workspace. `.vscode/mcp.json` mirrors the same server for VS Code MCP clients. Keep using KiCad's bundled Python from the `.app` bundle; do not switch MCP operations to Homebrew or system Python.
- `docs/mcp-setup.md` is source of truth for multi-client MCP setup in this repo. Use it when touching Codex, Claude Desktop, or Copilot / VS Code MCP configuration.
- The local MCP server checkout at `/Users/landonrohatensky/dev/KiCAD-MCP-Server` is valid on this machine, and `bash setup-macos.sh --verify` currently passes there. If MCP stops working, rerun that command before changing paths by hand.
- Upstream docs often show Claude Desktop's `mcpServers` format. Codex uses workspace `.mcp.json` with `mcpServers`; VS Code uses `.vscode/mcp.json` with `servers`. Do not "normalize" one format into another unless you are intentionally editing that client config.
