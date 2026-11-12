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
- `3dmodels/` is a gitignored link to the KiCad 3D models in the private `c6remote-explode` repository. See "Key repository conventions".
- `export/` contains generated Gerber and drill files.

The firmware files are in the repository root:

- `c6remote.yaml` is the production ESPHome config. The `c6remote-test-*.yaml` files are bench configs.
- `ir_learning.h` holds the `IrCodeStore` and `IrUi` singletons for IR capture, playback, and receiver mode.
- `components/button_config/` is a local ESPHome component. It serves the web page at the root URL `/` from `web_server_base`. The production config has no `web_server` entity page, so the component reserves lwIP sockets for page connections.
- `components/ha_action/` is a local ESPHome component. It stores one Home Assistant action for each slot and sends it over the native API. See `RECEIVER.md`.
  The Home Assistant switch turns the actions off at once. If the switch is off at boot, `on_boot` holds the API server down until the next boot.
- `components/idle_sleep/` is a local ESPHome component for idle and hold deep sleep. It uses a `GPIO5` ext1 wake and a wake stub that latches the waking button.
- `zigbee_learning.h` holds the `ZigbeeAssignmentManager` singleton for target storage, address resolve, and command send.
- `RECEIVER.md` documents receiver mode, the assignment slots, and the web configurator.
- `ZIGBEE.md` documents Zigbee pairing, the target kinds, and the send path. Read it before you change Zigbee behavior.
- `scripts/tests/` holds `unittest` regression checks. Run `python3 -m unittest discover -s scripts/tests -t .` from the repository root.
- `scripts/tests/page_dom_stub.js` runs the web page script against a DOM stub. `test_page_js.py` drives it and needs `node`. Without `node` the check skips, so run it locally before you change the page.
- `scripts/preview-buttons-page.py` serves the web page with a fake remote behind it. It needs no build and no hardware.

Run `python3 scripts/preview-buttons-page.py [--port 8123]`. Then open `http://127.0.0.1:8123/`.

The script reads the page out of the header for each request, so the preview cannot drift from the source.

The fake state can drift. If you change the page or `ButtonConfig::handle_state_()`, update the state in the script in the same change.

A missing field makes the preview show a state that the firmware never serves.

If the task needs the remaining open work, read the open GitHub issues. `docs/timeline.md` records board status, fabrication history, and closed findings.

### Website

The project website is in `site/`. It contains `index.html`, `s3.html`, `original.html`, and the shared `style.css`.

`site/assets/legacy/` holds the images from the old Cargo site. No other copy of these images exists.

`site/esphome-component-from-scratch.html` and `site/first-year.html` hold the two blog posts from the old Cargo site.

The images that only these posts use are in `site/assets/legacy/`, and their file names start with `esphome-` or `first-year-`.

Every link and asset path in `site/` must be relative, because GitHub Pages serves the site from a sub-path.

`scripts/build-site.sh` assembles the site into `_site/`, or into the directory that you give as the argument.

The script copies the product images from `docs/readme-assets/`. Do not add copies of these images to `site/`.

If a page uses a new image from `docs/readme-assets/`, add the file name to the list in `scripts/build-site.sh`.

To preview the site, run this command from the repository root. Then open `http://127.0.0.1:8130/`.

```bash
scripts/build-site.sh && python3 -m http.server 8130 -d _site
```

`.github/workflows/pages.yml` deploys the site to GitHub Pages on each push to `develop` that changes the site inputs.

The site does not deploy from `main`, because a push to `main` also creates a board release.

The `github-pages` environment accepts deploys from `develop` and `main`. If you remove `develop` from it, the deploy job fails.

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

If a board edit can affect pours, write a refilled board before the commit. This rule covers footprint moves, footprint changes, new tracks, new vias, and net changes.

Run `python3 scripts/refill-zones.py` from the repository root. To fill and check without a change to the board file, add `--dry-run`.

The script fills a copy of the board in a temporary directory, then copies only the board file back. If content outside the `filled_polygon` blocks changes, the script does not write the board.

