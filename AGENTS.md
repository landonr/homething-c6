# Agent instructions

`AGENTS.md` is the real file. `CLAUDE.md` and `.github/copilot-instructions.md` are symlinks to it, so Claude Code, Codex, and Copilot all read the same text. Edit `AGENTS.md` only; never replace a symlink with a copy, or the three clients drift apart.

## Response style

Respond terse like smart caveman. All technical substance stay. Only fluff die.

- Drop: articles (a/an/the), filler (just/really/basically), pleasantries, hedging.
- Fragments OK. Short synonyms. Technical terms exact. Code unchanged.
- Pattern: [thing] [action] [reason]. [next step].
- Not: "Sure! I'd be happy to help you with that." Yes: "Bug in auth middleware. Fix:"
- Switch level: `/caveman lite|full|ultra|wenyan`. Stop: "stop caveman" or "normal mode".
- Auto-Clarity: drop caveman for security warnings, irreversible actions, user confused. Resume after.
- Boundaries: code, commits, and PRs written normal.

Response shape:

- Report what happened and what it proves. Every sentence carries a new fact: result, number, file, next step. Stop when facts stop.
- Describe only actions taken and their outcomes. Skipped checks, unused alternatives, possible follow-ups: mention only when the user must act on them.
- Yes: "ERC 0. Netlist matches board, parity 45. Committed fee23d4."
- Not: "ERC 0. Note I didn't re-run DRC since copper unchanged. Could also have used kicad-cli instead. Want me to check parity too, or update the README?"
- Exception: failures and blockers get full detail. What failed, exact error output, what was tried, what input is needed to unblock.

Code comments: brief. Only facts the code cannot show (hardware quirks, ordering constraints, non-obvious magic numbers). No file-header essays, no section banners, no restating the next line. A comment arguing why a change is correct, rather than stating a constraint the next reader needs, gets deleted.

## Repository layout

KiCad hardware project, not a software application. Source of truth under `c6remote-kicad/`:

- `c6remote.kicad_sch` - single-sheet schematic
- `c6remote.kicad_pcb` - board layout
- `c6remote.kicad_pro` - ERC/DRC settings, BOM settings, project metadata
- `ano rotary.kicad_sym` - project-local custom symbol library, `ENC1` only
- `Local.kicad_sym` - the other project symbol library, `SW_TL3315NF160Q` and `TSOP61xx`
- `../kicad lib/Library.pretty/` - custom footprints used by the board
- `3dmodels/` - 3D models the project footprints point at through `${KIPRJMOD}`
- `export/` - generated Gerbers and drill files

Board status, validation history, and "what's left" work live in `ROADMAP.md`. Read it first.

## Validation and fabrication commands

Run from `c6remote-kicad/`. App-bundled binary on this machine:

```bash
cd c6remote-kicad
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli

# Schematic only
$KC sch erc c6remote.kicad_sch --exit-code-violations

# Board only
$KC pcb drc c6remote.kicad_pcb --exit-code-violations

# Board plus schematic parity and in-memory zone refill
$KC pcb drc c6remote.kicad_pcb --schematic-parity --refill-zones --exit-code-violations

# All fabrication outputs into export/. Run after any schematic or board change.
scripts/regen-fab.sh

# Gerbers alone
$KC pcb export gerbers c6remote.kicad_pcb -o export --board-plot-params
```

ERC for the schematic and DRC for the PCB are the only scoped checks; there is no finer-grained test harness.

**Zone refill before commit:** `--refill-zones` refills in memory only, it never writes the refill back to `c6remote.kicad_pcb`. After any board edit that can affect copper pours (moved or changed footprints, new tracks or vias, net changes), do not commit until Landon has refilled in the GUI (Edit → Fill All Zones, then save) and confirmed. Stage the board file only after that confirmation.

### Scripts

`scripts/regen-fab.sh` wraps four `kicad-cli` exports (gerbers, drill, `c6remote-pos.csv`, `c6remote-bom.csv`) in the project's formats: position file CSV/mm/both-sides; BOM grouped by Value+Footprint with the custom sourcing columns (Reference, Qty, Value, Footprint, Datasheet, Description, Manufacturer, MPN, Digikey, Mouser, Adafruit, LCSC) and ", "-joined references. Override the binary with `KICAD_CLI=/path/to/kicad-cli`.

