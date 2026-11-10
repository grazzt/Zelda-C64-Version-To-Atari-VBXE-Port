"""Dungeon (underworld) data from the game's RAM: the level block ($687E: six 128-byte attribute tables, one byte per
room of the 16x8 map) and the level info ($6B7E). Decoding follows the NES disassembly (aldonunez/zelda1-disassembly,
Z_05 FindDoorTypeByDoorBit, InitMode4/DestroyObject_WRAM, CheckSecretTrigger): the C64 port keeps this RAM unchanged.

Doors: attr A bits 5-7 north, 2-4 south; attr B bits 5-7 west, 2-4 east. Types: 0 open, 1 wall, 2/3 false wall (walk
through), 4 bombable, 5/6 locked (a key), 7 shutter. Attr E & $1F: room item (3 = none). Attr F & 7: secret trigger
(1 all dead -> shutters, 2 ringleader, 3 last boss, 4 push block -> shutters, 5 push block -> stairs, 6 money or life,
7 all dead -> the room item appears); F bits 4-5: item position index. Attr D bit 6: push block. Cellars
(LevelInfo cellar array, 10 rooms): attr A/B = the rooms the left/right stairs lead back to."""
A0, B0, C0, D0, E0, F0 = 0x687E, 0x68FE, 0x697E, 0x69FE, 0x6A7E, 0x6AFE
INFO = 0x6B7E
DIRS = ('up', 'down', 'left', 'right')
STEP = {'up': -16, 'down': 16, 'left': -1, 'right': 1}
OPP = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'}
DOOR = {0: 'open', 1: 'wall', 2: 'false', 3: 'false', 4: 'bomb', 5: 'key', 6: 'key', 7: 'shutter'}
DOOR_BIT = {'right': 1, 'left': 2, 'down': 4, 'up': 8}
ITEMS = {0x00: 'bombs', 0x01: 'wood sword', 0x02: 'white sword', 0x03: None, 0x04: 'bait', 0x05: 'recorder',
         0x06: 'blue candle', 0x07: 'red candle', 0x08: 'arrows', 0x09: 'silver arrows', 0x0A: 'bow',
         0x0B: 'magic key', 0x0C: 'raft', 0x0D: 'ladder', 0x0E: 'triforce of power', 0x0F: '5 rupees',
         0x10: 'wand', 0x11: 'book', 0x12: 'blue ring', 0x13: 'red ring', 0x14: 'bracelet', 0x15: 'letter',
         0x16: 'compass', 0x17: 'map', 0x18: 'rupee', 0x19: 'key', 0x1A: 'heart container', 0x1B: 'triforce',
         0x1C: 'magic shield', 0x1D: 'boomerang', 0x1E: 'magic boomerang', 0x1F: 'blue potion'}
CELLAR_ITEMS = {'bow', 'raft', 'ladder', 'recorder', 'wand', 'book', 'red candle', 'magic key', 'silver arrows',
                'red ring', 'magic boomerang', 'heart container', 'bracelet'}
SECRET = {0: None, 1: 'all dead', 2: 'ringleader', 3: 'last boss', 4: 'block door', 5: 'block stairs',
          6: 'money or life', 7: 'foes for item'}


class Level:
    def __init__(self, m):
        self.A, self.B, self.C, self.D, self.E, self.F = (m.peek(a, 128) for a in (A0, B0, C0, D0, E0, F0))
        info = m.peek(INFO, 0x80)
        self.foe_counts = info[0x24:0x28]
        self.start_y = info[0x28]
        self.item_pos = [(p & 0xF0, (p & 0x0F) << 4) for p in info[0x29:0x2D]]   # (x, y)
        self.start = info[0x2F]
        self.triforce = info[0x30]
        self.number = info[0x33]
        self.cellars = [c for c in info[0x34:0x3E] if c < 0x80]
        self.boss = info[0x3E]
        self.flags_addr = info[0x31] | info[0x32] << 8
        self.m = m
        # Level 3's cellar list is all $FF in the cartridge (C64 and port alike), yet its raft room $0F lies under
        # room $69: the NES code searches on past the list. So item rooms whose A = B = a room of this level, holding
        # a cellar item, count as cellars too.
        base = self.rooms()
        for r in range(128):
            if r in base or r in self.cellars: continue
            if self.A[r] == self.B[r] and self.A[r] in base and self.item(r) in CELLAR_ITEMS:
                self.cellars.append(r)

    def flags(self):
        """The level's room flags (world flags): bit $10 = the room item was taken, bits 0-3 = doors opened (E W S N)."""
        return self.m.peek(self.flags_addr, 128)

    def taken(self):
        f = self.flags()
        return {r for r in range(128) if f[r] & 0x10}

    def opened(self):
        f = self.flags(); out = set()
        for r in range(128):
            for d, bit in DOOR_BIT.items():
                if f[r] & bit and 0 <= r + STEP[d] < 128: out.add(frozenset((r, r + STEP[d])))
        return out

    def door(self, r, d):
        if d == 'up': return self.A[r] >> 5
        if d == 'down': return (self.A[r] >> 2) & 7
        if d == 'left': return self.B[r] >> 5
        return (self.B[r] >> 2) & 7

    def item(self, r):
        return ITEMS.get(self.E[r] & 0x1F, '?%02X' % (self.E[r] & 0x1F))

    def secret(self, r): return SECRET[self.F[r] & 7]
    def push_block(self, r): return bool(self.D[r] & 0x40)
    def layout(self, r): return self.D[r] & 0x3F

    def item_xy(self, r):
        return self.item_pos[(self.F[r] >> 4) & 3]

    def is_cellar(self, r): return r in self.cellars

    def neighbours(self, r):
        """[(direction, room, door type)] for doors that are not walls, inside the map."""
        out = []
        for d in DIRS:
            t = self.door(r, d)
            n = r + STEP[d]
            if t == 1 or not (0 <= n < 128) or (d in ('left', 'right') and n >> 4 != r >> 4): continue
            out.append((d, n, t))
        return out

    def stairs_to(self, r):
        """Rooms reached by stairs from room r (through a cellar): [(cellar, other room)]."""
        out = []
        for c in self.cellars:
            if c >= 128: continue
            a, b = self.A[c] & 0x7F, self.B[c] & 0x7F
            if r == a: out.append((c, b))
            elif r == b: out.append((c, a))
        return out

    def rooms(self):
        """The rooms of this level: everything connected to the start room by doors and stairs."""
        seen = {self.start}; todo = [self.start]
        while todo:
            r = todo.pop()
            nxt = [n for d, n, t in self.neighbours(r)] + [o for c, o in self.stairs_to(r)]
            for n in nxt:
                if n not in seen and not self.is_cellar(n): seen.add(n); todo.append(n)
        return seen

    def describe(self, r):
        ds = ' '.join('%s:%s' % (d[0].upper(), DOOR[self.door(r, d)]) for d in DIRS)
        s = '%02X %s' % (r, ds)
        it = self.item(r)
        if it: s += ' item=%s@%s' % (it, self.item_xy(r))
        if self.secret(r): s += ' secret=%s' % self.secret(r)
        if self.push_block(r): s += ' block'
        st = self.stairs_to(r)
        if st: s += ' stairs->' + ','.join('%02X(via %02X)' % (o, c) for c, o in st)
        return s


