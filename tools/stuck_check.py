#!/usr/bin/env python3
"""python3 tools/stuck_check.py [frames] : run build/zelda.car; report whether the game's IRQ count stops or the stack collapses."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
n = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
start = int(sys.argv[2]) if len(sys.argv) > 2 else 600
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    e.frame(start); last = e.peek(0xF07C, 1)[0]; still = 0; res = 'ok'
    for k in range(n):
        e.frame(1); c = e.peek(0xF07C, 1)[0]; r = e.registers()
        still = still + 1 if c == last else 0; last = c
        if still >= 30: res = 'IRQs stopped at %d' % (start + 1 + k); break
        if (r['S'] < 0x10) or (r['S'] < 0xA0 and not e.peek(0xFCF0, 1)[0]): res = 'stack collapsed at %d' % (start + 1 + k); break   # the renderer runs on $0100-$019F
    print(res)
finally:
    e.close()
