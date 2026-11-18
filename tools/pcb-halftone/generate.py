from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
import xml.etree.ElementTree as ET
import argparse
import re
import subprocess
from tempfile import TemporaryDirectory

parser = argparse.ArgumentParser(description='Apply the saved halftone presets to a KiCad board copy.')
parser.add_argument('board', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--preset', help='Use a named preset from settings.json.')
args = parser.parse_args()
if args.board.resolve() == args.output.resolve():
    parser.error('Specify a separate output file.')
source_dir = Path(__file__).resolve().parent
scratch = TemporaryDirectory(prefix='c6-halftone-')
work = Path(scratch.name)
command = [
    'node', str(source_dir / 'extract.mjs'), str(source_dir / 'tuner.html'),
    str(source_dir / 'settings.json'), str(work),
]
if args.preset is not None:
    command.append(args.preset)
subprocess.run(command, check=True)
specs = [
    ('F.SilkS', 'Front ripple artwork', work/'front.svg', '34.837455', 1),
    ('B.SilkS', 'Back ripple artwork', work/'back.svg', '71.819855', -1),
]

def strip_artwork(source):
    ids = set()
    for layer,name,*_ in specs:
        group = re.search(rb'^\t\(group "'+name.encode()+rb'"\n.*?^\t\)\n',source,re.M|re.S)
        assert group
        members = re.findall(rb'^\t\t\t"([0-9a-f-]+)"$',group[0],re.M)
        assert members and len(set(members)) == len(members)
        assert not ids.intersection(members)
        ids.update(members)
        source = source[:group.start()]+source[group.end():]
    def strip_circle(match):
        shape = match[0]
        uid = re.search(rb'\(uuid "([0-9a-f-]+)"\)',shape)
        if uid and uid[1] in ids:
            ids.remove(uid[1])
            return b''
        return shape
    source = re.sub(rb'^\t\(gr_circle\n.*?^\t\)\n',strip_circle,source,flags=re.M|re.S)
    assert not ids
    return source

original = strip_artwork(args.board.read_bytes())
shapes = []
groups = []
all_ids = set()

def uid(name):
    value = str(uuid5(NAMESPACE_URL, f'homeThing-c6:silkscreen-ripples:{name}'))
    assert value not in all_ids and value.encode() not in original
    all_ids.add(value)
    return value

for layer, name, source, x0, direction in specs:
    xml = ET.parse(source)
    dots = [tuple(Decimal(dot.attrib[key]) for key in ('cx','cy','r'))
            for dot in xml.getroot().iter('{http://www.w3.org/2000/svg}circle')]
    assert len(dots) == len(set(dots))
    members = []
    for x,y,r in sorted(dots, key=lambda item: (item[1],item[0],item[2])):
        shape_id = uid(f'{layer}:{x}:{y}:{r}')
        members.append(shape_id)
        center_x = Decimal(x0) + direction*x
        center_y = Decimal('28.214') + y
        shapes.append(
            f'\t(gr_circle\n'
            f'\t\t(center {center_x} {center_y})\n'
            f'\t\t(end {center_x + r} {center_y})\n'
            f'\t\t(stroke\n'
            f'\t\t\t(width 0)\n'
            f'\t\t\t(type solid)\n'
            f'\t\t)\n'
            f'\t\t(fill yes)\n'
            f'\t\t(layer "{layer}")\n'
            f'\t\t(uuid "{shape_id}")\n'
            f'\t)\n'
        )
    groups.append(f'\t(group "{name}"\n\t\t(uuid "{uid(layer)}")\n\t\t(members\n' +
                  ''.join(f'\t\t\t"{member}"\n' for member in sorted(members)) +
                  '\t\t)\n\t)\n')
    bins = {}
    min_gap = Decimal('1')
    for x,y,r in dots:
        bx,by = int(x),int(y)
        for i in range(bx-1,bx+2):
            for j in range(by-1,by+2):
                for px,py,pr in bins.get((i,j),()):
                    distance = ((x-px)**2+(y-py)**2).sqrt()
                    min_gap = min(min_gap,distance-r-pr)
        bins.setdefault((bx,by),[]).append((x,y,r))
    assert min_gap >= Decimal('.10')
    print(f'{layer}: {len(dots)} circles, diameter {min(p[2] for p in dots)*2} to {max(p[2] for p in dots)*2} mm, min gap {min_gap:.3f} mm')

geometry = ''.join(shapes).encode()
grouping = ''.join(groups).encode()
geom_marker = b'\n\t(segment\n'
group_marker = b'\n\t(embedded_fonts no)\n'
assert original.count(group_marker) == 1 and geom_marker in original
candidate = original.replace(geom_marker, b'\n'+geometry+geom_marker[1:], 1).replace(group_marker, b'\n'+grouping+group_marker[1:], 1)
assert strip_artwork(candidate) == original
args.output.write_bytes(candidate)
scratch.cleanup()
