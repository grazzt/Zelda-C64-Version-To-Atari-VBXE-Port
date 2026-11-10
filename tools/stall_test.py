#!/usr/bin/env python3
"""python3 tools/stall_test.py N : N runs of boot_game(); main-loop passes per 60 frames in the game (0 = stalled)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
for i in range(int(sys.argv[1])):
    e = boot_game()
    try:
        p = e.peek(0xC105, 1)[0]; q = e.peek(0xF07C, 1)[0]; e.frame(60)
        z = e.peek(0x13, 3)
        print('run', i, 'passes/60', (e.peek(0xC105, 1)[0] - p) & 255, 'irqs/60', (e.peek(0xF07C, 1)[0] - q) & 255,
              'zp13-15', z.hex(), flush=True)
        if z[1] != 5: e.screenshot(f'build/stall{i}.png'); print('   shot build/stall%d.png' % i)
    finally:
        e.close()
