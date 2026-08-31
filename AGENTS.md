# Agent instructions

`AGENTS.md` is the source file. `CLAUDE.md` and `.github/copilot-instructions.md` are symlinks to this file.

Edit only `AGENTS.md`. Never replace a symlink with a copy. A copy causes the three clients to use different instructions.

## Response style

Use terse caveman style in chat. Keep all technical information and remove filler.

- Omit articles, filler, pleasantries, and hedging when clarity permits.
- Use fragments and short synonyms. Keep technical terms and code exact.
- Use this pattern: `[thing] [action] [reason]. [next step].`
- Do not write: "Sure! I'd be happy to help you with that."
- Write: "Bug in auth middleware. Fix:"
- Change the level with `/caveman lite|full|ultra|wenyan`.
- Stop this style with "stop caveman" or "normal mode".
- Use normal prose for security warnings, irreversible actions, or user confusion. Resume caveman style after the warning.
- Use normal prose in code, commits, and pull requests.

Report each result and what it proves. Give each sentence one new fact, number, file, or next step.

Describe only completed actions and their outcomes. Mention omitted checks or alternatives only when the user must act.

Give full details for failures and blockers. Include the exact error, attempted actions, and required input.

Keep code comments brief. State only hardware quirks, order constraints, and non-obvious constants that the code cannot show.

Remove file-header essays, section banners, and comments that restate code. Keep a rationale only when the next reader needs the constraint.

## Documentation style

Use ASD-STE100 Simplified Technical English for every prose file. This rule includes vendor and supplier messages.

Before a large rewrite, load the `/simple-english:simple-english` skill for its complete 53-rule catalog.

Caveman style controls chat. STE controls files. If the styles conflict in a file, STE has priority.

Use articles and complete grammar in files. Do not use telegraph style in files.

Apply these primary rules:

- Limit a procedural sentence to 20 words. Limit a descriptive sentence to 25 words.
- Count code, identifiers, and quoted text as one word each.
- Use the imperative for instructions.
- Put the condition first. Example: "If the build fails, read the log."
- Use active voice and simple tenses.
- Do not use an `-ing` form as a verb.
- Use only `can`, `will`, and `must` as modal verbs.
- Use "must" for a requirement and "can" for a possibility.
- Do not use semicolons.
- Use "but" instead of "however".
- Use "so" or "as a result" instead of "therefore".
- Use "because" instead of "since".
- Use one term for one item throughout a document.
- Never change code, identifiers, paths, CLI flags, quoted errors, or quoted datasheet text.
- Quote datasheet text exactly, even when it does not comply with these rules.

Use `docs/mic-v2-debugging.md` as the repository reference. It complies with these rules and the 25-word limit.

## Repository layout

This repository contains a KiCad hardware project and the ESPHome firmware for the same board.

The hardware source files are in `c6remote-kicad/`:

- `c6remote.kicad_sch` is the single-sheet schematic.
- `c6remote.kicad_pcb` is the board layout.
- `c6remote.kicad_pro` contains ERC settings, DRC settings, BOM settings, and project metadata.
- `ano rotary.kicad_sym` contains only the custom `ENC1` symbol.
- `Local.kicad_sym` contains `SW_TL3315NF160Q` and `TSOP61xx`.
- `../kicad lib/Library.pretty/` contains the custom board footprints.
- `3dmodels/` contains models that use `${KIPRJMOD}`.
- `export/` contains generated Gerber and drill files.

The firmware files are in the repository root:

- `c6remote.yaml` is the production ESPHome config. The `c6remote-test-*.yaml` files are bench configs.
- `ir_learning.h` holds the `IrCodeStore` and `IrUi` singletons for IR capture, playback, and receiver mode.
- `components/button_config/` is a local ESPHome component. It serves the `/buttons` assignment page from `web_server`.
- `RECEIVER.md` documents receiver mode, the assignment slots, and the web configurator.
- `scripts/tests/` holds `unittest` regression checks. Run `python3 -m unittest discover -s scripts/tests -t .` from the repository root.
- `scripts/tests/page_dom_stub.js` runs the `/buttons` page script against a DOM stub. `test_page_js.py` drives it and needs `node`. Without `node` the check skips, so run it locally before you change the page.

Read `ROADMAP.md` when the task needs the remaining open work. `docs/timeline.md` records board status, fabrication history, and closed findings.

## Validation and fabrication commands

Run these commands from `c6remote-kicad/`:

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

