"""Render-only board parts the board GLB lacks: the J1 socket and the battery set.

Shared by render-board-blender.py and the c6remote-explode viewer render scripts.
"""
import bmesh
import bpy
from mathutils import Matrix


def lin(hexv):
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    return (c((hexv >> 16) & 255), c((hexv >> 8) & 255), c(hexv & 255), 1.0)


def bsdf(m):
    return next(nd for nd in m.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")


GLYPHS = {
    "-": "00000 00000 00000 11111 00000 00000 00000",
    "+": "00000 00100 00100 11111 00100 00100 00000",
    "X": "10001 10001 01010 00100 01010 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110",
    "N": "10001 11001 10101 10011 10001 10001 10001",
    "J": "00111 00010 00010 00010 00010 10010 01100",
    "7": "11111 00001 00010 00100 01000 01000 01000",
    "0": "01110 10001 10011 10101 11001 10001 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111",
    "5": "11111 10000 11110 00001 00001 10001 01110",
    "3": "01110 10001 00001 00110 00001 10001 01110",
    ".": "00000 00000 00000 00000 00000 01100 01100",
    "V": "10001 10001 10001 10001 10001 01010 00100",
    "8": "01110 10001 10001 01110 10001 10001 01110",
    "m": "00000 00000 11010 10101 10101 10101 10101",
    "A": "01110 10001 10001 11111 10001 10001 10001",
    "h": "10000 10000 10110 11001 10001 10001 10001",
    "C": "01110 10001 10000 10000 10000 10001 01110",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    " ": "00000 00000 00000 00000 00000 00000 00000",
}
DOT, PITCH = 0.21, 0.27
CHAR = 6 * PITCH
LABEL_L, LABEL_DX, LABEL_KY0 = 25.6, 6.4, 126.0
BARS = (0.3, 0.15, 0.45, 0.15, 0.15, 0.3, 0.3, 0.15, 0.15, 0.45, 0.3, 0.3, 0.15, 0.15, 0.15, 0.3,
        0.45, 0.15, 0.3, 0.15, 0.15, 0.45, 0.3, 0.15, 0.3, 0.3, 0.15, 0.15, 0.45, 0.15, 0.3, 0.15,
        0.45, 0.3, 0.15, 0.15, 0.3, 0.15, 0.3, 0.45, 0.15, 0.15, 0.3, 0.15, 0.45, 0.15, 0.3, 0.3)


def build(scene, board, battery=None):
    """Create J1 under board and the plug, leads, pouch and label under battery (board if None).

    Parents are in KiCad mm as Blender (x, -y, z) with the board bottom face at z=0.
    Returns the created objects.
    """
    # Render-only parts the board GLB lacks. Args are KiCad mm (x right, y down, z below the
    # bottom face is negative). Blender mm is (x, -y, z). KiCad 10 ships no J1 model.
    EXTRA_MATS = {}
    parent = [board]
    made = []

    def xmat(name, color, metallic=0.0, roughness=0.5):
        if name not in EXTRA_MATS:
            m = bpy.data.materials.new(f"extra-{name}")
            m.use_nodes = True
            b = bsdf(m)
            b.inputs["Base Color"].default_value = lin(color)
            b.inputs["Metallic"].default_value = metallic
            b.inputs["Roughness"].default_value = roughness
            EXTRA_MATS[name] = m
        return EXTRA_MATS[name]

    def bake(o, mat):
        """Apply modifiers, tag as an extra and attach to the current parent."""
        me = bpy.data.meshes.new_from_object(o.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        name = o.name
        bpy.data.objects.remove(o, do_unlink=True)
        o = bpy.data.objects.new(name, me)
        scene.collection.objects.link(o)
        me.materials.clear()
        me.materials.append(mat)
        for poly in me.polygons:
            poly.use_smooth = True
        o["extra"] = 1
        o.parent = parent[0]
        made.append(o)
        return o

    def xbox(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0, seg=3):
        me = bpy.data.meshes.new(name)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        bm.to_mesh(me)
        bm.free()
        me.transform(Matrix.Translation(((x0 + x1) / 2, -(y0 + y1) / 2, (z0 + z1) / 2))
                     @ Matrix.Diagonal((x1 - x0, y1 - y0, z1 - z0, 1)))
        o = bpy.data.objects.new(name, me)
        scene.collection.objects.link(o)
        if bevel:
            md = o.modifiers.new("bevel", "BEVEL")
            md.width, md.segments, md.limit_method = bevel, seg, "NONE"
        return bake(o, mat)

    def xlead(name, pts, mat, radius=0.5):
        """pts: [(position, handle_in, handle_out)] in KiCad mm."""
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth, cu.bevel_resolution, cu.resolution_u = radius, 4, 24
        cu.use_fill_caps = True
        sp = cu.splines.new("BEZIER")
        sp.bezier_points.add(len(pts) - 1)
        for bp, (p, hi, ho) in zip(sp.bezier_points, pts):
            bp.handle_left_type = bp.handle_right_type = "FREE"
            bp.co, bp.handle_left, bp.handle_right = (
                (q[0], -q[1], q[2]) for q in (p, hi, ho))
        o = bpy.data.objects.new(name, cu)
        scene.collection.objects.link(o)
        bpy.context.view_layer.update()
        return bake(o, mat)


    ivory, white = xmat("ivory", 0xE6DCC0, 0, 0.45), xmat("plug", 0xF2EEE2, 0, 0.4)
    tin = xmat("tin", 0xC9CBCF, 1.0, 0.28)
    red, blk = xmat("red", 0xC41414, 0, 0.4), xmat("black", 0x141414, 0, 0.4)
    pouch, kapton = xmat("pouch", 0xB8BCC2, 0.5, 0.7), xmat("kapton", 0xCC8A18, 0, 0.3)

    # J1 JST S2B-PH-SM4-TB, bottom side, origin (40.25, 152.4). Pads are at y +2.85, the
    # nails at y -2.9 and the mating opening faces -y (inboard).
    JX, ZT, ZB = 40.25, -0.1, -4.9
    xbox("J1-rear", JX - 3.95, JX + 3.95, 153.2, 154.0, ZB, ZT, ivory)
    xbox("J1-roof", JX - 3.95, JX + 3.95, 148.0, 154.0, ZT - 0.8, ZT, ivory)
    xbox("J1-floor", JX - 3.95, JX + 3.95, 148.0, 154.0, ZB, ZB + 0.5, ivory)
    for sx in (-1, 1):
        xbox(f"J1-wall{sx}", JX + sx * 3.1 if sx > 0 else JX - 3.95, JX + 3.95 if sx > 0 else JX - 3.1,
             148.0, 154.0, ZB, ZT, ivory)
        xbox(f"J1-post{sx}", JX + sx - 0.25, JX + sx + 0.25, 149.0, 153.3, -2.9, -2.4, tin)
        xbox(f"J1-tail{sx}", JX + sx - 0.3, JX + sx + 0.3, 153.0, 157.0, -0.3, -0.1, tin)
        nx0, nx1 = (JX + 3.95, JX + 4.2) if sx > 0 else (JX - 4.2, JX - 3.95)
        xbox(f"J1-nail{sx}", nx0, nx1, 148.3, 150.7, -3.4, -0.1, tin)
        xbox(f"J1-nailfoot{sx}", min(nx0, JX + sx * 2.6), max(nx1, JX + sx * 2.6),
             148.3, 150.7, -0.3, -0.1, tin)

    # PHR-2 plug, seated, rear at y 145. Everything from here on is the separable battery part.
    parent[0] = battery if battery is not None else board
    xbox("plug", JX - 2.95, JX + 2.95, 145.0, 153.0, -4.3, -1.0, white, bevel=0.25)
    xbox("plug-rib", JX - 1.5, JX + 1.5, 145.0, 147.0, -1.0, -0.7, white, bevel=0.15)

    # 702050 pouch, 7 x 20 x 50, 0.6 below the bottom face, 1.5 in from the high-x edge to clear the shell.
    PX0, PX1, PZ = 49.5, 69.5, -0.6
    xbox("pouch", PX0, PX1, 89.0, 138.9, PZ - 7.0, PZ, pouch, bevel=1.7, seg=6)
    # Kapton wraps the PCM end, 0.05 proud of the pouch so the faces do not z-fight.
    xbox("pouch-pcm", PX0 - 0.05, PX1 + 0.05, 133.0, 139.0, PZ - 7.05, PZ + 0.05, kapton, bevel=1.7, seg=6)

    # Cell label replica on the outer pouch face: 5x7 dot-matrix print and a barcode. It reads
    # away from the Kapton end (toward -y) with its up toward +x, so the face reads correctly
    # from outside the cell. Label u runs along Blender +y, v along +x.
    ink = xmat("ink", 0x1A1A1A, 0, 0.6)
    bm = bmesh.new()

    def quad(u0, u1, v0, v1):
        bm.faces.new([bm.verts.new(c) for c in ((u0, v0, 0), (u1, v0, 0), (u1, v1, 0), (u0, v1, 0))])

    def dots(text, u0, v0):
        for i, ch in enumerate(text):
            for r, row in enumerate(GLYPHS[ch].split()):
                for c, bit in enumerate(row):
                    if bit == "1":
                        u, v = u0 + i * CHAR + c * PITCH, v0 + (6 - r) * PITCH
                        quad(u, u + DOT, v, v + DOT)


    dots("- XINJ", 0, 5.5)
    dots("702050", LABEL_L - 6 * CHAR, 5.5)
    dots("+ 3.7V 800mAh", 0, 0)
    dots("CE", LABEL_L - 2 * CHAR, 0)
    u, gap = 2 * CHAR, False
    for w in BARS * 2:
        if not gap and u + w <= LABEL_L:
            quad(u, u + w, 2.9, 4.3)
        u += w
        gap = not gap
        if u >= LABEL_L:
            break
    me = bpy.data.meshes.new("label")
    bm.to_mesh(me)
    bm.free()
    me.transform(Matrix(((0, 1, 0, PX0 + LABEL_DX), (1, 0, 0, -LABEL_KY0), (0, 0, -1, PZ - 7.02), (0, 0, 0, 1))))
    t = bpy.data.objects.new("label", me)
    scene.collection.objects.link(t)
    bake(t, ink)

    # Leads leave the Kapton end 1 to 5 mm in from PX0 and enter the plug rear at the BAT and GND pads.
    LZ, PZL = PZ - 3.6, -2.65
    for nm, mat, x0, xp in (("lead-bat", red, PX0 + 2, JX - 1), ("lead-gnd", blk, PX0 + 4, JX + 1)):
        xlead(nm, [((x0, 138.6, LZ), (x0, 136.6, LZ), (x0, 142.2, LZ)),
                   ((xp, 145.4, PZL), (xp, 142.0, PZL), (xp, 146.4, PZL))], mat)

    bpy.context.view_layer.update()
    return made
