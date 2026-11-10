#!/usr/bin/env python3
"""python3 tools/pairseq.py START STEP N OUT.png : screenshot + VIC-model render of RAM (same moment) pairs, contact sheet."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari')); sys.path.insert(0, os.path.join(_REPO, 'tools/host'))
from altirra import Altirra
from PIL import Image
from c64host import C64
from vicrender import render
m = C64(os.path.join(_REPO, 'assets/original/Zelda_C64.crt'))
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
pairs = []
try:
    st, step, n = map(int, sys.argv[1:4]); e.frame(st)
    for i in range(n):
        e.screenshot('build/_p.png'); d = e.peek(0, 0x10000)
        m.ram[:] = d; m.vic[:] = d[0xF000:0xF040]; m.color[:] = bytes(b & 15 for b in d[0xD800:0xDC00]); m.cia[1][0] = d[0xDD00]; m.cia[1][2] = d[0xDD02]
        a = Image.open('build/_p.png').convert('RGB'); b = render(m).convert('RGB').resize(a.size)
        pairs.append((a, b)); e.frame(step)
finally:
    e.close()
w, h = pairs[0][0].size; cols = 4
W = Image.new('RGB', (w * cols, 2 * h * ((n + cols - 1) // cols)))
for k, (a, b) in enumerate(pairs):
    x = (k % cols) * w; y = (k // cols) * 2 * h; W.paste(a, (x, y)); W.paste(b, (x, y + h))
W.save(sys.argv[4])
