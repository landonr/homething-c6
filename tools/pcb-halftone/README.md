Open tuner.html to preview the artwork. The slider defaults specify the front preset. The backSettings object specifies the rear preset.

Use Python and Node.js to generate a board copy.

```sh
python3 tools/pcb-halftone/generate.py c6remote-kicad/c6remote.kicad_pcb /tmp/c6remote-halftone.kicad_pcb
```

The generator replaces the two ripple artwork groups. It uses the keepouts and board coordinates for this C6 revision.