The comparison ignores three changes that a KiCad save makes. It ignores the order of the top-level items and the format of a number. It also ignores a number change that is not more than `NOISE_MM` in the script.

KiCad makes these changes after a script or a manual patch writes the board. When the script writes the board, the board gets the KiCad format.

The comparison finds each top-level item by its `uuid` and compares its content in order. As a result, a moved track end, a new item, or a changed net stops the write.

The script shows the fill outlines of each zone and fails if DRC with and without `--refill-zones` gives different results. If KiCad is open, the script does not start.

Do not use the MCP `refill_zones` tool. It first saves the board that the MCP server holds in memory, and that copy can be older than the file. Its fill subprocess also does not protect the project files.

`scripts/check-design.py` runs both checks from the repository root. It fails on violations outside the documented baseline below. `.github/workflows/design-checks.yml` runs it on every push and pull request in the `kicad/kicad:10.0` container. Run it locally the same way as CI:

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

Store a product URL in `LCSC`, not a bare C-number. Only `Q2`, `Q3`, `D2`-`D7`, `J1`, and `J2` have LCSC values.

`Q2` and `Q3` use `C15127`. `D2`-`D7` use `C5349955`. `J1` uses `C177225`. `J2` uses `C160404`.

Regenerate the BOM with `scripts/export-bom.sh` or `scripts/regen-fab.sh`. Do not use the MCP `export_bom` tool.

The MCP tool changes the schema, removes sourcing columns, lists test points, and overwrites the curated CSV.

Edit datasheet and sourcing fields on the schematic symbols. Then rerun the script.

### Pre-commit hook

The hook is at `scripts/hooks/pre-commit`. Run `git config core.hooksPath scripts/hooks` once for each clone.

Use `git commit --no-verify` to bypass the hook for one commit.

When you stage the schematic or board, the hook performs these actions:

- It runs `regen-fab.sh` and stages `export/`.
- It runs `scripts/render-readme-assets.sh` and stages `docs/readme-assets/`. The board PNGs render with Blender from `scripts/render-board-blender.py`.
- A staged PCB uses `--only board`. A staged schematic uses `--only schematic`. Both files use `--only all`.
- The board renders need the linked 3D models. If a model is missing, a commit with a staged PCB fails.
- A staged PCB runs `scripts/render-annotated-remote.py --only board`. This step updates the four annotated board SVGs from the new board PNGs.
- A staged PCB runs `scripts/gen-ibom.sh` for `c6remote-kicad/ibom.html`.
- After the hook regenerates a render group, it runs `scripts/render-status.py --write <group> --stage`. That step stages only the entry of that group in `docs/readme-assets/renders.stamp.json`.
- Last, the hook runs `scripts/render-status.py --check --if-staged`. This check also runs without a staged schematic or board. It shows a warning for each stale group that a staged file feeds. It never blocks the commit.
- `scripts/renders.json` lists every render group with its outputs, inputs, and refresh steps. If you add an image or a video under `docs/readme-assets/` or `site/assets/`, add it to a group.

The iBOM is a gitignored pre-fabrication pin-1 artifact. Never stage it.

The iBOM step is nonfatal because it needs KiCad Python and a first-run network clone.

`WARNING: gen-ibom.sh failed` means that `ibom.html` is stale. It does not mean that the commit failed.

Gerber and drill headers contain timestamps. A board commit restages all files in `export/`, even without geometry changes.

### Validation baseline from 2026-11-12

- `sch erc` reports 0 violations.
- `pcb drc` reports 0 errors, 0 unconnected items, and 0 warnings.
- Each footprint on the board is equal to its library footprint, so DRC reports no `lib_footprint_mismatch` warning.
- `U1` uses `Library:XIAO-ESP32C6-SMD`, which this project drew. Pads 24-31 are plated holes, and pads 32 and 33 are SMD pads.
- `U1` pads 24-31 also have F.Mask, so their copper is open on the front.
- Parity reports 0 issues.
- `TP1`-`TP6` are bare debug pads. The BOM and the position file exclude them. The board has no board-only items.

