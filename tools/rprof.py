#!/usr/bin/env python3
"""python3 tools/rprof.py START [N] : where idle renders spend their time (renderer routines; resident by address)."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys, collections, re
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
names = set(re.findall(r'^([a-z_A-Z0-9]+):', open('atari/src/render.s').read(), re.M))
rnames = set(re.findall(r'^([a-z_A-Z0-9]+):', open('atari/src/resident.s').read(), re.M))
labs = []; rl = []
for ln in open('build/labels.txt'):
    p = ln.split(); a = int(p[1], 16); n = p[2].lstrip('.')
    if n in names and 0x8000 <= a < 0xC000: labs.append((a, n))
    if n in rnames and a >= 0xE000: rl.append((a, n))
labs.sort(); rl.sort()
def nm(pc, L):
    g = [n for a, n in L if a <= pc]; return g[-1] if g else '?'
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    e.frame(int(sys.argv[1])); N = int(sys.argv[2]) if len(sys.argv) > 2 else 2500
    r = collections.Counter(); n = 0
    for i in range(N):
        e.command('CYCLES 1931'); pc = e.registers()['PC']; n += 1
        if e.peek(0xF06D, 1)[0] and not e.peek(0xF071, 1)[0]:
            r[nm(pc, labs) if 0x8000 <= pc < 0xC000 else 'res ' + nm(pc, rl)] += 1
    tot = sum(r.values())
    print('render share %.1f%%' % (100 * tot / n))
    for k, v in r.most_common(22): print('   %-24s %4.1f%% of render' % (k, 100 * v / tot))
finally:
    e.close()
