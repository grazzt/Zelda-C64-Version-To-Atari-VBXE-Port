#!/usr/bin/env python3
"""python3 tools/host/explore.py [SEED] [FRAMES] : random exploration of the C64 original in the host model, to reach
game phases no scripted audit played. From the start (registers LUNA, starts, sets the sword flag $0657 and keeps
Link's health topped up) it wanders, mostly towards screens not visited yet ($ED = screen index), with sword
swings. Reports the game modes and distinct screens seen, and flags:
  - writes to the renderer's zero-page bytes (RZP below = atari.inc zscr .. ztmp: the port assumes the game never
    writes or reads them),
  - hardware access sites (VIC/SID/CIA/EF) that work/an/audit.pkl does not list (unpatched in the port unless
    tools/hw_scan.py / patches.STATIC_SITES cover them),
  - CPU errors (BRK / undocumented opcode: a crash).
Screens are counted by a hash of screen RAM rows 3-24 at the moment a scroll ends (mode 4 -> 5).
--state FILE: start from a host-model state instead of the start screen (work/an/states/: dungeon3_entry.pkl = just
inside the LEVEL-3 dungeon; made by walking west from the start screen to screen $74, see HANDOFF)."""
import sys, os, random, pickle, hashlib, collections
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host'))
from c64host import C64
KEYS = {'F7': [(3, 0)], 'F5': [(6, 0)], 'F8': [(3, 0), (7, 1)]}
JOY = {'up': 1, 'down': 2, 'left': 4, 'right': 8, 'fire': 16}
seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
total = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
rnd = random.Random(seed)
audit = pickle.load(open(ROOT / 'work/an/audit.pkl', 'rb'))
known = {k for k in audit}
m = C64(ROOT / 'assets/original/Zelda_C64.crt', trace=True)
# a core whose zero-page writes to $D2-$E1 go through special() (so the writer's PC is known)
sys.path.insert(0, _KIT + '/tools/c64')
import mos6502
from itertools import repeat
_src = mos6502._source(False).replace("        op = mem[pc]\n", "        op = mem[pc]\n        self.ipc = pc\n")
assert "if ea > 1:" in _src
_src = _src.replace("if ea > 1:", "if ea > 1 and ea < 0x100 and False:")
_ns = {'repeat': repeat, 'CPUError': mos6502.CPUError}
exec(compile(_src, '<zp-trace core>', 'exec'), _ns)
class _ZCPU(mos6502.CPU):
    ipc = 0
    def __init__(self, mem):
        super().__init__(mem, False); self._run = _ns['run']
m.cpu = _ZCPU(m.mem); m.cpu.io_read, m.cpu.on_event = m.io_read, m.on_event
m.cpu.next_event = 65; m.remap(); m.cpu.pc = m.mem[0xFFFC] | m.mem[0xFFFD] << 8
zpwriters = collections.Counter()
_special = m.special
zpw_all = collections.Counter(); hiw = collections.Counter()
def _sp(ea, v):
    if ea >= 0xE000 and m.frame > 400:                          # RAM under the KERNAL: the port's resident code/RAM
        pc = m.cpu.ipc; hiw[(m.bank if 0x8000 <= pc < 0xC000 else -1, pc, ea & 0xFF00)] += 1
    if 1 < ea < 0x100:
        if m.frame > 400: zpw_all[ea] += 1
        if ea in RZP and m.frame > 400:
            pc = m.cpu.ipc; zpwriters[(m.bank if 0x8000 <= pc < 0xC000 else -1, pc, ea, m.mem[0x14])] += 1
        m.mem[ea] = v; return
    return _special(ea, v)
m.cpu.special = _sp
newsites = collections.Counter(); zpw = collections.Counter(); modes = collections.Counter(); screens = set()
prev_zp = [None]; prev_mode = [0]
RZP = [0x81, 0x82, 0x83, 0x84, 0x95, 0x96, 0x97, 0x98, 0xA9, 0xAA, 0xAB, 0xAC, 0xD2, 0xD3, 0x5F, 0x60]   # atari.inc
def lg(kind, addr, val, pc):
    b = m.bank if 0x8000 <= pc < 0xC000 else -1
    if (b, pc) not in known and m.frame > 1500: newsites[(b, pc, kind, addr)] += 1
m.log = lg
zpchanged = set(); prev_all = [None]
poison = []
if '--poison' in sys.argv:
    i = sys.argv.index('--poison'); poison = [int(x, 16) for x in sys.argv[i + 1].split(',')]
