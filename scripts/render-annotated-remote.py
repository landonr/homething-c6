from pathlib import Path
import base64
import json
import subprocess
import struct
from html import escape

root = Path(__file__).resolve().parents[1]
assets = root / 'docs/readme-assets'
work = Path('/tmp/c6remote-annotations')
work.mkdir(exist_ok=True)
black = '#151515'
light = '#f2f2e8'
callouts_path = root / 'scripts/annotation-callouts.json'


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
           font=42, detail_font=31, detail_dy=38, ids=False, write=True):
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
    # Leaders share the text colour, so an opposite-colour halo keeps them visible over the dark PCB and keys.
    halo_color = light if text_color == black else black
    halo = round(0.6 * stroke, 1)
    def tag(index, is_halo=False):
        if not ids:
            return ''
        return f' data-callout="{index}"' + (' data-halo="1"' if is_halo else '')

    for color, grow in ((halo_color, halo), (text_color, 0)):
        for index, (_, points, _, _, _, _) in enumerate(scaled_callouts):
            path = 'M ' + ' L '.join(f'{px:.1f} {py:.1f}' for px, py in points)
            svg.append(f'<path{tag(index, grow > 0)} d="{path}" fill="none" stroke="{color}" stroke-width="{stroke + 2 * grow:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
            px, py = points[0]
            svg.append(f'<circle{tag(index, grow > 0)} cx="{px:.1f}" cy="{py:.1f}" r="{dot + grow:.1f}" fill="{color}"/>')

    def line(index, text, x, y, size, anchor):
        return (f'<text{tag(index)} x="{x}" y="{y}" text-anchor="{anchor}" fill="{text_color}" font-family="Arial,sans-serif" '
                f'font-size="{size}" font-weight="400">{escape(text)}</text>')

    for index, (_, _, label, tx, ty, align) in enumerate(scaled_callouts):
        text_anchor = 'end' if align in ('left', 'end') else 'start'
        title, detail = label if isinstance(label, tuple) else (label, '')
        title_lines = title.split('\n')
        for i, text in enumerate(title_lines):
            svg.append(line(index, text, tx, ty + i * round(font * 1.2), font, text_anchor))
        if detail:
            base = ty + (len(title_lines) - 1) * round(font * 1.2) + detail_dy
            for i, text in enumerate(detail.split('\n')):
                svg.append(line(index, text, tx, base + i * detail_dy, detail_font, text_anchor))
    svg.append('</svg>')

    content = '\n'.join(svg)
    if write:
        out_path = assets / output
        out_path.write_text(content)
        print(out_path)
    return content


def load_callouts():
    return json.loads(callouts_path.read_text())


def write_callouts(data):
    sets = []
    for key, callouts in data.items():
        rows = ',\n'.join('    ' + json.dumps(c, ensure_ascii=False) for c in callouts)
        sets.append(f'  {json.dumps(key)}: [\n{rows}\n  ]')
    callouts_path.write_text('{\n' + ',\n'.join(sets) + '\n}\n')


def as_tuples(callouts):
    return [(c['name'], [tuple(p) for p in c['points']],
             tuple(c['label']) if isinstance(c['label'], list) else c['label'],
             c['tx'], c['ty'], c['anchor']) for c in callouts]


# Front images carry labels on the left, back images on the right. All callouts are in final canvas coordinates.
text = dict(font=88, detail_font=66, detail_dy=75)
case_canvas = (1840, 2912)
board_text = dict(font=46, detail_font=35, detail_dy=40)
board_canvas = (1060, 2001)
SETS = {
    'case_front': ('remote-controls-annotated', case_canvas, 'case-annotated-front.png', (1.35, 887, 40),
                   dict(trim=True, **text)),
    'case_back': ('remote-back-annotated', case_canvas, 'case-annotated-back.png', (1.28, 30, 114),
                  dict(trim=True, **text)),
    'board_front': ('board-front-annotated', board_canvas, 'board-3d-rotated-top.png', (1.0, 500, 30), board_text),
    'board_back': ('board-back-annotated', board_canvas, 'board-3d-rotated-bottom.png', (1.0, 30, 30), board_text),
}


def render_set(key, data, suffix='', text_color=black, ids=False, write=True):
    output, canvas, source, placement, options = SETS[key]
    return render(f'{output}{suffix}.svg', canvas, source, placement, as_tuples(data[key]),
                  text_color=text_color, ids=ids, write=write, **options)


def render_editor(key, data=None):
    return render_set(key, data or load_callouts(), ids=True, write=False)


def render_all(data=None):
    data = data or load_callouts()
    for suffix, color in (('', black), ('-dark', light)):
        for key in SETS:
            render_set(key, data, suffix, color)


if __name__ == '__main__':
    render_all()