`LCSC` holds a product URL like the other distributor columns, not a bare C-number, and only `Q2` (`C15127`) and `D2`-`D5` (`C5349955`) carry one. JLCPCB assembly upload matches on the bare part number, so read it out of the URL rather than pasting the column.

BOM regen goes through `scripts/export-bom.sh` (or `regen-fab.sh`, which calls it). NOT the MCP `export_bom` tool: it emits a different schema (regrouped rows, no sourcing columns, test points listed) and clobbers the curated CSV. Datasheet and sourcing fields live on the schematic symbols; edit them there, then rerun the script.

### Pre-commit hook

Tracked at `scripts/hooks/pre-commit`. Activate once per clone with `git config core.hooksPath scripts/hooks`; bypass one commit with `git commit --no-verify`. When `c6remote.kicad_sch` or `c6remote.kicad_pcb` is staged it:

- runs `regen-fab.sh` and stages `export/`, so fab outputs never drift from the design
- reruns `scripts/render-readme-assets.sh` and stages `docs/readme-assets/`: staged PCB is `--only board`, staged schematic is `--only schematic`, both is `--only all`
- staged PCB also reruns `scripts/gen-ibom.sh` for `c6remote-kicad/ibom.html`, the pre-fab pin-1 walk artifact, gitignored and deliberately never staged. Non-fatal, because it needs KiCad's bundled Python and a first-run network clone, so `WARNING: gen-ibom.sh failed` means that file is stale, not that the commit is bad.

Gerber and drill headers embed a creation timestamp, so any board-touching commit restages all of `export/` even when geometry is unchanged.

### Baseline as of 2026-08-04

- `sch erc`: 0 violations.
- `pcb drc`: 0 errors, 0 unconnected, 1 warning (`lib_footprint_mismatch` on `U1`). `U1` is the only footprint diverging from its library.
- Parity: 0 issues. The 14 `TP_*` test points are gone from the board, so nothing is board-only any more.

Treat those counts as pre-existing unless the task is about them. Anything above 1 warning is a regression from the current task, not inherited.

Run DRC with `--refill-zones` when checking against this baseline. Without it you are measuring the stored fill, which goes stale the moment anything moves, and a stale fill reports phantom `isolated_copper` and zone-to-zone `unconnected_items`. Those two together are the signature of a pour split into unreachable pieces, worth knowing because the JSON export reports the zone's *anchor* for them rather than the island, so every zone violation appears to be at the top-left board corner. Use the GUI DRC panel or the ratsnest airwire to locate one.

`silk_over_copper` and `silk_edge_clearance` were set to `ignore` in the GUI on 2026-07-30, deliberately. The 24 `silk_over_copper` and 4 `silk_edge_clearance` are muted, not fixed, and still in the artwork; 5 of the `silk_over_copper` are the ANO wheel outline crossing ENC1 pads, which is intentional. Do not re-enable either severity to "restore the baseline".

## Branches and releases

Work happens on **`develop`**. **`main`** holds released snapshots only and is the GitHub default branch, so it is what a visitor sees first and what relative doc links resolve against. Do not commit to `main` and do not push it as a shortcut: a push to `main` is the release event. Check `git branch --show-current` before the first commit of a session, since a checkout left on `main` puts working commits on the release branch.

`.github/workflows/release.yml` fires on every push to `main`. It packages the committed `c6remote-kicad/export/`, tags ESPHome-style CalVer (`YYYY.M.PATCH`, month not zero padded, so `2026.7.0` then `2026.7.1`; patch derived by scanning existing tags for that year and month), and publishes three assets: `c6remote-<version>-fab.zip` (gerbers, drill, job file) plus `c6remote-<version>-bom.csv` and `c6remote-<version>-pos.csv` as separate files, which is how JLCPCB and PCBWay want them uploaded. All three names carry the version, so `gh` cannot name assets after the files in `export/`; the workflow copies the two CSVs to versioned names in `RUNNER_TEMP` first.

Dead URLs, use the new tags in any new link: `v0.1` was renamed `2026.6.0` (2026-07-29, mapped from the 2026-06-16 fab date), so `releases/tag/v0.1` and `releases/download/v0.1/...` are gone; `2026.7.0` was renamed in place (2026-07-30), killing its `c6remote-bom.csv` and `c6remote-pos.csv` download URLs.

