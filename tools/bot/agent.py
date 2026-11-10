"""The playing agent, second generation: everything from one RAM snapshot per decision (zero page, pages 3-4, the
inventory page), objects classified by type (NES object types, aldonunez/zelda1-disassembly Z_07 jump tables), fights
that keep out of reach (danger map around monsters and shots), and room retries that keep the cleanest attempt.

Grid and coordinates as nav.py: cell (c, k) = Link at X 8c, Y 61 + 8k. Walkable tiles: overworld from walk_ow.json,
underworld tile < ObjectFirstUnwalkableTile ($034A, $78 in dungeons)."""
import math, random, os
import zram as Z
import nav as N

# ---- object types (index = ObjType)
NAMES = {1: 'blue lynel', 2: 'red lynel', 3: 'blue moblin', 4: 'red moblin', 5: 'blue goriya', 6: 'red goriya',
         7: 'red octorok', 8: 'red octorok f', 9: 'blue octorok', 10: 'blue octorok f', 11: 'red darknut',
         12: 'blue darknut', 13: 'blue tektite', 14: 'red tektite', 15: 'blue leever', 16: 'red leever',
         17: 'zora', 18: 'vire', 19: 'zol', 20: 'gel', 21: 'gel', 22: 'pols voice', 23: 'like like',
         24: 'digdogger child', 26: 'peahat', 27: 'keese', 28: 'keese', 29: 'keese', 30: 'armos', 31: 'boulders',
         32: 'boulder', 33: 'ghini', 34: 'flying ghini', 35: 'blue wizzrobe', 36: 'red wizzrobe', 37: 'patra child',
         38: 'patra child', 39: 'wallmaster', 40: 'rope', 42: 'stalfos', 43: 'bubble', 44: 'bubble', 45: 'bubble',
         46: 'whirlwind', 47: 'pond fairy', 48: 'gibdo', 49: 'dodongo', 50: 'dodongo', 51: 'gohma', 52: 'gohma',
         53: 'rupee stash', 54: 'grumble', 55: 'zelda', 56: 'digdogger', 57: 'digdogger', 58: 'lamnola',
         59: 'lamnola', 60: 'manhandla', 61: 'aquamentus', 62: 'ganon', 63: 'guard fire', 64: 'fire',
         65: 'moldorm', 66: 'gleeok', 67: 'gleeok', 68: 'gleeok', 69: 'gleeok', 70: 'gleeok head', 71: 'patra',
         72: 'patra', 73: 'trap', 74: 'trap'}
for _t in range(75, 83): NAMES[_t] = 'person'
for _t in range(83, 93): NAMES[_t] = 'shot'
NAMES[85] = NAMES[86] = 'fireball'
NOT_FOES = {25, 41, 47, 53, 54, 55} | set(range(75, 83))
UNKILLABLE = {43, 44, 45, 46, 63, 64, 73, 74, 31, 32, 17}      # bubbles, whirlwind, fires, traps, boulders, zora (not armos: awake, the sword kills it)
SHOTS = set(range(83, 93))                       # (92: a goriya's boomerang, in a monster slot)
BIG = {61, 66, 67, 68, 69, 62, 49, 50, 51, 52, 56, 57, 71, 72}  # bosses: 32-px bodies (not Manhandla: five
                                                                   # 16-px parts, body in the middle)

DIR_OF_BITS = {1: 'right', 2: 'left', 4: 'down', 8: 'up'}


