#!/usr/bin/env python3
"""python3 tools/stages.py T [T...] : average renderer stage durations (scanlines) over 60 frames after each point."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys, statistics
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    t = 0
    for step in map(int, sys.argv[1:]):
        e.frame(step); t += step; rows = []
        for i in range(60):
            e.frame(1); t += 1
            if e.peek(0xF07E, 1)[0]: continue
            s = list(e.peek(0xF0B5, 5)); rows.append([(s[k + 1] - s[k]) % 131 * 2 for k in range(4)])
        if rows:
            print('frame %5d: lines avg palette %d atlas %d scan %d compose %d  (max scan %d compose %d) ys %d' % (
                t, *[round(statistics.mean(x[k] for x in rows)) for k in range(4)], max(x[2] for x in rows), max(x[3] for x in rows), e.peek(0xF011, 1)[0] & 7))
finally:
    e.close()