ERC and DRC are the only scoped checks. This repository has no finer-grained test harness.

### Zone refill before a commit

`--refill-zones` refills zones in memory. It does not write the refill to `c6remote.kicad_pcb`.

If a board edit can affect pours, do not commit until Landon refills and saves the zones in KiCad.

Use Edit → Fill All Zones. Stage the board file only after Landon confirms the refill.

This rule covers footprint moves, footprint changes, new tracks, new vias, and net changes.

`scripts/check-design.py` runs both checks from the repository root. It fails on violations outside the documented six-warning baseline below. `.github/workflows/design-checks.yml` runs it on every push and pull request in the `kicad/kicad:10.0` container. Run it locally the same way as CI:

```bash
python3 scripts/check-design.py            # both checks
python3 scripts/check-design.py --only erc # or --only drc
```

It finds `kicad-cli` on `PATH`, falls back to the app bundle path above, and takes `KICAD_CLI` as an override. When the baseline legitimately moves, edit `ALLOWED_DRC` in that script and the counts below in the same commit.

### Scripts

`scripts/regen-fab.sh` exports Gerbers, drill files, `c6remote-pos.csv`, and `c6remote-bom.csv`.

The position file uses CSV, millimeters, and both sides.

The BOM groups by Value+Footprint. It joins references with `, ` and includes these columns:

`Reference, Qty, Value, Footprint, Datasheet, Description, Manufacturer, MPN, Digikey, Mouser, Adafruit, LCSC`

Set `KICAD_CLI=/path/to/kicad-cli` to override the binary.

Store a product URL in `LCSC`, not a bare C-number. Only `Q2` and `D2`-`D5` have LCSC values.

`Q2` uses `C15127`. `D2`-`D5` use `C5349955`.

Regenerate the BOM with `scripts/export-bom.sh` or `scripts/regen-fab.sh`. Do not use the MCP `export_bom` tool.

The MCP tool changes the schema, removes sourcing columns, lists test points, and overwrites the curated CSV.

Edit datasheet and sourcing fields on the schematic symbols. Then rerun the script.

### Pre-commit hook

The hook is at `scripts/hooks/pre-commit`. Run `git config core.hooksPath scripts/hooks` once for each clone.

Use `git commit --no-verify` to bypass the hook for one commit.

When you stage the schematic or board, the hook performs these actions:

- It runs `regen-fab.sh` and stages `export/`.
- It runs `scripts/render-readme-assets.sh` and stages `docs/readme-assets/`.
- A staged PCB uses `--only board`. A staged schematic uses `--only schematic`. Both files use `--only all`.
- A staged PCB runs `scripts/gen-ibom.sh` for `c6remote-kicad/ibom.html`.

The iBOM is a gitignored pre-fabrication pin-1 artifact. Never stage it.

The iBOM step is nonfatal because it needs KiCad Python and a first-run network clone.

`WARNING: gen-ibom.sh failed` means that `ibom.html` is stale. It does not mean that the commit failed.

Gerber and drill headers contain timestamps. A board commit restages all files in `export/`, even without geometry changes.

### Validation baseline from 2026-08-31

- `sch erc` reports 0 violations.
- `pcb drc` reports 0 errors, 0 unconnected items, and 1 allowed warning.
- The `lib_footprint_mismatch` warning is for `U1`.
- `U1` is the only footprint that differs from its library footprint.
- Parity reports 0 issues.
- The board has no `TP_*` test points or board-only items.

Treat these counts as the baseline unless the task targets them. A second warning is a new regression.

Two choices keep the silkscreen text checks quiet. `min_text_height` is 0.8mm, because the XIAO pin labels need it.

The two brand texts use the `Iosevka Bold` face. For a TrueType font, KiCad measures the glyph outlines and ignores the `thickness` property.

Do not select the `Iosevka` family with the bold attribute. Only the `Iosevka Bold` family passes the `text_thickness` check.

Run DRC with `--refill-zones` for baseline checks. A stale fill can report false `isolated_copper` and zone `unconnected_items`.

Together, these errors indicate unreachable pour islands. JSON reports the zone anchor, so violations can appear at the top-left corner.

Use the KiCad DRC panel or ratsnest airwire to locate an island.

The project ignores `silk_over_copper` and `silk_edge_clearance`. Do not enable these rules to restore the baseline.

The artwork still has 24 `silk_over_copper` and 4 `silk_edge_clearance` cases.

Five `silk_over_copper` cases are intentional ENC1 wheel-outline crossings.

