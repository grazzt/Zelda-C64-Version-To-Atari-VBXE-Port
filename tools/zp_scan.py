#!/usr/bin/env python3
"""python3 tools/zp_scan.py [CART] [LO HI] : static scan of the game banks (0-7) for instructions in plausible code whose
zero-page operand falls in LO..HI (default $D2-$E1). Note: plausible-code hits are mostly data; compare the count with
other 16-byte blocks. The real check is tools/host/explore.py (every zero-page write trapped, poison test). zp, zp,X / zp,Y and the
indirect (zp,X) / (zp),Y pointers, which touch zp and zp+1. Exit status 1 if any is found: then the game may use the
renderer's zero page (the host-model check only covered the phases it played)."""
import sys, os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
sys.path.insert(0, _KIT + '/tools/c64')
from code6502 import OPCODES
LEN = {'imp': 1, 'acc': 1, 'imm': 2, 'zp': 2, 'zpx': 2, 'zpy': 2, 'indx': 2, 'indy': 2, 'rel': 2, 'abs': 3, 'absx': 3, 'absy': 3, 'ind': 3}
ZPM = ('zp', 'zpx', 'zpy', 'indx', 'indy')


def plausible(img, off, back=16, need=3):
    for start in range(max(0, off - back), off):
        o, k = start, 0
        while o < off and img[o] in OPCODES:
            o += LEN.get(OPCODES[img[o]][1], 3); k += 1
        if o == off and k >= need: return True
    return False


def main():
    a = sys.argv[1:]
    car = open(a[0] if a else 'build/zelda.car', 'rb').read()[16:]
    lo, hi = (int(a[1], 16), int(a[2], 16)) if len(a) > 2 else (0xD2, 0xE1)
    hits = []
    for b in range(8):
        img = car[b * 0x4000:(b + 1) * 0x4000]
        for off in range(len(img) - 1):
            if img[off] not in OPCODES: continue
            mn, mode = OPCODES[img[off]]
            if mode not in ZPM: continue
            z = img[off + 1]
            top = z + 1 if mode in ('indx', 'indy') else z
            if top >= lo and z <= hi and plausible(img, off):
                hits.append((b, 0x8000 + off, mn, mode, z))
    for h in hits: print('bank %d $%04X %s %s $%02X' % h)
    print('%d instruction(s) in plausible code touch $%02X-$%02X' % (len(hits), lo, hi))
    sys.exit(1 if hits else 0)


if __name__ == '__main__':
    main()