The PCB front silkscreen revision marking must equal the release the board ships in. It currently reads `2026.8.1`. The patch counts, not only the month: any artwork change, copper or silk, makes it a different board, and the workflow derives the next patch from existing tags. Whenever a merge to `main` would compute a version the silk does not show, update the silk before merging.

No KiCad runs in CI, so the release is only as correct as what is committed. `scripts/hooks/pre-commit` is what keeps `export/` in lockstep; a stale `export/` is a bad commit, not a workflow bug.

`c6remote-kicad/export.zip` is gitignored on purpose, a local convenience copy rebuilt on demand with `(cd c6remote-kicad/export && zip -X ../export.zip *.gbr *.gbrjob *.drl)`. Deliberately not wired into the hook, because the release workflow is what publishes a fab package. Never track it.

## High-level architecture

Centered on a **Seeed Studio XIAO ESP32-C6** module (`U1`). Single sheet, heavy use of global labels, so understanding behavior means following named nets across the sheet and then checking the matching PCB nets and footprints.

- **Audio input:** `MK1`, ICS-43434 / INMP441-style I2S mic on `sck`, `ws`, `sd`.
- **IR:** `U2` is a `TSOP6136TT` receiver on `IR REC`, a Vishay Panhead SMD part on B.Cu that receives perpendicular to the board through the bottom face. `D1` is the IR LED, driven through `Q1` and `R1` from `IR EMIT`.
- **Input expansion:** `U3` is a `PCF8575DBR` on `sda`/`scl`, fanning out `sw1`-`sw11` plus the rotary switch nets `ano_sw1`-`ano_sw5`. All 16 expander IO used.
- **Custom rotary:** `ENC1`, the project-specific "Ano Rotary" part. Encoder outputs `ano_enc1`/`ano_enc2` plus `ano_sw1`-`ano_sw5`.
- **Status lighting:** `D2`-`D5`, four `XL-2020RGBC-WS2812B` (XINGLIGHT, LCSC `C5349955`) in cascade. See below.

Pin budget: all 11 XIAO edge pads (D0-D10) are used. `D10`/`GPIO18` was the last free one and now carries `led_en`. The board has no test points at all since 2026-08-01, so there is no probe pad on any signal. The module's bottom pad row is also available and routable, proven by `GPIO4` (`bat_sense`) and `GPIO5` (`exp_int`) already coming off it. `GPIO6` (pad 29) took `ir_en` on 2026-08-04, so `GPIO7` (pad 25) is the only free pad left. It is in the `GPIO0`-`GPIO7` LP range, so it is the last pin that can serve as a deep-sleep wake source; spend it deliberately. Note `IR REC` sits on `GPIO16`, outside that range, so IR cannot wake the board from deep sleep as wired. `GPIO9` (pad 30) is unconnected but is the BOOT strapping pin, so avoid it. Verify against `U1`'s pads in the board file before relying on any of this.

Signal split: `ano_enc1`/`ano_enc2` go straight from `ENC1` to `U1`, while the rotary push-switch nets and all eleven discrete switches go through `U3`.

Power splits three ways: **`+3.3V`** for logic, the switched **`led_vdd`** branch off it for `D2`-`D5`, and the switched **`ir_vdd`** branch off it for `U2` as of 2026-08-04. Do not collapse or rename those rails casually, and in particular do not "simplify" either switched branch back onto `+3.3V`. Both gates are the same shape: an `AO3401A` P-FET high-side, source on `+3.3V`, a 1M gate pull-up so the rail is off by default, and an enable net driven low to turn on. `Q2`/`R10`/`led_en` for the LEDs, `Q3`/`R11`/`ir_en` for the receiver. The old **`VCC`** rail is gone as of 2026-08-01: it had shrunk to the `U1`/14 VBUS node alone, and that pin now carries a schematic no-connect flag, so the board reads `unconnected-(U1-VBUS-Pad14)`. VBUS is unavailable on the board; a 5V feature needs a new net, not a revived label.

### LED rail detail

`U1` `GPIO17` drives `D2` DIN on `led_1` with no series resistor, then `led_2`, `led_3`, `led_4` carry DOUT to the next DIN. `D5` DOUT is a no-connect.

