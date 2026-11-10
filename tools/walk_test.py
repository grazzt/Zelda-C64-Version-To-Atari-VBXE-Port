#!/usr/bin/env python3
"""python3 tools/walk_test.py [-s PREFIX] "up*160 w*30 down*160 ..." : from the first overworld screen (boot_game), hold
each joystick direction N frames (w = centre); prints every change of the game mode ($14: 5 playing, 6/7 screen scroll,
4 scroll end, $10 cave) with the frame, sprite 0 (Link) after each step, and with -s a screenshot PREFIXnnnnn.png after each step.
Same script syntax as tools/host/audit.py, so a route found in the host model can be replayed (frame counts differ)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game

args = sys.argv[1:]
pre = None
if args[0] == '-s': pre = args[1]; args = args[2:]
e = boot_game()
try:
    f, prev, scrolls = 0, None, 0
    for st in args[0].split():
        d, _, n = st.partition('*')
        e.command('JOY 0 ' + ('center' if d == 'w' else d))
        for i in range(int(n or 4) // 2):
            e.frame(2); f += 2
            md = e.peek(0x14, 1)[0]
            if md != prev:
                print(f, st, 'mode %02X' % md); prev = md
                if md == 4: scrolls += 1
        v = e.peek(0xF000, 0x11)
        print('  after', st, 'sprite 0 at', v[0] | (v[0x10] & 1) << 8, v[1])
        if pre: e.screenshot(f'{pre}{f:05d}.png')
    e.command('JOY 0 center')
    print('frames', f, 'scrolls completed', scrolls, 'final mode %02X' % prev)
finally:
    e.close()
