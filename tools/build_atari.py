#!/usr/bin/env python3
"""Build the Atari MegaCart: EF banks 0-7 (patched) + Atari banks 8-15 -> build/zelda.car (256 KB, type 30)."""
import os, struct, subprocess, sys
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
KIT = Path(_KIT)
sys.path.insert(0, str(ROOT / 'tools/host'))
from c64host import load_crt, C64
import patches, pickle
from c64host import ROMDIR
host_rom = lambda n: ROMDIR / n
OUT = ROOT / 'build'; OUT.mkdir(exist_ok=True)

def asm():
    srcs = sorted((ROOT / 'atari/src').glob('*.s')); objs = []
    for s in srcs:
        o = OUT / (s.stem + '.o'); subprocess.check_call([str(KIT / 'local/bin/ca65'), '-g', *[f'-D{d}' for d in os.environ.get('ZDEFS', '').split() if d], '-I', str(ROOT / 'atari/src'), str(s), '-o', str(o)]); objs.append(str(o))
    subprocess.check_call([str(KIT / 'local/bin/ld65'), '-C', str(ROOT / 'atari/atari.cfg'), '-o', str(OUT / 'atari'), '-m', str(OUT / 'map.txt'), '-Ln', str(OUT / 'labels.txt'), *objs])
    return [(OUT / f'atari.{n}').read_bytes() for n in ('b8', 'b9', 'b12', 'eapi')]

ROWF = 0xF640            # must match atari.inc
SCR, SHS_W, COLRAM, SHC_W = 0x0800, 0xE800, 0xD800, 0xEC00


def gen_compare(base, colour, ryield):
    """Unrolled compare of all 1000 cells against the VBXE-window shadows; sets ROWF[r]=1 for each row with a difference
    (the rest of that row is skipped). Characters: LDA scr / CMP shadow. Colours: LDA col / AND #$0F / CMP shadow.
    Rows 5, 10, 15 and 20 start with JSR ryield (the main loop may need the CPU: one half takes ~100 scanlines)."""
    cell = 13 if colour else 11
    yrow = {5, 10, 15, 20}
    starts = []
    a = base
    for r in range(25):
        starts.append(a)
        a += (3 if r in yrow else 0) + 40 * cell
    rts_at = a
    stub_base = rts_at + 1                                   # after the final RTS
    code = bytearray()
    for r in range(25):
        stub = stub_base + r * 8
        if r in yrow:
            code += bytes([0x20, ryield & 0xFF, ryield >> 8])
        for c in range(40):
            k = r * 40 + c
            if colour:
                code += bytes([0xAD, (COLRAM + k) & 0xFF, (COLRAM + k) >> 8, 0x29, 0x0F,
                               0xCD, (SHC_W + k) & 0xFF, (SHC_W + k) >> 8])
            else:
                code += bytes([0xAD, (SCR + k) & 0xFF, (SCR + k) >> 8, 0xCD, (SHS_W + k) & 0xFF, (SHS_W + k) >> 8])
            code += bytes([0xF0, 0x03, 0x4C, stub & 0xFF, stub >> 8])
    assert base + len(code) == rts_at
    code += b'\x60'                                          # RTS
    for r in range(25):
        nxt = starts[r + 1] if r < 24 else rts_at              # next row (or the RTS after row 24)
        code += bytes([0xA9, 0x01, 0x8D, (ROWF + r) & 0xFF, (ROWF + r) >> 8, 0x4C, nxt & 0xFF, nxt >> 8])
    return bytes(code)


def main():
    roml, romh = load_crt(ROOT / 'assets/original/Zelda_C64.crt')
    banks = [bytearray(roml[b] + romh[b]) for b in range(8)]
    b8, b9, b12, eapi = asm()
    labs = patches.read_labels(OUT / 'labels.txt')
    host = C64(ROOT / 'assets/original/Zelda_C64.crt'); host.run_frames(400); host.remap()
    # the hardware-access audit: tools/audit.json (from work/an/audit*.pkl by tools/host/audit_export.py)
    audit, ctxs = patches.load_audit(ROOT / 'tools/audit.json', [bytes(b) for b in banks])
    log = patches.apply(banks, host.ram, labs, audit, ctxs)
    print(len(log), 'patches')
    # bank 0: Atari trampoline over the unused C64 boot stub, and the cartridge header
    banks[0][0:7] = b8[0:7]
    banks[0][0x3FF9] = 0x60                     # RTS: INIT target
    banks[0][0x3FFA:0x4000] = bytes([0x00, 0x80, 0x00, 0x04, 0xF9, 0xBF])
    # EF bank 0 $B800-$BAFF: the EasyFlash EAPI driver the game copies to $1000 -> the Atari save driver (atari/src/eapi.s)
    assert banks[0][0x3800:0x3804] == b'eapi' and len(eapi) == 0x300
    banks[0][0x3800:0x3B00] = eapi
    chargen = open(host_rom('chargen-901225-01.bin'), 'rb').read()   # from the local VICE install; never committed
    cmp_ch = gen_compare(0x9000, False, labs['ryield'])
    cmp_col = gen_compare(0x8000, True, labs['ryield'])
    assert len(cmp_ch) <= 0x3000 and len(cmp_col) <= 0x4000, (len(cmp_ch), len(cmp_col))
    b10 = chargen + b'\xff' * (0x1000 - len(chargen)) + cmp_ch
    b10 += b'\xff' * (0x4000 - len(b10))
    b11 = cmp_col + b'\xff' * (0x4000 - len(cmp_col))
    allb = [bytes(b) for b in banks] + [b8, b9, b10, b11, b12] + [b'\xff' * 0x4000] * 3
    data = b''.join(allb)
    car = b'CART' + struct.pack('>II', 30, sum(data) & 0xFFFFFFFF) + b'\0' * 4 + data
    (OUT / 'zelda.car').write_bytes(car)
    print('wrote', OUT / 'zelda.car', len(data) // 1024, 'KB')
    sav = OUT / 'zelda_save.atr'                    # a blank 90 KB disk for D1: (atari/src/save.s); never overwritten
    if not sav.exists():
        size = 720 * 128
        sav.write_bytes(bytes([0x96, 0x02, (size >> 4) & 0xFF, (size >> 12) & 0xFF, 0x80, 0x00, size >> 20]) + bytes(9 + size))
        print('wrote', sav, '(blank save disk)')
    r = subprocess.run([sys.executable, str(ROOT / 'tools/hw_scan.py'), str(OUT / 'zelda.car')], capture_output=True, text=True)
    if r.returncode: print('WARNING: tools/hw_scan.py found unpatched VIC/SID/CIA sites:\n' + r.stdout, end='')
main()
