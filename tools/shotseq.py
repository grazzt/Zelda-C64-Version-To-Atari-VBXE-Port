#!/usr/bin/env python3
"""python3 tools/shotseq.py START STEP N OUT.png : N screenshots STEP frames apart from START, as one contact sheet."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
from PIL import Image
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
ims = []
try:
    st, step, n = map(int, sys.argv[1:4]); e.frame(st)
    for i in range(n):
        e.screenshot('build/_seq.png'); ims.append(Image.open('build/_seq.png').convert('RGB')); e.frame(step)
finally:
    e.close()
w, h = ims[0].size; cols = 4
W = Image.new('RGB', (w * cols, h * ((n + cols - 1) // cols)))
for k, im in enumerate(ims): W.paste(im, ((k % cols) * w, (k // cols) * h))
W.save(sys.argv[4])