## Branches and releases

Do all work on `develop`. Keep `main` for released snapshots only.

Do not commit to `main` or push it as a shortcut. A push to `main` creates a release.

Before the first commit, run `git branch --show-current`. This check prevents work on a retained `main` checkout.

GitHub uses `main` as the default branch. Visitors and relative documentation links use its released state.

`.github/workflows/release.yml` runs on each push to `main`.

The release workflow itself runs no KiCad; it only packages what is committed. `scripts/hooks/pre-commit` is what keeps `export/` in lockstep, and nothing in CI checks it, so a stale `export/` is a bad commit, not a workflow bug. ERC and DRC are checked in CI by `design-checks.yml`, which is the one thing `--no-verify` no longer gets past.

The workflow packages `c6remote-kicad/export/` and creates an ESPHome-style CalVer tag.

The tag format is `YYYY.M.PATCH`, with no zero padding for the month. The workflow scans monthly tags for the patch.

Examples are `2026.7.0` and `2026.7.1`.

The workflow publishes these assets:

- `c6remote-<version>-fab.zip` contains Gerbers, drill files, and the job file.
- `c6remote-<version>-bom.csv` contains the BOM.
- `c6remote-<version>-pos.csv` contains positions.

PCBWay requires the CSV files as separate uploads. The workflow first copies them to versioned names in `RUNNER_TEMP`.

Do not use `v0.1` release URLs. The `2026.6.0` tag replaced `v0.1`.

Do not use old `2026.7.0` asset URLs. The tag rename removed its unversioned BOM and position asset URLs.

The PCB front silkscreen revision must equal the release version. It currently reads `2026.9`.

Every copper or silkscreen change creates a different board. The patch value changes for artwork changes.

Before a merge to `main`, calculate the next tag. If the silkscreen differs, update it before the merge.

CI does not run KiCad. The committed output determines release quality.

Use `scripts/hooks/pre-commit` to keep `export/` synchronized. Treat stale output as a bad commit, not a workflow defect.

`c6remote-kicad/export.zip` is a gitignored local convenience file. Rebuild it with this command:

```bash
(cd c6remote-kicad/export && zip -X ../export.zip *.gbr *.gbrjob *.drl)
```

Do not add this command to the hook. The release workflow publishes the fabrication archive. Never track `export.zip`.

## High-level architecture

`U1` is a Seeed Studio XIAO ESP32-C6 module. The single sheet uses global labels for most connections.

Follow named nets across the schematic. Then verify the corresponding board nets and footprints.

- Audio uses `MK1`, an ICS-43434 or INMP441-style I2S microphone, on `sck`, `ws`, and `sd`.
- IR uses `U2`, a `TSOP6136TT` receiver, on `IR REC`.
- `U2` is a Vishay Panhead SMD part on B.Cu. It receives through the board bottom face.
- `D1`, `Q1`, and `R1` transmit IR from `IR EMIT`.
- `U3` is a `PCF8575DBR` expander on `sda` and `scl`.
- `U3` carries `sw1`-`sw11` and `ano_sw1`-`ano_sw5`. It uses all 16 I/O pins.
- `ENC1` is the custom Ano Rotary part. It uses `ano_enc1`, `ano_enc2`, and `ano_sw1`-`ano_sw5`.
- `D2`-`D5` form a cascade of XINGLIGHT `XL-2020RGBC-WS2812B` status LEDs.

The encoder directions map to these expander bits. Measured on unit 1 on 2026-07-27.

| direction | expander bit | port | net | ENC1 symbol |
| --- | --- | --- | --- | --- |
| up | 12 | P14 | `ano_sw2` | S4_UP |
| down | 14 | P16 | `ano_sw4` | S2_DOWN |
| left | 15 | P17 | `ano_sw5` | S5_LEFT |
| right | 11 | P13 | `ano_sw1` | S3_RIGHT |
| centre | 13 | P15 | `ano_sw3` | S1_CENTER |

### Pin budget

All 11 XIAO edge pads, D0-D10, are in use. `D10` or `GPIO18` carries `led_en`.

The board has no test points. It has no probe pads for signals.

The bottom pad row is routable. `GPIO4` carries `bat_sense`, and `GPIO5` carries `exp_int`.

`GPIO6`, pad 29, carries `ir_en`. `GPIO7`, pad 25, is the only free usable pad.

`GPIO7` is in the `GPIO0`-`GPIO7` low-power range. It is the last possible deep-sleep wake pin.

