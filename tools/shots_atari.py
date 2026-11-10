#!/usr/bin/env python3
"""python3 tools/shots_atari.py PREFIX F1 F2 ... : screenshots (frames are step sizes)."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    t = 0
    for n in map(int, sys.argv[2:]):
        e.frame(n); t += n; e.screenshot(f'{sys.argv[1]}{t:05d}.png')
finally:
    e.close()
