#!/usr/bin/env python3
"""python3 tools/flicker_game.py N [OUTDIR] : on the first overworld screen, N consecutive frames; changed pixels per frame
(Link standing still, so any change is flicker), frames saved as OUTDIR/fNN.png."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
from PIL import Image, ImageChops
n = int(sys.argv[1]); out = sys.argv[2] if len(sys.argv) > 2 else 'build/fl'
os.makedirs(out, exist_ok=True)
e = boot_game()
try:
    prev = None
    for i in range(n):
        e.frame(1); p = f'{out}/f{i:02d}.png'; e.screenshot(p)
        im = Image.open(p).convert('RGB')
        if prev is not None:
            d = ImageChops.difference(im, prev).convert('L').point(lambda v: 255 if v else 0)
            bb = d.getbbox(); cnt = sum(1 for v in d.getdata() if v)
            print(i, 'changed', cnt, 'bbox', bb, 'frame_ctr', e.peek(0xF082, 1).hex(), 'passes', e.peek(0xC105, 1).hex(), 'r_blank', e.peek(0xFD2D,1).hex(), 'VB_CORE?', flush=True)
        prev = im
finally:
    e.close()
