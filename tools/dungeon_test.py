#!/usr/bin/env python3
"""python3 tools/dungeon_test.py [CART] [ROUNDS] : into the LEVEL-3 dungeon and fight there. Route (found in the host
model, see HANDOFF): from the start screen ($77) west to $76, Link placed at (24, 117) and walked left to $75, at (24, 45) and
walked left onto $74, placed at (128, 141) below the entrance and walked up (game modes $10, 2, 3, 4, 5). Then ROUNDS
rounds of wandering with sword swings (sword flag $0657 set, health topped up). FAIL if the game freezes (main-loop
counter $17 stops for 60 frames); screenshots build/_dg*.png. ($72/$86 = Link's object position.)"""
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
cart = sys.argv[1] if len(sys.argv) > 1 else None
rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 40
e = boot_game(cart)
f = [0]
def pos(): return e.peek(0x72, 1)[0], e.peek(0x86, 1)[0]
def mode(): return e.peek(0x14, 1)[0]
def scr(): return e.peek(0xED, 1)[0]
def wait(n):
    for i in range(n):
        e.frame(1); f[0] += 1
        if f[0] % 30 == 0:                                  # full hearts ($066F: max << 4 | hearts) and partial
            h = e.peek(0x066F, 1)[0]; e.poke(0x066F, (h & 0xF0) | (h >> 4)); e.poke(0x0670, 0xFF)
def hold(d, cond, limit=600):
    e.command('JOY 0 ' + d)
    for i in range(limit):
        wait(1)
        if cond(): break
    e.command('JOY 0 center')
    return cond()
try:
    wait(60); e.poke(0x0657, 1)
    print('start screen %02X link %s' % (scr(), pos()), flush=True)
    assert hold('left', lambda: scr() == 0x76 and mode() == 5, 900), ('west', hex(scr()), pos())
    e.poke(0x72, 24); e.poke(0x86, 117); wait(2)                # (the open row on $76's west edge)
    assert hold('left', lambda: scr() == 0x75 and mode() == 5, 900), ('west', hex(scr()), pos())
    e.poke(0x72, 24); e.poke(0x86, 45); wait(2)
    assert hold('left', lambda: scr() == 0x74 and mode() == 5, 900), ('onto $74', hex(scr()), pos())
    e.poke(0x72, 128); e.poke(0x86, 141); wait(2)
    seen = []
    e.command('JOY 0 up')
    for i in range(600):
        wait(1); md = mode()
        if not seen or seen[-1] != md: seen.append(md)
        if seen[-2:] == [4, 5] or (len(seen) > 3 and md == 5): break
    e.command('JOY 0 center'); wait(60)
    print('into the dungeon: modes %s, screen %02X, link %s' % (' '.join('%02X' % m for m in seen), scr(), pos()), flush=True)
    e.screenshot('build/_dg0.png')
    rnd = random.Random(1); c, still = e.peek(0x17, 1)[0], 0
    dungeon = scr(); rooms = {dungeon}; outs = 0
    for r in range(rounds):
        if scr() == 0x74 and mode() == 5:                   # walked out of the entrance: back in
            outs += 1; e.poke(0x72, 128); e.poke(0x86, 141); wait(2)
            hold('up', lambda: mode() == 5 and scr() != 0x74, 600); wait(30)
        rooms.add(scr())
        d = rnd.choice(['up', 'up', 'left', 'right', 'down'])
        if rnd.random() < 0.4:
            e.command('JOY 0 center fire'); wait(6); e.command('JOY 0 center'); wait(4)
        e.command('JOY 0 ' + d)
        for i in range(rnd.randrange(20, 60)):
            wait(1); c2 = e.peek(0x17, 1)[0]
            still = still + 1 if c2 == c else 0; c = c2
            if still >= 60:
                print('FAIL: frozen at frame %d mode %02X screen %02X' % (f[0], mode(), scr())); e.screenshot('build/_dgfreeze.png'); raise SystemExit(1)
        e.command('JOY 0 center')
        if r % 10 == 9: e.screenshot('build/_dg%d.png' % (r // 10 + 1))
    print('PASS: %d rounds in the dungeon (%d rooms: %s, walked out %d times), final mode %02X screen %02X' % (
        rounds, len(rooms), ' '.join('%02X' % x for x in sorted(rooms)), outs, mode(), scr()))
finally:
    e.close()
