#!/usr/bin/env python3
"""python3 tools/hangprof.py SCRIPT [N] : run a tools/play.py-style prefix (w/start/joy only), then sample the PC N times
(CYCLES steps) and print a histogram by resident label (RAM >= $E000), cart bank + label, or game address/64."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys, collections
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
labs = sorted((int(p[1], 16), p[2].lstrip('.')) for p in (l.split() for l in open('build/labels.txt')) if not p[2].lstrip('.').startswith('@'))
def nm(pc):
    g = [n for a, n in labs if a <= pc]; return g[-1] if g else '?'
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    for tok in sys.argv[1].split():
        if tok[0] == 'w': e.frame(int(tok[1:]))
        elif tok in ('start', 'select', 'option'): e.command(f'CONSOL {tok}'); e.frame(4); e.command('CONSOL')
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 1500
    h = collections.Counter()
    for i in range(N):
        e.command('CYCLES 1931'); pc = e.registers()['PC']
        mp = e.peek(0xFCC7, 1)[0]
        if pc >= 0xE000 or 0x1000 <= pc < 0x1300: k = 'res ' + nm(pc)
        elif 0x8000 <= pc < 0xC000: k = 'cart %02X %s' % (mp, nm(pc) if mp in (9, 12) else '%04X' % (pc & 0xFFC0))
        else: k = 'game %04X' % (pc & 0xFFC0)
        h[k] += 1
    for k, v in h.most_common(25): print('%-30s %5.1f%%' % (k, 100 * v / N))
finally:
    e.close()