Treat these counts as the baseline unless the task targets them. A DRC warning is a new regression.

Two choices keep the silkscreen text checks quiet. `min_text_height` is 0.8mm, because the XIAO pin labels need it.

The two brand texts use the `DejaVu Sans Bold` face. For a TrueType font, KiCad measures the glyph outlines and ignores the `thickness` property.

Keep the `DejaVu Sans Bold` face on both brand texts. Do not replace it with a family-level bold attribute.

Run DRC with `--refill-zones` for baseline checks. A stale fill can report false `isolated_copper` and zone `unconnected_items`.

Together, these errors indicate unreachable pour islands. JSON reports the zone anchor, so violations can appear at the top-left corner.

Use the KiCad DRC panel or ratsnest airwire to locate an island.

The project ignores `silk_over_copper` and `silk_edge_clearance`. Do not enable these rules to restore the baseline.

The artwork still has 24 `silk_over_copper` and 4 `silk_edge_clearance` cases.

Five `silk_over_copper` cases are intentional ENC1 wheel-outline crossings.

## Branches and releases

Do all work on a non-`main` branch. Keep `main` for released snapshots only.

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

The PCB front silkscreen revision must equal the release version. It currently reads `2026.10`.

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

`U1` is on B.Cu at `(52.85, 137.12)` with orientation 0, against the +x long edge. The position file lists `U1` on the `bottom` side.

The `U1` USB-C connector extends past the +y short edge. Some B.Cu tracks run under the module body.

The `U1 antenna keepout` rule area prohibits tracks, vias, and copper pour on F.Cu and B.Cu at x 62.35-67.55, y 137.1-139.5.

Follow named nets across the schematic. Then verify the corresponding board nets and footprints.

- Audio uses `MK1`, a PUI Audio `DMM-4026-B-I2S-R` I2S microphone, on `sck`, `ws`, and `sd`.
- `MK1` pins are 1 LR, 2 CONFIG, 3 VDD, 4 GND, 5 WS, 6 SCK, and 7 SD. Pins 1, 2, and 4 go to GND.
- Pin 1 low selects the left channel, so ESPHome must keep `channel: left`.
- `C5` is the 100nF VDD decoupling capacitor. `R12` is the 100k pull-down that the datasheet requires on `sd`.
- The part needs a 2.048 to 4.096 MHz bit clock in normal mode. GitHub issue #12 tracks the sample-rate change.
- IR uses `U2`, a `TSOP6136TT` receiver, on `IR REC`.
- `U2` is a Vishay Panhead SMD part on B.Cu. It receives through the board bottom face.
- `D1`, `Q1`, and `R1` transmit IR from `IR EMIT`.
- `U3` is a `PCF8575DBR` expander on `sda` and `scl`.
- `U3` carries `sw1`-`sw11` and `ano_sw1`-`ano_sw5`. It uses all 16 I/O pins.
- `U3` has A0-A2 on GND, so its I2C address is `0x20`. `R4` and `R5` are the 4.7k bus pull-ups to `+3.3V`.
- `J2` is a JST `SM04B-SRSS-TB(LF)(SN)` Qwiic connector. Its pins use Qwiic order: 1 GND, 2 `+3.3V`, 3 `sda`, and 4 `scl`.
- `J2` uses the `Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal` footprint. Its two MP mounting pads have no connection.
- `J2` is on B.Cu at `(38.125, 135.25)`, rotation 90, on the -x long edge. The connector mouth faces the board edge.
- `J2` pin 1 is at y 136.75, and pin 4 is at y 133.75.
- `J2` takes power from `+3.3V`, not from `led_vdd` or `ir_vdd`. A Qwiic device must not use address `0x20`.
- The assembler fits `J2`. The BOM lists `J2`, and the position file lists it on the `bottom` side.
- B.SilkS shows "Qwiic" and a "GND" pin-1 marker for `J2`.
- `J1` is the battery connector, a Molex PicoBlade 1.25 mm `53261-0271`. Pin 1 is `BAT` (+), and pin 2 is `GND`.
- `J1` uses the `Connector_Molex:Molex_PicoBlade_53261-0271_1x02-1MP_P1.25mm_Horizontal` footprint and its stock 3D model. Its MP pads have no connection.
- `J1` is on B.Cu at `(38.55, 149.625)`, rotation -90. The connector mouth faces +x, toward `U1`. The 0.5 mm copper-to-edge rule on pads 1 and 2 sets this x.
- The `J1` mating parts are the `51021-0200` plug housing and `50079-8000` crimp terminals.
- B.SilkS shows "+" and "-" beside the `J1` pins and a "Battery" label.
- `J1` pad 1 agrees with circuit 1 on sheet 2 of the Molex drawing `532610001-SD`. The verification date is 2026-11-02.
- `ENC1` is the custom Ano Rotary part. It uses `ano_enc1`, `ano_enc2`, and `ano_sw1`-`ano_sw5`.
- `D2`-`D7` form a cascade of six XINGLIGHT `XL-2020RGBC-WS2812B` status LEDs round the `ENC1` wheel.

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

