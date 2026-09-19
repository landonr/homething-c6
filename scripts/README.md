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
../c6remote-explode/scripts/render-case-exploded.sh
../c6remote-explode/scripts/render-case-spin.sh
```

The case render scripts use the sibling `c6remote-explode` checkout.
The scripts need Node, Playwright, and `ffmpeg`.
Run `npm install` in `c6remote-explode` one time.
Set `C6REMOTE_REPO` if the board checkout is not in the default `homething-c6` directory.
