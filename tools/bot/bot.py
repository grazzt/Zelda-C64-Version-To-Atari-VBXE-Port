"""The playing bot: walks with nav.py paths, fights what comes near, travels screen to screen, retries from checkpoints.

Everything it does goes through Emu (logged input); decisions read only game RAM (zram.py). Checkpoints: one per screen
reached; a death or a heavy loss of hearts reloads the last one and tries again with a different start delay."""
import random
import zram as Z
import nav as N

OPP = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}
SCREEN_STEP = {'left': -1, 'right': 1, 'up': -16, 'down': 16}


class Event(Exception):
    """Something ended the current walk: a screen change, a cave, damage, death."""
    def __init__(self, kind): super().__init__(kind); self.kind = kind


class Bot:
    def __init__(self, m, seed=1, log=print):
        self.m = m
        self.rnd = random.Random(seed)
        self.log = log
        self.learned = {}                                  # screen -> cells found blocked
        self.visits = {}
        self.fight = True

    # ---- state
    def st(self): return Z.state(self.m)
    def mode(self): return self.m.peek(Z.MODE)
    def pos(self): return self.m.peek(Z.LINK_X), self.m.peek(Z.LINK_Y)
    def cell(self): return N.cell_of(*self.pos())
    def screen(self): return self.m.peek(Z.SCREEN)

    def grid(self):
        return N.Grid(Z.tiles(self.m), blocked=self.learned.get((self.m.peek(Z.LEVEL), self.screen()), ()))

    def wait_play(self, limit=900):
        """Frames until the game is back in normal play (after a scroll, a cave entry)."""
        for i in range(limit // 4):
            if self.mode() == 5: return True
            self.m.hold('center', 4)
        return self.mode() == 5

    # ---- fighting
    def threats(self, radius=56):
        x, y = self.pos()
        return [e for e in Z.enemies(self.m) if abs(e[2] - x) < radius and abs(e[3] - y) < radius]

    def attack(self, limit=90):
        """Face the nearest enemy along a row or column and swing until it is gone or far."""
        for t in range(limit // 6):
            th = self.threats(64)
            if not th or self.mode() != 5: return
            x, y = self.pos()
            e = min(th, key=lambda e: abs(e[2] - x) + abs(e[3] - y))
            dx, dy = e[2] - x, e[3] - y
            if abs(dy) <= 6:   face = 'right' if dx > 0 else 'left'
            elif abs(dx) <= 6: face = 'down' if dy > 0 else 'up'
            else:
                # line up on the axis that is closer: a step along the other
                if abs(dy) < abs(dx): face = 'down' if dy > 0 else 'up'
                else: face = 'right' if dx > 0 else 'left'
                self.m.hold(face, 3)
                continue
            self.m.hold(face, 1)
            self.m.hold(face, 5, fire=True)
            self.m.hold('center', 2)

    # ---- walking
    def check(self, hp0):
        md = self.mode()
        if md == 0x11: raise Event('death')
        if md in (6, 7): raise Event('scroll')
        if md == 0x0B or self.m.peek(Z.LEVEL) != self.level0: raise Event('enter')
        hp = Z.hearts(self.m)[0]
        if hp <= 1: raise Event('low')

    def walk_to(self, goal_fn, then=None, tries=12):
        """Walk to the first cell where goal_fn is true; then hold direction `then` (off the screen, into a door)."""
        self.level0 = self.m.peek(Z.LEVEL)
        hp0 = Z.hearts(self.m)[0]
        for attempt in range(tries):
            g = self.grid()
            start = self.cell()
            avoid = set()
            for e in Z.enemies(self.m):
                ec = N.cell_of(e[2], e[3])
                for dc in (-1, 0, 1):
                    for dk in (-1, 0, 1): avoid.add((ec[0] + dc, ec[1] + dk))
            path = g.path(start, goal_fn, avoid)
            if path is None:
                if not g.open(*start):                     # (off the grid: nudge)
                    self.m.hold(self.rnd.choice(list(N.STEP)), 4); continue
                return False
            ok = self.follow(path)
            self.check(hp0)
            if ok and goal_fn(self.cell()):
                if then:
                    for i in range(80):
                        self.m.hold(then, 2); self.check(hp0)
                    return False
                return True
        return False

    def follow(self, path):
        for d, end in N.segments(path):
            tx, ty = N.pos_of(*end)
            still = 0
            last = self.pos()
            for i in range(200):
                x, y = self.pos()
                rem = {'left': x - tx, 'right': tx - x, 'up': y - ty, 'down': ty - y}[d]
                if rem <= 0: break
                if self.fight and self.threats(40):
                    self.attack(); return False                # (replan from where the fight left Link)
                self.m.hold(d, 1 if rem <= 3 else 2 if rem <= 6 else 4)
                self.check(None)
                p = self.pos()
                still = still + 1 if p == last else 0
                last = p
                if still >= 4:                                  # blocked: remember the next cell, replan
                    nxt = N.cell_of(*p)
                    nxt = (nxt[0] + N.STEP[d][0], nxt[1] + N.STEP[d][1])
                    key = (self.m.peek(Z.LEVEL), self.screen())
                    self.learned.setdefault(key, set()).add(nxt)
                    self.log('  blocked at %s going %s: cell %s marked' % (N.cell_of(*p), d, nxt))
                    return False
        self.m.hold('center', 1)
        return True

    def leave(self, d):
        """Walk off the screen in direction d. Returns the new screen (or None)."""
        s0 = self.screen()
        try:
            self.walk_to(lambda c: d in N.Grid.exits(None, *c), then=d)
        except Event as ev:
            if ev.kind != 'scroll': raise
        if not self.wait_play(): return None
        return self.screen() if self.screen() != s0 else None
