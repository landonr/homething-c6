"""Render the four README board PNGs from a board GLB. Run inside Blender:

blender -b --factory-startup -noaudio --python-exit-code 1 -P scripts/render-board-blender.py -- \
    --glb <file> --hdr <file> --out-dir <dir> [--samples N]
"""
import argparse
import colorsys
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

YAW = 265
MARGIN = 0.05

# (file, fwd = tgt - pos, up, width, areaWidth, areaHeight, model pos, model quat x,y,z,w)
FLIP = ((106.67491, 0, 3.26), (0, 1, 0, 0))
ID = ((0, 0, 0), (0, 0, 0, 1))
ISO = (200, 200, -282.842712474619)
VIEWS = [
    ("board-3d-rotated-top.png", ISO, (0, 0, 1), 1200, 1200, 900, *ID),
    ("board-3d-rotated-bottom.png", ISO, (0, 0, 1), 1200, 1200, 900, *FLIP),
    ("board-3d-top.png", (0, 0, -1), (0, 1, 0), 400, 328, 1176, *ID),
    ("board-3d-bottom.png", (0, 0, -1), (0, 1, 0), 400, 328, 1176, *FLIP),
]

# Re-dress by refdes, from materials.js: color, metallic, roughness.
DRESS = {
    "ENC1": (0x101012, 0.0, 0.15),
    "U2": (0x0C0C0E, 0.0, 0.3),
}

ap = argparse.ArgumentParser()
ap.add_argument("--glb", required=True)
ap.add_argument("--hdr", required=True)
ap.add_argument("--out-dir", required=True)
ap.add_argument("--samples", type=int, default=1600)
a = ap.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def lin(hexv):
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (c((hexv >> 16) & 255), c((hexv >> 8) & 255), c(hexv & 255), 1.0)


def bsdf(m):
    return next(nd for nd in m.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")


for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)
scene = bpy.context.scene

model = bpy.data.objects.new("model", None)
scene.collection.objects.link(model)
model.rotation_mode = "QUATERNION"
grp = bpy.data.objects.new("part-board", None)
scene.collection.objects.link(grp)
grp.parent = model

before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=a.glb)
new = [o for o in bpy.data.objects if o not in before]
# The GLB is in metres. The importer already converts glTF Y-up to Z-up.
root = bpy.data.objects.new("board-mm", None)
scene.collection.objects.link(root)
root.scale = (1000, 1000, 1000)
for o in new:
    if o.parent is None:
        o.parent = root
root.parent = grp

# Open CASCADE writes baseColorFactor only, and glTF defaults metallic to 1.
seen = set()
for o in new:
    for slot in o.material_slots:
        m = slot.material
        if not m or m.name in seen or not m.node_tree:
            continue
        seen.add(m.name)
        for nd in m.node_tree.nodes:
            if nd.type == "BSDF_PRINCIPLED":
                r, g, b, _ = nd.inputs["Base Color"].default_value
                h, l, _ = colorsys.rgb_to_hls(r, g, b)
                metal = l > 0.35 and (h < 0.19 or h > 0.93)
                nd.inputs["Metallic"].default_value = 1.0 if metal else 0.0
                nd.inputs["Roughness"].default_value = 0.3 if metal else 0.5

# The GLB shares one material per colour across unrelated parts, so dress copies.
for ref, (color, metallic, roughness) in DRESS.items():
    node = next((o for o in new if o.name == ref), None)
    if node is None:
        print(f"board: no {ref} to re-dress", flush=True)
        continue
    for o in [node, *node.children_recursive]:
        if o.type != "MESH":
            continue
        if not any(s.material for s in o.material_slots):
            # A model with no colours imports bare and draws in Blender's default grey.
            m = bpy.data.materials.new(f"{ref}-dress")
            m.use_nodes = True
            o.data.materials.clear()
            o.data.materials.append(m)
        for slot in o.material_slots:
            if slot.material:
                m = slot.material = slot.material.copy()
                b = bsdf(m)
                b.inputs["Base Color"].default_value = lin(color)
                b.inputs["Metallic"].default_value = metallic
                b.inputs["Roughness"].default_value = roughness
