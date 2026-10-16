#!/usr/bin/env python3
"""Render the SLS and FDM front shells alone, in matte clay, from one isometric
camera, for case/README.md.

    python3 scripts/render-case-fronts-blender.py [--samples N] [--width PX]

Started with python3, it runs itself under Blender. BLENDER overrides the binary."""

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "case" / "export"
OUT = ROOT / "docs" / "readme-assets"
SHELLS = (
    ("sls", "c6remote-case-front.stl"),
    ("fdm", "c6remote-case-front-fdm.stl"),
)

try:
    import bpy
    from mathutils import Vector
except ImportError:
    bpy = None


def blender_bin():
    for b in (os.environ.get("BLENDER"), shutil.which("blender"),
              "/Applications/Blender.app/Contents/MacOS/Blender"):
        if b and os.access(b, os.X_OK):
            return b
    sys.exit("Blender not found: set BLENDER, or put blender on PATH")


if bpy is None:
    sys.exit(subprocess.call([blender_bin(), "-b", "--factory-startup", "-noaudio",
                              "--python-exit-code", "1", "-P", __file__, "--", *sys.argv[1:]]))

import argparse  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--samples", type=int, default=512)
ap.add_argument("--width", type=int, default=1200)
ap.add_argument("--geometry", default=str(EXPORT), help="directory with the front STLs and c6remote-caps.json")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
EXPORT = Path(a.geometry).resolve()

ELEVATION = math.radians(35.26)
# Camera sits off the grip end and the +X side, so the IR end (+Y) reads at the top.
AZIMUTH = math.radians(-35)
MARGIN = 0.0
# The frame holds the face from the key rows out past the mic port, and only the top of the walls.
FOCUS_X_PAD = -4.0
FOCUS_Y_PAD = -12.0
ASPECT = 2.0
FOCUS_DEPTH = 3.0
SMOOTH_ANGLE = math.radians(32)

scene = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

clay = bpy.data.materials.new("clay")
bsdf = clay.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.70, 0.665, 0.62, 1)
bsdf.inputs["Roughness"].default_value = 0.62
bsdf.inputs["Specular IOR Level"].default_value = 0.25

shells = {}
for name, stl in SHELLS:
    bpy.ops.wm.stl_import(filepath=str(EXPORT / stl))
    o = bpy.context.selected_objects[0]
    o.name = name
    me = o.data
    me.materials.append(clay)
    me.set_sharp_from_angle(angle=SMOOTH_ANGLE)
    shells[name] = o

bounds = [o.matrix_world @ Vector(c) for o in shells.values() for c in o.bound_box]
keys = json.loads((EXPORT / "c6remote-caps.json").read_text()).values()
x0 = max(min(k[0] for k in keys) - FOCUS_X_PAD, min(c.x for c in bounds))
x1 = min(max(k[0] for k in keys) + FOCUS_X_PAD, max(c.x for c in bounds))
y0 = max(min(k[1] for k in keys) - FOCUS_Y_PAD, min(c.y for c in bounds))
y1 = min(max(k[1] for k in keys) + FOCUS_Y_PAD, max(c.y for c in bounds))
z1 = max(c.z for c in bounds)
corners = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z1 - FOCUS_DEPTH, z1)]
center = sum(corners, Vector()) / len(corners)
fwd = Vector((math.cos(ELEVATION) * math.sin(AZIMUTH),
              math.cos(ELEVATION) * math.cos(AZIMUTH),
              -math.sin(ELEVATION)))
cam_data = bpy.data.cameras.new("cam")
cam_data.type = "ORTHO"
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
cam.rotation_euler = fwd.to_track_quat("-Z", "Y").to_euler()
cam.location = center - fwd * 400
cam_data.clip_end = 1000
scene.camera = cam

bpy.context.view_layer.update()
inv = cam.matrix_world.inverted()
local = [inv @ c for c in corners]
xs, ys = [p.x for p in local], [p.y for p in local]
w, h = (max(xs) - min(xs)) * (1 + 2 * MARGIN), (max(ys) - min(ys)) * (1 + 2 * MARGIN)
w, h = min(w, h * ASPECT), min(w, h * ASPECT) / ASPECT
mid = cam.matrix_world @ Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, 0))
cam.location = mid - fwd * 400
cam_data.ortho_scale = max(w, h)
scene.render.resolution_x = a.width
scene.render.resolution_y = round(a.width * h / w)
if h > w:
    cam_data.sensor_fit = "VERTICAL"


def sun(name, strength, elevation, azimuth, angle):
    d = bpy.data.lights.new(name, "SUN")
    d.energy = strength
    d.angle = math.radians(angle)
    o = bpy.data.objects.new(name, d)
    scene.collection.objects.link(o)
    to = Vector((math.cos(math.radians(elevation)) * math.sin(math.radians(azimuth)),
                 math.cos(math.radians(elevation)) * math.cos(math.radians(azimuth)),
                 -math.sin(math.radians(elevation))))
    o.rotation_euler = to.to_track_quat("-Z", "Y").to_euler()


# A raking key from the IR end shades the basin walls that face the grip end. Any
# lower and the shallow dish reads far deeper than it is.
sun("key", 9.5, 10, 180, 4)
sun("fill", 0.5, 60, -60, 15)

world = bpy.data.worlds.new("world")
scene.world = world
world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.18

scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
kind = None
for k in ("OPTIX", "CUDA", "METAL", "HIP", "ONEAPI"):
    try:
        prefs.compute_device_type = k
    except TypeError:
        continue
    prefs.get_devices()
    if any(dv.type == k for dv in prefs.devices):
        kind = k
        break
for dv in prefs.devices:
    dv.use = dv.type == kind
scene.cycles.device = "GPU" if any(dv.use for dv in prefs.devices) else "CPU"
scene.cycles.samples = a.samples
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPTIX" if kind == "OPTIX" else "OPENIMAGEDENOISE"
scene.render.film_transparent = True
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Base Contrast"

for name, _ in SHELLS:
    for other, o in shells.items():
        o.hide_render = other != name
    scene.render.filepath = str(OUT / f"case-front-iso-{name}.png")
    print(f"rendering {name} {scene.render.resolution_x}x{scene.render.resolution_y}, "
          f"{a.samples} samples on {kind or 'CPU'}", flush=True)
    bpy.ops.render.render(write_still=True)