Use `GPIO7` only after deliberate review.

`IR REC` uses `GPIO16`, outside the low-power range. IR cannot wake this board from deep sleep.

`GPIO9`, pad 30, has no connection but serves as the BOOT strapping pin. Avoid it.

Before you use a pin, verify its pad in the `U1` board footprint.

`ano_enc1` and `ano_enc2` connect directly from `ENC1` to `U1`.

All rotary push switches and 11 discrete switches connect through `U3`.

### Power rails

Power uses `+3.3V`, switched `led_vdd`, and switched `ir_vdd`.

Do not rename or combine these rails. Do not reconnect a switched branch directly to `+3.3V`.

Each switched rail uses an `AO3401A` P-channel high-side MOSFET and a 1M gate pull-up.

The pull-up keeps the rail off by default. Drive the enable net low to enable the rail.

`Q2`, `R10`, and `led_en` control the LEDs. `Q3`, `R11`, and `ir_en` control the receiver.

The old `VCC` rail no longer exists. `U1` pad 14 has a no-connect flag and no board VBUS connection.

The board net is `unconnected-(U1-VBUS-Pad14)`. A 5 V feature needs a new net. Do not restore `VCC`.

### LED rail

`GPIO17` drives `D2` DIN on `led_1` without a series resistor.

`led_2`, `led_3`, and `led_4` connect each DOUT to the next DIN. `D5` DOUT is no-connect.

All four VDD pins use `led_vdd`. The four devices draw approximately 2.0 mA when dark.

`Q2` is an `AO3401A` at F.Cu `(42, 84.4375)`. Pad 2 is the `+3.3V` source.

Pad 3 is the `led_vdd` drain. Pad 1 is the `led_en` gate from `GPIO18`.

`R10` is a 1M 0603 resistor at B.Cu `(41, 89.575)`. It pulls `led_en` to `+3.3V`.

`GPIO18` starts as a floating input. `R10` holds the gate at the source and disables the rail.

`C4` is a 1uF 50V X7R 0805 capacitor at B.Cu `(46.75, 67.3)`. It is the local `led_vdd` reservoir.

The gated rail uses an approximately 90 mm trace tree and four vias instead of the former `+3.3V` plane taps.

The tree has 39.3 mm on F.Cu and 51.9 mm on B.Cu.

`C4` returns through a 5.2 mm B.Cu stub to through-hole GND at `ENC1` pad 6.

All LED VSS pads use solid `zone_connect 2` connections to the F.Cu GND pour.

**When `led_vdd` is off, firmware must hold `GPIO17` low or high-impedance.**

Otherwise, DIN can feed current through the LED input clamp into the disabled rail.

The LED uses WS2812B-compatible protocol: one wire, 800 kHz, GRB high-bit first, and reset greater than 100 us.

Keep ESPHome at `chipset: WS2812` and `rgb_order: GRB`.

The selected LED has a 3.5-5.5 V VDD range, 0.5*VDD VIH, and 5 mA per channel.

The former `WS2812B-2020` has 3.7-5.3 V VDD, 2.7 V VIH, and 12 mA per channel.

No stocked LCSC 2020 package has a 3.3 V datasheet rating.

The Dialight `587-1024-147F` has a 3.3-5.5 V rating but zero LCSC stock. See `docs/timeline.md`.

### IR rail

`Q3` is an `AO3401A` at F.Cu `(38.45, 140.3125)`. It switches `ir_vdd` from `+3.3V`.

`ir_vdd` feeds `R6` and `U2`. `R11` is a 1M 0603 resistor at F.Cu `(37.5, 144.0)`.

`R11` pulls `ir_en` to `+3.3V`, so the hardware rail is off by default.

`ir_en` comes from `U1` pad 29, `GPIO6`.

The downstream filter uses `R6` 100R and `C3` 100nF. It remains unchanged and supplies local decoupling.

As a result, `Q3` needs no reservoir.

Keep `Q3` and `R11` near `U1`. Do not move them next to `U2`.

This placement keeps the high-impedance 1M `ir_en` net short. The approximately 110 mm `ir_vdd` run loses 0.2 mV at 350 uA.

Firmware defaults the IR rail on, although the hardware pull-up defaults it off.

ESPHome uses an `IR Rail` switch on `GPIO6` with `inverted: true` and `restore_mode: ALWAYS_ON`.

`remote_receiver` cannot decode while `U2` has no power.