print(f"board: {len(new)} objects, {len(seen)} materials", flush=True)

# Blender's equirect is Z-up, so only the yaw is left.
world = bpy.data.worlds.new("env")
scene.world = world
wn = world.node_tree
for nd in list(wn.nodes):
    wn.nodes.remove(nd)
coords, mapping = wn.nodes.new("ShaderNodeTexCoord"), wn.nodes.new("ShaderNodeMapping")
mapping.vector_type = "POINT"
mapping.inputs["Rotation"].default_value = (0, 0, math.radians(-YAW))
tex = wn.nodes.new("ShaderNodeTexEnvironment")
tex.image = bpy.data.images.load(a.hdr)
bg, wout = wn.nodes.new("ShaderNodeBackground"), wn.nodes.new("ShaderNodeOutputWorld")
bg.inputs["Strength"].default_value = 1.0
wn.links.new(coords.outputs["Generated"], mapping.inputs["Vector"])
wn.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
wn.links.new(tex.outputs["Color"], bg.inputs["Color"])
wn.links.new(bg.outputs["Background"], wout.inputs["Surface"])


def measure():
    pts = []
    for o in scene.objects:
        if o.type == "MESH":
            co = np.empty(len(o.data.vertices) * 3, np.float32)
            o.data.vertices.foreach_get("co", co)
            mw = np.array(o.matrix_world)
            pts.append(co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])
    return np.concatenate(pts)


def look(fwd, up):
    right = fwd.cross(up).normalized()
    cam_up = right.cross(fwd).normalized()
    return right, cam_up, Matrix((right, cam_up, -fwd)).transposed().to_4x4()


cam_d = bpy.data.cameras.new("cam")
cam_d.type = "ORTHO"
cam_d.clip_start, cam_d.clip_end = 1, 20000
cam = bpy.data.objects.new("cam", cam_d)
scene.collection.objects.link(cam)
scene.camera = cam
grow = 1 + 2 * MARGIN

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
gpus = [dv.name for dv in prefs.devices if dv.use]
scene.cycles.device = "GPU" if gpus else "CPU"
scene.cycles.samples = a.samples
scene.cycles.use_denoising = True
scene.cycles.denoiser = "OPTIX" if kind == "OPTIX" else "OPENIMAGEDENOISE"
scene.cycles.max_bounces = 16
scene.cycles.transmission_bounces = 16
scene.cycles.glossy_bounces = 8
scene.cycles.transparent_max_bounces = 16
scene.render.film_transparent = True
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "AgX"

os.makedirs(a.out_dir, exist_ok=True)
for name, fwd_v, up_v, W, aw, ah, pos, (qx, qy, qz, qw) in VIEWS:
    model.location = pos
    # The presets give x,y,z,w. Blender wants w,x,y,z.
    model.rotation_quaternion = Quaternion((qw, qx, qy, qz))
    bpy.context.view_layer.update()
    pts = measure()
    H = round(W / (aw / ah))
    right, up, rot = look(Vector(fwd_v).normalized(), Vector(up_v))
    fwd = Vector(fwd_v).normalized()
    cs = pts @ np.array([right, up, fwd]).T
    lo, hi = cs.min(0), cs.max(0)
    need_w = max((hi[0] - lo[0]) * grow, (hi[1] - lo[1]) * grow * W / H)
    centre = right * ((lo[0] + hi[0]) / 2) + up * ((lo[1] + hi[1]) / 2) + fwd * (lo[2] - 2000)
    cam.matrix_world = Matrix.Translation(centre) @ rot
    cam_d.ortho_scale = need_w if W >= H else need_w * H / W
    scene.render.resolution_x, scene.render.resolution_y = W, H
    scene.render.filepath = os.path.join(a.out_dir, name)
    print(f"rendering {name} {W}x{H}, {a.samples} samples on {kind or 'CPU'}", flush=True)
    bpy.ops.render.render(write_still=True)
