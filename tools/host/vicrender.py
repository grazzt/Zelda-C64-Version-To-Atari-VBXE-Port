"""Render the host model's current VIC state to a 320x200 (+border-less) RGB image. Whole-frame (no raster splits)."""
from PIL import Image
PAL = [(0,0,0),(255,255,255),(136,57,50),(103,182,189),(139,63,150),(85,160,73),(64,49,141),(191,206,114),
       (139,84,41),(87,66,0),(184,105,98),(80,80,80),(120,120,120),(148,224,137),(120,105,196),(159,159,159)]

def render(m, border=False):
    v = m.vic; ram = m.ram
    bank = (~m.cia[1][0]) & 3 if False else (~(m.cia[1][0] | ~m.cia[1][2] & 0)) & 3
    base = bank * 0x4000
    def vm(a):  # VIC memory view: char ROM at $1000/$9000 of banks 0/2
        a &= 0x3FFF
        if bank in (0, 2) and 0x1000 <= a < 0x2000: return m.chargen[a - 0x1000]
        return ram[base + a]
    d11, d16, d18 = v[0x11], v[0x16], v[0x18]
    bmm, ecm, mcm = d11 & 0x20, d11 & 0x40, d16 & 0x10
    screen = (d18 >> 4) * 0x400; chars = (d18 & 14) * 0x400; bmbase = (d18 & 8) * 0x400
    bg = [v[0x21 + i] & 15 for i in range(4)]
    img = Image.new('RGB', (320, 200)); px = img.load()
    if not (d11 & 0x10): return img
    mcbm = bool(mcm)
    for row in range(25):
        for col in range(40):
            sc = vm(screen + row * 40 + col); cr = m.color[row * 40 + col] & 15
            for y in range(8):
                if bmm:
                    b = vm(bmbase + (row * 40 + col) * 8 + y)
                    if mcbm:
                        cols = [bg[0], sc >> 4, sc & 15, cr]
                        for x in range(4):
                            c = cols[(b >> (6 - 2 * x)) & 3]
                            px[col*8+x*2, row*8+y] = px[col*8+x*2+1, row*8+y] = PAL[c]
                    else:
                        for x in range(8):
                            c = (sc >> 4) if (b >> (7 - x)) & 1 else (sc & 15)
                            px[col*8+x, row*8+y] = PAL[c]
                else:
                    b = vm(chars + (sc & (0x3F if ecm else 0xFF)) * 8 + y)
                    if mcbm and cr & 8:
                        cols = [bg[0], bg[1], bg[2], cr & 7]
                        for x in range(4):
                            c = cols[(b >> (6 - 2 * x)) & 3]
                            px[col*8+x*2, row*8+y] = px[col*8+x*2+1, row*8+y] = PAL[c]
                    else:
                        bgc = bg[(sc >> 6) & 3] if ecm else bg[0]
                        for x in range(8):
                            px[col*8+x, row*8+y] = PAL[cr if (b >> (7 - x)) & 1 else bgc]
    # sprites (low priority first: 7..0)
    for s in range(7, -1, -1):
        if not (v[0x15] >> s) & 1: continue
        x = v[s*2] | (((v[0x10] >> s) & 1) << 8); y = v[s*2+1]
        ptr = vm(screen + 0x3F8 + s)
        xe, ye, mc = (v[0x1D] >> s) & 1, (v[0x17] >> s) & 1, (v[0x1C] >> s) & 1
        col = v[0x27 + s] & 15
        for r in range(21):
            data = [vm(ptr * 64 + r * 3 + i) for i in range(3)]
            bits = data[0] << 16 | data[1] << 8 | data[2]
            for k in range(24 if not mc else 12):
                if mc:
                    c = (bits >> (22 - 2 * k)) & 3
                    cc = [None, v[0x25] & 15, col, v[0x26] & 15][c]; w = 2
                else:
                    c = (bits >> (23 - k)) & 1; cc = col if c else None; w = 1
                if cc is None: continue
                for dy in range(1 + ye):
                    for dx in range(w * (1 + xe)):
                        X = x - 24 + (k * w * (1 + xe)) + dx; Y = y - 50 + r * (1 + ye) + dy
                        if 0 <= X < 320 and 0 <= Y < 200: px[X, Y] = PAL[cc]
    return img