`TP1`-`TP6` and `U1` pads 24-31 give probe access on the front. The front shell covers them, so remove the shell before you probe.

`TP1` to `TP6` connect to `ws`, `sck`, `sd`, `IR EMIT`, `IR REC`, and `led_1`, in that order.

`U1` pads 24, 25, 27, 28, 29, and 31 carry `exp_int`, `usb_present_n`, GND, `bat_sense`, `ir_en`, and `+3.3V`. Pads 26 (`CHIP_EN`) and 30 (`GPIO9`) have no board connection.

The `J2` Qwiic connector gives access to `sda` and `scl`.

The module underside pads, 24-33, face the board back. Pads 24-31 are plated holes, so tracks on F.Cu and B.Cu can reach them.

`GPIO4` carries `bat_sense`, and `GPIO5` carries `exp_int`.

`U1` pads 32 (BAT) and 33 (GND) are SMD pads on B.Cu, and the assembler reflows them. A via next to each pad connects it to F.Cu.

`GPIO6`, pad 29, carries `ir_en`. `GPIO7`, pad 25, carries the active-low `usb_present_n` signal.

`GPIO7` is in the `GPIO0`-`GPIO7` low-power range, but it is not free for another function.

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

The F.Cu pour is GND, and the B.Cu pour is `+3.3V`. A GND pad on B.Cu needs a via to the F.Cu GND pour.

`Q2`, `R10`, and `led_en` control the LEDs. `Q3`, `R11`, and `ir_en` control the receiver.

The old `VCC` rail no longer exists. `U1` pad 14 connects USB VBUS to the `usb_vbus` detection net.

`R13` (100k) feeds `usb_vbus` to the base of `Q4` (`MMBT2222A`). `R15` (1M) pulls the base to GND.

`R14` (100k) pulls the `Q4` collector to `+3.3V`. USB VBUS turns `Q4` on and pulls `usb_present_n` low.

Without USB VBUS, `Q4` is off and `usb_present_n` is high. Do not restore `VCC`.

`Q4`, `R13`, and `R14` are on F.Cu at `(44, 150.5)`, `(43, 146.5)`, and `(46, 153.75)`.

`R15` is at F.Cu `(41, 150)`. Its GND pad uses a solid pour connection because the nearby tracks restrict thermal spokes.

### LED rail

`GPIO17` drives `D2` DIN on `led_1` without a series resistor.

The chain order is `D2`, `D3`, `D6`, `D4`, `D5`, and `D7`. From the front, this order goes clockwise round the wheel from the bottom left.

`led_2` to `led_6` connect each DOUT to the next DIN in that order. `D7` DOUT is no-connect.

`led_3` connects `D3` to `D6`, and `led_4` connects `D6` to `D4`. `D6` is at the top centre, and `D7` is at the bottom centre.

All six VDD pins use `led_vdd`. The six devices draw approximately 3.0 mA when dark.

`Q2` is an `AO3401A` at F.Cu `(42, 84.4375)`. Pad 2 is the `+3.3V` source.

