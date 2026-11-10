#!/usr/bin/env python3
"""(build with ZDEFS=DCHK) python3 tools/check_d.py START [STEP N] : compare the displayed VBXE buffer with BG (xor 1) outside sprite rectangles.
Prints, per sample, the number of differing pixels and the BG cells (row, col) they fall in."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
P, DT = 416, 42
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
def vram(a, n):
    out = b''
    while n:
        k = min(n, 0x1000 - (a & 0xFFF)); e.poke(0xD65F, 0x80 + (a >> 12)); out += e.peek(0xE000 + (a & 0xFFF), k); a += k; n -= k
    return out
try:
    start = int(sys.argv[1]); step = int(sys.argv[2]) if len(sys.argv) > 2 else 1; n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    e.frame(start); t = start
    for i in range(n):
        ok = False
        for _ in range(60):   # a composed frame waiting for its flip, BG unchanged since, no render or blit running
            if e.peek(0xF65A, 1)[0] == 1 and e.peek(0xF675, 1)[0] == 1 and e.peek(0xF676, 1)[0] == 0 and e.peek(0xD653, 1)[0] == 0:
                ok = True; break
            e.frame(1); t += 1
        if not ok: print('frame', t, 'no quiet point'); continue
        e.poke(0xD65E, 0xE8)
        a = e.peek(0xF65B, 3); xa = a[0] | a[1] << 8 | a[2] << 16
        hid = e.peek(0xF084, 1)[0]; shown = hid   # the buffer checked: the composed one about to be shown
        base = 0x40000 if shown == 0 else 0x60000
        if xa < base or xa >= base + 300 * P: print('frame', t, 'XDL %06X not in shown buffer %d' % (xa, shown)); e.poke(0xD65E, 0); break
        line = (xa - base - 48) // P; bl = line - DT
        disp = vram(xa, 199 * P + 320); bg = vram(0x20000 + bl * 320, 200 * 320)
        mask = set(); nr = 0
        for bnd in range(5):
            ob = vram(0x1000 + 0x930 + (shown * 5 + bnd) * 72, 72); cnt = ob[2]; nr += cnt
            for i in range(cnt):
                en = ob[8 + i * 8:8 + i * 8 + 8]; dl = en[1]; dc = en[2] | en[3] << 8; w = en[4] + 1; h = en[5] + 1
                for y in range(h):
                    for x in range(w): mask.add((dl + y - line, dc + x - 48))
        cells = {}; bad = 0
        for y in range(200):
            for x in range(320):
                if (y, x) in mask: continue
                if disp[y * P + x] != bg[y * 320 + x] ^ 1:
                    bad += 1; br = bl + y - 8; cells[(br // 8, x // 8)] = cells.get((br // 8, x // 8), 0) + 1
        if bad and '-v' in sys.argv:
            rows = sorted({r for r, c in cells})
            for r in rows[:4]:
                y0 = (r + 1) * 8 - bl   # screen line of BG row r (BG line 8+8r)
                for dy in range(8):
                    y = y0 + dy
                    if not 0 <= y < 200: continue
                    d = bytes(disp[y * P:y * P + 320]); hits = [o for o in range(-24, 25) if 0 <= bl + y + o < 216 and bytes(b ^ 1 for b in vram(0x20000 + (bl + y + o) * 320, 320)) == d]
                    print('   BG row %d line %d: matches BG at offset %s' % (r, dy, hits[:6]))
            i = e.peek(0xF6FF, 1)[0]; ev = e.peek(0xF6A0, 32); fr = e.peek(0xF6C0, 32)
            names = {1: 'full', 2: 'incr', 3: 'SHIFT', 4: 'flip'}
            print('   log:', ' '.join('%d:%s%s' % (fr[(i + k) & 31], names.get(ev[(i + k) & 31] >> 4, '?'), ev[(i + k) & 31] & 15 if ev[(i + k) & 31] >> 4 != 3 else '') for k in range(32)))
            print('   r_dv', list(e.peek(0xF65F, 2)), 'r_cdn', list(e.peek(0xF661, 2)), 'r_hidden', hid, 'XDL line', line)
        if bad and '-dump' in sys.argv:
            from PIL import Image
            im = Image.new('RGB', (320, 200))
            px = [((255, 0, 0) if disp[y * P + x] != (bg[y * 320 + x] ^ 1) and (y, x) not in mask else ((0, 80, 0) if (y, x) in mask else (40, 40, 40) if bg[y*320+x] else (0, 0, 0))) for y in range(200) for x in range(320)]
            im.putdata(px); im.resize((640, 400)).save('build/cd_dump.png')
            pal = [((i * 37) % 256, (i * 91) % 256, (i * 53) % 256) for i in range(256)]
            a = Image.new('RGB', (320, 200)); a.putdata([pal[disp[y * P + x]] for y in range(200) for x in range(320)]); a.resize((640, 400)).save('build/cd_d.png')
            b = Image.new('RGB', (320, 200)); b.putdata([pal[bg[y * 320 + x] ^ 1] for y in range(200) for x in range(320)]); b.resize((640, 400)).save('build/cd_bg.png')
            print('dumped'); break
        e.poke(0xD65E, 0)   # MEMAC off again (the game's RAM at $E000)
        print('frame %d ys %d shown %d rects %d: %d bad px, cells %s' % (t, e.peek(0xF011, 1)[0] & 7, shown, nr, bad, sorted(cells.items())[:20]))
        e.frame(step); t += step
finally:
    e.close()