When the rail is off, the `GPIO16` pull-up backfeeds approximately 42 uA through the internal 33k OUT-to-Vs path.

Deep sleep releases the pull-up and can recover the full 350 uA.

`U2` is a four-pin `TSOP6136` with 0.35 mA typical `ISD`.

Its pins are 1 GND, 2 N.C., 3 Vs, and 4 OUT.

It uses `Library:Vishay_PANHEAD-4Pin_TopView` at B.Cu `(42.845,31.8575)`.

Pad 1 reaches the F.Cu GND pour through a via, not a through-hole barrel.

`TT` is the top-view lead form. `TR` is the side-view lead form. Both use the same four-pad land pattern.

The `TT` lens receives perpendicular to the board through the bottom face.

If the carrier frequency changes, keep the AGC digit at 1.

`TSOP6136` uses permissive AGC1. Both firmware variants use `remote_receiver` with `dump: all`.

Before an AGC change, verify code acceptance with `vishay.com/en/landingpage/agcmaptool/`.

## KiCad workflow

- Start agent schematic and custom-footprint work with `scripts/hw.py preflight <session>`.
- After each edit, run `scripts/hw.py quick <session>`.
- End the edit loop with `scripts/hw.py verify <session>`.
- Reuse one session for one edit loop. Then remove it with `scripts/hw.py clean <session>`.
- Do not use this fast loop for PCB edits. `verify` requires the original PCB hash.
- Use native KiCad ERC for schematic validity. Use analyzer output for semantic regression checks.
- Use KiCad MCP tools first for inspection, validation, and edits. Discover deferred tools before fallback.
- Use `kicad-cli` or manual patches only when MCP lacks the operation or fails.
- Use MCP schematic tools for parity changes. Raw patches can misalign labels and wire endpoints.
- After an MCP connect or edit, run ERC and DRC immediately. Some operations change PCB metadata and parity state.

MCP edits can rewrite large sections or collapse a file to one line.

If a turn stops during an edit, reread the file before another patch.

Before a commit, run `kicad-cli sch upgrade <file> --force` to restore canonical schematic formatting.

KiCad can rewrite all of `c6remote.kicad_pro` from the copy loaded at project open.

No KiCad setting prevents this known behavior. Do not investigate it again.

The pre-commit hook runs `scripts/check-kicad-pro-drift.py`.

It blocks staged changes to `board.design_settings.rules`, either `rule_severities` block, or the netclass list.

For an intentional change, use `--no-verify`. Treat the committed values as correct.

The unguarded `defaults.pads` value is cosmetic GUI state. Keep its current value.

`rotate_schematic_component` moves attached wire endpoints.

After a delete, add, and rotate replacement, compare each pin with `get_schematic_pin_locations`. Then run ERC.

A rotated stub can connect a power rail to a signal pin.

### Autorouting

Use KiCadRoutingTools at `~/dev/KiCadRoutingTools`. Do not use the MCP Freerouting autorouter.

Freerouting needs Java 25. This machine has only Java 17 and 23.

Run this command:

```bash
~/dev/KiCadRoutingTools/.venv/bin/python ~/dev/KiCadRoutingTools/route.py <board.kicad_pcb>
```

The command writes `<board>_routed.kicad_pcb` and does not change the input board.

If you use `--overwrite`, the command replaces the input board.

Use `--nets "<glob>"` to limit nets. Use `route_diff.py` for differential pairs and `route_planes.py` for planes.

The virtual environment contains numpy, scipy, shapely, and `grid_router.so` from `build_router.py`.

If the schematic changed, update the board from the schematic before routing.

### Schematic-to-board synchronization

**Never run the MCP `sync_schematic_to_board` on this board.**

Ask Landon to run Tools -> Update PCB from Schematic (F8) in pcbnew.

The MCP tool once corrupted 16 existing pad assignments after it added `Q3` and `R11`.

The corruption affected `MK1`, `U1`, `U3`, `C3`, `C4`, `D2`, `R6`, and `U2`.

It also restored `VCC`, broke `led_vdd`, swapped switch nets, and assigned pads to virtual `PWR_FLAG`.

After any synchronization, compare every board pad net with the schematic netlist.

### Footprint verification

Before you adopt a footprint, verify its pad numbers against the part datasheet.

KiCad symbols and footprints in the same family can use incompatible numbering.

`LED_SK6812_EC15_1.5x1.5mm` uses 1 DIN, 2 VDD, 3 DOUT, and 4 GND.

