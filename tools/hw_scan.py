#!/usr/bin/env python3
"""python3 tools/hw_scan.py [CART] : static scan of the patched game banks (0-7) of build/zelda.car for instructions that
still address the C64's VIC ($D000-$D03F), SID ($D400-$D41F) or CIA1 ($DC00-$DC0F) directly, in plausible code (a
clean instruction stream of 3+ instructions leads to it), and indexed stores whose base + X/Y can reach them (bank 7
$83FC STA $CFFE,X: X from a table selects the VIC register). On the Atari $D000 is GTIA and $D400 ANTIC: an unpatched SID
write can move the display list or switch NMIs off (the sword/hit freeze: bank 0 $96AC STA $D412). Exit status 1 if
any site is found that is not in KNOWN_OK; review each hit by disassembly, then patch it (patches.py STATIC_SITES)."""
import sys, os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
sys.path.insert(0, _KIT + '/tools/c64')
from code6502 import OPCODES

KNOWN_OK = {
    (0, 0x802A),                                                  # C64 boot stub (not replayed: patches.SKIP_PC)
    (0, 0x9A88), (0, 0x9A8B), (0, 0x9A92), (0, 0x9A95),           # keyboard column selects/reads -> RAM images (input.s)
    (7, 0x84A8), (7, 0x84AB), (7, 0x84BA), (7, 0x84BF), (7, 0x84C2), (7, 0x84CC), (7, 0x84CF), (7, 0x84E7), (7, 0x84EC),
    (7, 0x8115), (7, 0x811B),                                     # CIA interrupt control at init: plain RAM on the Atari
    (0, 0xAE75), (6, 0xBC25),                                     # data that only looks like code (BRK runs around it)
    (1, 0xAC66),                                                  # STA $CFFD,Y: Y 0/1 (RAM)
    (7, 0x9EC2), (7, 0x9ECB), (7, 0x9F06), (7, 0xAD59), (7, 0xAD64), (7, 0xAD6A), (7, 0xADCD), (7, 0xADD2),
                                                                  # RAM arrays at $CFE2-$CFEA indexed by an object slot
}
LEN = {'imp': 1, 'acc': 1, 'imm': 2, 'zp': 2, 'zpx': 2, 'zpy': 2, 'izx': 2, 'izy': 2, 'indx': 2, 'indy': 2, 'rel': 2, 'abs': 3, 'absx': 3, 'absy': 3, 'ind': 3}


def plausible(img, off, back=16, need=3):
    for start in range(max(0, off - back), off):
        o, k = start, 0
        while o < off and img[o] in OPCODES:
            o += LEN.get(OPCODES[img[o]][1], 3); k += 1
        if o == off and k >= need: return True
    return False


def main():
    car = open(sys.argv[1] if len(sys.argv) > 1 else 'build/zelda.car', 'rb').read()[16:]
    bad = 0
    for b in range(8):
        img = car[b * 0x4000:(b + 1) * 0x4000]
        for off in range(len(img) - 2):
            if img[off] not in OPCODES: continue
            mn, mode = OPCODES[img[off]]
            if mode not in ('abs', 'absx', 'absy') or mn in ('JMP', 'JSR'): continue
            t = img[off + 1] | img[off + 2] << 8
            hw = lambda a: 0xD000 <= a <= 0xD03F or 0xD400 <= a <= 0xD41F or 0xDC00 <= a <= 0xDC0F
            reach = hw(t) or (mode in ('absx', 'absy') and t < 0xD000 and t + 255 >= 0xD000 and mn.startswith('ST'))
            if reach and plausible(img, off):
                if (b, 0x8000 + off) in KNOWN_OK: continue
                print('bank %d $%04X %s %s $%04X' % (b, 0x8000 + off, mn, mode, t)); bad += 1
    print('%d unpatched hardware site(s)' % bad)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