class Snap:
    """One look at the game: zero page, pages 3-4 and the inventory."""
    def __init__(self, m):
        self.z = m.peek(0x0000, 0x100)
        self.p = m.peek(0x0300, 0x200)
        self.inv = m.peek(0x0656, 0x2A)

    def zp(self, a): return self.z[a]
    def pg(self, a): return self.p[a - 0x300]
    @property
    def mode(self): return self.z[0x14]
    @property
    def level(self): return self.z[0x12]
    @property
    def room(self): return self.z[0xED]
    @property
    def x(self): return self.z[0x72]
    @property
    def y(self): return self.z[0x86]
    @property
    def ldir(self): return DIR_OF_BITS.get(self.z[0x9A], 'up')
    @property
    def lstate(self): return self.z[0xAE]
    @property
    def all_dead(self): return self.pg(0x34D)
    def item(self, a): return self.inv[a - 0x656]
    @property
    def hp(self):
        h, p = self.item(Z.HEARTS), self.item(Z.HEART_PART)
        return (h & 15) * 2 + (2 if p >= 0x80 else 1 if p else 0)
    @property
    def hp_max(self): return ((self.item(Z.HEARTS) >> 4) + 1) * 2
    @property
    def full(self): return self.item(Z.HEART_PART) >= 0x80 and (self.item(Z.HEARTS) & 15) == self.item(Z.HEARTS) >> 4

    def obj(self, i):
        return {'slot': i, 'type': self.pg(0x34F + i), 'x': self.z[0x72 + i], 'y': self.z[0x86 + i],
                'hp': self.pg(0x485 + i), 'meta': self.pg(0x405 + i), 'inv': self.pg(0x4F0 + i),
                'dir': self.z[0x9A + i], 'state': self.z[0xAE + i]}

    def objects(self):
        out = []
        for i in range(1, 12):
            t = self.pg(0x34F + i)
            if t and t not in NOT_FOES and (t < 0x4B or t in SHOTS):
                o = self.obj(i)
                o['name'] = NAMES.get(t, '?%02X' % t)
                out.append(o)
        return out

    def foes(self):
        """Live monsters (not dying, not still a spawn cloud), and shots."""
        out = []
        for o in self.objects():
            if o['type'] in SHOTS: out.append(o); continue
            if o['meta'] != 0: continue
            if not (0 < o['x'] < 255 and 56 <= o['y'] < 240): continue
            out.append(o)
        return out

    def pending(self):
        """Monsters still appearing (spawn cloud)."""
        return [o for o in self.objects() if o['type'] not in SHOTS and o['type'] not in UNKILLABLE and 1 <= o['meta'] < 0x10]

    def targets(self):
        out = [o for o in self.foes() if o['type'] not in SHOTS and o['type'] not in UNKILLABLE]
        mh = [o for o in out if o['type'] == 60]                # Manhandla: the middle part (no head) only when
        if len(mh) > 1:                                          # it is the last one
            cx = sum(o['x'] for o in mh) / len(mh); cy = sum(o['y'] for o in mh) / len(mh)
            body = min(mh, key=lambda o: abs(o['x'] - cx) + abs(o['y'] - cy))
            out = [o for o in out if o is not body]
        return out

    def room_item(self):
        """The room's item object (slot 19) if it is out: (x, y)."""
        if self.z[0xAE + 19] == 0xFF: return None
        return self.z[0x72 + 19], self.z[0x86 + 19]


DOORWAY_OFF = {(c, k) for c in list(range(0, 4)) + list(range(27, 31)) for k in range(N.ROWS) if k != 10} | \
              {(c, k) for k in list(range(0, 3)) + list(range(18, 21)) for c in range(N.COLS) if c != 15}


def _rm(path):
    try: os.remove(path)
    except OSError: pass


def size(o): return 32 if o['type'] in BIG else 16


SHIELDED = {11, 12}                                       # darknuts: the sword only from the side or behind
OPPD = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}


def blocked_by_shield(o, f):
    """Link facing f to strike o: does o's shield face him?"""
    return o['type'] in SHIELDED and DIR_OF_BITS.get(o['dir'] & 15) == OPPD[f]


