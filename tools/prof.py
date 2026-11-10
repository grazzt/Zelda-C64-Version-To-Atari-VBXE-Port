#!/usr/bin/env python3
"""python3 tools/prof.py T1 T2 ... : needs ZDEFS='LOOPCOUNT PROF'. Per window of 60 frames: render time, raster-hook time, main-loop rate."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
def rd(a): b = e.peek(a, 2); return b[0] | b[1] << 8
try:
    t = 0
    for step in map(int, sys.argv[1:] or ['600', '1200', '1200', '1200']):
        e.frame(step); t += step
        r0, h0, l0 = rd(0xF0E2), rd(0xF0E4), e.peek(0xF6F2, 1)[0]
        e.frame(60); t += 60
        r1, h1, l1 = rd(0xF0E2), rd(0xF0E4), e.peek(0xF6F2, 1)[0]
        rl = ((r1 - r0) & 0xFFFF) * 2 / 60; hl = ((h1 - h0) & 0xFFFF) * 2 / 60
        print('frame %5d: render %3.0f lines/frame (%2.0f%%)  raster hook %3.0f lines (%2.0f%%)  main loop %2d/60' % (t, rl, rl / 2.62, hl, hl / 2.62, (l1 - l0) % 256))
finally:
    e.close()
