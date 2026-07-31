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

Code comments: brief. Only facts the code cannot show (hardware quirks, ordering constraints, non-obvious magic numbers). No file-header essays, no section banners, no restating what the next line does. If a comment explains why the change is correct rather than a constraint the next reader needs, delete it.

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

`scripts/regen-fab.sh` wraps four `kicad-cli` exports (gerbers + drill + `c6remote-pos.csv` position file + `c6remote-bom.csv` BOM) with the project's established formats: position file is CSV/mm/both-sides; BOM is grouped by Value+Footprint with the custom sourcing columns (Reference, Qty, Value, Footprint, Datasheet, Description, Manufacturer, MPN, Digikey, Mouser, Adafruit, LCSC) and ", "-joined references. `LCSC` holds a product URL like the other distributor columns, not a bare C-number, and only `Q2` (`C15127`) and `D2`-`D5` (`C5349955`) carry one; JLCPCB's assembly upload matches on the bare part number, so read it out of the URL rather than pasting the column. Override the binary with `KICAD_CLI=/path/to/kicad-cli scripts/regen-fab.sh`.

BOM regen: run `scripts/export-bom.sh` (or `scripts/regen-fab.sh`, which calls it). NOT the MCP `export_bom` tool, which emits a different schema (regrouped rows, drops the custom sourcing columns, lists test points) and clobbers the curated CSV. Datasheet and sourcing fields live on the schematic symbols (source of truth); edit them there, then rerun the script.

A tracked pre-commit hook (`scripts/hooks/pre-commit`) runs `regen-fab.sh` and stages `export/` automatically whenever `c6remote.kicad_sch` or `c6remote.kicad_pcb` is part of a commit, so fabrication outputs never drift from the design. It also rerenders README assets via `scripts/render-readme-assets.sh` and stages `docs/readme-assets/`: a staged PCB rerenders the board views (`--only board`), a staged schematic rerenders `schematic.svg` (`--only schematic`), both staged rerenders everything (`--only all`). A staged PCB additionally reruns `scripts/gen-ibom.sh` to refresh `c6remote-kicad/ibom.html`, the pre-fab pin-1 walk artifact, which is gitignored and deliberately never staged; that step is non-fatal because it needs KiCad's bundled Python and a first-run network clone, so a `WARNING: gen-ibom.sh failed` line means the file is stale and needs a manual rerun, not that the commit is bad. Activate it once per clone with `git config core.hooksPath scripts/hooks`; bypass a single commit with `git commit --no-verify`. Because gerber/drill headers embed a creation timestamp, any board-touching commit restages all of `export/` even when geometry is unchanged.

There is no finer-grained single-test harness in this repo; the closest scoped checks are ERC for the schematic and DRC for the PCB, run separately.

**Zone refill before commit:** `kicad-cli pcb drc --refill-zones` refills copper zones in memory only, it never saves the refill back into `c6remote.kicad_pcb`. After any board edit that can affect copper pours (moved/changed footprints, new tracks or vias, net changes), do NOT commit until Landon has refilled zones in the KiCad GUI (Edit → Fill All Zones, then save) and confirmed. Stage and commit the board file only after that confirmation.

Baseline as of 2026-07-31: `sch erc` 0 violations, `pcb drc` 0 errors and 0 unconnected items with 2 warnings (1 `lib_footprint_mismatch` for `U1`, 1 `silk_overlap`). Treat those 2 as pre-existing unless the task is specifically about them, and a count above 2 is a regression introduced by the current task, not inherited. `U1` is the only footprint still diverging from its library; the 13 `TP_*` mismatches were cleared on 2026-07-31.

It was 43 until 2026-07-30, when `silk_over_copper` and `silk_edge_clearance` were set to `ignore` in the GUI and that change was committed deliberately. The 24 `silk_over_copper` and 4 `silk_edge_clearance` are muted, not fixed, so they are still in the artwork: 5 of the `silk_over_copper` are the ANO wheel outline crossing ENC1 pads, which is intentional. Do not read the drop from 43 to 15 as 28 defects resolved, and do not re-enable either severity to "restore the baseline". Earlier history, for context: 48 until 2026-07-26, dropping in two steps, `silk_overlap` 3 to 1 during the back-silk artwork, then `silk_edge_clearance` 7 to 4 at 25f2f92 when dropping the two IR cutouts took away three of the four U2 back-silk clips that sat against the notch walls.

Schematic-vs-board parity is 13 issues, all `extra_footprint` for the board-only `TP_*` test points. The board now carries the D2-D5 `XL-2020RGBC-WS2812B` swap, the D3-D5 chain, the SW1-11 terminal remap, and the MK1 ICS-43434 pin renumber, so those no longer diverge.

