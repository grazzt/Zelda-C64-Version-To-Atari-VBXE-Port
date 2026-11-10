#!/usr/bin/env python3
"""python3 tools/first_stale.py START END : step frame by frame; report the first frame where a cell is 'believed up to date' but its BG pixels are wrong."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
def vram(a, n):
    out = b''
    while n:
        k = min(n, 0x1000 - (a & 0xFFF)); e.poke(0xD65F, 0x80 + (a >> 12)); out += e.peek(0xE000 + (a & 0xFFF), k); a += k; n -= k
    return out
try:
    e.frame(int(sys.argv[1]))
    for f in range(int(sys.argv[1]), int(sys.argv[2])):
        e.frame(1)
        if e.peek(0xF07E, 1)[0] or e.peek(0xF07D, 1)[0]: continue
        ram = e.peek(0, 0x10000); e.poke(0xD65E, 0xE8)
        d18 = ram[0xF018]; scr = (d18 >> 4) * 0x400; chars = (d18 & 14) * 0x400; mcm = ram[0xF016] & 0x10
        bg = vram(0x20000 + 8 * 320, 320 * 200); shs = vram(0x800, 1000); shc = vram(0xC00, 1000)
        bad = []
        for r in range(25):
            for c in range(40):
                ch = ram[scr + r * 40 + c]; col = ram[0xD800 + r * 40 + c] & 15
                exp = []
                for y in range(8):
                    b = ram[chars + ch * 8 + y]; row = []
                    if mcm and col & 8:
                        for x in range(4):
                            code = (b >> (6 - 2 * x)) & 3; v = [0, 2, 3, 4 * ((col & 7) + 1) + 3][code]; row += [v, v]
                    else:
                        for x in range(8): row.append(4 * (col + 1) + 3 if (b >> (7 - x)) & 1 else 0)
                    exp.append(bytes(row))
                got = [bg[(r * 8 + y) * 320 + c * 8:(r * 8 + y) * 320 + c * 8 + 8] for y in range(8)]
                if got != exp and shs[r * 40 + c] == ch and shc[r * 40 + c] == col: bad.append((r, c, ch, col))
        if bad:
            print('frame', f, 'ys', ram[0xF011] & 7, 'first stale cells', bad[:6], 'count', len(bad)); break
    else:
        print('no stale cells found')
finally:
    e.close()