Stock SK68xx symbols use 1 DOUT, 2 VSS, 3 DIN, and 4 VDD.

This mismatch rotates all four functions. The ENC1 pad 6 and 8 fault had the same failure class.

Datasheet revisions can also disagree.

The xonstorage `XL-2020RGBC-WS2812B` table lists 1 VDD, 2 DOUT, 3 GND, and 4 DIN.

Its diagram contradicts that table. The newer DigiKey revision lists 1 DO, 2 GND, 3 DI, and 4 VDD.

The DigiKey table matches both diagrams and the cloned `WS2812B-2020`.

Prefer the distributor-hosted revision. Compare each pin table with its diagram.

## Key repository conventions

- Never add `Co-Authored-By:` trailers to commit messages.
- Use only the Git user as the author in commits and documentation.
- The `scripts/hooks/commit-msg` and `scripts/hooks/pre-commit` hooks reject trailer lines and known AI bot email addresses.
- Use a period, colon, comma, or parentheses for a break. Do not use an em dash anywhere.
- Treat Opus and Terra as interchangeable names for exploration, search, research, and implementation subagents.
- Treat Sonnet and Luna as interchangeable names for summarization, classification, drafting, extraction, templating, formatting, and simple lookups.
- Keep the main thread for planning, dispatch, and synthesis.
- Make only trivial one-line edits on the main thread.
- Search global labels for cross-cutting changes. Important labels include `sw*`, `ano_*`, `IR EMIT`, and `IR REC`.
- Other important labels include `led_1`, `sda`, `scl`, `sck`, `ws`, and `sd`.
- Edit only live files: `c6remote.kicad_sch`, `c6remote.kicad_pcb`, and `c6remote.kicad_pro`.
- Do not edit `*.bak`, `*-bak`, or `c6remote-backups/` files.
- Regenerate `export/`. Never edit Gerber or drill files manually.

The repository tracks both configured library tables. Do not map libraries manually.

`sym-lib-table` defines symbols. `fp-lib-table` defines `Library`, `Local`, and `Seeed_Studio_XIAO_Series`.

`Library` points to `../kicad lib/Library.pretty`. The other names point to adjacent `.pretty` directories.

These custom footprints are part of the design:

- `XIAO-ESP32C6-DIP.kicad_mod`
- `SW_TL3315NF160Q.kicad_mod`
- `Ano Rotary.kicad_mod`
- `LED_XL-2020RGBC-WS2812B_PLCC4_2.0x2.0mm.kicad_mod`
- `Vishay_PANHEAD-4Pin_SideView.kicad_mod`
- `Vishay_PANHEAD-4Pin_TopView.kicad_mod`

After a footprint edit, verify the schematic symbol properties and all PCB footprint instances.

The models are in `c6remote-kicad/3dmodels/`. Record each new model citation in `c6remote-kicad/3dmodels/README.md`.

That file also records model sources and orientation constraints.

`ano rotary.kicad_sym` defines `ENC1`. Its pin electrical types are not clean ERC models.

If you change that symbol, expect a possible ERC baseline change.

Stored plot settings use a Windows path. Always give an explicit output directory, such as `-o export`.

`kicad-cli` writes `c6remote-erc.rpt` and `c6remote-drc.rpt` in `c6remote-kicad/`.

Treat these reports as scratch output unless the task requires them.

Before a commit, check tracked and untracked files.

Common untracked artifacts include `c6remote-kicad/.history/`, `c6remote-kicad/DRC.rpt`, and `c6remote-kicad/renders/`.

Other common artifacts are `.cursor/`, `.windsurf/`, `.opencode/`, and `.clinerules/`.

Codex Git writes can fail with `.git/index.lock` because the sandbox blocks `.git` writes.

If no lock file exists, rerun the Git write with escalation. Do not diagnose repository corruption.

`.mcp.json` contains the Codex KiCad MCP definition. `.vscode/mcp.json` contains the VS Code mirror.

Use KiCad Python from the `.app` bundle. Do not use Homebrew Python or system Python.

The valid MCP checkout is `/Users/landonrohatensky/dev/KiCAD-MCP-Server`.

If MCP fails, run `bash setup-macos.sh --verify` there before you change paths.

Claude Desktop documentation uses the `mcpServers` shape.

Codex uses `.mcp.json` with `mcpServers`. VS Code uses `.vscode/mcp.json` with `servers`.

Do not make these configurations identical unless the task intentionally changes that client.