## Branches and releases

Work happens on **`dev`**, which is the GitHub default branch. **`main`** holds released snapshots only. Do not commit to `main` directly and do not push it as a shortcut: a push to `main` is the release event.

`.github/workflows/release.yml` fires on every push to `main`. It packages the committed `c6remote-kicad/export/` directory, tags an ESPHome-style CalVer (`YYYY.M.PATCH`, month not zero padded, so `2026.7.0` then `2026.7.1`, patch derived by scanning existing tags for that year and month), and publishes a release with three assets: `c6remote-<version>-fab.zip` holding the gerbers, drill and job file, plus `c6remote-<version>-bom.csv` and `c6remote-<version>-pos.csv` as separate files, which is how JLCPCB and PCBWay want them uploaded. All three asset names carry the version, so a downloaded BOM or position file still says which release it came from; because `gh` names an asset after the file it uploads, the workflow copies the two CSVs to versioned names in `RUNNER_TEMP` first rather than uploading them straight out of `export/`. The `2026.7.0` release was renamed in place on 2026-07-30 to match, so its `c6remote-bom.csv` and `c6remote-pos.csv` download URLs are dead. The historical `v0.1` tag was renamed `2026.6.0` on 2026-07-29 so every tag matches the CalVer scheme, mapped from the 2026-06-16 fab date. The old `releases/tag/v0.1` and `releases/download/v0.1/...` URLs are dead: any new link must use `2026.6.0`.

The PCB front silkscreen revision marking must be kept equal to the release the board will ship in; it currently reads `2026.7.1`. The patch number counts too, not just the month: the silk went `2026.7.0` to `2026.7.1` on 2026-07-30 for the via-in-pad fix, because a copper change makes it a different board and the workflow derives the next patch from the existing tags. Whenever a merge to `main` would compute a version the silk does not show, whether the month slipped or a `2026.7.0` tag already exists, update the silk before merging, not after.

No KiCad runs in CI, so the release is only as correct as what is committed. `scripts/hooks/pre-commit` is what keeps `export/` in lockstep, so a stale `export/` is a bad commit, not a workflow bug.

`c6remote-kicad/export.zip` is gitignored on purpose. It is a local convenience copy of the same gerber set, rebuilt on demand with `(cd c6remote-kicad/export && zip -X ../export.zip *.gbr *.gbrjob *.drl)`. It is deliberately **not** wired into the pre-commit hook, because the release workflow is the thing that publishes a fab package. Never track it.

## High-level architecture

The board is centered on a **Seeed Studio XIAO ESP32-C6** module (`U1`). Single-sheet KiCad design with heavy use of global labels, so understanding behavior usually means following named nets across the sheet and then checking the matching PCB nets and footprints.

Key functional blocks:

