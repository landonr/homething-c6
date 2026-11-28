#!/usr/bin/env python3
"""Render both one-piece shells in clear resin."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", required=True)
    parser.add_argument("--geometry", default="")
    args, renderer_args = parser.parse_known_args()

    explode = Path(os.environ.get("EXPLODE") or os.environ.get("C6REMOTE_EXPLODE")
                   or ROOT.parent / "c6remote-explode").expanduser().resolve()
    preset_path = Path(args.preset)
    if not preset_path.exists():
        preset_path = explode / "presets" / f"{args.preset}.json"
    with preset_path.open() as source:
        preset = json.load(source)
    preset["onePiece"] = True
    # The strip lights require a front material, but the fused shell uses ring.
    preset.pop("strips", None)
    geometry = Path(args.geometry).resolve() if args.geometry else explode / (
        "assets-draft" if preset.get("diff") == "draft" else "assets"
    )
    for part in ("front", "back"):
        shell = geometry / f"c6remote-case-{part}-one-piece.stl"
        if not shell.is_file():
            sys.exit(f"render-clear-case: missing one-piece {part}: {shell}")

    with tempfile.TemporaryDirectory(prefix="c6remote-clear-preset-") as directory:
        temp_root = Path(directory)
        for name in ("scripts", "assets", "assets-draft", "presets"):
            (temp_root / name).symlink_to(explode / name, target_is_directory=True)
        (temp_root / "package.json").write_text('{"type":"module"}')
        material_uri = (explode / "materials.js").as_uri()
        (temp_root / "materials.js").write_text(
            f"import {{ MATERIALS, COLORWAYS, LOOK }} from {json.dumps(material_uri)};\n"
            "const clear = { color: 0xffffff, hq: { color: 0xffffff, "
            "transmission: 1.0, roughness: 0.11, ior: 1.5 } };\n"
            "MATERIALS.ring = clear; MATERIALS.irwin = clear;\n"
            "export { MATERIALS, COLORWAYS, LOOK };\n"
        )
        overlay = temp_root / preset_path.name
        overlay.write_text(json.dumps(preset))
        command = [sys.executable, str(temp_root / "scripts/render-blender.py"),
                   "--preset", str(overlay)]
        if args.geometry:
            command.extend(["--geometry", str(geometry)])
        return subprocess.call(command + renderer_args)


if __name__ == "__main__":
    sys.exit(main())