prnd = random.Random(99); hashes = []
def of(_m):
    if poison and m.frame > 400:
        for a in poison: m.mem[a] = prnd.randrange(256)
    if m.frame % 60 == 0: hashes.append(hashlib.md5(bytes(m.mem[0x100:0x10000])).hexdigest()[:8])
    za = bytes(m.mem[0:256])
    if prev_all[0] is not None and m.frame > 400:
        zpchanged.update(i for i in range(256) if za[i] != prev_all[0][i])
    prev_all[0] = za
    md = m.mem[0x14]; modes[md] += 1
    if prev_mode[0] == 4 and md == 5: screens.add(hashlib.md5(bytes(m.mem[0x0878:0x0BE8])).hexdigest()[:8])
    prev_mode[0] = md
    if m.frame > 2000:
        m.mem[0x0657] = 1; m.mem[0x066F] = (m.mem[0x066F] & 0xF0) | (m.mem[0x066F] >> 4); m.mem[0x0670] = 0xFF
m.on_frame = of
def run(tok):
    tok, _, n = tok.partition('*'); n = int(n) if n else 4
    if tok[0] == 'w': m.run_frames(int(tok[1:]))
    elif tok in KEYS:
        for k in KEYS[tok]: m.keys[k] = 1
        m.run_frames(n); m.keys.clear()
    else:
        mask = sum(b for nm, b in JOY.items() if nm in tok); m.joy2 = 0xFF & ~mask; m.run_frames(n); m.joy2 = 0xFF
crash = None
def restore(st):
    import copy
    m.mem[:] = st[0]
    for k, v in st[1].items():
        if k not in ('on_frame', 'log'): setattr(m, k, copy.deepcopy(v))      # (keep this run's hooks)
    for k, v in st[2].items():
        if k not in ('_run', 'ipc', 'special', 'io_read', 'on_event'): setattr(m.cpu, k, copy.deepcopy(v))
try:
    if '--state' in sys.argv:
        restore(pickle.load(open(sys.argv[sys.argv.index('--state') + 1], 'rb')))
    else:
        for t in open(ROOT / 'work/an/reg_luna.txt').read().split(): run(t)
    d = 'up'
    visited = collections.Counter()
    step = {'up': -16, 'down': 16, 'left': -1, 'right': 1}
    while m.frame < total:
        here = m.mem[0xED]; visited[here] += 1                    # $ED: screen index (row * 16 + column)
        new = [k for k, v in step.items() if visited[(here + v) & 0xFF] == 0]
        if new and rnd.random() < 0.6: d = rnd.choice(new)        # head for screens not seen yet
        elif rnd.random() < 0.45: d = rnd.choice(['up', 'down', 'left', 'right'])
        run('%s*%d' % (d, rnd.randrange(20, 120)))
        r = rnd.random()
        if r < 0.35: run('fire'); run('w6')                         # (no F8: its menu's CONTINUE restarts at the start)
        if m.mem[0x14] == 8: run('F7'); run('w120')                       # continue screen: continue
except Exception as ex:
    crash = '%s at frame %d PC %04X bank %d' % (ex, m.frame, m.cpu.pc, m.bank)
print('seed %d: %d frames, %d screens (%d map positions $ED), modes %s' % (seed, m.frame, len(screens), len(visited), ' '.join('%02X:%d' % kv for kv in sorted(modes.items()))))
sites = sorted({(b, pc, kind, addr) for (b, pc, kind, addr) in newsites})
print('  writers of the renderer zero page (bank, pc, address, game mode): %d' % len(zpwriters))
for (b, pc, ea, md), c in sorted(zpwriters.items())[:30]: print('    bank %2d pc %04X -> $%02X  mode %02X  x%d' % (b, pc, ea, md, c))
print('  game writes to $E000-$FFFF (bank, pc, page): %d sites' % len(hiw))
for (b, pc, pg), c in sorted(hiw.items())[:20]: print('    bank %2d pc %04X -> $%04X page  x%d' % (b, pc, pg, c))
print('  hardware sites not in the audit: %d' % len(sites))
for b, pc, kind, addr in sites[:40]: print('    bank %2d pc %04X %s %04X' % (b, pc, kind, addr))
print('  CRASH: ' + crash if crash else '  no crash')
print('  zero page never changed after frame 400: ' + ' '.join('%02X' % i for i in range(256) if i not in zpchanged))
if '--hashes' in sys.argv: open(sys.argv[sys.argv.index('--hashes') + 1], 'w').write(' '.join(hashes))
print('  zero page never written after frame 400: ' + ' '.join('%02X' % i for i in range(2, 256) if not zpw_all[i]))
if '--zpout' in sys.argv: open(sys.argv[sys.argv.index('--zpout') + 1], 'w').write(' '.join('%02X' % i for i in sorted(zpw_all)))