- **Audio input:** `MK1` is an ICS-43434 / INMP441-style I2S microphone wired with `sck`, `ws`, and `sd`.
- **IR subsystem:** `U2` is a TSOP45xx IR receiver on `IR REC`. `D1` is the IR LED transmitter, driven through `Q1` and `R1` from `IR EMIT`.
- **User input expansion:** `U3` is a `PCF8575DBR` I2C GPIO expander on `sda` / `scl`. It fans out the discrete pushbutton signals `sw1` through `sw11` and also carries the custom rotary assembly switch signals `ano_sw1` through `ano_sw5`. All 16 expander IO are used. All 11 XIAO edge pads (D0-D10) are now used: `D10`/`GPIO18` was the last free one and now carries `led_en`, the LED rail enable, so `TP_GPIO18_D10_MOSI` is a probe point for that signal rather than a spare pad. The earlier claim that there are no spare pins at all was wrong and had already been used to reject one design option: the module's bottom pad row is also available, and `GPIO4` (`bat_sense`) and `GPIO5` (`exp_int`) already come off it, which proves the row is routable. `GPIO6` (pad 29) and `GPIO7` (pad 25) are unconnected and free, and both sit in the `GPIO0`-`GPIO7` LP range so they can also serve as deep-sleep wake sources. `GPIO9` (pad 30) is unconnected too but is the BOOT strapping pin, so avoid it. Verify against U1's pads in the board file before relying on any of this.
- **Custom rotary assembly:** `ENC1` is the project-specific "Ano Rotary" part. It exposes encoder outputs `ano_enc1` / `ano_enc2` plus switch nets `ano_sw1` through `ano_sw5`.
- **Status lighting:** `D2` through `D5` are addressable `XL-2020RGBC-WS2812B` LEDs (XINGLIGHT, LCSC `C5349955`) in a 4-long cascade. `U1` `GPIO17` drives `D2` DIN on `led_1` with no series resistor, then `led_2`, `led_3`, and `led_4` carry DOUT to the next DIN. `D5` DOUT is a no-connect. All four VDD sit on the switched `led_vdd` rail, not on `+3.3V` directly, because the cascade draws roughly 2.0mA quiescent even when dark, 0.5mA typical IDD per device on the XINGLIGHT datasheet. `Q2` is an `AO3401A` P-channel MOSFET (SOT-23, F.Cu at 42, 84.4375) with pad 2 source on `+3.3V`, pad 3 drain on `led_vdd`, and pad 1 gate on `led_en` from `U1` `GPIO18`. `R10` (1M 0603, B.Cu at 41, 89.575) pulls `led_en` up to `+3.3V`, so the rail is off by default: `GPIO18` boots as a floating input and `R10` holds the gate at the source. `C4` (1uF 50V X7R 0805, B.Cu at 46.75, 67.3) is the local reservoir on `led_vdd`, placed mid-chain, and gating the rail is exactly why it is needed now when the four LEDs previously ran with no decoupling at all: the four vias that dropped each VDD pad into the board-wide B.Cu `+3.3V` plane 0.0 to 4.4mm away are gone, and `led_vdd` is instead a ~90mm trace tree (39.3mm F.Cu plus 51.9mm B.Cu, 4 vias), so the plane no longer supplies switching charge locally. `C4`'s ground return is a 5.2mm B.Cu stub into `ENC1` pad 6, a through-hole GND pad, rather than a direct pour tap. The VSS side is unchanged: all four pads connect solid (`zone_connect 2`) into the F.Cu GND pour. Firmware must hold `GPIO17` low or high-impedance whenever the rail is down, else DIN pushes current through the LED input clamp into the dead rail. The part is WS2812B protocol compatible (single wire, 800kHz, GRB high bit first, reset >100us), so ESPHome stays on `chipset: WS2812` with `rgb_order: GRB`. It was chosen over the `WS2812B-2020` it replaced because it is rated VDD 3.5-5.5V rather than 3.7-5.3V, specifies VIH as 0.5*VDD rather than an absolute 2.7V, and drives 5mA/ch rather than 12mA, all of which buy headroom on the under-spec 3.3V rail. Nothing in a 2020 package is datasheet-rated down to 3.3V and stocked at LCSC; the Dialight `587-1024-147F` is rated 3.3-5.5V but LCSC stock is 0 (see `ROADMAP.md`).

The signal split matters: the rotary encoder channels `ano_enc1` / `ano_enc2` go straight from `ENC1` to `U1`, while the rotary push-switch nets and the eleven discrete switches go through `U3`. Power is also split three ways: **`+3.3V`**, the switched **`led_vdd`** branch off it, and **`VCC`**. Logic parts sit on `+3.3V`; `D2` through `D5` sit on `led_vdd`, which `Q2` gates from `+3.3V` under `led_en` and which is off unless firmware drives `GPIO18` low; `VCC` is now only the dangling `U1`/14 VBUS node. Do not collapse or rename those rails casually, and in particular do not "simplify" `led_vdd` back onto `+3.3V`.

## KiCad workflow

