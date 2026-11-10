#!/usr/bin/env python3
"""python3 tools/loop_rate.py : game main-loop iterations per 60 frames at several points (needs a build with the
hook_gfx counter, ZDEFS=LOOPCOUNT). The C64 original does 60."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    out = []
    for t in map(int, (sys.argv[1:] or ['600', '300', '600', '600', '600'])):
        e.frame(t); a = e.peek(0xF6F2, 1)[0]; e.frame(60); b = e.peek(0xF6F2, 1)[0]; out.append((b - a) % 256)
    print('main-loop iterations/60 frames:', out)
finally:
    e.close()
