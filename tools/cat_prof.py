#!/usr/bin/env python3
"""python3 tools/cat_prof.py START [N] : time split (render / game / game IRQ / resident hooks) and the top routines."""
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
glob = [(a, n) for a, n in labs if not n.startswith('.@')]
def nm(pc):
    g = [(a, n) for a, n in glob if a <= pc]; return g[-1][1] if g else '?'
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    e.frame(int(sys.argv[1])); N = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
    h = collections.Counter(); r = collections.Counter(); g = collections.Counter()
    for i in range(N):
        e.command('CYCLES 1931'); pc = e.registers()['PC']
        ren = e.peek(0xF06D, 1)[0]; girq = e.peek(0xF071, 1)[0]; nmi = e.peek(0xF07E, 1)[0]; act = e.peek(0xFCF0, 1)[0]
        bk = e.peek(0xF080, 1)[0]
        if (ren and not girq) or (nmi and not act):
            h['render'] += 1; r[nm(pc) if (0x8000 <= pc < 0xC000 or pc >= 0xF100) else 'x'] += 1
        elif pc >= 0xF100: h['resident'] += 1; r['(res) ' + nm(pc)] += 1
        elif 0x40C0 <= pc < 0x40E0: h['idle'] += 1
        else:
            h['game IRQ' if girq else 'game'] += 1; g['%s %04X' % (bk if 0x8000 <= pc < 0xC000 else '-', pc & 0xFF00)] += 1
    for k, v in h.most_common(): print('%-12s %4.1f%%' % (k, 100 * v / N))
    print('top:', ', '.join('%s %.1f%%' % (k, 100 * v / N) for k, v in r.most_common(14)))
    print('game:', ', '.join('%s %.1f%%' % (k, 100 * v / N) for k, v in g.most_common(12)))
finally:
    e.close()