- For board/schematic inspection, validation, and edits: use KiCad MCP tools first (run tool discovery for deferred ones). Fall back to `kicad-cli` or manual file patching only when MCP lacks the operation or fails.
- For schematic parity work, use KiCad MCP schematic tools (not raw file patching) because labels and wire endpoints must snap to exact coordinates.
- After KiCad MCP connect/edit operations, re-run ERC/DRC immediately because some MCP tools may also mutate PCB-side metadata or parity-relevant state.
- KiCad tools may rewrite large file sections for small edits, sometimes collapsing the whole file to one line. Re-read the file before a second patch if a turn was interrupted, and run `kicad-cli sch upgrade <file> --force` to restore canonical formatting before committing.
- `c6remote-kicad/c6remote.kicad_pro` drift: saving or closing eeschema rewrites the whole project file from the copy it loaded at project open, reverting rule and severity changes made since. Root caused 2026-07-31, no KiCad setting disables it, do not re-investigate. `scripts/hooks/pre-commit` runs `scripts/check-kicad-pro-drift.py`, which blocks a commit whose staged project file moved on `board.design_settings.rules`, either `rule_severities` block, or the netclass list; deliberate changes need `--no-verify`. Whatever is committed is the intended value; the hook is the record, so treat HEAD as correct rather than reasoning about which settings were meant. `defaults.pads` also churns and is deliberately unguarded: it is cosmetic GUI state, the dimensions of the last pad whose properties you opened, and it affects nothing but the next hand-placed pad. Leave whichever value is there.
- `rotate_schematic_component` drags attached wire endpoints along with the symbol. After a delete + add + rotate swap, re-check every pin against `get_schematic_pin_locations` and re-run ERC: a rotated stub can silently land a power rail on a signal pin.
- Autorouting: use KiCadRoutingTools (Rust A* router, no Java) at `~/dev/KiCadRoutingTools`, NOT the MCP Freerouting autoroute (its jar needs Java 25, only 17/23 installed here). Run: `~/dev/KiCadRoutingTools/.venv/bin/python ~/dev/KiCadRoutingTools/route.py <board.kicad_pcb>`. Writes `<board>_routed.kicad_pcb` (non-destructive; add `--overwrite` to replace). Scope with `--nets "<glob>"`. Diff pairs: `route_diff.py`; planes: `route_planes.py`. Deps live in that venv (numpy/scipy/shapely + prebuilt `grid_router.so` from `build_router.py`). Sync board from schematic (update_from_schematic / MCP `sync_schematic_to_board`) BEFORE routing when the schematic changed, else the router routes stale board topology.
- Verify a footprint's pad numbering against the part datasheet before adopting it. KiCad's stock symbols and footprints for the same part family do not always agree: `LED_SK6812_EC15_1.5x1.5mm` numbers pads 1 DIN / 2 VDD / 3 DOUT / 4 GND while every stock SK68xx symbol numbers 1 DOUT / 2 VSS / 3 DIN / 4 VDD, and pairing them rotates all four functions. Same failure class as the ENC1 pad 6/8 fault. Datasheets lie about this too, and revisions disagree: the `XL-2020RGBC-WS2812B` datasheet hosted at xonstorage prints a pin function table reading 1 VDD / 2 DOUT / 3 GND / 4 DIN that contradicts its own pin diagram on the same page, while the newer revision DigiKey hosts prints 1 DO / 2 GND / 3 DI / 4 VDD, matching both diagrams and the `WS2812B-2020` it clones. Prefer the distributor-hosted revision, and always cross-check the table against the diagram before trusting either.

## Key repository conventions

- **Never add `Co-Authored-By:` trailers to commit messages**, no Claude, no Copilot, none. Author identity in commits and docs is the git user only. Hooks `scripts/hooks/commit-msg` (message) and `scripts/hooks/pre-commit` (staged content) reject trailer-shaped lines and known AI-bot emails; install with `git config core.hooksPath scripts/hooks`.
- Punctuation for breaks: period, colon, comma, or parentheses. Applies everywhere: docs, README, commit messages, comments, chat. (Em dash banned.)
- For exploration/search/research subagent tasks, launch the Agent tool with `model: sonnet`. Keep the main-thread model for synthesis and edits.
- The schematic is a **single sheet** that relies on **global labels** for most interconnects. For cross-cutting changes, search label names such as `sw*`, `ano_*`, `IR EMIT`, `IR REC`, `led_1`, `sda`, `scl`, `sck`, `ws`, and `sd`.
- The live design files are `c6remote.kicad_sch`, `c6remote.kicad_pcb`, and `c6remote.kicad_pro`. Files such as `*.bak`, `*-bak`, and `c6remote-backups/` are archival backups, not normal edit targets.
- `export/` contains **generated fabrication artifacts**. Update it only when intentionally regenerating manufacturing outputs; do not hand-edit Gerbers or drill files.
- Both library tables are checked in and wired: `c6remote-kicad/sym-lib-table` for symbols, and `c6remote-kicad/fp-lib-table` mapping the three footprint nicknames the board uses, `Library` to `../kicad lib/Library.pretty`, plus `Local` and `Seeed_Studio_XIAO_Series` to the `.pretty` directories beside it. Nothing needs mapping by hand.
- Custom footprints under `kicad lib/Library.pretty/` are part of the design, especially `XIAO-ESP32C6-DIP.kicad_mod`, `SW_TL3315NF160Q.kicad_mod`, `Ano Rotary.kicad_mod`, and `LED_XL-2020RGBC-WS2812B_PLCC4_2.0x2.0mm.kicad_mod`. Changes to those parts affect both schematic-footprint linking and PCB geometry, so verify both the schematic symbol properties and the PCB footprint instances after editing them.
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
