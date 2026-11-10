#!/usr/bin/env python3
"""python3 tools/walk_white.py [N] : in the overworld, walk left N/2 frames then right; near-white pixel count of the
playfield (below the HUD) per frame. Steady counts = no colour-split flicker; jumps of ~800+ = a white strip."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
from PIL import Image
n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
e = boot_game()
try:
    ws = []
    e.command('JOY 0 left')
    for i in range(n):
        if i == n // 2: e.command('JOY 0 right')
        e.frame(1); e.screenshot('build/ww.png'); im = Image.open('build/ww.png').convert('RGB'); px = im.load(); W, H = im.size
        ws.append(sum(1 for y in range(45, H) for x in range(W) if min(px[x, y]) > 200))
    e.command('JOY 0 center')
    base = sorted(ws)[len(ws) // 2]
    print('median', base, 'frames > median+300:', sum(1 for w in ws if w > base + 300), 'of', n)
    print(ws)
finally:
    e.close()
