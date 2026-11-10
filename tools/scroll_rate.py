#!/usr/bin/env python3
"""python3 tools/scroll_rate.py [CART] [DIRS] : how smoothly the screen-to-screen scrolls look. For each direction (default
left,right,up,down; each from a fresh boot_game on the first overworld screen; down: from the screen north of it) hold it until the scroll starts (mode 6/7),
then up to N frames (SCROLL_N, default 130; until 5 frames after the scroll ends): a screenshot per frame. Prints the
number of frames whose picture changed, the longest run of frames without a change (a pause), the scroll's length in frames (mode 6/7 until mode 5; the C64 takes
~64 vertical / ~83 horizontal) and the game's main-loop passes ($17) per 60 frames during it."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
from PIL import Image, ImageChops

args = [a for a in sys.argv[1:]]
cart = args.pop(0) if args and args[0].endswith('.car') else None
dirs = (args[0] if args else 'left,right,up,down').split(',')
N = int(os.environ.get('SCROLL_N', '130'))
out = os.environ.get('SCROLL_OUT', 'build/_sr')
os.makedirs(out, exist_ok=True)
for d in dirs:
    e = boot_game(cart)
    try:
        e.frame(30)
        if d == 'down':                                   # (the start screen's south edge is blocked: go up and back)
            e.command('JOY 0 up')
            for i in range(600):
                e.frame(1)
                if e.peek(0x14, 1)[0] == 7: break
            while e.peek(0x14, 1)[0] != 5: e.frame(1)
            e.command('JOY 0 center'); e.frame(30)
        e.command('JOY 0 ' + d)
        for i in range(600):
            e.frame(1)
            if e.peek(0x14, 1)[0] in (6, 7): break
        else:
            print('%-5s no scroll (mode %02X)' % (d, e.peek(0x14, 1)[0])); continue
        e.command('JOY 0 center')
        prev = None; changed = 0; gap = 0; longest = 0; length = None; c0 = e.peek(0x17, 1)[0]; passes = 0
        gaps = []
        for i in range(N):
            if length is not None and i > length + 4: break   # (counted up to the scroll's end)
            e.frame(1)
            p = '%s/%s%03d.png' % (out, d, i); e.screenshot(p)
            im = Image.open(p).convert('RGB')
            if prev is not None:
                if ImageChops.difference(im, prev).getbbox():
                    changed += 1
                    if gap >= 6: gaps.append((i - gap, gap))
                    gap = 0
                else:
                    gap += 1; longest = max(longest, gap)
            prev = im
            c = e.peek(0x17, 1)[0]
            if length is None:
                passes += (c - c0) % 256
                if e.peek(0x14, 1)[0] == 5: length = i + 1
            c0 = c
        L = length or N
        n = min(N, (length or N) + 5) - 1
        print('%-5s changed %3d of %d  longest pause %2d  scroll %s frames  passes/60 %.1f  pauses>=6 (frame, len) %s' % (
            d, changed, n, longest, length if length else '>%d' % N, passes * 60 / L, gaps), flush=True)
    finally:
        e.close()