All four VDD sit on `led_vdd` rather than `+3.3V` because the cascade draws roughly 2.0mA quiescent even when dark (0.5mA typical IDD per device). `Q2`, an `AO3401A` P-channel MOSFET (SOT-23, F.Cu at 42, 84.4375), gates it: pad 2 source on `+3.3V`, pad 3 drain on `led_vdd`, pad 1 gate on `led_en` from `GPIO18`. `R10` (1M 0603, B.Cu at 41, 89.575) pulls `led_en` to `+3.3V`, so the rail is off by default; `GPIO18` boots as a floating input and `R10` holds the gate at the source.

`C4` (1uF 50V X7R 0805, B.Cu at 46.75, 67.3) is the local reservoir on `led_vdd`, placed mid-chain. Gating the rail is why it is needed now when the four LEDs previously ran with no decoupling: the four vias that dropped each VDD pad into the board-wide B.Cu `+3.3V` plane 0.0 to 4.4mm away are gone, and `led_vdd` is a ~90mm trace tree instead (39.3mm F.Cu plus 51.9mm B.Cu, 4 vias), so the plane no longer supplies switching charge locally. `C4`'s ground return is a 5.2mm B.Cu stub into `ENC1` pad 6, a through-hole GND pad, not a direct pour tap. VSS side unchanged: all four pads connect solid (`zone_connect 2`) into the F.Cu GND pour.

**Firmware must hold `GPIO17` low or high-impedance whenever the rail is down**, else DIN pushes current through the LED input clamp into the dead rail.

The part is WS2812B protocol compatible (single wire, 800kHz, GRB high bit first, reset >100us), so ESPHome stays on `chipset: WS2812` with `rgb_order: GRB`. Chosen over the `WS2812B-2020` it replaced for headroom on the under-spec 3.3V rail: VDD 3.5-5.5V rather than 3.7-5.3V, VIH as 0.5*VDD rather than an absolute 2.7V, 5mA/ch rather than 12mA. Nothing in a 2020 package is datasheet-rated down to 3.3V and stocked at LCSC; the Dialight `587-1024-147F` is rated 3.3-5.5V but LCSC stock is 0 (see `ROADMAP.md`).

### IR rail detail

Added 2026-08-04. `Q3` (`AO3401A`, F.Cu at 38.45, 140.3125) gates `ir_vdd` off `+3.3V`, feeding `R6` and so `U2`; `R11` (1M 0603, F.Cu at 37.5, 144.0) pulls `ir_en` to `+3.3V` so the rail is off by default. `ir_en` comes from `U1` pad 29, `GPIO6`. The existing `R6` 100R plus `C3` 100nF filter is downstream of the gate and unchanged, so `U2` keeps its local decoupling and `Q3` needs no reservoir cap of its own, unlike `C4` on the LED rail.

`Q3` and `R11` sit next to `U1`, not next to `U2`, which is the opposite of `Q2`. That is deliberate: `ir_en` is a 1M high-impedance node whenever `GPIO6` is an input, so the whole net is kept short, while `ir_vdd` takes the ~110mm run to `R6` because 350uA of DC over that length costs 0.2mV. Do not "tidy" this by moving `Q3` up beside its load.

Unlike the LED rail, **the IR rail defaults on**: `remote_receiver` cannot decode with `U2` unpowered, so the ESPHome `IR Rail` switch on `GPIO6` is `inverted: true` with `restore_mode: ALWAYS_ON`. Turning it off while awake saves less than it looks: `GPIO16` carries a pullup and `U2` has an internal 33k from OUT to Vs, so against a dead rail roughly 42uA flows back into it. The 350uA is only genuinely reclaimable in deep sleep, where the pullup is released.

`U2` went from the through-hole `TSOP4136` to the SMD `TSOP6136` on 2026-08-17 (`e6da487`). `ISD` is unchanged at 0.35mA typ, so every number above still holds; what changed is the package, not the rail. It is a 4-pin part now, 1 GND, 2 N.C., 3 Vs, 4 OUT, on the project footprint `Library:Vishay_PANHEAD-4Pin_TopView` at 42.845,31.8575 on B.Cu, with pad 1 reaching the F.Cu GND pour through a via rather than through a barrel. `TT` is the top-view lead form and `TR` is the side-view lead form; both share the same four-pad land pattern. The TT lens receives perpendicular to the board through the bottom face and lowers the bottom-side keepout from 5.34mm to about 4.0mm. Keep the AGC digit at 1 if the carrier frequency ever moves: `TSOP6136` is AGC1, the most permissive setting Vishay makes, and both firmwares run `remote_receiver` with `dump: all`, so a code the AGC rejects as noise is one that can never be learned. Vishay's AGC map tool at `vishay.com/en/landingpage/agcmaptool/` is how to re-check code acceptance before swapping to any other AGC.

