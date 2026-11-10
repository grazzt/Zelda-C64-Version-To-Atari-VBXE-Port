#!/usr/bin/env python3
"""Hardware-access audit of the C64 original under an input script, in the host model (traced core).

python3 tools/host/audit.py [--merge] [--shots DIR] [--dump FILE (64K memory at the end)] "w500 F7 w60 s right fire w20 ..."
  wN     run N frames                 s      save a VIC render (DIR/aNNNNN.png)
  F1 F3 F5 F7 F8 SPACE                press the key for 4 frames (F8 = SHIFT+F7)
  up down left right fire (combos: upfire, ...)  joystick 2 for 4 frames;  any token may end in *N: hold N frames
Prints the access sites that are new against work/an/audit.pkl; --merge adds them to it.
Audit format: {(bank or -1 for RAM, pc): {(kind, register): count}}; work/an/audit_ctx.pkl: {(-1, pc): code bytes pc-6..pc+9}
(RAM code is copied from the banks at run time; tools/patches.py finds the copy's source by these bytes).
"""
import collections, pickle, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host'))
from c64host import C64
from vicrender import render

KEYS = {'F7': [(3, 0)], 'F1': [(4, 0)], 'F3': [(5, 0)], 'F5': [(6, 0)], 'F8': [(3, 0), (7, 1)], 'SPACE': [(4, 7)]}
JOY = {'up': 1, 'down': 2, 'left': 4, 'right': 8, 'fire': 16}


def main():
    args = sys.argv[1:]
    merge = '--merge' in args
    shots = None
    if '--shots' in args:
        i = args.index('--shots'); shots = Path(args[i + 1]); shots.mkdir(parents=True, exist_ok=True); del args[i:i + 2]
    dump = None
    if '--dump' in args:
        i = args.index('--dump'); dump = Path(args[i + 1]); del args[i:i + 2]
    args = [a for a in args if a != '--merge']
    script = args[0].split()
    m = C64(ROOT / 'assets/original/Zelda_C64.crt', trace=True)
    found = collections.defaultdict(collections.Counter)
    ctx = {}                                     # RAM sites: the code bytes around them when they ran (pc-6 .. pc+9)

    def lg(kind, addr, val, pc):
        b = m.bank if 0x8000 <= pc < 0xC000 else -1
        found[(b, pc)][(kind, addr)] += 1
        if b < 0 and (b, pc) not in ctx: ctx[(b, pc)] = bytes(m.mem[pc - 6:pc + 9])
    m.log = lg
    for tok in script:
        tok, _, n = tok.partition('*')
        n = int(n) if n else 4
        if tok[0] == 'w' and tok[1:].isdigit():
            m.run_frames(int(tok[1:]))
        elif tok == 's':
            if not shots: continue
            p = shots / ('a%05d.png' % m.frame); render(m).save(p); print('shot', p, flush=True)
        elif tok in KEYS:
            for k in KEYS[tok]: m.keys[k] = 1
            m.run_frames(n); m.keys.clear()
        else:
            mask = 0
            for name, bit in JOY.items():
                if name in tok: mask |= bit
            assert mask, tok
            m.joy2 = 0xFF & ~mask; m.run_frames(n); m.joy2 = 0xFF
    if dump: dump.write_bytes(bytes(m.mem)); print('memory ->', dump)
    ap = ROOT / 'work/an/audit.pkl'
    audit = pickle.load(open(ap, 'rb'))
    new = {k: dict(v) for k, v in found.items() if k not in audit}
    for (b, pc), kinds in sorted(new.items(), key=lambda x: (x[0][1], x[0][0])):
        print('NEW bank %2d %04X' % (b, pc), sorted(kinds.items()))
    print(len(found), 'sites,', len(new), 'new; frame', m.frame)
    if merge:
        for k, v in new.items(): audit[k] = v
        pickle.dump(audit, open(ap, 'wb')); print('merged ->', ap)
        cp = ROOT / 'work/an/audit_ctx.pkl'
        old = pickle.load(open(cp, 'rb')) if cp.exists() else {}
        old.update({k: v for k, v in ctx.items() if k not in old})
        pickle.dump(old, open(cp, 'wb')); print(len(old), 'RAM contexts ->', cp)


main()
