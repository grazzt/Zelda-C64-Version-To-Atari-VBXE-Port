#!/usr/bin/env python3
"""python3 tools/cprof.py START N [STEP] : unbiased PC profile: N samples every STEP CPU cycles (default 7919), from frame START."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys, collections
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
labs = []
for ln in open('build/labels.txt'):
    p = ln.split(); labs.append((int(p[1], 16), p[2]))
labs.sort()
def name(a):
    c = [n for x, n in labs if x <= a]; return c[-1] if c else ''
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    e.frame(int(sys.argv[1])); n = int(sys.argv[2]); st = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != '-x' else 7919
    h = collections.Counter(); hf = collections.Counter()
    for i in range(n):
        e.command('CYCLES %d' % st); pc = e.registers()['PC']; bk = e.peek(0xF080, 1)[0]
        if e.peek(0xF06D, 1)[0] and not e.peek(0xF071, 1)[0]: bk = e.peek(0xFF45, 1)[0]   # an idle render: renderer bank mapped
        key = (bk if 0x8000 <= pc < 0xC000 else -1, pc & (0xFFFF if '-x' in sys.argv else 0xFFC0)); h[key] += 1
        if pc >= 0xF100 or bk == 9: hf[name(pc)] += 1
    for (bk, a), c in h.most_common(40 if '-x' in sys.argv else 25): print('bank %2d %04X %5.1f%%' % (bk, a, 100 * c / n))
    tot = collections.Counter()
    for (bk, a), c in h.items():
        tot['renderer' if bk in (9, 10, 11) else 'resident' if a >= 0xF100 else 'idle wait' if 0x40C0 <= a < 0x40E0 else 'game IRQ (C4xx-CFxx)' if 0xC400 <= a < 0xD000 else 'game'] += c
    print('totals:', ', '.join('%s %d%%' % (k, 100 * v // n) for k, v in tot.most_common()))
    print('resident:', ', '.join('%s %d%%' % (k, 100 * v // n) for k, v in hf.most_common(12)))
finally:
    e.close()
