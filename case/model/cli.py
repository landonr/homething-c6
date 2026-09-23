"""The command line: build every part, write the STLs and the cap placement
JSON, and print the summary of what the stack came out as.

case.py is the entry point that calls main() here.
"""

import argparse
import json

from build123d import Pos

import board
import cache
import params

from .backform import contour_depth
from .caps import (
    cap_body,
    cap_flat,
    cap_counterbore,
    cap_face_hole,
    cap_flange,
    cap_proud,
    cap_refs,
    counterbore_land,
    keycap,
)
from .cell import cell_axis, cell_bay
from .features import write_features
from .hardware import (
    end_screw_axis,
    end_screw_length,
    legacy_retention_floors,
    legacy_screw_length,
    mount_points,
)
from .ir import (
    emitter_reach,
    ir_window,
    ir_window_retention,
    ir_window_span,
)
from .keypad import (
    button_pad,
    centerline_keys_span,
    centerline_x,
    face_depth_at,
    key_pitch,
    key_size,
    keypad_recess_facts,
    outline_length,
    pad_lobes,
    pad_wheel_gap,
    recess_span,
    ring_roof_left,
    wheel_ledge_left,
)
from .legends import _bounds, _legend_faces, legend_entry, legend_solids
from .mic import (
    mic_duct_wall_left,
    mic_fillet_r,
    mic_mouth_r,
    mic_port,
    mic_port_drill,
    mic_taper_angle,
    mic_taper_r,
    mic_taper_top,
    mic_throat_d,
)
from .shells import back_shell, front_edge_round, front_shell
from .support import support_bearing_margins, support_run_lengths
from .wheel_ring import (
    LED_RING_TOP,
    led_ring_clip_reach,
    led_ring_inner_r,
    led_ring_mouth_outer_r,
    led_ring_outer_r,
    led_ring_roof_flat,
    led_ring_roof_outer_r,
    led_ring_wall_height,
    led_ring_web_left,
    led_y_reach,
    pad_clear_y,
)
from .stack import (
    BOARD_TOP,
    FDM_FACE,
    LAP_OUT,
    CAP_BOTTOM,
    CAVITY_FRONT,
    CAVITY_FRONT_USB,
    COUNTERBORE_TOP,
    DISH_HEADROOM,
    EXPORT,
    KEYPAD_CEILING,
    KEYPAD_KEEPOUT,
    LIP_CLEAR_R,
    PAD_WEB_BOTTOM,
    SHELL_BACK,
    SHELL_FRONT,
    SHELL_SEAM,
    SKIRT_BOTTOM,
    SKIRT_OUT,
    STEM_TOP,
    SUPPORT_TOP,
    WHEEL_LIP_OD,
    WHEEL_LIP_Z0,
    WHEEL_LIP_Z1,
    WHEEL_MAIN_OD,
    WHEEL_OPENING_R,
    WHEEL_TOP,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="preview via ocp-vscode")
    ap.add_argument(
        "--draft",
        action="store_true",
        help="write the STLs and cap placements only, no feature map, no summary",
    )
    args = ap.parse_args()

    print(cache.provenance())

    parts = {
        "c6remote-case-front": front_shell(),
        "c6remote-case-back": back_shell(),
        "c6remote-case-pad": button_pad(),
        "c6remote-ir-window": ir_window(),
    }
    caps = {f"c6remote-cap-{ref.lower()}": keycap(ref) for ref in cap_refs()}

    if args.show:
        from ocp_vscode import show

        show(*parts.values(), *caps.values())
        return

    # The FDM front is a second copy of the same part, not a fifth part of the
    # assembly, so it is added after --show has returned: showing both would
    # draw two front shells in the same place. features.py keys its features
    # under its own file name, since that is the file the viewer loads.
    parts["c6remote-case-front-fdm"] = front_shell(fdm=True)
    parts["c6remote-case-pad-fdm"] = button_pad(fdm=True)

    # The caps are built where their switches are, which is where --show wants
    # them and nowhere near where a slicer does.
    placements = board.components()
    for name, ref in zip(caps, cap_refs()):
        x, y, _, _ = placements[ref]
        parts[name] = Pos(-x, -y, -CAP_BOTTOM) * caps[name]

    EXPORT.mkdir(exist_ok=True)
    # Where each cap STL goes back to in the case frame, since the file itself no
    # longer says. Anything reassembling the export reads this rather than
    # rediscovering the switch positions from the board. Caps only: the shells
    # and the IR window plate are all exported where they belong, so they need
    # no entry here and adding one would name them keycaps.
    with (EXPORT / "c6remote-caps.json").open("w") as f:
        json.dump(
            {
                f"{name}.stl": [round(v, 3) for v in (*placements[ref][:2], CAP_BOTTOM)]
                for name, ref in zip(caps, cap_refs())
            },
            f,
            indent=2,
        )

    for name, part in parts.items():
        cache.export_stl_cached(part, EXPORT / f"{name}.stl")
        box = part.bounding_box()
        print(f"{name}  {box.size.X:.2f} x {box.size.Y:.2f} x {box.size.Z:.2f}")

    # The facts below all query built geometry, which costs more than the meshes
    # on a warm cache. A draft stops here and leaves the last full run's feature
    # map in place, so Identify still answers, off the geometry it was written from.
    if args.draft:
        return

    # What each surface in those meshes is called, for a viewer that has only
    # triangles to go on. Written from the same builders the parts came from, so
    # a feature that moves takes its box with it.
    named = write_features(EXPORT / "c6remote-features.json")["parts"]
    print(
        "features "
        + ", ".join(f"{name} {len(entries)}" for name, entries in named.items())
    )

    _, _, cy0, cy1 = cell_axis()
    lo, hi = cell_bay()
    box = board.board_profile().bounding_box()
    front = SHELL_FRONT - BOARD_TOP
    over = params.BOARD_FIT + params.WALL
    print(f"\ncase closes to {SHELL_FRONT - SHELL_BACK:.2f} over the cell")
    print(
        f"  {front + contour_depth(box.min.Y):.2f} at the grip end, "
        f"{front + contour_depth(box.max.Y):.2f} at the IR end, "
        f"{front + contour_depth(box.max.Y + over):.2f} at its tip"
    )
    usb_box = board.usb_envelope()
    print(
        f"front face one flat plane at {SHELL_FRONT:.2f}: keypad region ceiling "
        f"{CAVITY_FRONT:.2f} to {SHELL_FRONT:.2f} ({KEYPAD_CEILING:.2f} thick, "
        f"keepout {KEYPAD_KEEPOUT:.2f} off the board, switch plus "
        f"{params.KEYPAD_PLUNGER_STUB:.2f} of plunger stub), USB region a local "
        f"pocket to {CAVITY_FRONT_USB:.2f} over {usb_box.size.X:.1f}x"
        f"{usb_box.size.Y:.1f} of connector, leaving "
        f"{SHELL_FRONT - CAVITY_FRONT_USB:.2f} of ceiling above it; bosses carry "
        f"their own material the rest of the way to the face regardless"
    )
    print(
        f"face flat at {SHELL_FRONT:.2f}; wheel top measured at {WHEEL_TOP:.3f}, "
        f"lip {WHEEL_LIP_OD:.2f} OD (WHEEL_OD param {board.WHEEL_OD:.2f}) over z "
        f"{WHEEL_LIP_Z0:.3f} .. {WHEEL_LIP_Z1:.3f}, main body {WHEEL_MAIN_OD:.2f} OD above it"
    )
    print(
        f"  shell opening a {2 * WHEEL_OPENING_R:.2f} bore, flush to the main "
        f"body at {params.WHEEL_OPENING_CLEARANCE:.2f} rotating clearance and "
        f"flush to the wheel top by construction (face is WHEEL_TOP)"
    )
    wheel = keypad_recess_facts()["dishes"]["wheel"]
    wx, wy = board.wheel_center()
    print(
        f"  seated in the keypad recess's own wheel basin: a "
        f"{2 * wheel['half'][0]:.2f} angular blend ({params.WHEEL_BASIN_SPREAD:.2f} "
        f"past the bore on its axes), dishing to "
        f"{face_depth_at(wx + WHEEL_OPENING_R, wy):.2f} at the bore on the axes, "
        f"{face_depth_at(wx + WHEEL_OPENING_R * 0.7071, wy + WHEEL_OPENING_R * 0.7071):.2f} "
        f"on the diagonals and "
        f"{face_depth_at(wx, wy - WHEEL_OPENING_R):.2f} where a join leaves it; "
        f"its {params.WHEEL_SQUIRCLE_N:.1f} exponent sets exact diagonal reach, "
        f"while its cardinal axes keep circular curvature; the "
        f"rim keeps {wheel_ledge_left():.2f} of seat clear of the bore all the way "
        f"round, against a {params.WHEEL_RIM_LEDGE:.2f} floor"
    )
    print(
        f"  pad kept {pad_clear_y():.2f} either side of the wheel "
        f"({'lip clearance' if pad_clear_y() == LIP_CLEAR_R else 'LED reach'} "
        f"governs), which its two lobes clear by {pad_wheel_gap():.2f}; no "
        f"moulded ring and no bore cut any more"
    )
    print(
        f"  LEDs uncovered by {pad_clear_y() - led_y_reach():.2f}, "
        f"{PAD_WEB_BOTTOM - BOARD_TOP - params.LED_HEIGHT:.2f} of air over each "
        f"package, firing into the ring channel: {led_ring_inner_r():.2f} to "
        f"{led_ring_outer_r():.2f} around the wheel, void up to {LED_RING_TOP:.2f}, "
        f"{params.LED_RING_ROOF:.2f} of translucent roof over it "
        f"({ring_roof_left():.2f} where the recess crosses it)"
    )
    print(
        f"  inner wall plumb at {led_ring_inner_r():.2f} over the full "
        f"{led_ring_wall_height():.2f} of height, outer wall raked 45 degrees "
        f"and widest at the mouth: {led_ring_mouth_outer_r():.2f} there, closing "
        f"to {led_ring_roof_outer_r():.2f} at the roof, so "
        f"{led_ring_roof_flat():.2f} of flat glows and {led_ring_web_left():.2f} "
        f"of web is left to the bore at every height"
    )
    print(
        f"  chorded flush against the cavity wall at "
        f"{led_ring_clip_reach(0.0):.2f} near the X axis, which still leaves "
        f"{led_ring_clip_reach(0.0) - led_ring_inner_r():.2f} of ring there"
    )
    print(
        f"cell bay {cy1 - cy0:.2f} long for a {params.CELL_L:.1f} cell, "
        f"in {hi - lo:.2f} of clear run"
    )
    lengths = support_run_lengths()
    margins = support_bearing_margins()
    print(
        f"board support {len(lengths)} runs at {params.SUPPORT_BEARING:.2f} bearing, "
        f"{params.SUPPORT_GAP:.2f} below the board"
    )
    print("  run lengths " + ", ".join(f"{length:.2f}" for length in lengths))
    print(
        "  bearing margin "
        + ", ".join(f"{side} {margin:.2f}" for side, margin in margins.items())
    )
    sizes = {}
    for ref in board.refs("SW"):
        sizes.setdefault(round(key_size(ref), 2), []).append(ref)
    spread = ", ".join(
        f"{size:.2f} square x{len(refs)}" for size, refs in sorted(sizes.items(), reverse=True)
    )
    print(
        f"keys {spread}, superellipse corners at exponent "
        f"{params.KEY_SQUIRCLE_N:.1f}, flanks bowed out further than the "
        f"{params.KEYPAD_SQUIRCLE_N:.1f} of the recesses they sit in, on a "
        f"{key_pitch():.2f} grid with a {params.KEY_GAP:.1f} gap"
    )
    for size, refs in sorted(sizes.items()):
        if size < key_size() - 0.01:
            print(f"  {', '.join(refs)} cut back from {key_size():.2f} by a screw boss")
    proud = sorted((cap_proud(ref), ref) for ref in cap_refs())
    lands = sorted((counterbore_land(ref), ref) for ref in cap_refs())
    print(
        f"caps on all {len(cap_refs())} keys, {params.CAP_PROTRUSION:.2f} proud of "
        f"the face and standing "
        f"{proud[0][0]:.2f} ({proud[0][1]}) to {proud[-1][0]:.2f} ({proud[-1][1]}) "
        f"proud of the recess floor around them"
    )
    full = max(cap_refs(), key=key_size)
    print(
        f"  bodies {cap_body(full):.2f} square through {cap_face_hole(full):.2f} face "
        f"holes, {params.CAP_GUIDE_CLEARANCE:.2f} of guide clearance per side"
    )
    print(
        f"  flange {cap_flange(full):.2f} in a {cap_counterbore(full):.2f} counterbore, "
        f"{COUNTERBORE_TOP - (CAP_BOTTOM + params.CAP_FLANGE_T):.2f} of float under a "
        f"face land of {DISH_HEADROOM:.2f} flat, {lands[0][0]:.2f} at its thinnest "
        f"({lands[0][1]}, under the deepest point of a recess)"
    )
    print(
        f"  locating recess {STEM_TOP - CAP_BOTTOM:.2f} deep on a {params.STEM_W:.1f} "
        f"stem, {params.STEM_GRIP:.2f} interference per side"
    )
    print(
        f"  {params.CAP_LIFT:.2f} of lift under the flange against "
        f"{params.SWITCH_TRAVEL:.2f} of switch travel"
    )
    print(
        f"  legends {params.LEGEND_DEPTH:.1f} deep into {params.CAP_TOP_T:.1f} of roof, "
        f"so print a cap top face down, over a "
        f"{(cap_flange(full) - cap_body(full)) / 2:.2f} stepped overhang at the flange"
    )
    flat = cap_flat(full)
    print(
        f"  in {flat:.2f} of top, the largest square the cap's own curve holds, "
        f"sized off each legend's own ink:"
    )
    for ref in cap_refs():
        spec, size = legend_entry(ref)
        faces = _legend_faces(spec, size)
        box = _bounds(faces)
        what = f"svg {spec[1]}" if not isinstance(spec, str) else repr(spec)
        note = "" if size == params.LEGEND_SIZE else f" at {size:.1f}"
        print(
            f"    {ref:<4} {what:<22}{note:<9} ink {box.size.X:.2f} x {box.size.Y:.2f}, "
            f"cuts {sum(s.volume for s in legend_solids(ref)):.2f} mm3"
        )
    print(
        f"mic inlet one funnel, {mic_throat_d():.2f} throat on the board's own "
        f"{mic_port_drill():.2f} port ({params.MIC_THROAT_MARGIN / 2:.2f} of alignment "
        f"slop per side) opening out to {2 * mic_mouth_r():.2f} at the recess's "
        f"own floor, {face_depth_at(*mic_port()):.2f} under the face there, no "
        f"straight section between"
    )
    print(
        f"  taper cone {mic_taper_top() - BOARD_TOP:.2f} tall, "
        f"{params.MIC_TAPER_SHARE:.0%} of the way out to {2 * mic_taper_r():.2f}, "
        f"{mic_taper_angle():.1f} degrees off the axis so it self-supports either "
        f"way up"
    )
    print(
        f"  mouth finished by a {mic_fillet_r():.2f} concave fillet, tangent to the "
        f"floor and continuous with the taper, sinking that same {mic_fillet_r():.2f} "
        f"below the floor and leaving {mic_duct_wall_left():.2f} of wall in a "
        f"{params.MIC_DUCT_OD:.1f} duct at its widest"
    )
    x0, x1, y0, y1 = ir_window_span()
    print(
        f"IR receiver bottom aperture {x1 - x0:.2f} x {y1 - y0:.2f}, x "
        f"{x0:.2f} .. {x1:.2f}, y {y0:.2f} .. {y1:.2f}, derived from U2's "
        "complete envelope"
    )
    print(
        f"  conformal pane {params.IR_WINDOW_T:.2f} thick in the beam with "
        f"{params.IR_WINDOW_PRESS:.2f} press per side; interior flange "
        f"{params.IR_WINDOW_FLANGE_T:.2f} thick reaches "
        f"{params.IR_WINDOW_FLANGE:.2f} past the opening, retaining on "
        f"{ir_window_retention():.2f} with {params.IR_WINDOW_FIT:.2f} adhesive gap"
    )
    lens = board.emitter_envelope()
    print(
        f"  D1 fires through its own {2 * (max(lens.size.X, lens.size.Z) / 2 + params.IR_EMITTER_FIT):.2f} "
        f"bore, uncovered, {params.IR_EMITTER_FIT:.2f} around a {lens.size.X:.2f} "
        f"lens that stops {emitter_reach():.2f} short of the exterior face"
    )
    print(
        f"FDM front is the same shell with the face finished differently: the "
        f"recess's own outline, the same {outline_length():.1f} of rim, as a "
        f"{params.FDM_OUTLINE_W:.2f} x {params.FDM_OUTLINE_DEPTH:.2f} slot in an "
        f"otherwise flat face, so it prints face down with no support on the "
        f"cosmetic surface"
    )
    print(
        f"  top edge has a {front_edge_round(True):.2f} 45 degree chamfer "
        f"rather than a {front_edge_round():.2f} round, leaving the outline "
        f"{params.FDM_OUTLINE_EDGE_CLEAR:.2f} of flat face outboard of it"
    )
    print(
        f"  face sits {params.FDM_FACE_DROP:.2f} below the recessed front's, at "
        f"{FDM_FACE:.2f}, so flattening the dish does not keep the material the "
        f"dish took out; caps and the wheel stand that far proud, against the "
        f"{min(cap_proud(r) for r in cap_refs()):.2f} to "
        f"{max(cap_proud(r) for r in cap_refs()):.2f} a cap already stands proud "
        f"of the dish around it"
    )
    facts = keypad_recess_facts()
    span = recess_span()
    print(
        f"keypad face carries one continuous recess, {span[1] - span[0]:.2f} long "
        f"on the x={facts['centerline'][0]:.2f} centreline (the three basin "
        f"centres agree on it to {facts['centerline'][1]:.3f}), lofted through "
        f"{facts['stations']} stations as one solid; no flat floor, no wall, no "
        f"seam and no cusp, in {DISH_HEADROOM:.2f} of face land, clearing the wall by "
        f"{facts['edge_gap']:.2f} (wants {params.KEYPAD_EDGE_MARGIN:.2f})"
    )
    for name, f in facts["dishes"].items():
        keys = (
            f"keys sit {f['key_depths'][0]:.2f} to {f['key_depths'][1]:.2f} down"
            if f["key_depths"]
            else "no keys under it, the bore takes its middle"
        )
        print(
            f"  basin {name:<6} {2 * f['half'][0]:.2f} x {2 * f['half'][1]:.2f} at "
            f"y {f['center'][1]:.2f}, exponent {f['n']:.1f}, {f['depth']:.2f} deep, "
            f"{keys}"
        )
    for label, f in facts["necks"].items():
        print(
            f"  join {label:<13} reach {f['reach'][0]:.1f}/{f['reach'][1]:.1f} into the two rims, y "
            f"{f['span'][0]:.2f} .. {f['span'][1]:.2f}, narrowing from "
            f"{2 * f['ends'][0]:.2f} to {2 * f['waist'][1]:.2f} and out to "
            f"{2 * f['ends'][1]:.2f}"
        )
        print(
            f"       outline turns through {f['radius']:.2f} at its tightest, "
            f"floor never shallower than {f['floor']:.2f}"
        )
    ky0, ky1 = centerline_keys_span()
    walk = min(
        face_depth_at(centerline_x(), ky0 + (ky1 - ky0) * i / 800) for i in range(801)
    )
    print(
        f"  unbroken along the centreline from one island's keys to the other's, "
        f"y {ky0:.2f} .. {ky1:.2f}, never shallower than {walk:.2f}"
    )
    print(
        f"  every counterbore inside the rim, thinnest land {lands[0][0]:.2f} at "
        f"{lands[0][1]}; ring roof down to {ring_roof_left():.2f} where the recess "
        f"crosses it"
    )
    print(
        f"pad two lobes, {params.PAD_MARGIN:.1f} of web past each island's own "
        f"keys on all four sides, {params.PAD_RADIUS:.1f} corners:"
    )
    for name, x0, y0, x1, y1 in pad_lobes():
        print(f"  {name:<6} {x1 - x0:.2f} x {y1 - y0:.2f}")
    # Both derived from the same stack rather than quoted: a board screw crosses
    # the board and takes the pilot, and the end screw crosses the wall left
    # under its head, the gap the block stands off that wall by, and its own
    # shorter engagement. They come out the same length, so the case takes one
    # fastener: END_SCREW_PILOT_DEPTH is what keeps it that way.
    short_screw = params.BOARD_THICKNESS + params.BOSS_PILOT_DEPTH
    end_x, end_z = end_screw_axis()
    print(
        f"screws: {len(mount_points())}x M2 x {short_screw:.0f} into the front "
        f"plate through the board's own {board.mounting_holes()[0][2]:.1f} holes, plus "
        f"one M2 x {end_screw_length():.0f} through the -Y end wall at x "
        f"{end_x:.2f}, z {end_z:.2f}, into a block behind the front skirt"
    )
    print(
        f"  {params.BOSS_PILOT_DEPTH:.1f} of self-tapped engagement in a "
        f"{params.BOSS_PILOT_D:.2f} pilot, {params.BOSS_OD:.1f} boss; heads "
        f"{params.SCREW_HEAD_D:.1f} across sit on the board's underside"
    )
    legacy_point = board.legacy_retention_point()
    _, legacy_cavity = legacy_retention_floors()
    print(
        f"  optional: one M2 x {legacy_screw_length():.0f} at {legacy_point} into a "
        f"{params.LEGACY_RETENTION_OD:.1f} post standing {SUPPORT_TOP - legacy_cavity:.2f} off "
        f"the back floor, for a V2 board's own upper-right hole. Retention only: "
        f"V2's IR parts and upper keys still land wrong, and the V2 board fastens "
        f"to the back before the front closes, the reverse of V3"
    )
    print(
        f"IR end: skirt {SHELL_SEAM - (BOARD_TOP - params.CATCH_SKIRT_H):.1f} deep "
        f"over {params.CATCH_SPAN:.1f}, "
        f"with 2 windows {params.CATCH_W:.0f}x{params.CATCH_H:.1f}, detents "
        f"{params.CATCH_D:.1f} proud of the lap behind them; the +x window is held "
        f"{params.CATCH_EMITTER_CLEAR:.1f} off D1's bore rather than mirrored"
    )
    print(
        f"grip end: no detents, closed by the one end-wall screw into a "
        f"{params.END_SCREW_BLOCK_W:.1f}x{params.END_SCREW_BLOCK_D:.1f} block, "
        f"{params.END_SCREW_PILOT_DEPTH:.1f} of engagement under "
        f"{LAP_OUT - params.BOARD_FIT - params.SHELL_SCREW_HEAD_H:.1f} of wall, "
        f"standing {params.END_SCREW_BLOCK_GAP:.2f} off the back's inner wall"
    )
    print(
        f"lap: skirt {SKIRT_OUT - params.BOARD_FIT:.2f} thick under a "
        f"{params.SKIRT_T:.2f} lap, {SHELL_SEAM - SKIRT_BOTTOM:.1f} deep"
    )
    print(f"written to {EXPORT}")
