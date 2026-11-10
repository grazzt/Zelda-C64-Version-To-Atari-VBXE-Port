#!/usr/bin/env python3
"""python3 tools/scroll_shots.py DIR [N] [STEP] : from the first overworld screen walk DIR (up/left/right/down) until the
screen scroll starts (mode 7), then take N screenshots STEP frames apart -> build/scroll_DIR.png (a grid).
Also reports frames in mode 7 and the BG shift count ($F6F8, LOOPCOUNT builds only)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
from PIL import Image
d = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 16; step = int(sys.argv[3]) if len(sys.argv) > 3 else 6
e = boot_game(); ims = []
try:
    e.command('JOY 0 ' + d)
    for i in range(600):
        e.frame(1)
        if e.peek(0x14, 1)[0] == 7: break
    t7 = 0
    for i in range(n):
        e.frame(step); e.screenshot('build/_s.png'); ims.append(Image.open('build/_s.png').copy())
        if e.peek(0x14, 1)[0] == 7: t7 += step
    print('mode 7 for about', t7, 'frames; mode now %02X' % e.peek(0x14, 1)[0], 'F6F8', e.peek(0xF6F8, 1)[0])
finally:
    e.close()
w, h = ims[0].size; ims = [i.resize((w // 2, h // 2)) for i in ims]; w, h = ims[0].size
out = Image.new('RGB', (w * 4, h * ((len(ims) + 3) // 4)))
for i, im in enumerate(ims): out.paste(im, ((i % 4) * w, (i // 4) * h))
out.save(f'build/scroll_{d}.png'); print('->', f'build/scroll_{d}.png')
