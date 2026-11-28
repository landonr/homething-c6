#!/usr/bin/env python3
"""Render the front shells in matte clay or the breakaway grid in matte black.

    python3 scripts/render-case-fronts-blender.py [--keycap-grid] [--samples N] [--width PX]

Started with python3, it runs itself under Blender. BLENDER overrides the binary."""

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "case" / "export"
OUT = ROOT / "docs" / "readme-assets"
SHELLS = (
    ("sls", "c6remote-case-front.stl"),
    ("fdm", "c6remote-case-front-fdm.stl"),
    ("one-piece", "c6remote-case-front-one-piece.stl"),
)
GRID = (("keycap-grid", "c6remote-keycap-grid.stl"),)

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
ap.add_argument("--keycap-grid", action="store_true", help="render only the breakaway keycap grid")
ap.add_argument("--geometry", default=str(EXPORT), help="directory with the case exports")
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
EXPORT = Path(a.geometry).resolve()
parts = GRID if a.keycap_grid else SHELLS

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


def grid_silkscreen(bounds):
    svg = EXPORT / "keycap-grid-marking" / "keycap-grid-legends.svg"
    if not svg.is_file():
        sys.exit(f"Missing {svg}. Run scripts/export-keycap-grid-marking.py first.")
    converter = shutil.which("rsvg-convert")
    if converter is None:
        sys.exit("Install rsvg-convert from librsvg to render the grid silkscreen.")
    with TemporaryDirectory() as scratch:
        png = Path(scratch) / "silkscreen.png"
        subprocess.run(
            [converter, "--width=3600", "--output", str(png), str(svg)],
            check=True,
        )
        image = bpy.data.images.load(str(png))
        image.pack()

    left, right = min(p.x for p in bounds), max(p.x for p in bounds)
    front, back = min(p.y for p in bounds), max(p.y for p in bounds)
    z = max(p.z for p in bounds) + 0.01
    mesh = bpy.data.meshes.new("silkscreen")
    mesh.from_pydata(
        [(left, front, z), (right, front, z), (right, back, z), (left, back, z)],
        [], [(0, 1, 2, 3)],
    )
    uv = mesh.uv_layers.new()
    for item, corner in zip(uv.data, ((0, 0), (1, 0), (1, 1), (0, 1))):
        item.uv = corner
    screen = bpy.data.objects.new("silkscreen", mesh)
    scene.collection.objects.link(screen)

    pigment = bpy.data.materials.new("white silkscreen")
    mesh.materials.append(pigment)
    tree = pigment.node_tree
    white = tree.nodes["Principled BSDF"]
    white.inputs["Base Color"].default_value = (0.82, 0.82, 0.82, 1)
    white.inputs["Roughness"].default_value = 0.7
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = image
    texture.extension = "CLIP"
    transparent = tree.nodes.new("ShaderNodeBsdfTransparent")
    mix = tree.nodes.new("ShaderNodeMixShader")
    tree.links.new(texture.outputs["Alpha"], mix.inputs[0])
    tree.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    tree.links.new(white.outputs["BSDF"], mix.inputs[2])
    tree.links.new(mix.outputs["Shader"], tree.nodes["Material Output"].inputs["Surface"])


scene = bpy.context.scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

material = bpy.data.materials.new("matte black" if a.keycap_grid else "clay")
bsdf = material.node_tree.nodes["Principled BSDF"]
base_color = (0.018, 0.019, 0.022, 1) if a.keycap_grid else (0.70, 0.665, 0.62, 1)
bsdf.inputs["Base Color"].default_value = base_color
bsdf.inputs["Roughness"].default_value = 0.66 if a.keycap_grid else 0.62
bsdf.inputs["Specular IOR Level"].default_value = 0.25

objects = {}
for name, stl in parts:
    bpy.ops.wm.stl_import(filepath=str(EXPORT / stl))
    o = bpy.context.selected_objects[0]
    o.name = name
    me = o.data
    me.materials.append(material)
    me.set_sharp_from_angle(angle=SMOOTH_ANGLE)
    if a.keycap_grid:
        # The STL prints face down.
        o.rotation_euler.x = math.pi
    objects[name] = o

bpy.context.view_layer.update()
bounds = [o.matrix_world @ Vector(c) for o in objects.values() for c in o.bound_box]
if a.keycap_grid:
    corners = bounds
    grid_silkscreen(bounds)
    elevation, azimuth = math.radians(52), math.radians(-28)
    margin = 0.08
else:
    keys = json.loads((EXPORT / "c6remote-caps.json").read_text()).values()
    x0 = max(min(k[0] for k in keys) - FOCUS_X_PAD, min(c.x for c in bounds))
    x1 = min(max(k[0] for k in keys) + FOCUS_X_PAD, max(c.x for c in bounds))
    y0 = max(min(k[1] for k in keys) - FOCUS_Y_PAD, min(c.y for c in bounds))
    y1 = min(max(k[1] for k in keys) + FOCUS_Y_PAD, max(c.y for c in bounds))
    z1 = max(c.z for c in bounds)
    corners = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z1 - FOCUS_DEPTH, z1)]
    elevation, azimuth = ELEVATION, AZIMUTH
    margin = MARGIN
center = sum(corners, Vector()) / len(corners)
fwd = Vector((math.cos(elevation) * math.sin(azimuth),
              math.cos(elevation) * math.cos(azimuth),
              -math.sin(elevation)))
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
w, h = (max(xs) - min(xs)) * (1 + 2 * margin), (max(ys) - min(ys)) * (1 + 2 * margin)
if not a.keycap_grid:
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


if a.keycap_grid:
    sun("key", 3.0, 44, 145, 12)
    sun("fill", 0.65, 64, -60, 22)
else:
    # A raking key shades the basin walls without making the dish read too deep.
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

for name, _ in parts:
    for other, o in objects.items():
        o.hide_render = other != name
    filename = "case-keycap-grid.png" if a.keycap_grid else f"case-front-iso-{name}.png"
    scene.render.filepath = str(OUT / filename)
    print(f"rendering {name} {scene.render.resolution_x}x{scene.render.resolution_y}, "
          f"{a.samples} samples on {kind or 'CPU'}", flush=True)
    bpy.ops.render.render(write_still=True)
