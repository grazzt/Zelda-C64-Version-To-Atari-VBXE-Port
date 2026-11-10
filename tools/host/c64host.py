#!/usr/bin/env python3
"""Headless C64 + EasyFlash host model used as the oracle for the Zelda port.

Line-granular (65 cycles x 263 lines, NTSC): raster counter, VIC raster IRQ, CIA1/2 timers,
EasyFlash banking ($DE00/$DE02), KERNAL/BASIC/CHAR ROM banking.  Every access to VIC/SID/CIA/EF
is logged so the hardware patch list can be derived from the original code, not guessed.
"""
import os, struct, sys, collections
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
from pathlib import Path
sys.path.insert(0, _KIT + '/tools/c64')
from mos6502 import CPU
sys.path.insert(0, str(Path(__file__).parent))

ROMDIR = Path(_KIT) / 'local/vice/usr/share/vice/C64'
CYC_LINE, LINES = 65, 263


def load_crt(path):
    d = open(path, 'rb').read()
    p = struct.unpack('>I', d[16:20])[0]
    roml, romh = {}, {}
    while p < len(d):
        _, l, _, b, a, sz = struct.unpack('>4sIHHHH', d[p:p + 16])
        (roml if a == 0x8000 else romh)[b] = d[p + 16:p + 16 + sz]
        p += l
    return roml, romh


