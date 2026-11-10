#!/usr/bin/env python3
"""python3 tools/bot/run_l1.py [OUT.json] : power-on to the inside of Level 1, played by the bot.
Title, register GZ, the sword from the first cave, overworld to screen $37 (Level 1's entrance), in through the door,
a few steps into the first room. Writes the input log (replayed by record.py for the movie)."""
import sys, os, json, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from emu import Emu, ROOT
from menus import to_game
import zram as Z, nav as N
from bot import Bot, Event, SCREEN_STEP

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build/bot_l1.json')
TARGET = 0x37
t0 = time.time()
m = Emu()
b = Bot(m)
notes = []                                                # (frame, what) for the movie's chapters and the report


def note(s):
    notes.append((m.frames, s)); print('[%6d %4.0fs] %s' % (m.frames, time.time() - t0, s), flush=True)


def sxy(s): return s & 15, s >> 4


def get_sword():
    try:
        b.walk_to(lambda c: c == (8, 2), then='up')
    except Event as ev:
        assert ev.kind == 'enter', ev.kind
    note('in the cave, mode %02X' % b.mode())           # (mode $0B is the play mode underground)
    m.hold('center', 730)                                 # (the old man's text)
    def hold_until(d, cond, n):
        for i in range(n // 2):
            if cond(): return
            m.hold(d, 2)
    hold_until('up', lambda: b.pos()[1] <= 180, 100)
    x0 = b.pos()[0]
    hold_until('right', lambda: b.pos()[0] >= x0 + 6, 60)
    hold_until('up', lambda: m.peek(Z.SWORD) != 0, 150)
    assert m.peek(Z.SWORD), 'no sword'
    note('sword')
    m.hold('center', 150)
    hold_until('left', lambda: b.pos()[0] <= 112, 40)
    hold_until('down', lambda: b.mode() == 5 and b.pos()[1] < 100, 900)
    assert b.wait_play(), 'out of the cave'
    note('out of the cave, screen %02X' % b.screen())


MAPF = os.path.join(HERE, 'ow_map.json')
KNOW = json.load(open(MAPF)) if os.path.exists(MAPF) else {'exits': {}, 'edges': {}}


def plan(s, target):
    """A* over screens: known exits of visited screens, unvisited screens assumed open both ways."""
    import heapq
    tx, ty = sxy(target)
    h = lambda n: abs((n & 15) - tx) + abs((n >> 4) - ty)
    best = {s: 0}; prev = {}; q = [(h(s), 0, s)]
    while q:
        f, g, cur = heapq.heappop(q)
        if cur == target:
            path = [cur]
            while cur in prev: cur, d = prev[cur]; path.append(d)
            return path[::-1]
        dirs = KNOW['exits'].get('%02X' % cur, list(SCREEN_STEP))
        for d in dirs:
            n = KNOW['edges'].get('%02X%s' % (cur, d), cur + SCREEN_STEP[d])
            if not (0 <= n < 128) or (d in ('left', 'right') and (n >> 4) != (cur >> 4)): continue
            if g + 1 < best.get(n, 99):
                best[n] = g + 1; prev[n] = (cur, d); heapq.heappush(q, (g + 1 + h(n), g + 1, n))
    return None


def travel(target):
    tries = {}
    cp = m.save('screen_%02X' % b.screen()); hp_cp = Z.hearts(m)[0]
    while b.screen() != target:
        s = b.screen()
        g = b.grid()
        reach = g.reachable(b.cell())
        dirs = sorted({d for c in reach for d in g.exits(*c)})
        KNOW['exits']['%02X' % s] = [d for d in dirs if tries.get((s, d), 0) < 4]
        route = plan(s, target)
        if not route: raise SystemExit('no route from %02X' % s)
        d = route[0]
        try:
            new = b.leave(d)
        except Event as ev:
            tries[(s, d)] = tries.get((s, d), 0) + 1
            note('screen %02X going %s: %s, back to the checkpoint (try %d)' % (s, d, ev.kind, tries[(s, d)]))
            m.load(cp); m.hold('center', b.rnd.randrange(5, 60))
            continue
        if new is None:
            tries[(s, d)] = tries.get((s, d), 0) + 1
            note('screen %02X: could not leave %s' % (s, d))
            continue
        KNOW['edges']['%02X%s' % (s, d)] = new
        json.dump(KNOW, open(MAPF, 'w'), indent=0)
        hp, mx = Z.hearts(m)
        if hp_cp - hp >= 2 and tries.get((s, d), 0) < 6:   # (a heart or more lost on this screen: again, cleaner)
            tries[(s, d)] = tries.get((s, d), 0) + 1
            note('screen %02X -> %02X lost %d half hearts: again from the checkpoint (try %d)' % (s, new, hp_cp - hp, tries[(s, d)]))
            m.load(cp); m.hold('center', b.rnd.randrange(5, 60))
            continue
        note('screen %02X -> %02X (%s), hearts %d/%d' % (s, new, d, hp, mx))
        cp = m.save('screen_%02X' % new); hp_cp = hp


def enter_level():
    cp = m.save('level_door'); hp_cp = Z.hearts(m)[0]
    for t in range(8):
        g = b.grid()
        doors = sorted(c for c in g.reachable(b.cell()) if g.t[c[1] + 1][c[0]] == 0x24)
        assert doors, 'no door'
        try:
            b.walk_to(lambda c: c == doors[0], then='up')
        except Event as ev:
            if ev.kind == 'enter' and hp_cp - Z.hearts(m)[0] < 2: break
            note('to the door: %s, back to the checkpoint (try %d)' % (ev.kind, t + 1))
        m.load(cp); m.hold('center', b.rnd.randrange(5, 60))
    for i in range(300):
        if m.peek(Z.LEVEL) == 1 and b.mode() == 5: break
        m.hold('center', 4)
    note('in Level %d, room %02X, mode %02X' % (m.peek(Z.LEVEL), b.screen(), b.mode()))


try:
    to_game(m)
    note('game, screen %02X' % b.screen())
    get_sword()
    travel(TARGET)
    note('at Level 1 screen %02X' % b.screen())
    enter_level()
    b.fight = False
    for d, n in (('up', 40), ('center', 30)):
        m.hold(d, n)
    note('end')
finally:
    json.dump({'log': m.log, 'notes': notes, 'frames': m.frames}, open(out, 'w'))
    print('frames %d (%.1f min of game), %.0f s, log %s' % (m.frames, m.frames / 3600, time.time() - t0, out))
    m.close()