Pad 3 is the `led_vdd` drain. Pad 1 is the `led_en` gate from `GPIO18`.

`R10` is a 1M 0603 resistor at B.Cu `(41, 89.575)`. It pulls `led_en` to `+3.3V`.

`GPIO18` starts as a floating input. `R10` holds the gate at the source and disables the rail.

`C4` is a 1uF 50V X7R 0805 capacitor at B.Cu `(46.75, 67.3)`. It is the local `led_vdd` reservoir.

The gated rail uses an approximately 121 mm trace tree and six vias instead of the former `+3.3V` plane taps.

The tree has 62.3 mm on F.Cu and 58.6 mm on B.Cu.

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

`Q3` is an `AO3401A` at F.Cu `(62.6745, 145.9)`, rotation 180. It switches `ir_vdd` from `+3.3V`.

`ir_vdd` feeds `R6` and `U2`. `R11` is a 1M 0603 resistor at F.Cu `(64.75, 150.2631)`, rotation 90.

`R11` pulls `ir_en` to `+3.3V`, so the hardware rail is off by default.

`ir_en` comes from `U1` pad 29, `GPIO6`.

The downstream filter uses `R6` 100R and `C3` 100nF. It remains unchanged and supplies local decoupling.

As a result, `Q3` needs no reservoir.

Keep `Q3` and `R11` near `U1`. Do not move them next to `U2`. Both parts are beside `U1` pad 29.

This placement keeps the high-impedance 1M `ir_en` net short, at approximately 5.5 mm. The approximately 147 mm `ir_vdd` run loses approximately 0.13 mV at 350 uA.

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

`TSOP6136` uses permissive AGC1. Both firmware variants use `remote_receiver`, and production learns raw frames through `on_raw`.

Production has no `dump` option, because the protocol dumpers use too much flash. `c6remote-test-common.yaml` keeps `dump: all`.

Before an AGC change, verify code acceptance with `vishay.com/en/landingpage/agcmaptool/`.

## KiCad workflow

- Start agent schematic and custom-footprint work with `scripts/hw.py preflight <session>`.
- Before an edit, inspect exact items with `scripts/hw.py inspect <session> component|net|pin`.
- After each edit, run `scripts/hw.py quick <session>`.
- Inspect all baseline changes with `scripts/hw.py inspect <session> changes`.
- End the edit loop with `scripts/hw.py verify <session>`.
- Reuse one session for one edit loop. Then remove it with `scripts/hw.py clean <session>`.
- Keep the session baseline fixed for the complete edit loop.
- Use `--json` for structured inspection output.
- Use `--force` only when you must bypass validated cache reuse.
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

KiCadRoutingTools at `~/dev/KiCadRoutingTools` is the default router for this board.

Freerouting cuts the F.Cu GND pour because the KiCad Specctra export writes each zone as its outline. Freerouting does not refill a plane, so it cannot see the split.

Run the command from `~/dev/KiCadRoutingTools`, and give absolute board paths. With the four environment variables, KiCadRoutingTools does not remove existing copper.

```bash
cd ~/dev/KiCadRoutingTools
KICAD_FINALIZE_RIP=0 KICAD_IMPROVEMENT_GATE=0 \
KICAD_PLANE_FINALIZE=0 KICAD_RIP_PREEXISTING=0 \
.venv/bin/python py_router/route.py <in.kicad_pcb> <out.kicad_pcb> \
  --nets <net> ... \
  --track-width 0.2 --via-size 0.6 --via-drill 0.3 \
  --grid-step 0.25 --clearance 0.4 \
  --no-fix-drc-settings --keep-input-copper --escalation off \
  --same-net-pad-clearance 0.05 --direction-preference-cost 0 \
  --via-proximity-cost 0 --ordering inside_out
```

The flags match the hand-routed style of this board: 0.2 mm tracks, 0.6/0.3 mm vias, and 45 degree corners on the 0.25 mm grid.

`--clearance 0.4` sets only the routing clearance, and DRC keeps the project rule. This clearance gives gaps close to the gaps on the hand-routed board.