class C64:
    def __init__(self, crt, coverage=False, trace=False):
        self.roml, self.romh = load_crt(crt)
        self.kernal = open(ROMDIR / 'kernal-901227-03.bin', 'rb').read()
        self.basic = open(ROMDIR / 'basic-901226-01.bin', 'rb').read()
        self.chargen = open(ROMDIR / 'chargen-901225-01.bin', 'rb').read()
        self.ram = bytearray(65536)
        self.color = bytearray(1024)
        self.vic = bytearray(64)
        self.sid = bytearray(32)
        self.cia = [bytearray(16), bytearray(16)]
        self.port = [0xFF, 0xFF]                 # CIA ports as seen from outside
        self.keys = {}                           # (row,col) pressed -> matrix
        self.joy2 = 0xFF
        self.rom_regions = [(0xD000, 0xE000)]
        self.bank, self.efmode = 0, 0x00         # EF at reset: ultimax
        self.p0, self.p1 = 0x2F, 0x37
        self.mem = bytearray(65536)
        if trace:
            from tracecore import traced_cpu_class
            self.cpu = traced_cpu_class()(self.mem)
        else:
            self.cpu = CPU(self.mem, coverage=coverage)
        self.cpu.io_read, self.cpu.special = self.io_read, self.special
        self.cpu.on_event = self.on_event
        self.log = None                          # callable(kind, addr, val, pc)
        self.line, self.frame = 0, 0
        self.irq_vic = 0
        self.irq_mask = 0
        self.timers = [[0, 0, 0, 0], [0, 0, 0, 0]]   # per CIA: A cnt, B cnt, A latch, B latch
        self.icr = [0, 0]; self.icr_mask = [0, 0]
        self.next_line_cycle = CYC_LINE
        self.cpu.next_event = CYC_LINE
        self.on_frame = None
        self.remap()
        self.cpu.pc = self.mem[0xFFFC] | self.mem[0xFFFD] << 8

    # ---- banking -------------------------------------------------
    def modes(self):
        m = self.efmode
        if m & 4: return bool(m & 1), bool(m & 2)   # GAME low, EXROM low
        return True, False                          # power-on: ultimax boot

    def remap(self):
        ram = self.ram; mem = self.mem
        game_low, exrom_low = self.modes()
        lo, hi = self.p1 & 1, (self.p1 >> 1) & 1
        # keep a pristine copy of ram below; mem is the CPU view
        ultimax = game_low and not exrom_low
        for a, b in self.rom_regions: pass
        keep = bytearray(1)
        # write back RAM that the CPU stored straight into mem, skipping regions that showed ROM/IO
        prev = self.rom_regions
        pos = 0
        for a, b in sorted(prev) + [(0x10000, 0x10000)]:
            if pos < a: ram[pos:a] = mem[pos:a]
            pos = max(pos, b)
        self.rom_regions = []
        mem[:] = ram
        self.io_vis = False; self.chr_vis = False
        if ultimax:
            mem[0x8000:0xA000] = self.roml.get(self.bank, bytes(8192))
            mem[0xE000:0x10000] = self.romh.get(self.bank, bytes(8192))
            self.io_vis = True
            self.rom_regions += [(0x8000, 0xA000), (0xE000, 0x10000), (0xD000, 0xE000)]
        else:
            ch = (self.p1 >> 2) & 1
            if lo and hi and exrom_low:
                mem[0x8000:0xA000] = self.roml.get(self.bank, bytes(8192)); self.rom_regions.append((0x8000, 0xA000))
            if hi and exrom_low and game_low:   # 16K mode: ROMH at A000
                mem[0xA000:0xC000] = self.romh.get(self.bank, bytes(8192)); self.rom_regions.append((0xA000, 0xC000))
            elif lo and hi:
                mem[0xA000:0xC000] = self.basic; self.rom_regions.append((0xA000, 0xC000))
            if hi:
                mem[0xE000:0x10000] = self.kernal; self.rom_regions.append((0xE000, 0x10000))
            if (self.p1 & 3) and (self.p1 & 4):
                self.io_vis = True
            elif (self.p1 & 3):
                self.chr_vis = True
                mem[0xD000:0xE000] = self.chargen
        if lo == 0 and hi == 0 and (self.p1 & 4) == 0: pass

    # ---- I/O -----------------------------------------------------
    def note(self, kind, addr, val):
        if self.log: self.log(kind, addr, val, getattr(self.cpu, 'ipc', self.cpu.pc))

    def special(self, ea, v):
        if ea == 0:
            self.p0 = v; self.remap(); return
        if ea == 1:
            self.p1 = v; self.remap(); return
        if not self.io_vis:
            self.ram[ea] = v; self.mem[ea] = v   # D000 area: RAM under I/O
            return
        if 0xD000 <= ea < 0xD400:
            r = ea & 63; self.vic[r] = v; self.note('vicw', r, v)
            if r == 0x19: self.irq_vic &= ~v
        elif ea < 0xD800:
            self.sid[ea & 31] = v; self.note('sidw', ea & 31, v)
        elif ea < 0xDC00:
            self.color[ea - 0xD800] = v & 15
        elif ea < 0xDE00:
            c = (ea >> 8) & 1; r = ea & 15; self.cia_write(c, r, v)
        elif ea < 0xDF00:
            self.note('efw', ea, v)
            if ea == 0xDE00: self.bank = v & 63; self.remap()
            elif ea == 0xDE02: self.efmode = v; self.remap()
        else:
            self.note('iow', ea, v)

    def io_read(self, ea):
        if not self.io_vis:
            return self.mem[ea]
        if ea < 0xD400:
            r = ea & 63
            if r in (0x11, 0x12, 0x19, 0x1E, 0x1F): self.note('vicr', r, 0)
            if r == 0x11: return (self.vic[0x11] & 0x7F) | ((self.line >> 1) & 0x80)
            if r == 0x12: return self.line & 0xFF
            if r == 0x19: return self.irq_vic | (0x80 if self.irq_vic & self.vic[0x1A] & 15 else 0) | 0x70
            if r in (0x1E, 0x1F): return 0
            self.note('vicr', r, self.vic[r]); return self.vic[r] if r < 0x2F else 0xFF
        if ea < 0xD800:
            self.note('sidr', ea & 31, 0); return 0xFF if (ea & 31) < 0x19 else 0x00
        if ea < 0xDC00: return self.color[ea - 0xD800] | 0xF0
        if ea < 0xDE00: return self.cia_read((ea >> 8) & 1, ea & 15)
        if ea < 0xDF00: return 0xFF
        return 0xFF

    def cia_write(self, c, r, v):
        self.note('ciaw%d' % (c + 1), r, v)
        t = self.timers[c]
        if r == 4: t[2] = (t[2] & 0xFF00) | v
        elif r == 5:
            t[2] = (t[2] & 0xFF) | v << 8
            if not (self.cia[c][14] & 1): t[0] = t[2]
        elif r == 6: t[3] = (t[3] & 0xFF00) | v
        elif r == 7:
            t[3] = (t[3] & 0xFF) | v << 8
            if not (self.cia[c][15] & 1): t[1] = t[3]
        elif r == 13:
            if v & 0x80: self.icr_mask[c] |= v & 0x1F
            else: self.icr_mask[c] &= ~v
            return
        elif r == 14 and v & 0x10: t[0] = t[2]
        elif r == 15 and v & 0x10: t[1] = t[3]
        self.cia[c][r] = v & (0xEF if r in (14, 15) else 0xFF)

    def cia_read(self, c, r):
        self.note('ciar%d' % (c + 1), r, 0)
        if r == 0 and c == 0:
            return self.joy2 & self.keyscan_col()
        if r == 1 and c == 0:
            sel = self.cia[0][0]; res = 0xFF
            for (row, col) in self.keys:
                if not (sel >> col) & 1: res &= ~(1 << row)
            return res & (self.joy2 | 0xE0) if False else res
        if r == 0 and c == 1: return (self.cia[1][0] | 0x00) & 0xFF
        if r == 4: return self.timers[c][0] & 0xFF
        if r == 5: return self.timers[c][0] >> 8
        if r == 6: return self.timers[c][1] & 0xFF
        if r == 7: return self.timers[c][1] >> 8
        if r == 13:
            v = self.icr[c] | (0x80 if self.icr[c] & self.icr_mask[c] else 0); self.icr[c] = 0; return v
        return self.cia[c][r]

    def keyscan_col(self): return 0xFF

    # ---- timing --------------------------------------------------
    def tick_cia(self, cyc):
        for c in (0, 1):
            t = self.timers[c]
            for n, (cr, bit) in enumerate(((14, 1), (15, 2))):
                if self.cia[c][cr] & 1 and not (n == 1 and self.cia[c][cr] & 0x60):
                    t[n] -= cyc
                    while t[n] < 0:
                        t[n] += (t[n + 2] or 0x10000) + 1 if False else (t[n + 2] + 1)
                        self.icr[c] |= bit
                        if self.cia[c][cr] & 8: self.cia[c][cr] &= ~1

    def on_event(self):
        cpu = self.cpu
        while cpu.cycles >= self.next_line_cycle:
            self.next_line_cycle += CYC_LINE
            self.tick_cia(CYC_LINE)
            self.line += 1
            if self.line >= LINES:
                self.line = 0; self.frame += 1
                if self.on_frame: self.on_frame(self)
            rl = self.vic[0x12] | (self.vic[0x11] & 0x80) << 1
            if self.line == rl: self.irq_vic |= 1
        cpu.next_event = self.next_line_cycle
        irq = (self.irq_vic & self.vic[0x1A] & 15) or (self.icr[0] & self.icr_mask[0])
        if irq and not cpu.fi:
            if self.ultimax_or_ram_vectors(): pass
            cpu.interrupt(0xFFFE)
        nmi = self.icr[1] & self.icr_mask[1]
        if nmi and not self.nmi_seen:
            self.nmi_seen = True; cpu.interrupt(0xFFFA)
        elif not nmi: self.nmi_seen = False

    nmi_seen = False
    def ultimax_or_ram_vectors(self): return False

    def run_frames(self, n):
        target = self.frame + n
        while self.frame < target:
            self.cpu.run(1500)


if __name__ == '__main__':
    m = C64(sys.argv[1])
    cnt = collections.Counter()
    def lg(k, a, v, pc): cnt[(k, a)] += 1
    m.log = lg
    for i in range(int(sys.argv[2])):
        m.run_frames(1)
    print('frame', m.frame, 'pc %04X' % m.cpu.pc, 'p1', hex(m.p1), 'bank', m.bank, hex(m.efmode))
    for k, v in sorted(cnt.items()): print(k[0], '%02X' % k[1], v)