def plan(L, start, keys=0, bombs=0, want=('triforce',), taken=(), opened=(), blocked=None, came=None):
    """Cheapest sequence of moves (Dijkstra over room, keys, doors opened, items taken) from `start` until every item
    named in `want` is taken. Moves: ('door', dir) and ('stairs', cellar). Items are taken on entering their room
    (keys counted). Returns [(room, move)] or None."""
    import heapq, itertools
    rooms = L.rooms()
    mine = rooms | {c for r in rooms for c, o in L.stairs_to(r)}
    taken = set(taken) & mine                  # (levels 1-6 share one map and one set of room flags)
    opened = {e for e in opened if e <= rooms}
    wantset = set(want)
    tie = itertools.count()
    def items_in(r):
        it = L.item(r)
        return it
    # blocked: {(room, side entered from): exits not reachable from there} (a room split by water or blocks, Level 4
    # room $21: in from below, the island; the bombable top wall only from the left). The state keeps the side entered.
    blocked = blocked or {}
    s0 = (start, keys, frozenset(opened), frozenset(taken), came, min(bombs, 8))
    def done(st): return wantset <= {L.item(r) for r in st[3]} | {L.item(c) for c in st[3]}
    best = {s0: 0}; prev = {}
    q = [(0, next(tie), s0)]
    while q:
        cost, _, st = heapq.heappop(q)
        if cost > best.get(st, 1e9): continue
        if done(st):
            out = []
            while st in prev: st, mv = prev[st]; out.append((st[0], mv))
            return out[::-1]
        r, k, op, tk, cm, bb = st
        moves = []
        nogo = blocked.get((r, cm), ())
        for d, n, t in L.neighbours(r):
            if n not in rooms or d in nogo: continue
            edge = frozenset((r, n))
            k2, op2, c, b2 = k, op, 1, bb
            if t in (5, 6) and edge not in op:
                if k == 0: continue
                k2, op2 = k - 1, op | {edge}
            elif t == 4 and edge not in op:
                if bb == 0: continue                     # (bombs counted: a bomb item gives 4, a wall costs 1)
                op2 = op | {edge}; c = 3; b2 = bb - 1
            elif t == 7 and L.secret(r) not in ('all dead', 'block door', 'last boss', 'foes for item') and edge not in op:
                # (a shutter with no opener on this side: only passable if it is the way we came in, as open)
                c = 2
            moves.append((('door', d), n, k2, op2, c, b2))
        for cel, o in L.stairs_to(r):
            if 'stairs' in nogo: continue
            moves.append((('stairs', cel), o, k, op, 3, bb))
        for mv, n, k2, op2, c, b2 in moves:
            tk2 = tk
            if mv[0] == 'stairs' and L.A[mv[1]] == L.B[mv[1]] and mv[1] not in tk:
                tk2 = tk | {mv[1]}
            if n not in tk2 and L.item(n) and n != r:
                tk2 = tk2 | {n}
                if L.item(n) == 'key': k2 += 1
                if L.item(n) == 'bombs': b2 = min(8, b2 + 4)
            st2 = (n, k2, op2, tk2, OPP[mv[1]] if mv[0] == 'door' else 'stairs', b2)
            if cost + c < best.get(st2, 1e9):
                best[st2] = cost + c; prev[st2] = (st, mv); heapq.heappush(q, (cost + c, next(tie), st2))
    return None