If you do not give an output file, the command writes `<in>_routed.kicad_pcb`. `--overwrite` (`-O`) replaces the input board.

Some nets must cross the F.Cu GND pour near the ENC1 ring. Route these nets in a second run, after all other nets.

Add `--layer-costs 4 1` to the second run. As a result, B.Cu costs less than F.Cu. KiCadRoutingTools puts the crossing on B.Cu and does not cut the GND pour.

For example, the first D6/D7 run routed `led_3` and `led_4`. The second run routed `led_6` and `led_vdd` with `--layer-costs 4 1`.

`--keep-input-copper` keeps the existing tracks. KiCadRoutingTools can extend a track from a cut end.

If you replace part of a hand-routed track, first cut the track into stubs at the new pads.

Extend existing tracks where possible. A full redraw of the LED chain doubled the vias and isolated an LED VSS pad from the F.Cu GND pour.

After each run, run DRC with `--refill-zones`. The pour report from KiCadRoutingTools can miss a split in the GND pour.

Before you commit a routed board, follow the rule in "Zone refill before a commit".

`--nets` limits the run to the given nets and accepts glob patterns. Use `py_router/route_diff.py` for differential pairs and `py_router/route_planes.py` for planes.

If the schematic changed, update the board from the schematic before you route it.

The virtual environment contains numpy, scipy, and shapely. `build_router.py` writes the Rust module to `rust_router/grid_router.so`.

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
- Treat Opus and Terra as interchangeable names for exploration, search, and research subagents.
- Keep the main thread for planning, dispatch, and synthesis.
- Make only trivial one-line edits on the main thread.
- Search global labels for cross-cutting changes. Important labels include `sw*`, `ano_*`, `IR EMIT`, and `IR REC`.
- Other important labels include `led_1`, `sda`, `scl`, `sck`, `ws`, and `sd`.
- Edit only live files: `c6remote.kicad_sch`, `c6remote.kicad_pcb`, and `c6remote.kicad_pro`.
- Do not edit `*.bak`, `*-bak`, or `c6remote-backups/` files.
- Regenerate `export/`. Never edit Gerber or drill files manually.

The repository tracks both configured library tables. Do not map libraries manually.

`sym-lib-table` defines symbols. `fp-lib-table` defines `Library` and `Local`.

`Library` points to `../kicad lib/Library.pretty`. `Local` points to the adjacent `Local.pretty` directory.

These custom footprints are part of the design:

- `XIAO-ESP32C6-SMD.kicad_mod`
- `XIAO-ESP32C6-DIP.kicad_mod`
- `SW_TL3315NF160Q.kicad_mod`
- `Ano Rotary.kicad_mod`
- `LED_XL-2020RGBC-WS2812B_PLCC4_2.0x2.0mm.kicad_mod`
- `Vishay_PANHEAD-4Pin_SideView.kicad_mod`
- `Vishay_PANHEAD-4Pin_TopView.kicad_mod`

After a footprint edit, verify the schematic symbol properties and all PCB footprint instances.

The footprints and the board reference the custom 3D models as `${KIPRJMOD}/3dmodels/<file>`. Do not change these paths.

The models are in `3dmodels/` in the private `c6remote-explode` repository. Most are third-party files without a clear right to redistribute.

Do not add a model to this repository. `.gitignore` excludes `c6remote-kicad/3dmodels`.

Run `scripts/link-3dmodels.sh` once for each clone or worktree. It links `c6remote-kicad/3dmodels` to the models.

If the `c6remote-explode` checkout is not at `~/dev/c6remote-explode`, set `EXPLODE` to its path.

Without the link, the KiCad 3D view shows bare pads for the parts with custom models.

Fabrication outputs, ERC, DRC, CI, and the iBOM do not use the models.

`scripts/export-case-refs.sh` and the board renders in `scripts/render-readme-assets.sh` need the models.

Before an export, both scripts run `scripts/check-3dmodels.sh`. If a model that the board names is missing, the check stops the script and names the file.

Record each new model citation in `3dmodels/README.md` in `c6remote-explode`. That file also records model sources and orientation constraints.

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
