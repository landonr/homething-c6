from pathlib import Path
import base64
import subprocess
import struct
from html import escape

root = Path(__file__).resolve().parents[1]
assets = root / 'docs/readme-assets'
work = Path('/tmp/c6remote-annotations')
work.mkdir(exist_ok=True)
yellow = '#b5a000'
black = '#151515'
light = '#f2f2e8'


def png_data(path, expected=None):
    raw = path.read_bytes()
    size = struct.unpack('>II', raw[16:24])
    if expected and size != expected:
        raise ValueError(f'{path.name}: expected {expected}, got {size}')
    return size, base64.b64encode(raw).decode('ascii')


def check_paths(callouts):
    segments = []
    for name, points, *_ in callouts:
        for start, end in zip(points, points[1:]):
            segments.append((name, start, end))

    def orient(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a, b, p):
        return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])

    def intersects(a, b, c, d):
        o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
        if o1 == 0 and on_segment(a, b, c):
            return True
        if o2 == 0 and on_segment(a, b, d):
            return True
        if o3 == 0 and on_segment(c, d, a):
            return True
        if o4 == 0 and on_segment(c, d, b):
            return True
        return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)

    for index, (name_a, a0, a1) in enumerate(segments):
        for name_b, b0, b1 in segments[index + 1:]:
            if name_a == name_b:
                continue
            if intersects(a0, a1, b0, b1):
                raise ValueError(f'leader paths intersect: {name_a} and {name_b}')


def render(output, canvas, source, placement, callouts, rotate=False, text_color=black, tilt=0, trim=False,
           font=42, detail_font=31, detail_dy=38):
    source_path = assets / source
    if tilt or trim:
        tilted = work / f'{Path(source).stem}-tilt.png'
        box = subprocess.run(['magick', str(source_path), '-background', 'none', '-rotate', str(tilt), '+repage',
                              '-alpha', 'extract', '-threshold', '5%', '-trim', '-format', '%wx%h%O', 'info:'],
                             check=True, capture_output=True, text=True).stdout
        subprocess.run(['magick', str(source_path), '-background', 'none', '-rotate', str(tilt), '+repage',
                        '-crop', box, '+repage', str(tilted)], check=True)
        source_path = tilted
    if rotate:
        rotated = work / 'case-assembled-rotated.png'
        subprocess.run(['magick', str(source_path), '-rotate', '90', str(rotated)], check=True)
        source_path = rotated
    (source_w, source_h), image_b64 = png_data(source_path)
    scale, x, y = placement
    image_w, image_h = source_w * scale, source_h * scale
    scaled_callouts = []
    for name, pts, label, tx, ty, anchor in callouts:
        scaled_pts = [(round(px, 1), round(py, 1)) for px, py in pts]
        scaled_callouts.append((name, scaled_pts, label, tx, ty, anchor))
    check_paths(scaled_callouts)

    width, height = canvas
    title = output.replace('-', ' ').replace('.svg', '').title()
    description = 'Annotated c6remote hardware image with labels and leader lines.'
    stroke = round(2 * width / 350, 1)
    dot = round(1.8 * stroke, 1)
    svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<title>{escape(title)}</title><desc>{escape(description)}</desc>