class Agent:
    def __init__(self, m, seed=1, log=print):
        self.m = m
        self.rnd = random.Random(seed)
        self.log = log
        self.learned = {}
        self.fight = True
        self.guarding = True                 # segment search: no damage taken if a retry can avoid it
        self.segs = []                       # [(checkpoint, hp, start frame, tries)] newest last
        self.seg_len = 60
        self.seg_tries = 8
        self.retries = 0

    def reset_guard(self):
        self.segs = []
        self.retries0 = self.retries

    def guard(self, s):
        """Call once per decision. Every seg_len frames a checkpoint; when Link has lost hearts since the newest one,
        reload it (up to seg_tries times, then the one before) with a random pause, so another future plays out.
        Returns True when it reloaded (the caller re-reads the state)."""
        w = getattr(self, 'watch', None)
        if w: w(s)
        if not self.guarding: return False
        if s.mode not in (5, 9, 0x0B, 0x11): return False
        n = self.retries - getattr(self, 'retries0', 0)
        if n > 900: return False                  # (hard budget: a room's own retries pick its best attempt)
        if n > 600 and s.mode != 0x11: return False          # (unavoidable hits: take them; a death only after 900)
        f = self.m.frames
        key = (s.level, s.room, 9 if s.mode == 9 else 5)
        if self.segs and getattr(self, '_segkey', None) != key:
            self.segs = []                        # (a checkpoint from another room or the cellar is not a retry: one
        self._segkey = key                        # from room $69 was reloaded inside its cellar, the raft not taken)
        if not self.segs:
            self._seg(s); return False
        cp, hp, f0, tries = self.segs[-1]
        if s.hp < hp or s.mode == 0x11:
            for j in range(len(self.segs) - 1, -1, -1):
                cp, hp, f0, tries = self.segs[j]
                if tries < self.seg_tries:
                    for c in self.segs[j + 1:]: _rm(c[0][0])
                    del self.segs[j + 1:]
                    self.segs[j] = (cp, hp, f0, tries + 1)
                    self.m.load(cp); self.retries += 1
                    self.m.hold('center', self.rnd.randrange(1, 10))
                    self._tiles = None
                    return True
            if s.mode == 0x11 and self.segs:      # (a death is never taken: the oldest checkpoint again)
                cp = self.segs[0][0]
                for c in self.segs[1:]: _rm(c[0][0])
                self.segs = [(cp, self.segs[0][1], self.segs[0][2], 0)]
                self.m.load(cp); self.retries += 1
                self.m.hold('center', self.rnd.randrange(1, 30))
                self._tiles = None
                return True
            self.segs = []; self._seg(s)          # (no retry avoided it: take it)
            return False
        if f - f0 >= self.seg_len:
            self._seg(s)
        return False

    def _seg(self, s):
        n = len(self.segs)
        self._segn = getattr(self, '_segn', 0) + 1           # (unique names: a reused name once paired an old log
        cp = self.m.save('seg%06d' % self._segn)            # with a newer state)
        self.segs.append((cp, s.hp, self.m.frames, 0))
        if len(self.segs) > 3: _rm(self.segs.pop(0)[0][0])

    def snap(self): return Snap(self.m)

    def walkset(self, s):
        if s.mode == 9: return {0x24, 0x6F}                # (a cellar, side view: floors and ladders)
        if s.level == 0:                                # (cave and level mouths only when going in)
            if getattr(self, 'allow_caves', False):        # (going in: cave mouths, stairs, a dried lake's bed)
                return N.WALK_OW | {0x70, 0x71, 0x72, 0x73} | (set(range(0x8D, 0x99)) if s.room == 0x42 else set())
            return N.WALK_OW - {0x24}
        return set(range(s.pg(0x34A)))

    def tiles(self, s):
        """The play-area tiles, re-read on a room change or every 60 frames (doors and blocks change them)."""
        key = (s.level, s.room, s.mode)
        c = getattr(self, '_tiles', None)
        if c is None or c[0] != key or self.m.frames - c[1] > 60:
            c = self._tiles = (key, self.m.frames, Z.tiles(self.m))
        return c[2]

    def grid(self, s=None, ladder=True):
        s = s or self.snap()
        lad = {0xF4} if ladder and s.level and s.mode != 9 and s.item(Z.LADDER) else ()  # (dungeon water: the ladder)
        blocked = set(self.learned.get((s.level, s.room), ()))
        if s.level and s.mode != 9:                     # (door passages: only along them, Link turns nowhere in a
            blocked |= DOORWAY_OFF                      # doorway: Level 8 room $7E, up from the left door)
        return N.Grid(self.tiles(s), walk=self.walkset(s), blocked=blocked, ladder=lad)

    def cell(self, s=None):
        s = s or self.snap()
        return N.cell_of(s.x, s.y)

    # ---- danger
    def danger(self, s, margin=2):
        """Cells Link should not step into: within reach of a monster or a shot (by its box + margin)."""
        bad = set()
        for o in s.foes():
            sz = size(o)
            x0, y0, x1, y1 = o['x'] - 16 - margin, o['y'] - 16 - margin, o['x'] + sz + margin, o['y'] + sz + margin
            for c in range(max(0, (x0 + 7) // 8), min(N.COLS, x1 // 8 + 1)):
                for k in range(max(0, (y0 - Z.PLAY_TOP + 7) // 8), min(N.ROWS, (y1 - Z.PLAY_TOP) // 8 + 1)):
                    px, py = N.pos_of(c, k)
                    if x0 < px < x1 and y0 < py < y1: bad.add((c, k))
        return bad

    # ---- sword
    def swing(self, face):
        if self.snap().ldir != face:
            self.m.hold(face, 1)
        self.m.hold(face, 2, fire=True)
        for i in range(8):
            self.m.hold('center', 2)
            if self.m.peek(0xAE) == 0: break

    def aligned(self, s, o, reach):
        """The direction to face to hit o from here, or None."""
        dx, dy = o['x'] - s.x, o['y'] - s.y
        sz = size(o)
        if -sz + 6 <= dy <= 10:
            if 0 < dx <= reach: return 'right'
            if -reach - sz + 16 <= dx < 0: return 'left'
        if -sz + 6 <= dx <= 10:
            if 0 < dy <= reach: return 'down'
            if -reach - sz + 16 <= dy < 0: return 'up'
        return None

    def kill_all(self, limit=3600, want=None):
        """Fight until no killable monster is left (or `want()` says stop). Returns True when the room is clear."""
        start = self.m.frames
        while self.m.frames - start < limit:
            s = self.snap()
            if self.guard(s): continue
            if s.mode not in (5, 9, 0x0B): return False
            if want and want(s): return True
            tg = s.targets()
            if not tg:
                if s.all_dead or not s.pending(): return True
                self.m.hold('center', 2); continue
            reach = 200 if s.full else 22
            hit = None
            for o in sorted(tg, key=lambda o: abs(o['x'] - s.x) + abs(o['y'] - s.y)):
                f = self.aligned(s, o, reach if o['type'] not in (11, 12) else 22)
                if f and o['inv'] == 0: hit = f; break
            if hit:
                self.swing(hit); continue
            self.approach(s, tg)
        return False

    def approach(self, s, tg):
        """A few frames toward a cell from which to hit the nearest target, keeping out of the danger cells."""
        g = self.grid(s)
        here = N.cell_of(s.x, s.y)
        bad = self.danger(s)
        o = min(tg, key=lambda o: abs(o['x'] - s.x) + abs(o['y'] - s.y))
        sz = size(o)
        goals = set()
        for c in range(N.COLS):
            for k in range(N.ROWS):
                px, py = N.pos_of(c, k)
                dx, dy = o['x'] - px, o['y'] - py
                if -sz + 6 <= dy <= 10:
                    if 16 <= dx <= 24 and not blocked_by_shield(o, 'right'): goals.add((c, k))
                    if -sz - 8 <= dx <= -sz and not blocked_by_shield(o, 'left'): goals.add((c, k))
                if -sz + 6 <= dx <= 10:
                    if 16 <= dy <= 24 and not blocked_by_shield(o, 'down'): goals.add((c, k))
                    if -sz - 8 <= dy <= -sz and not blocked_by_shield(o, 'up'): goals.add((c, k))
        if s.full and o['type'] not in SHIELDED:          # (the sword beam: any distance on the row/column)
            oc = N.cell_of(o['x'], o['y'])
            for c in range(N.COLS): goals.add((c, oc[1]))
            for k in range(N.ROWS): goals.add((oc[0], k))
        goals = {c for c in goals if g.open(*c) and c not in bad}
        if here in bad:                                     # (too close: step out first)
            esc = [(N.cell_of(s.x, s.y)[0] + dc, N.cell_of(s.x, s.y)[1] + dk) for dc, dk in N.STEP.values()]
            esc = [c for c in esc if g.open(*c)]
            if esc:
                best = max(esc, key=lambda c: min(abs(N.pos_of(*c)[0] - f['x']) + abs(N.pos_of(*c)[1] - f['y'])
                                                  for f in s.foes()))
                self.step_toward(s, best, 4); return
        path = g.path(here, lambda c: c in goals, avoid=bad) if goals else None
        if not path or len(path) < 2:
            self.m.hold('center', 3); return
        self.step_toward(s, path[1] if len(path) > 1 else path[0], 4)

    def step_toward(self, s, cell, n):
        tx, ty = N.pos_of(*cell)
        dx, dy = tx - s.x, ty - s.y
        cur = N.cell_of(s.x, s.y)
        # A move to the next cell along one axis: first finish lining up on the other one (a few pixels off and
        # walking into a 1-cell gap, Link pushed against its edge for good: Level 1 room $33)
        if cell[0] == cur[0] and cell[1] != cur[1] and 0 < abs(dx) < 8:
            self.m.hold('right' if dx > 0 else 'left', 1); return
        if cell[1] == cur[1] and cell[0] != cur[0] and 0 < abs(dy) < 8:
            self.m.hold('down' if dy > 0 else 'up', 1); return
        if abs(dx) >= abs(dy) and dx: d = 'right' if dx > 0 else 'left'
        elif dy: d = 'down' if dy > 0 else 'up'
        else: self.m.hold('center', 1); return
        self.m.hold(d, max(1, min(n, (abs(dx) or abs(dy)) * 2 // 3)))   # (1.5 px a frame: no overshoot, which
                                                                          # put the ladder out next to water)


FRONT = {'up': (15, 4), 'down': (15, 16), 'left': (4, 10), 'right': (26, 10)}   # dungeon door: the cell inside it


class Stuck(Exception): pass


def _agent_goto(self, goal, limit=1500, fight=True, exact=None):
    """Walk to a cell where goal(cell) is true (exact: a cell to stand on to the pixel). Fights targets that come
    within reach on the way. Returns True when there."""
    start = self.m.frames
    last, still = None, 0
    its = 0
    while self.m.frames - start < limit and its < limit:
        its += 1
        s = self.snap()
        if self.guard(s):
            last, still = None, 0; continue
        if s.mode not in (5, 9, 0x0B): self._why = 'mode %02X' % s.mode; return False
        here = N.cell_of(s.x, s.y)
        if exact and here == exact:
            tx, ty = N.pos_of(*exact)
            if (s.x, s.y) == (tx, ty): return True
            d = ('right' if tx > s.x else 'left') if s.x != tx else ('down' if ty > s.y else 'up')
            self.m.hold(d, 1)
            if (s.x, s.y) == last: still += 1
            if still > 12: return True                   # (as close as it gets)
            last = (s.x, s.y); continue
        if not exact and goal(here): return True
        if fight:
            near = [o for o in s.targets() if abs(o['x'] - s.x) < 28 and abs(o['y'] - s.y) < 28]
            for o in near:
                f = self.aligned(s, o, 22)
                if f and o['inv'] == 0: self.swing(f); break
            else: near = None
            if near: continue
        g = self.grid(s, ladder=False)                   # (dry land first: the ladder only where nothing else goes)
        bad = self.danger(s, margin=2) - {here}
        path = g.path(here, goal, avoid=bad) or g.path(here, goal)
        if path is None:
            g = self.grid(s)
            path = g.path(here, goal, avoid=bad)
        if path is None:
            path = g.path(here, goal)
            if path is None:
                if not g.open(*here):
                    self.m.hold(self.rnd.choice(list(N.STEP)), 3); continue
                self._why = 'no path from %s' % (here,); return False
        if len(path) < 2:
            if goal(here): return True
            self.m.hold('center', 2); continue
        self.step_toward(s, path[1], 4)
        if (s.x, s.y) == last and any(s.pg(0x34F + i) == 0x5F for i in range(1, 12)):
            self.off_ladder(); last, still = None, 0; continue
        if (s.x, s.y) == last:
            still += 1
            nxt = path[1]
            px, py = N.pos_of(*nxt)
            foe_near = any(abs(o['x'] - px) < 28 and abs(o['y'] - py) < 28 for o in s.foes())
            if foe_near: still = 0                       # (a monster in the way, not a wall)
            if still >= 6 and s.level == 0:            # (dungeon walls are exact: tile < $78; learn only outside)
                self.learned.setdefault((s.level, s.room), set()).add(nxt)
                self.log('  blocked at %s: cell %s marked' % (here, nxt)); still = 0
        else: still = 0
        last = (s.x, s.y)
    self._why = 'limit'; return False


Agent.goto = _agent_goto


def _agent_off_ladder(self):
    """The ladder is out (object $5F, put down when Link walks into water with it): Link moves only along it.
    Step each way until he moves and it is gone (Level 5 room $47: pushed left against it for good)."""
    for d in ('down', 'up', 'right', 'left', 'down', 'up'):
        x0, y0 = self.m.peek(0x72), self.m.peek(0x86)
        self.m.hold(d, 8)
        if not any(self.m.peek(0x34F + i) == 0x5F for i in range(1, 12)): return True
    return False


Agent.off_ladder = _agent_off_ladder


# ---- prediction and dodging
def _agent_track(self, s):
    """Velocities of the foes (px per frame) from the last snapshot: {slot: (vx, vy)}."""
    prev = getattr(self, '_prev', None)
    f = self.m.frames
    cur = {o['slot']: (o['x'], o['y'], o['type']) for o in s.foes()}
    vel = {}
    if prev and 0 < f - prev[0] <= 8:
        dt = f - prev[0]
        for k, (x, y, t) in cur.items():
            p = prev[1].get(k)
            if p and p[2] == t and abs(x - p[0]) < 24 and abs(y - p[1]) < 24:
                vel[k] = ((x - p[0]) / dt, (y - p[1]) / dt)
    orb = {}                                             # (Patra's orbiters: a straight line misses them; angle and
    pat = [o for o in s.foes() if o['type'] in (71, 72)]  # radius round Patra, with Patra's own drift)
    if pat and prev and 0 < f - prev[0] <= 8:
        P = pat[0]; pc = (P['x'] + 8, P['y'] + 8)
        pp = prev[2] if len(prev) > 2 else None
        if pp:
            dt = f - prev[0]
            pv = ((pc[0] - pp[0]) / dt, (pc[1] - pp[1]) / dt)
            for k, (x, y, t) in cur.items():
                p = prev[1].get(k)
                if t not in (37, 38) or not p or p[2] != t: continue
                a0 = math.atan2(p[1] + 8 - pp[1], p[0] + 4 - pp[0]); a1 = math.atan2(y + 8 - pc[1], x + 4 - pc[0])
                r0 = math.hypot(p[1] + 8 - pp[1], p[0] + 4 - pp[0]); r1 = math.hypot(y + 8 - pc[1], x + 4 - pc[0])
                da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
                orb[k] = (pc, pv, r1, a1, (r1 - r0) / dt, da / dt)
        self._prev = (f, cur, pc)
    else:
        self._prev = (f, cur)
    self._vel = vel
    self._orb = orb
    return vel


def orbit_at(orb, t):
    """Top left of an orbiter t frames on."""
    pc, pv, r, a, dr, da = orb
    r, a = r + dr * t, a + da * t
    return pc[0] + pv[0] * t + r * math.cos(a) - 4, pc[1] + pv[1] * t + r * math.sin(a) - 8


LINK_SPEED = 1.5
MOVES = {'center': (0, 0), 'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}


def _agent_risk(self, s, move, horizon=16, shots_only=False):
    """First frame (1..horizon) at which Link, doing `move`, would touch a foe going on at its current velocity;
    horizon + 1 when none does."""
    vel = getattr(self, '_vel', {})
    g = self.grid(s)
    mx, my = MOVES[move]
    foes = [o for o in s.foes() if not shots_only or o['type'] in SHOTS]
    for t in range(1, horizon + 1, 2):
        lx, ly = s.x + mx * LINK_SPEED * t, s.y + my * LINK_SPEED * t
        if move != 'center' and not g.open(*N.cell_of(int(lx), int(ly))):
            lx, ly = s.x, s.y                                # (a wall: he stays)
        orb = getattr(self, '_orb', {})
        for o in foes:
            vx, vy = vel.get(o['slot'], (0, 0))
            fx, fy = o['x'] + vx * t, o['y'] + vy * t
            if o['slot'] in orb: fx, fy = orbit_at(orb[o['slot']], t)
            sz = size(o)
            shot = o['type'] in SHOTS
            pad = 2 if shot else 3
            ox0, ox1 = (fx + 4, fx + 12) if shot and sz == 16 else (fx, fx + sz)
            oy0, oy1 = (fy + 4, fy + 12) if shot and sz == 16 else (fy, fy + sz)
            if lx + 16 - pad > ox0 and lx + pad < ox1 and ly + 16 - pad > oy0 and ly + pad < oy1:
                return t
    return horizon + 1


def _agent_dodge(self, s, horizon=14):
    """If staying put gets Link hit within the horizon, the move that keeps him clear longest (else None)."""
    stay = self.risk(s, 'center', horizon)
    if stay > horizon: return None
    best = max(MOVES, key=lambda mv: (self.risk(s, mv, horizon), mv == 'center'))
    return best if best != 'center' and self.risk(s, best, horizon) > stay else None


Agent.track = _agent_track
Agent.risk = _agent_risk
Agent.dodge = _agent_dodge


def _agent_kill_all(self, limit=3600, want=None):
    """Fight until no killable monster is left (or `want()` says stop). Each decision: dodge what is about to hit,
    else swing at a target in line (if standing still for the swing is safe), else move toward a striking cell."""
    start = self.m.frames
    its = 0
    while self.m.frames - start < limit and its < limit:     # (reloads rewind frames: count decisions too)
        its += 1
        s = self.snap()
        if self.guard(s): self._prev = None; continue
        if s.mode not in (5, 9, 0x0B): return False
        if want and want(s): return True
        self.track(s)
        tg = s.targets()
        if not tg:
            if s.all_dead or not s.pending(): return True
            d = self.dodge(s)
            self.m.hold(d or 'center', 2); continue
        d = self.dodge(s)
        if d:
            self.m.hold(d, 3); continue
        reach = 200 if s.full else 26
        hit = None
        for o in sorted(tg, key=lambda o: abs(o['x'] - s.x) + abs(o['y'] - s.y)):
            f = self.aligned(s, o, reach if o['type'] not in SHIELDED else 26)
            if f and o['inv'] == 0 and not blocked_by_shield(o, f): hit = f; break
        if hit and self.risk(s, 'center', 14) > 14:
            self.swing(hit); continue
        if hit:                                            # (in line but a hit is coming: back off)
            self.m.hold(self.dodge(s, 24) or 'center', 2); continue
        self.approach(s, tg)
    return False


Agent.kill_all = _agent_kill_all


# ---- items (B button = SPACE)
ITEM_SLOT = {'boomerang': 0, 'bombs': 1, 'bow': 2, 'candle': 4, 'recorder': 5, 'bait': 6, 'potion': 7, 'wand': 8}
# (measured for the recorder: the menu offered 0, 1, 5 with boomerang, bombs, recorder; 5 + B made the whirlwind)


def _agent_select(self, slot, tries=16):
    """Choose the B item through the menu (START, right until $0656 = slot, START). True when selected.
    The port can hang in the menu (HANDOFF bug 4: bank 11 $BC38 waits for raster bit 8, which the port's virtual
    raster shows for 6 lines only): when the game's frame counter stops, back to before START and try later."""
    if self.m.peek(0x656) == slot: return True
    if self.m.peek(Z.MODE) != 5 or self.m.peek(0xAE) != 0: return False
    cp = self.m.save('menu')
    for t in range(tries):
        if t:
            self.m.load(cp); self.m.hold('center', self.rnd.randrange(8, 40)); self.hangs = getattr(self, 'hangs', 0) + 1
        r = self._menu(slot)
        if r: return True
        if r is None: self.log('  menu hung (try %d)' % (t + 1))
    self.m.load(cp)
    return False


def _agent_menu(self, slot):
    def wait(cond, n):
        fc, still = self.m.peek(0x17), 0
        for i in range(n):
            if cond(): return True
            self.m.hold('center', 4)
            f2 = self.m.peek(0x17)
            still = still + 1 if f2 == fc else 0
            fc = f2
            if still >= 10: return None                  # (frame counter stopped: hung)
        return cond()
    self.m.hold('center', 4, consol='start'); self.m.hold('center', 2)
    for i in range(10):
        if self.m.peek(0xE3): break
        self.m.hold('center', 2)
    if not self.m.peek(0xE3): return False
    r = wait(lambda: self.m.peek(0xE3) == 8, 120)      # (the C64 menu: 7 scrolls down, 8 is open: the cursor
                                                         # moved during 7 only by luck)
    if r is None: return None
    for i in range(10):
        if self.m.peek(0x656) == slot: break
        self.m.hold('right', 4); self.m.hold('center', 6)
    self.m.hold('center', 40)          # (START soon after a cursor move hung the menu too: E3 stayed 8)
    self.m.hold('center', 4, consol='start'); self.m.hold('center', 2)
    r = wait(lambda: self.m.peek(0xE3) == 0, 120)
    if r is None: return None
    self.m.hold('center', 2)
    return self.m.peek(0x656) == slot


Agent._menu = _agent_menu


def _agent_use_b(self, face=None):
    """Use the B item, facing `face`."""
    if face and self.snap().ldir != face: self.m.hold(face, 1)
    self.m.hold(face or 'center', 2, key='space')
    self.m.hold('center', 2)


Agent.select = _agent_select
Agent.use_b = _agent_use_b


# ---- dropped items (an object of type $60 in a monster slot; item id in its ObjState)
DROP_IDS = {0x18: 'rupee', 0x0F: '5 rupees', 0x00: 'bombs', 0x22: 'heart', 0x23: 'fairy', 0x21: 'clock', 0x19: 'key'}


def _snap_drops(self):
    out = []
    for i in range(1, 12):
        if self.pg(0x34F + i) == 0x60:
            out.append({'slot': i, 'id': self.z[0xAE + i], 'x': self.z[0x72 + i], 'y': self.z[0x86 + i],
                        'name': DROP_IDS.get(self.z[0xAE + i], '?%02X' % self.z[0xAE + i])})
    return out


Snap.drops = _snap_drops


def _agent_collect(self, limit=600):
    """Walk over the useful drops on the screen (rupees, bombs, keys; hearts and fairies when hurt)."""
    start = self.m.frames
    while self.m.frames - start < limit:
        s = self.snap()
        if s.mode not in (5, 0x0B): return
        want = [d for d in s.drops() if d['name'] in ('rupee', '5 rupees', 'bombs', 'key', 'clock')
                or (d['name'] in ('heart', 'fairy') and s.hp < s.hp_max)]
        if not want: return
        d = min(want, key=lambda d: abs(d['x'] - s.x) + abs(d['y'] - s.y))
        goal = N.cell_of(d['x'], d['y'] - 3)
        g = self.grid(s)
        near = [(goal[0] + dc, goal[1] + dk) for dc in (0, -1, 1) for dk in (0, -1, 1)]
        near = [c for c in near if g.open(*c)]
        if not near: return
        slot = d['slot']
        ok = self.goto(lambda c: c in near, limit=240)
        for i in range(6):
            if self.m.peek(0x34F + slot) != 0x60: break
            self.step_toward(self.snap(), goal, 2)
        if self.m.peek(0x34F + slot) == 0x60 and not ok: return


Agent.collect = _agent_collect
