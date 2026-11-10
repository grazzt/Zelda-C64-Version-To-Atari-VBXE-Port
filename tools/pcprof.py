#!/usr/bin/env python3
"""(build with ZDEFS=PCPROF) python3 tools/pcprof.py START N : where the CPU is at each VBI, N frames from START."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys, collections
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    e.frame(int(sys.argv[1])); h = collections.Counter(); n = int(sys.argv[2])
    for i in range(n):
        e.frame(1); b = e.peek(0xF6A0, 4); pc = b[0] << 8 | b[1]; h[(b[3] if 0x8000 <= pc < 0xC000 else -1, pc & 0xFFC0)] += 1
    for (bk, a), c in h.most_common(30): print('bank %2d %04X-%04X %3d%%' % (bk, a, a + 63, 100 * c // n))
finally:
    e.close()
