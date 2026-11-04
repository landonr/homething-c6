# Scripts

## Zone refill

Run `python3 scripts/refill-zones.py` from the repository root to fill the copper zones and save the fill into `c6remote-kicad/c6remote.kicad_pcb`.
The script fills a copy in a temporary directory with KiCad's Python, then copies only the board file back.
It does not start if KiCad is open. It does not write the board if content outside the `filled_polygon` blocks changes.
It then compares DRC with and without `--refill-zones`. Add `--dry-run` to write nothing, or `--no-drc` to skip DRC.
Set `KICAD_PYTHON` or `KICAD_CLI` to override a binary path.

## Draft preview in 3D

Run this command from the repository root to see the current case model in the exploded viewer:

```bash
../c6remote-explode/preview-case.sh
```

The script lives in the viewer checkout. It builds the STL files, copies them into the viewer, and opens it.
If the viewer already runs, the script says so. Reload the tab.

The default build is a draft. It skips the feature map and the summary.
As a result, Identify reports the boxes from the last complete build.
Use `../c6remote-explode/preview-case.sh --full` to write the feature map again.

Both of those builds read the working tree. They write the draft geometry set.
Use `../c6remote-explode/preview-case.sh --baseline` to rebuild the committed geometry that the viewer's diff view compares against.
That mode builds git HEAD in a temporary worktree. It does not touch the working tree.

Run `scripts/export-case-refs.sh` first after a board change.
The script reads the board exports, but it cannot detect a KiCad change.

Set `REPO` for a board checkout outside `~/dev/homething-c6`.
Set `PORT` for a server port other than 8731.

## Preview assets

Run these commands from the repository root to regenerate the case preview assets:

```bash
./scripts/render-readme-assets.sh
../c6remote-explode/scripts/render-case-assembled.sh --blender
../c6remote-explode/scripts/render-case-exploded.sh --blender
../c6remote-explode/scripts/render-case-explode-loop.sh
```

Every 3D render uses Blender's Cycles.
`render-readme-assets.sh` needs Blender. Set `BLENDER` to override the binary path.
It exports a board GLB from the PCB and renders the two `board-3d-rotated-*.png` views with `scripts/render-board-blender.py`. It writes them into `docs/readme-assets/`.
`scripts/board_extras.py` builds the PicoBlade battery plug, its leads, and the battery for the Blender scripts. The board GLB contains the stock `J1` model. The `c6remote-explode` repository also uses it.
`scripts/assets/env-studio.hdr` is the Poly Haven `studio_small_09` HDRI at 1k. Its license is CC0.
The three case scripts use the sibling `c6remote-explode` checkout. Set `C6REMOTE_EXPLODE` if that checkout is not at `../c6remote-explode`.
The case scripts need Node, `ffmpeg`, and `img2webp` (`brew install webp`) as well. They render the case geometry the viewer has, so run `../c6remote-explode/refresh-assets.sh` after a case or board change.
Add `--rig` to a case script to render on the Windows Rig over SSH.
The case scripts write dated files into `c6remote-explode`; copy them into `docs/readme-assets/` as `case-assembled.png`, `case-exploded.png`, and `case-explode-loop.webp`.
The annotated case images `case-annotated-front.png` and `case-annotated-back.png` come from `../c6remote-explode/scripts/render-blender.py`.
Use `--preset readme-annotated-front` or `--preset readme-annotated-back` for them.
If the checkout is a git worktree, run `REPO=<checkout> ../c6remote-explode/refresh-assets.sh`. Without `REPO`, the script copies from `~/dev/homething-c6`.

Run `python3 scripts/render-annotated-remote.py` to draw the labels and leader lines over the board and case images.
The script writes each annotated SVG in a light version and a `-dark` version.
Add `--only board` or `--only case` to draw one image set. The default is `--only all`.
The pre-commit hook uses `--only board`, because the case sets go through ImageMagick and can change without a design change.

`scripts/stamp-case-renders.py` tells you when the case renders are stale.
It calculates a hash from the git blob IDs of the case render sources. The `INPUTS` constant in the script lists these sources.
`docs/readme-assets/case-renders.stamp` records the hash of the sources for the current case renders.
Run `scripts/stamp-case-renders.py --check` to compare the index with the stamp. Add `--strict` to exit with status 1 when the renders are stale.
The pre-commit hook runs the check when you stage a case render source. The check only shows a warning.
After you copy new case renders into `docs/readme-assets/`, run `scripts/stamp-case-renders.py --write`.
Use `--rev <commit>` to record the sources of a commit instead of the index.

After a new `case-explode-loop.webp`, run `scripts/site-media.sh <IMG_7480_clicks.mp4>` to make the C6 page videos in `site/assets/c6/`.
The script also cuts the four feature clips from the living room demo video. It needs `ffmpeg` and ImageMagick.
It also crops the web page image for the "No flashing needed" card from `buttons-page-assign.png`.

Run `scripts/browser-frame.sh <in.png> <out.png> [address]` to draw a browser window around a web page screenshot.
The README uses `buttons-page-assign-framed.png` and `buttons-page-config-framed.png`, which this script makes from the two plain screenshots.
After a new web page screenshot, run the script again. The script needs ImageMagick.

Run `case/.venv/bin/python scripts/render-face-svg.py --version sls` and `--version fdm` to draw the two front faces for `case/README.md`.
The script reads the case model. It writes `case-front-face-sls.svg` and `case-front-face-fdm.svg` into `docs/readme-assets/`.
Without `--version`, it writes `case-front-face.svg` for the web page. Keep that file small, because the firmware embeds it.

Run `python3 scripts/render-case-fronts-blender.py` to render the two front shells in isometric view for `case/README.md`.
The script needs Blender, and it runs itself under Blender. Set `BLENDER` to override the binary path.
It reads `case/export/c6remote-case-front.stl` and `c6remote-case-front-fdm.stl`. It writes `case-front-iso-sls.png` and `case-front-iso-fdm.png` into `docs/readme-assets/`.
Both renders use one camera and one light set, so they show the same scale.