## KiCad workflow

- Inspection, validation, and edits: KiCad MCP tools first (run tool discovery for deferred ones). Fall back to `kicad-cli` or manual file patching only when MCP lacks the operation or fails.
- Parity work goes through the MCP schematic tools, not raw file patching, because labels and wire endpoints must snap to exact coordinates.
- Re-run ERC and DRC immediately after MCP connect or edit operations; some of those tools also mutate PCB-side metadata and parity state.
- MCP edits may rewrite large file sections for a small change, sometimes collapsing the file to one line. Re-read a file before a second patch if a turn was interrupted, and run `kicad-cli sch upgrade <file> --force` to restore canonical formatting before committing.
- `c6remote.kicad_pro` drift: saving or closing eeschema rewrites the whole project file from the copy loaded at project open, reverting rule and severity changes made since. Root caused 2026-07-31, no KiCad setting disables it, do not re-investigate. `scripts/check-kicad-pro-drift.py` runs from the pre-commit hook and blocks a commit whose staged project file moved on `board.design_settings.rules`, either `rule_severities` block, or the netclass list. A deliberate change needs `--no-verify`. Whatever is committed is the intended value: the hook is the record, so treat HEAD as correct rather than reasoning about which settings were meant. `defaults.pads` also churns and is deliberately unguarded, cosmetic GUI state holding the last-opened pad's dimensions; leave whichever value is there.
- `rotate_schematic_component` drags attached wire endpoints along with the symbol. After a delete plus add plus rotate swap, re-check every pin against `get_schematic_pin_locations` and re-run ERC: a rotated stub can silently land a power rail on a signal pin.
- Autorouting: KiCadRoutingTools (Rust A* router, no Java) at `~/dev/KiCadRoutingTools`, NOT the MCP Freerouting autoroute (its jar needs Java 25, only 17 and 23 installed here). Run `~/dev/KiCadRoutingTools/.venv/bin/python ~/dev/KiCadRoutingTools/route.py <board.kicad_pcb>`, which writes `<board>_routed.kicad_pcb` (non-destructive, `--overwrite` replaces). Scope with `--nets "<glob>"`. Diff pairs: `route_diff.py`. Planes: `route_planes.py`. Deps live in that venv (numpy, scipy, shapely, prebuilt `grid_router.so` from `build_router.py`). Sync the board from the schematic BEFORE routing when the schematic changed, else the router routes stale topology, but see the next bullet for how.
- **Never run the MCP `sync_schematic_to_board` on this board.** Ask Landon to run Tools → Update PCB from Schematic (F8) in pcbnew instead. Measured 2026-08-04 adding `Q3`/`R11`: the tool placed the two new footprints correctly and then silently corrupted 16 existing pad assignments, caught only by diffing every pad's net against HEAD. It rotated `MK1` 1/2/4/6 (`ws`→`sck`, `GND`→`ws`, `sck`→`sd`, `sd`→`GND`), recreating the exact ICS-43434 pin fault the board was fixed for; swapped `U1`/1 and `U1`/4; swapped `sw9` and `sw10` on `U3`/13-14; moved `C4`/1 and `D2`/4 off `led_vdd` back to `+3.3V`, which would have defeated the LED gate; revived the retired `VCC` on `U1`/14; and dumped `C3`/1, `R6`/2, `U2`/3, `MK1`/5 and `U1`/32 onto the virtual `PWR_FLAG` net. The earlier note that it only misbehaves "near PWR_FLAG symbols" understated it. After any sync, diff board pad nets against the schematic netlist before trusting the result.
- Verify pad numbering against the part datasheet before adopting a footprint. KiCad's stock symbol and footprint for the same family do not always agree: `LED_SK6812_EC15_1.5x1.5mm` numbers pads 1 DIN / 2 VDD / 3 DOUT / 4 GND while every stock SK68xx symbol numbers 1 DOUT / 2 VSS / 3 DIN / 4 VDD, and pairing them rotates all four functions. Same failure class as the ENC1 pad 6/8 fault. Datasheet revisions disagree too: the `XL-2020RGBC-WS2812B` sheet hosted at xonstorage prints a pin table (1 VDD / 2 DOUT / 3 GND / 4 DIN) contradicting its own diagram on the same page, while the newer DigiKey-hosted revision prints 1 DO / 2 GND / 3 DI / 4 VDD, matching both diagrams and the `WS2812B-2020` it clones. Prefer the distributor-hosted revision, and cross-check table against diagram before trusting either.

