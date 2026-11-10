"""Overworld travel with the agent: A* over the 16x8 screens (exits learned in ow_map.json, unvisited screens assumed
open), then on each screen the agent walks to an edge cell and off it. Entrances (levels, caves) from the overworld
level block: attr B & $FC = cave index << 2 (1-9 a level, $10+ a cave), as the NES code reads it."""
import os, json, heapq
import nav as N
import zram as Z

HERE = os.path.dirname(os.path.abspath(__file__))
MAPF = os.path.join(HERE, 'ow_map.json')
STEP = {'left': -1, 'right': 1, 'up': -16, 'down': 16}
LOST = {0x61: {'left', 'down', 'up'}}   # Lost Woods: these exits loop back (only right leaves; west by the 'woods' move)


def load_map():
    return json.load(open(MAPF)) if os.path.exists(MAPF) else {'exits': {}, 'edges': {}}


class Overworld:
    def __init__(self, agent, note=print):
        self.a = agent
        self.m = agent.m
        self.note = note
        self.know = load_map()
        self.blocked = {}                  # (screen, dir) -> failures

    def caves(self):
        """{screen: cave index} from the overworld level block (call in the overworld)."""
        B = self.m.peek(0x68FE, 128)
        return {r: B[r] >> 2 for r in range(128) if B[r] >> 2}

    def wait_play(self, limit=1500):
        for i in range(limit // 4):
            if self.m.peek(Z.MODE) in (5, 0x0B): return True
            self.m.hold('center', 4)
        return False

    def plan(self, s, target, strict=True):
        tx, ty = target & 15, target >> 4
        h = lambda n: abs((n & 15) - tx) + abs((n >> 4) - ty)
        best = {s: 0}; prev = {}; q = [(h(s), 0, s)]
        while q:
            f, g, cur = heapq.heappop(q)
            if cur == target:
                path = []
                while cur in prev: cur, d = prev[cur]; path.append(d)
                return path[::-1]
            dirs = self.know['exits'].get('%02X' % cur, list(STEP)) if strict else list(STEP)
            # (remembered exits come from the part of a screen Link was in: $17 is split, its left and up exits
            # only from the west; without them no way to Level 9. Not strict: every exit, failures still count)
            if cur == 0x61 and g + 4 < best.get(0x60, 99):  # (the Lost Woods: up, left, down, left lead to $60)
                best[0x60] = g + 4; prev[0x60] = (cur, 'woods'); heapq.heappush(q, (g + 4 + h(0x60), g + 4, 0x60))
            for d in dirs:
                if d in LOST.get(cur, ()): continue
                if self.blocked.get((cur, d), 0) >= 3: continue
                n = self.know['edges'].get('%02X%s' % (cur, d), cur + STEP[d])
                if not (0 <= n < 128) or (d in ('left', 'right') and (n >> 4) != (cur >> 4)): continue
                if g + 1 < best.get(n, 99):
                    best[n] = g + 1; prev[n] = (cur, d); heapq.heappush(q, (g + 1 + h(n), g + 1, n))
        return None

    def leave(self, d):
        s0 = self.m.peek(Z.SCREEN)
        ok = self.a.goto(lambda c: d in N.Grid.exits(None, *c), limit=2400)
        if ok and self.m.peek(Z.MODE) == 5:                 # (only from the edge: pushing on regardless walked Link
                                                            # into Level 6's door on $22)
            for i in range(60):
                self.m.hold(d, 2)
                if self.m.peek(Z.MODE) != 5: break
        if not self.wait_play(): return None
        r = self.m.peek(Z.SCREEN)
        return r if r != s0 and self.m.peek(Z.LEVEL) == 0 else None

    def travel(self, target):
        forgot = False
        while self.m.peek(Z.SCREEN) != target:
            if self.m.peek(Z.LEVEL) != 0: raise RuntimeError('travel: not on the overworld (level %d)' % self.m.peek(Z.LEVEL))
            s = self.m.peek(Z.SCREEN)
            g = self.a.grid()
            c0 = self.a.cell()
            reach = set()
            for dc in (-2, -1, 0, 1, 2):                   # (Link can stand where the grid says blocked: just
                for dk in (-2, -1, 0, 1, 2):               # in from an edge, off the 8-pixel grid)
                    c = (c0[0] + dc, c0[1] + dk)
                    if g.open(*c) and c not in reach: reach |= g.reachable(c)
            self.know['exits']['%02X' % s] = sorted({d for c in reach for d in g.exits(*c)})
            route = self.plan(s, target)
            if not route and self.blocked and not forgot:  # (exits failed 3 times, often for monsters in the way:
                self.blocked = {}; forgot = True; route = self.plan(s, target)     # forget them once a trip)
            if not route:
                route = self.plan(s, target, strict=False)
            if not route: raise RuntimeError('no route from %02X to %02X' % (s, target))
            d = route[0]
            self.a.collect(limit=300)
            if d == 'woods':
                for w in ('up', 'left', 'down', 'left'): self.leave(w)
                self.note('screen 61: through the Lost Woods, now %02X' % self.m.peek(Z.SCREEN))
                continue
            new = self.leave(d)
            if new is None:
                self.blocked[(s, d)] = self.blocked.get((s, d), 0) + 1
                self.a.learned.pop((0, s), None)            # (blocked cells learned here may be monsters' doing)
                self.note('screen %02X: could not leave %s' % (s, d)); continue
            actual = {-1: 'left', 1: 'right', -16: 'up', 16: 'down'}.get(new - s)
            if actual != d: self.note('screen %02X: went %s, left %s' % (s, d, actual))
            if actual: self.know['edges']['%02X%s' % (s, actual)] = new
            json.dump(self.know, open(MAPF, 'w'), indent=0)
            st = self.a.snap()
            self.note('screen %02X -> %02X (%s), hearts %d/%d' % (s, new, d, st.hp, st.hp_max))

    def enter(self, level=None):
        """Into the entrance on this screen (a $24 tile reachable from here): walk there and up."""
        self.a.allow_caves = True; self.a._tiles = None
        try:
            g = self.a.grid()
            door_t = {0x24, 0x70, 0x71, 0x72, 0x73}          # (cave mouths; stairs: Level 7's in the dried lake, $42)
            doors = sorted(c for c in g.reachable(self.a.cell()) | {(c, k) for c in range(N.COLS) for k in range(N.ROWS)} if g.t[c[1] + 1][c[0]] in door_t and g.t[c[1] + 1][c[0] + 1] in door_t)
            if not doors: raise RuntimeError('no entrance on screen %02X' % self.m.peek(Z.SCREEN))
            door = doors[0]
            stairs = g.t[door[1] + 1][door[0]] == 0x70
            if stairs:                                      # (stairs: walked onto, from above ($34) or the side ($6D);
                c, k = door[0], door[1] + 1                 # standing on them does nothing)
                for (sc, sk), d in (((c, k - 2), 'down'), ((c - 2, k), 'right'), ((c + 2, k), 'left'),
                                    ((c - 2, k - 2), 'down'), ((c, k + 2), 'up')):
                    if not g.open(sc, sk): continue
                    self.a.goto(lambda q: q == (sc, sk), exact=(sc, sk))
                    for i in range(30):
                        if self.m.peek(Z.MODE) != 5: break
                        self.m.hold(d, 2)
                    if self.m.peek(Z.MODE) != 5: break
            else:
                self.a.goto(lambda c: c == door, exact=door)
        finally:
            self.a.allow_caves = False
        for attempt in range(3):                          # (standing in the doorway already, pushing up did not go
            for i in range(80):                           # in: back off a step and walk in again)
                self.m.hold('up', 2)
                if self.m.peek(Z.MODE) != 5: break
            if self.m.peek(Z.MODE) != 5: break
            self.m.hold('down', 12)
        for i in range(400):
            if self.m.peek(Z.MODE) in (5, 0x0B) and (level is None or self.m.peek(Z.LEVEL) == level): break
            self.m.hold('center', 4)
        return self.m.peek(Z.LEVEL)


def take_cave_item(ow, x=120, addr=Z.SWORD, wait=300):
    """In a cave: wait for the text, walk up to the item at X `x` (they stand on row Y ~$98) until the inventory
    byte at `addr` changes. Returns the new value."""
    m = ow.m
    m.hold('center', wait)
    for i in range(60):
        if m.peek(Z.LINK_Y) <= 181: break
        m.hold('up', 2)
    for i in range(60):
        lx = m.peek(Z.LINK_X)
        if lx == x: break
        m.hold('right' if x > lx else 'left', 1)
    v0 = m.peek(addr)
    for i in range(80):
        if m.peek(addr) != v0: break
        m.hold('up', 2)
    m.hold('center', 150)
    return m.peek(addr)


def leave_cave(ow):
    """Out of a cave: to the exit at the bottom middle, down, until back on the overworld."""
    m = ow.m
    for i in range(60):
        lx = m.peek(Z.LINK_X)
        if lx == 112: break
        m.hold('right' if 112 > lx else 'left', 1)
    for i in range(400):
        if m.peek(Z.MODE) == 5 and m.peek(Z.LINK_Y) < 200 and m.peek(Z.LEVEL) == 0: break
        m.hold('down', 2)
    ow.wait_play()
    m.hold('center', 10)


Overworld.take_cave_item = take_cave_item
Overworld.leave_cave = leave_cave
