#!/usr/bin/env python3
"""python3 tools/render_atari_ram.py RAMDUMP.bin OUT.png : render an Atari RAM dump (64K) with the VIC model (regs from the shadow at $F000)."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
import sys
sys.path.insert(0, os.path.join(_REPO, 'tools/host'))
from c64host import C64
from vicrender import render
d = open(sys.argv[1], 'rb').read()
m = C64(os.path.join(_REPO, 'assets/original/Zelda_C64.crt'))
m.ram[:] = d[:0x10000]
m.vic[:] = d[0xF000:0xF040]
m.color[:] = bytes(b & 15 for b in d[0xD800:0xDC00])
m.cia[1][0] = d[0xDD00]; m.cia[1][2] = d[0xDD02]
render(m).save(sys.argv[2])
