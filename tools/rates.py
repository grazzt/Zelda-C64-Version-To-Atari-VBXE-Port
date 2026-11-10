#!/usr/bin/env python3
"""(build with ZDEFS=LOOPCOUNT) python3 tools/rates.py STEP... : per-60-frame counters (shifts, composes, band derivations,
VBI renders, idle renders, main-loop passes, cells drawn) at frame points."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
def w(a): b = e.peek(a, 2); return b[0] | b[1] << 8
try:
    t = 0
    for step in map(int, sys.argv[1:]):
        e.frame(step - 60); t += step - 60
        a = e.peek(0xF6F8, 6); c = w(0xF6F0); e.frame(60); t += 60; b = e.peek(0xF6F8, 6)
        d = [(b[i] - a[i]) % 256 for i in range(6)]
        print('frame %5d shifts %2d compose %2d derive %3d VBI %d idle %2d passes %2d cells %4d bands %d' % (t, *d, (w(0xF6F0) - c) % 65536, e.peek(0xF8F8, 1)[0]))
finally:
    e.close()
