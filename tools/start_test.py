#!/usr/bin/env python3
"""python3 tools/start_test.py T1 T2 ... : press START at frame T, report when the select screen mode ($14=1) begins."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
flags = [a for a in sys.argv[1:] if a.startswith('-')]
for t in [int(a) for a in sys.argv[1:] if not a.startswith('-')]:
    e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
    try:
        e.frame(t); e.command('CONSOL start'); e.frame(4); e.command('CONSOL')
        res = None
        for i in range(0, 400, 10):
            e.frame(10)
            z = e.peek(0x13, 3)
            if z[1] == 1: res = i + 10; break
        r = e.registers()
        if res is None and '-p' in flags:
            import collections
            labs = sorted((int(p[1], 16), p[2].lstrip('.')) for p in (l.split() for l in open('build/labels.txt')) if not p[2].lstrip('.').startswith('@'))
            nm = lambda pc: ([n for a, n in labs if a <= pc] or ['?'])[-1]
            h = collections.Counter()
            for i in range(1500):
                e.command('CYCLES 1931'); pc = e.registers()['PC']; mp = e.peek(0xFCC7, 1)[0]
                k = ('res ' + nm(pc)) if pc >= 0xE000 or 0x1000 <= pc < 0x1300 else ('cart %02X %s' % (mp, nm(pc) if mp in (9, 12) else '%04X' % (pc & 0xFFC0))) if 0x8000 <= pc < 0xC000 else 'game %04X' % (pc & 0xFFC0)
                h[k] += 1
            for k, v in h.most_common(25): print('   %-30s %5.1f%%' % (k, v / 15))
        print(t, 'select mode after', res, 'zp13-15', z.hex(), 'bank', e.peek(0xF080, 1).hex(), 'PC %04X' % r['PC'], 'stack', e.peek(0x1F0, 16).hex(), flush=True)
    finally:
        e.close()
