#!/usr/bin/env python3
"""python3 tools/sword_fight_test.py [CART] [ROUNDS] : from the first overworld screen (boot_game) fetch the sword from the
cave (CAVE=1; default: set the sword flag $0657), walk to the screen east of the start, then fight there (sword swings, moving about) for ROUNDS rounds. Reports
every hit taken; FAIL if the game freezes (main-loop counter $17 stops for 60 frames: e.g. raster events dead after an
unpatched SID write landed on ANTIC), PASS otherwise. Link is kept alive by refilling his health after each hit.
Steers by Link's object position ($72/$86; sprite 0 is not always Link), so the route does not depend on the game's speed.
PRIME=1: instead of fetching the sword, keep the sound driver's last voice-3 effect number ($7E51) at $0F, as a sword
swing leaves it, so a hit's (lower-numbered) effect takes the restart path at bank 0 $96A0 (the unpatched SID write
$96AC STA $D412 = ANTIC DLISTL in the builds before the static patches)."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game

cart = sys.argv[1] if len(sys.argv) > 1 else None
rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 40
e = boot_game(cart)
f = [0]
def pos(): return e.peek(0x72, 1)[0], e.peek(0x86, 1)[0]     # Link's object (= sprite coordinates - (56, 13))
def mode(): return e.peek(0x14, 1)[0]
def hold(d, cond, limit=600):
    e.command('JOY 0 ' + d)
    for i in range(limit):
        e.frame(1); f[0] += 1
        if cond(): break
    e.command('JOY 0 center')
    return cond()
def wait(n):
    for i in range(n): e.frame(1); f[0] += 1
try:
    prime = os.environ.get('PRIME') == '1'
    wait(60)
    if os.environ.get('CAVE') != '1':
        e.poke(0x0657, 1)                                 # the sword ($0657: 1 once it is picked up in the cave)
    elif not prime:
        assert hold('left', lambda: pos()[0] <= 64), pos()
        assert hold('up', lambda: mode() == 0x0B), 'cave'
        wait(720)                                         # (the old man's text)
        for d, n in [('up', 30), ('up', 30), ('down', 20), ('left', 20), ('up', 30), ('right', 40), ('up', 30),
                     ('left', 20), ('down', 10), ('up', 30)]:   # onto the sword (Link's object: $72/$86)
            hold(d, lambda: False, n)
        wait(120)
        assert hold('down', lambda: mode() == 5, 900), 'leave cave'
        wait(30); e.screenshot('build/_sword.png')
    assert hold('down', lambda: pos()[1] >= 144), pos()
    assert hold('right', lambda: pos()[0] >= 208), pos()
    assert hold('up', lambda: pos()[1] <= 140), pos()
    assert hold('right', lambda: mode() == 7, 300), 'east scroll'
    assert hold('center', lambda: mode() == 5, 600), 'scroll end'
    print('frame', f[0], 'on the east screen, link at', pos(), flush=True)
    hp = e.peek(0x066F, 2); hits = 0
    irq0 = [e.peek(0xF07C, 1)[0]]; dumped = []
    c, still = e.peek(0x17, 1)[0], 0
    import random
    rnd = random.Random(1)
    e.screenshot('build/_fight0.png')
    for r in range(rounds):
        for k in range(4):
            x, y = pos()                                  # wander the middle of the screen, swing now and then
            d = rnd.choice(['up', 'down', 'left', 'right'] + ['right'] * (x < 64) + ['left'] * (x > 184) +
                           ['down'] * (y < 97) + ['up'] * (y > 177))
            if rnd.random() < float(os.environ.get('SWING', '0.4')):
                e.command('JOY 0 center fire'); wait(6); e.command('JOY 0 center'); wait(6)
            e.command('JOY 0 ' + d)
            for i in range(rnd.randrange(10, 40)):
                if prime and e.peek(0x7E51, 1)[0] < 0x0F: e.poke(0x7E51, 0x0F)
                e.frame(1); f[0] += 1
                ir = e.peek(0xF07C, 1)[0]
                if (ir - irq0[0]) % 256 > 120 and not dumped:      # IRQ storm: the CPU is lost (BRKs)
                    dumped.append(f[0]); r = e.registers()
                    print('IRQ STORM at frame', f[0], 'PC %04X S %02X' % (r['PC'], r['S']), 'gs_s %02X rs_s %02X r_act %d in_ren %d in_girq %d' % (
                        e.peek(0xFCF2, 1)[0], e.peek(0xFCF1, 1)[0], e.peek(0xFCF0, 1)[0], e.peek(0xF06D, 1)[0], e.peek(0xF071, 1)[0]))
                    st = e.peek(0x0100, 0x100)
                    for a in range(0, 256, 32): print('   %04X' % (0x100 + a), st[a:a + 32].hex())
                irq0[0] = ir
                c2 = e.peek(0x17, 1)[0]
                still = still + 1 if c2 == c else 0; c = c2
                if still >= 60:
                    print('FAIL: frozen at frame', f[0], 'mode %02X' % mode(), 'after', hits, 'hits; DLIST %04X' % e.antic()['DLIST'], 'NMIEN %02X' % e.antic()['NMIEN'])
                    e.screenshot('build/_freeze.png')
                    i0 = e.peek(0xF07C, 1)[0]; pcs = []
                    for k in range(8): e.command('CYCLES 3001'); pcs.append('%04X' % e.registers()['PC'])
                    print('  PCs', ' '.join(pcs), 'mapped', e.peek(0xFCC7, 1)[0], 'irqs/8 samples', (e.peek(0xF07C, 1)[0] - i0) % 256,
                          'D012 shadow', e.peek(0xF012, 1)[0], 'r_tgt', e.peek(0xF07A, 1)[0], 'dl_idx', e.peek(0xFCF3, 1)[0],
                          'ev_vbi', e.peek(0xFCF4, 1)[0], 'vector %02X%02X' % tuple(reversed(e.peek(0xC100, 2))), 'D01A', e.peek(0xF01A, 1)[0],
                          'C102', e.peek(0xC102, 1)[0], 'r_act', e.peek(0xFCF0, 1)[0], 'in_nmi', e.peek(0xF07E, 1)[0])
                    raise SystemExit(1)
                h = e.peek(0x066F, 2)
                if h != hp:
                    hits += 1; print('frame', f[0], 'hit: health', hp.hex(), '->', h.hex(), flush=True)
                    e.poke(0x0670, 0xFF); hp = e.peek(0x066F, 2)
            e.command('JOY 0 center')
            if mode() in (6, 7):
                hold('center', lambda: mode() == 5, 600)       # (wandered off the screen: come back)
                hold({'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}[d], lambda: mode() == 7, 300)
                hold('center', lambda: mode() == 5, 600)
                irq0[0] = e.peek(0xF07C, 1)[0]; c = e.peek(0x17, 1)[0]; still = 0   # (counters across the scrolls)
    e.screenshot('build/_fight1.png')
    print('PASS: %d rounds, %d hits, final mode %02X' % (rounds, hits, mode()))
finally:
    e.close()
