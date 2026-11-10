#!/usr/bin/env python3
"""python3 tools/perf_walk.py [CART] : normal-play rates. From the first overworld screen, 300 frames of walking about
(left/right/up/down within the screen, no scrolls) and 120 frames standing; prints the game's main-loop passes ($17,
the C64 does 60 per 60 frames) and the display flips (r_hidden) per 60 frames."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
e = boot_game(sys.argv[1] if len(sys.argv) > 1 else None)
try:
    e.frame(60)
    def run(moves):
        n = 0; fl = 0; h = e.peek(0xF084, 1)[0]; c0 = e.peek(0x17, 1)[0]; passes = 0; modes = set()
        for d, k in moves:
            e.command('JOY 0 ' + d)
            for i in range(k):
                e.frame(1); n += 1
                x = e.peek(0xF084, 1)[0]
                if x != h: fl += 1; h = x
                c = e.peek(0x17, 1)[0]; passes += (c - c0) % 256; c0 = c; modes.add(e.peek(0x14, 1)[0])
        if modes != {5}: print('  (left the screen: game modes %s; rates not comparable)' % ' '.join('%02X' % m for m in sorted(modes)))
        e.command('JOY 0 center')
        return n, passes * 60 / n, fl * 60 / n
    n, p, f = run([('left', 30), ('right', 30), ('up', 20), ('down', 20), ('right', 30), ('left', 30)] * 2 + [('center', 60)])
    print('walking %d frames: passes/60 %.1f flips/60 %.1f' % (n, p, f))
    n, p, f = run([('center', 120)])
    print('standing %d frames: passes/60 %.1f flips/60 %.1f' % (n, p, f))
finally:
    e.close()