## Key repository conventions

- **Never add `Co-Authored-By:` trailers to commit messages**, no Claude, no Copilot, none. Author identity in commits and docs is the git user only. `scripts/hooks/commit-msg` (message) and `scripts/hooks/pre-commit` (staged content) reject trailer-shaped lines and known AI-bot emails.
- Punctuation for breaks: period, colon, comma, or parentheses. Em dash banned everywhere: docs, README, commit messages, comments, chat.
- Exploration, search, and research subagents launch with `model: sonnet`. Keep the main-thread model for synthesis and edits.
- Single sheet, global labels for most interconnects. For cross-cutting changes search label names: `sw*`, `ano_*`, `IR EMIT`, `IR REC`, `led_1`, `sda`, `scl`, `sck`, `ws`, `sd`.
- Live design files are `c6remote.kicad_sch`, `c6remote.kicad_pcb`, `c6remote.kicad_pro`. `*.bak`, `*-bak`, and `c6remote-backups/` are archival, not edit targets.
- `export/` is generated. Update it only by regenerating; never hand-edit Gerbers or drill files.
- Both library tables are checked in and wired: `sym-lib-table` for symbols, `fp-lib-table` for the three footprint nicknames the board uses (`Library` to `../kicad lib/Library.pretty`, plus `Local` and `Seeed_Studio_XIAO_Series` to the `.pretty` directories beside it). Nothing needs mapping by hand.
- Custom footprints under `kicad lib/Library.pretty/` are part of the design, especially `XIAO-ESP32C6-DIP.kicad_mod`, `SW_TL3315NF160Q.kicad_mod`, `Ano Rotary.kicad_mod`, `LED_XL-2020RGBC-WS2812B_PLCC4_2.0x2.0mm.kicad_mod`, `Vishay_PANHEAD-4Pin_SideView.kicad_mod`, `Vishay_PANHEAD-4Pin_TopView.kicad_mod`. Editing one affects both symbol-footprint linking and PCB geometry, so verify schematic symbol properties and PCB footprint instances after. Their 3D models live under `c6remote-kicad/3dmodels/`; sources and orientation caveats are in `c6remote-kicad/3dmodels/README.md`, which is also where a new model's citation goes.
- `ano rotary.kicad_sym` defines `ENC1`. Its pin electrical types are not modeled cleanly for ERC, so changing that symbol can shift the ERC baseline.
- Stored plot settings point at a Windows path. Always pass an explicit output directory such as `-o export`.
- `kicad-cli` drops `c6remote-erc.rpt` and `c6remote-drc.rpt` in `c6remote-kicad/`. Generated scratch output unless a task says to keep them.
- Check tracked vs untracked before commit. Common untracked artifacts: `c6remote-kicad/.history/`, `c6remote-kicad/DRC.rpt`, `c6remote-kicad/renders/`, `.cursor/`, `.windsurf/`, `.opencode/`, `.clinerules/`.
- Git writes from Codex can fail with `.git/index.lock` because the sandbox blocks writes inside `.git`, not because a lock is stale. If the lock file is absent, rerun the git write with escalation instead of chasing repo corruption.
- `.mcp.json` holds the working KiCad MCP server definition for Codex; `.vscode/mcp.json` mirrors it for VS Code. Keep using KiCad's bundled Python from the `.app` bundle, not Homebrew or system Python.
- The MCP server checkout at `/Users/landonrohatensky/dev/KiCAD-MCP-Server` is valid on this machine and `bash setup-macos.sh --verify` passes there. If MCP breaks, rerun that before changing paths by hand.
- Upstream docs usually show Claude Desktop's `mcpServers` shape. Codex uses `.mcp.json` with `mcpServers`, VS Code uses `.vscode/mcp.json` with `servers`. Do not normalize one into the other unless intentionally editing that client's config.
