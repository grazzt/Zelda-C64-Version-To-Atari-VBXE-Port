#!/usr/bin/env python3
"""python3 tools/host/make_dungeon_state.py [OUT] : host-model state just inside the LEVEL-3 dungeon (default
work/an/states/dungeon3_entry.pkl, for tools/host/explore.py --state). Route: register LUNA, start, sword flag $0657;
from the start screen ($77, $ED = screen index) west to $76; Link's object ($72/$86) placed at (24, 117) and walked
left to $75; at (24, 45) and walked left to $74; at (128, 141) below the dungeon entrance and walked up.
(The rows were found by trying each one: the screens' west edges are mostly trees.)"""
import sys, copy, pickle, types
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host'))
from c64host import C64
KEYS = {'F7': [(3, 0)], 'F5': [(6, 0)]}
JOY = {'up': 1, 'down': 2, 'left': 4, 'right': 8, 'fire': 16}
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'work/an/states/dungeon3_entry.pkl'
m = C64(ROOT / 'assets/original/Zelda_C64.crt')
def run(tok):
    tok, _, n = tok.partition('*'); n = int(n) if n else 4
    if tok[0] == 'w': m.run_frames(int(tok[1:]))
    elif tok in KEYS:
        for k in KEYS[tok]: m.keys[k] = 1
        m.run_frames(n); m.keys.clear()
    else:
        mask = sum(b for nm, b in JOY.items() if nm in tok); m.joy2 = 0xFF & ~mask; m.run_frames(n); m.joy2 = 0xFF
def hold(d, cond, limit=600):
    for i in range(limit // 2):
        run('%s*2' % d)
        if cond(): return True
    return False
def snap(o):
    return {k: copy.deepcopy(v) for k, v in vars(o).items()
            if not callable(v) and not isinstance(v, types.ModuleType) and k not in ('mem', 'cpu', 'seen')}
for t in open(ROOT / 'work/an/reg_luna.txt').read().split(): run(t)
run('w60'); m.mem[0x0657] = 1
here = lambda s: m.mem[0xED] == s and m.mem[0x14] == 5
assert hold('left', lambda: here(0x76), 900), hex(m.mem[0xED])
for (x, y), s in (((24, 117), 0x75), ((24, 45), 0x74)):
    m.mem[0x72], m.mem[0x86] = x, y
    assert hold('left', lambda: here(s), 900), (hex(m.mem[0xED]), m.mem[0x72], m.mem[0x86])
m.mem[0x72], m.mem[0x86] = 128, 141
modes = []
for i in range(150):
    run('up*2')
    if not modes or modes[-1] != m.mem[0x14]: modes.append(m.mem[0x14])
run('w120')
assert 0x10 in modes, modes
out.parent.mkdir(parents=True, exist_ok=True)
pickle.dump((bytes(m.mem), snap(m), snap(m.cpu)), open(out, 'wb'))
print('in the dungeon: modes %s, screen $%02X, frame %d -> %s' % (' '.join('%02X' % x for x in modes), m.mem[0xED], m.frame, out))