<image x="{x}" y="{y}" width="{image_w:.1f}" height="{image_h:.1f}" href="data:image/png;base64,{image_b64}" preserveAspectRatio="none"/>''']
    for _, points, _, _, _, _ in scaled_callouts:
        path = 'M ' + ' L '.join(f'{px:.1f} {py:.1f}' for px, py in points)
        svg.append(f'<path d="{path}" fill="none" stroke="{yellow}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round"/>')
        px, py = points[0]
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{dot}" fill="{yellow}"/>')

    def line(text, x, y, size, anchor):
        return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{text_color}" font-family="Arial,sans-serif" '
                f'font-size="{size}" font-weight="400">{escape(text)}</text>')

    for _, _, label, tx, ty, align in scaled_callouts:
        text_anchor = 'end' if align in ('left', 'end') else 'start'
        title, detail = label if isinstance(label, tuple) else (label, '')
        title_lines = title.split('\n')
        for i, text in enumerate(title_lines):
            svg.append(line(text, tx, ty + i * round(font * 1.2), font, text_anchor))
        if detail:
            base = ty + (len(title_lines) - 1) * round(font * 1.2) + detail_dy
            for i, text in enumerate(detail.split('\n')):
                svg.append(line(text, tx, base + i * detail_dy, detail_font, text_anchor))
    svg.append('</svg>')

    out_path = assets / output
    out_path.write_text('\n'.join(svg))
    print(out_path)


# Front images carry labels on the left, back images on the right. All callouts are in final canvas coordinates.
text = dict(font=88, detail_font=66, detail_dy=75)
case_canvas = (1840, 2912)
case_front_callouts = [
    ('mic', [(1439, 201), (740, 201)], 'Microphone', 727, 232, 'end'),
    ('wheel', [(1432, 923), (740, 923)], ('Scroll wheel', '+ 5-way control'), 727, 954, 'end'),
    ('leds', [(1142, 1181), (740, 1181)], 'RGB status LEDs', 727, 1212, 'end'),
    ('keypad', [(1222, 1685), (740, 1685)], '11 assignable\nbuttons', 727, 1716, 'end'),
    ('radios', [(1447, 2547), (740, 2547)], ('XIAO ESP32-C6', 'Zigbee · Wi-Fi · BLE'), 727, 2578, 'end'),
    ('USB-C', [(1454, 2809), (740, 2809)], 'USB-C', 727, 2840, 'end'),
]
case_back_callouts = [
    ('emitter', [(346, 268), (1090, 268)], 'IR emitter', 1105, 299, 'start'),
    ('receiver', [(551, 685), (1090, 685)], 'IR receiver', 1105, 716, 'start'),
    ('battery', [(480, 2300), (1090, 2300)], ('800 mAh battery', 'About a month\nper charge'), 1105, 2331, 'start'),
    ('shell', [(904, 1980), (1090, 1980)], 'Translucent\nenclosure', 1105, 2011, 'start'),
]
board_text = dict(font=46, detail_font=35, detail_dy=40)
board_canvas = (1060, 2001)
board_front_callouts = [
    ('switches', [(618, 365), (410, 365)], '11 tactile\nswitches', 400, 381, 'end'),
    ('leds', [(600, 542), (410, 542)], 'RGB status\nLEDs', 400, 558, 'end'),
    ('encoder', [(830, 695), (410, 695)], 'Rotary encoder', 400, 711, 'end'),
    ('expander', [(782, 1510), (410, 1510)], 'GPIO expander', 400, 1526, 'end'),
    ('module', [(814, 1680), (410, 1680)], 'XIAO ESP32-C6', 400, 1696, 'end'),
]
board_back_callouts = [
    ('receiver', [(435, 180), (647, 180)], 'IR receiver', 660, 196, 'start'),
    ('mic', [(303, 178), (303, 290), (647, 290)], 'I²S microphone', 660, 306, 'start'),
    ('emitter', [(192, 175), (192, 400), (647, 400)], 'IR emitter', 660, 416, 'start'),
    ('pouch', [(250, 1250), (647, 1250)], '800 mAh LiPo\nbattery', 660, 1266, 'start'),
    ('connector', [(486, 1760), (647, 1760)], 'Battery\nconnector', 660, 1776, 'start'),
]
for suffix, color in (('', black), ('-dark', light)):
    render(f'remote-controls-annotated{suffix}.svg', case_canvas, 'case-annotated-front.png', (1.35, 887, 40),
           case_front_callouts, trim=True, text_color=color, **text)
    render(f'remote-back-annotated{suffix}.svg', case_canvas, 'case-annotated-back.png', (1.28, 30, 114),
           case_back_callouts, trim=True, text_color=color, **text)
    render(f'board-front-annotated{suffix}.svg', board_canvas, 'board-3d-rotated-top.png', (1.0, 500, 30),
           board_front_callouts, text_color=color, **board_text)
    render(f'board-back-annotated{suffix}.svg', board_canvas, 'board-3d-rotated-bottom.png', (1.0, 30, 30),
           board_back_callouts, text_color=color, **board_text)
