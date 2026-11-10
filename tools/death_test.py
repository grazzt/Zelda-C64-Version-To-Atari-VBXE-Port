#!/usr/bin/env python3
"""python3 tools/death_test.py [-s PREFIX] [ROUTE] : from the first overworld screen (boot_game), cut Link's health to a
sliver ($066F low nibble = full hearts, $0670 = partial heart) and walk ROUTE (walk_test syntax) until an enemy kills
him, then wait and report every game-mode change ($14: $11 = dying). Passes if the game leaves the death mode (the
continue screen follows) instead of hanging and START (CONTINUE) brings it back to the overworld (mode 5). -s PREFIX: screenshots PREFIXnnnnn.png every 60 frames after the death."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game

args = sys.argv[1:]
pre = None
if args and args[0] == '-s': pre = args[1]; args = args[2:]
route = args[0] if args else ('right*150 up*200 left*250 up*200 right*300 down*300 right*300 down*300 left*300 left*300 '
                                  'up*300 up*300 left*300 down*300 ' + 'right*200 left*200 up*100 down*100 ' * 4)
e = boot_game()
try:
    f, prev, died = 0, None, None

    def step(n):
        global f, prev, died
        for i in range(n // 2):
            e.frame(2); f += 2
            md = e.peek(0x14, 1)[0]
            if md != prev:
                print(f, 'mode %02X' % md, flush=True); prev = md
                if md == 0x11 and died is None: died = f
            if died is not None: return
    for st in route.split():
        d, _, n = st.partition('*')
        e.command('JOY 0 ' + ('center' if d == 'w' else d))
        e.poke(0x066F, e.peek(0x066F, 1)[0] & 0xF0); e.poke(0x0670, 1)
        step(int(n or 4))
        if died is not None: break
    e.command('JOY 0 center')
    if died is None: raise SystemExit('Link never died on that route')
    left = None
    for i in range(30):
        for j in range(30):
            e.frame(2); f += 2
            md = e.peek(0x14, 1)[0]
            if md != prev:
                print(f, 'mode %02X' % md, flush=True); prev = md
                if left is None and md != 0x11: left = f
        if pre and i % 2 == 0: e.screenshot(f'{pre}{f:05d}.png')
    print('died at', died, 'left death mode at', left, 'final mode %02X' % prev,
          'C100 vector %02X%02X' % tuple(reversed(e.peek(0xC100, 2))), 'D012 shadow', e.peek(0xF012, 1)[0])
    if not left: raise SystemExit('FAIL: still in death mode %d frames after dying' % (f - died))
    e.command('CONSOL start'); e.frame(4); e.command('CONSOL')          # CONTINUE (F7)
    for i in range(300):
        e.frame(2); f += 2
        md = e.peek(0x14, 1)[0]
        if md != prev: print(f, 'mode %02X' % md, flush=True); prev = md
    if pre: e.screenshot(f'{pre}{f:05d}c.png')
    print('PASS: continue -> mode %02X' % prev if prev == 5 else 'FAIL: continue left the game in mode %02X' % prev)
finally:
    e.close()
