#!/usr/bin/env python3
"""python3 tools/edge_test.py [PREFIX] : walk right off the first overworld screen; report the game mode ($14) over time
and whether Link's screen changed (screenshots PREFIXnn.png). Mode 5 = playing, 7 = screen scroll."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
pre = sys.argv[1] if len(sys.argv) > 1 else 'build/edge'
e = boot_game()
try:
    e.command('JOY 0 right'); modes = []
    for i in range(12):
        e.frame(30); modes.append(e.peek(0x13, 3).hex()); e.screenshot(f'{pre}{i:02d}.png')
    e.command('JOY 0 center')
    print('zp13-15 every 30 frames:', ' '.join(modes))
finally:
    e.close()
