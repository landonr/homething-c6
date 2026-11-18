Generate a PCB copy with Python and Node.js.

```sh
python3 tools/pcb-halftone/generate.py c6remote-kicad/c6remote.kicad_pcb /tmp/c6remote-halftone.kicad_pcb
```

The generator uses the front and back settings in `settings.json`. To use a saved preset, add `--preset 'Preset 8'`. The generator replaces the ripple artwork groups in the output copy. It uses keepouts and coordinates for this C6 revision.

The front and back PNGs show the current settings.
