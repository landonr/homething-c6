# Scripts

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
`scripts/board_extras.py` builds the J1 socket, the battery plug, and the battery for the Blender scripts. The `c6remote-explode` repository also uses it.
`scripts/assets/env-studio.hdr` is the Poly Haven `studio_small_09` HDRI at 1k. Its license is CC0.
The three case scripts use the sibling `c6remote-explode` checkout. Set `C6REMOTE_EXPLODE` if that checkout is not at `../c6remote-explode`.
The case scripts need Node, `ffmpeg`, and `img2webp` (`brew install webp`) as well. They render the case geometry the viewer has, so run `../c6remote-explode/refresh-assets.sh` after a case or board change.
Add `--rig` to a case script to render on the Windows Rig over SSH.
The case scripts write dated files into `c6remote-explode`; copy them into `docs/readme-assets/` as `case-assembled.png`, `case-exploded.png`, and `case-explode-loop.webp`.
