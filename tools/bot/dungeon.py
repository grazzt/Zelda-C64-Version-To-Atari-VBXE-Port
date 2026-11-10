"""Playing a dungeon: the plan from level.py (room graph, keys, doors from RAM), executed room by room by the agent.
Every room is tried from a checkpoint up to `tries` times; the attempt that lost the fewest hearts is kept (the movie
shows only that one). Cellars (item stairs) handled as well."""
import level as LV
import nav as N
import zram as Z
from agent import Agent, FRONT, Snap

DIRS4 = {1: 'right', 2: 'left', 4: 'down', 8: 'up'}
PICK = {'key', 'bow', 'boomerang', 'magic boomerang', 'heart container', 'triforce', 'map', 'compass', 'raft',
        'ladder', 'recorder', 'wand', 'red candle', 'book', 'magic key', 'silver arrows', 'red ring', 'bracelet',
        'bombs', '5 rupees', 'rupee', 'blue ring', 'magic shield'}


class Dungeon:
    def __init__(self, agent, note=print, tries=4):
        self.a = agent
        self.m = agent.m
        self.note = note
        self.tries = tries
        self.cellars_done = set()
        self.cps = []

    # ---- basic actions
    def wait_play(self, limit=1200):
        for i in range(limit // 4):
            md = self.m.peek(Z.MODE)
            if md in (5, 0x0B): return True
            self.m.hold('center', 4)
        return False

    def opened(self, d):
        return bool(self.m.peek(0xF0) & LV.DOOR_BIT[d])

    def through(self, d):
        """Walk out of the room through door d. Returns the new room or None."""
        s = self.a.snap(); r0 = s.room
        L = self.L
        t = L.door(r0, d)
        if t == 7 and not self.opened(d):
            self.clear_room()
            if L.secret(r0) == 'block door' and not self.opened(d):      # (Level 4 room $12: the block opens them)
                self.push_block()
            for i in range(60):
                if self.opened(d): break
                self.m.hold('center', 2)
        f = FRONT[d]
        if t == 4 and not self.opened(d):                  # (a bombable wall: a bomb against it, step back)
            self.bomb_wall(d)
        # Blade traps sit in the corners, in line with the door fronts: stopping on the front cell sets them off
        # (Level 3 room $5A: Link pinned in a corner until dead). With traps in the room, line up 4 cells back on the
        # door's axis and walk through in one go; every step guarded (a hit reloads and the approach is redone).
        traps = any(o['type'] in (73, 74) for o in self.a.snap().objects())
        back = {'left': (4, 0), 'right': (-4, 0), 'up': (0, 4), 'down': (0, -4)}[d]
        appr = (f[0] + back[0], f[1] + back[1])
        g = self.a.grid()
        if not (traps and g.open(*appr) and appr in g.reachable(self.a.cell())): appr = f
        for attempt in range(20):
            self.a.goto(lambda c: c == appr, exact=appr)
            reloaded = False
            for i in range(120):
                s = self.a.snap()
                if self.a.guard(s): reloaded = True; break
                if s.mode != 5: break
                self.m.hold(d, 2)
            if not reloaded: break
        if not self.wait_play(): return None
        r = self.m.peek(Z.SCREEN)
        return r if r != r0 else None

    def clear_room(self):
        s = self.a.snap()
        for i in range(25):                               # (monsters appear a moment after Link: the boss check
            if s.objects(): break                          # missed Gohma at the entry and fought it with the sword)
            self.m.hold('center', 2); s = self.a.snap()
        if any(o['type'] in (49, 50) for o in s.objects()): return self.dodongo()
        if any(o['type'] in (66, 67, 68, 69) for o in s.objects()): return self.gleeok()
        if any(o['type'] in (51, 52) for o in s.objects()): return self.gohma()
        if any(o['type'] == 62 for o in s.objects()): return self.ganon()
        if any(s.pg(0x34F + i) == 54 for i in range(1, 12)) and self.m.peek(0x065D): self.feed()   # (54 is not a foe:
                                                                                                    # not in objects())
        if any(o['type'] in (56, 57) for o in s.objects()) and self.m.peek(Z.RECORDER): self.recorder()
        return self.a.kill_all()

    def gleeok(self, limit=6000, below=40):
        """Gleeok: one object (the body); its heads swing on necks below it and are not objects. Stand under the
        body, face up and swing (the heads come to Link; at full health the beam goes up into them); dodge only the
        fireballs. Done when the body is gone."""
        a = self.a
        its = 0
        while its < limit:
            its += 1
            s = a.snap()
            if a.guard(s): a._prev = None; continue
            if s.mode != 5: return False
            gl = [o for o in s.objects() if o['type'] in (66, 67, 68, 69)]
            if not gl:
                return a.kill_all()
            b = gl[0]
            a.track(s)
            d = a.dodge(s)                      # (fireballs and the flying cut-off heads; the body is far above)
            if d: self.m.hold(d, 3); continue
            goal = N.cell_of(b['x'] + 8 - 8, min(205, b['y'] + below))
            g = a.grid(s)
            if not g.open(*goal):
                goal = min((c for c in g.reachable(a.cell(s))), key=lambda c: abs(N.pos_of(*c)[0] - b['x']) + abs(N.pos_of(*c)[1] - b['y'] - below))
            here = a.cell(s)
            if abs(here[0] - goal[0]) + abs(here[1] - goal[1]) > 1:
                path = g.path(here, lambda c: c == goal)
                if path and len(path) > 1: a.step_toward(s, path[1], 3)
                else: self.m.hold('center', 2)
                continue
            a.swing('up')
        return False

    def ganon(self, limit=6000):
        """Ganon (type 62, HP $F0, a magic-sword hit $40): the hit after HP $30 sets HP back to $F0 and his state
        ($AE+slot) to $FB, counting down ~1 per 2 frames while he stands still, brown: then a silver arrow kills
        him. The bow is selected first (the sword stays on A); guard off (each sword hit was undone by the fireball
        that followed it); when he is stunned, stand in line with his 32x32 body and shoot."""
        a = self.a
        if self.m.peek(Z.ARROWS) < 2 or not self.m.peek(Z.BOW): self.note('  Ganon: no silver arrows')
        for t in range(4):                                 # (not from the doorway: the menu stays shut there and B
            a.goto(lambda c: 8 <= c[0] <= 22 and 11 <= c[1] <= 15, limit=300)   # laid all the bombs)
            if a.select(2): break
            self.m.hold('center', 20)
        if self.m.peek(0x656) != 2:
            self.note('  Ganon: could not select the bow'); return False
        guarding, a.guarding = a.guarding, False
        try:
            return self._ganon(a, limit)
        finally:
            a.guarding = guarding
            a.reset_guard()                                # (else the next guarded move rewound to before the fight)

    def _ganon(self, a, limit):
        shots = 0
        for its in range(limit):
            s = a.snap()
            if s.mode != 5: return False
            gl = [o for o in s.objects() if o['type'] == 62]
            if not gl or s.room_item():                    # (his ashes stay a type-62 object: the Triforce of
                self.note('  Ganon down (%d arrows)' % shots)   # Power showing is the sign)
                return True
            G = gl[0]; st = s.zp(0xAE + G['slot'])
            if st < 0x40:                                  # (not stunned: the sword)
                a.kill_all(limit=8); continue
            gx, gy = G['x'], G['y']
            spots = [('up', gx + 8, gy + 36), ('down', gx + 8, gy - 22), ('left', gx + 38, gy + 8),
                     ('right', gx - 22, gy + 8)]
            g = a.grid(s); here = a.cell(s); reach = g.reachable(here)
            best = None
            for face, tx, ty in spots:
                if not (32 <= tx <= 208 and 77 <= ty <= 189): continue
                cands = [c for c in reach if abs(N.pos_of(*c)[0] - tx) <= 4 and abs(N.pos_of(*c)[1] - ty) <= 4]
                if not cands: continue
                c = min(cands, key=lambda c: abs(N.pos_of(*c)[0] - tx) + abs(N.pos_of(*c)[1] - ty))
                d = abs(s.x - N.pos_of(*c)[0]) + abs(s.y - N.pos_of(*c)[1])
                if best is None or d < best[0]: best = (d, face, c)
            if best is None: self.m.hold('center', 1); continue
            d, face, c = best
            if d > 4:
                path = g.path(here, lambda q: q == c)
                if path and len(path) > 1: a.step_toward(s, path[1], 3)
                else: a.goto(lambda q: q == c, exact=c, limit=60)
                continue
            if self.m.peek(0x34F + 18) == 0:
                a.use_b(face); shots += 1
                self.m.hold('center', 6)
            else:
                self.m.hold('center', 1)
        return False

    def patra(self, limit=6000, item=2, shot=18):
        """Patra: eight orbiters (HP $60, three white-sword hits) circle it 40-55 px out, and Patra (HP $B0) is
        hurt only when they are gone. Patra keeps to the middle of the room: stand at the side wall farther from it,
        lined up with its Y, and fire the wand (its beam is slot 14, ~2.5 px a frame) whenever none is in flight."""
        a = self.a
        if not a.select(item):
            self.note('  could not select item %d' % item); return a.kill_all()
        guarding, a.guarding = a.guarding, False          # (a reload would undo the beam in flight, as with Gohma)
        try:
            return self._patra(a, limit, shot)
        finally:
            a.guarding = guarding
            a.reset_guard()                                # (else the next guarded move rewound to before the fight)

    def _patra(self, a, limit, shot=18):
        shots = 0
        for its in range(limit):
            s = a.snap()
            if s.mode != 5: return False
            if s.hp <= 4: return False                    # (low: give the room's retry a chance)
            ob = s.objects()
            pl = [o for o in ob if o['type'] in (71, 72)]
            if not pl:
                self.note('  Patra down after %d wand shots' % shots)
                return a.kill_all()
            P = pl[0]
            a.track(s)
            d = a.dodge(s)
            if d: self.m.hold(d, 3); continue
            near = 32 if s.x < P['x'] else 208           # (stay on Link's side while it is far enough: crossing the
            tx = near if abs(near - P['x']) >= 72 else 240 - near   # ring to the other wall cost 4 hearts)
            ty = max(77, min(189, P['y']))
            face = 'right' if tx < P['x'] else 'left'
            g = a.grid(s)
            if abs(s.x - tx) > 8 or abs(s.y - ty) > 24:
                cand = [c for c in g.reachable(a.cell(s)) if abs(N.pos_of(*c)[0] - tx) <= 8]
                goal = min(cand, key=lambda c: abs(N.pos_of(*c)[1] - ty)) if cand else N.cell_of(tx, ty)
                path = g.path(a.cell(s), lambda c: c == goal)
                if path and len(path) > 1: a.step_toward(s, path[1], 3)
                else: self.m.hold('center', 1)
                continue
            if abs(s.y - ty) > 4:
                self.m.hold('down' if ty > s.y else 'up', 1); continue
            if s.ldir != face:                            # (the 1-frame y steps turn Link: a beam fired then went
                self.m.hold(face, 2); continue            # down the wall)
            if self.m.peek(0x34F + shot) == 0 and self.m.peek(0xAE + shot) == 0:
                self.m.hold('center', 2, key='space'); shots += 1
                self.m.hold('center', 10); continue       # (the beam leaves after the rod swing)
            self.m.hold('center', 1)
        return False

    def gohma(self, limit=5000):
        """Gohma: only an arrow flying up into its middle (parts at X-8 and X: NES Gohma_HandleWeaponCollision) while
        Gohma_ObjEyeState ($046B+slot) = 3 hurts it; $0444+slot is the eye-open timer (state 3 while it is $10-$6F).
        Stand under it lined up to the pixel, dodge the fireballs, shoot only into an open eye."""
        a = self.a
        if not (self.m.peek(Z.BOW) and self.m.peek(Z.ARROWS)): return a.kill_all()
        a.goto(lambda c: 6 <= c[0] <= 24 and 10 <= c[1] <= 17, limit=400)
        if not a.select(2):
            self.note('  could not select the bow'); return False
        its = shots = 0
        guarding, a.guarding = a.guarding, False         # (a red Gohma comes close: its fireballs hit, and each
        try:                                             # reload undid the arrow in the air; hits are taken here)
            return self._gohma(a, limit)
        finally:
            a.guarding = guarding
            a.reset_guard()                                # (else the next guarded move rewound to before the fight)

    def _gohma(self, a, limit):
        its = shots = 0
        while its < limit:
            its += 1
            s = a.snap()
            if s.mode != 5: return False
            if s.hp <= 4: return False                   # (low: give the room's retry a chance)
            gl = [o for o in s.objects() if o['type'] in (51, 52)]
            if not gl:
                self.note('  Gohma down after %d arrows' % shots)
                return a.kill_all()
            gm = gl[0]; sl = gm['slot']
            a.track(s)
            d = a.dodge(s)
            if d: self.m.hold(d, 3); continue
            tx, ty = max(16, min(224, gm['x'] - 4)), min(181, gm['y'] + 64)   # (y 197+ is the bottom doorway:
                                                                              # B does nothing there, 151 shots lost)
            g = a.grid(s)
            if abs(s.y - ty) > 16 or abs(s.x - tx) > 12:
                goal = N.cell_of(tx, ty)
                cand = [c for c in g.reachable(a.cell(s)) if abs(N.pos_of(*c)[1] - ty) <= 16]
                if cand: goal = min(cand, key=lambda c: abs(N.pos_of(*c)[0] - tx) + abs(N.pos_of(*c)[1] - ty))
                path = g.path(a.cell(s), lambda c: c == goal)
                if path and len(path) > 1: a.step_toward(s, path[1], 3)
                else: self.m.hold('center', 1)
                continue
            eye, left = s.pg(0x46B + sl), s.pg(0x444 + sl)
            if abs(s.x - tx) > 6:                        # (the middle parts are 16 px wide: within 6 px; to the
                self.m.hold('right' if tx > s.x else 'left', 1); continue   # pixel, a moving red Gohma was never met)
            if eye == 3 and left >= 0x10 + 14 and s.pg(0x34F + 18) == 0:
                a.use_b('up'); shots += 1
                self.m.hold('center', 4)
                continue
            self.m.hold('center', 1)
        return False

    def feed(self):
        """The hungry Goriya (type 54) blocks the way until it gets food: select the bait (B slot 6) and put it down
        in front of it."""
        a = self.a
        s0 = a.snap()
        gi = [i for i in range(1, 12) if s0.pg(0x34F + i) == 54][0]
        g = s0.obj(gi)
        hungry = lambda: any(a.snap().pg(0x34F + i) == 54 for i in range(1, 12))
        a.goto(lambda c: 6 <= c[0] <= 24 and 5 <= c[1] <= 15 and abs(N.pos_of(*c)[0] - g['x']) <= 8
               and 24 <= N.pos_of(*c)[1] - g['y'] <= 48, limit=900)
        if not a.select(6):
            self.note('  could not select the bait'); return False
        a.use_b('up')
        for i in range(150):
            if not hungry(): break
            self.m.hold('center', 4)
        self.note('  fed the Goriya: %s' % ('gone' if not hungry() else 'still there'))
        return True

    def recorder(self):
        """Digdogger: the recorder shrinks it (into small ones the sword kills). Select it (B: slot 5, the NES order
        boomerang 0, bombs 1, arrow 2, candle 4, recorder 5, food 6) and play it inside the room: in a doorway the
        game ignores the B button (Level 5's boss room: three plays at the entry did nothing)."""
        self.a.goto(lambda c: 6 <= c[0] <= 24 and 5 <= c[1] <= 15, limit=400)
        if not self.a.select(5):
            self.note('  could not select the recorder'); return False
        for i in range(30):
            s = self.a.snap()
            if not any(o['type'] in (56, 57) for o in s.objects()): break
            self.a.use_b()
            self.m.hold('center', 60)
        self.note('  recorder played: %s' % [o['name'] for o in self.a.snap().objects()])
        return True

    BOMB_FROM = {'up': (15, 6), 'down': (15, 14), 'left': (6, 10), 'right': (23, 10)}   # (bomb lands on the hotspot)

    def bomb_wall(self, d):
        """A bomb at the wall's hotspot (NES BombableWallHotspots: the door fronts; within 24 px), dropped from two
        cells back so Link is not in line with corner traps while he waits."""
        if self.m.peek(Z.BOMBS) == 0: raise RuntimeError('no bombs for the wall')
        if not self.a.select(1): raise RuntimeError('could not select the bombs')
        c = self.BOMB_FROM[d]
        reach = self.a.grid().reachable(self.a.cell())
        if c not in reach and FRONT[d] in reach: c = FRONT[d]      # (Level 4 room $21: the usual spot is water)
        self.a.goto(lambda x: x == c, exact=c)
        self.a.use_b(d)
        back = LV.OPP[d]
        self.m.hold(back, 24)                             # (14 frames back: the blast still clipped Link, and the
        for i in range(50):                               # guard then reloaded from before the bomb: the wall shut
            if self.opened(d): break                      # again, bomb back, Level 8 room $3E)
            self.m.hold('center', 2)
        self.m.hold('center', 10)
        self.a.reset_guard()                              # (from here on: the opened wall is the new base)
        self.a._tiles = None
        self.note('  bombed the %s wall: %s' % (d, 'open' if self.opened(d) else 'still shut'))

    def dodongo(self, limit=5400):
        """Dodongo: an unexploded bomb at its mouth (it eats it) or a blast next to it (stunned: the sword hurts
        then). Bombs go down ahead of it on its way; when it is bloated or stunned, sword."""
        a = self.a
        start = self.m.frames
        its = 0
        while self.m.frames - start < limit and its < limit:
            its += 1
            s = a.snap()
            if a.guard(s): a._prev = None; continue
            if s.mode != 5: return False
            dd = [o for o in s.targets() if o['type'] in (49, 50)]
            if not dd:
                if any(o['type'] in (49, 50) for o in s.objects()):   # (still appearing, or dying)
                    self.m.hold(a.dodge(s) or 'center', 2); continue
                return a.kill_all()
            o = dd[0]
            st = s.zp(0xAE + o['slot'])
            a.track(s)
            dg = a.dodge(s)
            if dg: self.m.hold(dg, 3); continue
            if st == 2:                                        # (stunned: sword)
                f = a.aligned(s, o, 26)
                if f and a.risk(s, 'center', 10) > 10: a.swing(f); continue
                a.approach(s, [o]); continue
            if st == 1 or s.zp(0xAE + 16):                     # (bloated, or a bomb already down: keep clear)
                a.m.hold(a.dodge(s, 30) or 'center', 3); continue
            if self.m.peek(Z.BOMBS) == 0:
                a.approach(s, [o]); continue                   # (no bombs: nothing else to do)
            if not a.select(1):
                a.m.hold(a.dodge(s, 20) or 'center', 4); continue
            # stand ahead of its mouth, facing it: the bomb (16 px ahead of Link) lands ~26 px before its mouth
            # window (NES Dodongo_TryEatBomb: within 4 px of its centre line, 0-16 px ahead of its centre), which it
            # reaches during the 48-frame fuse at half a pixel a frame
            od = DIRS4.get(o['dir'], 'left')
            tx, ty = {'left': (o['x'] - 34, o['y']), 'right': (o['x'] + 50, o['y']),
                      'up': (o['x'], o['y'] - 42), 'down': (o['x'], o['y'] + 42)}[od]
            cell = N.cell_of(max(16, min(224, tx)), max(64, min(216, ty)))
            px, py = N.pos_of(*cell)
            if (od in ('left', 'right') and abs(py - o['y']) > 3) or (od in ('up', 'down') and abs(px - o['x']) > 3):
                a.m.hold(a.dodge(s, 20) or 'center', 2); continue
            g = a.grid(s)
            if not g.open(*cell):
                a.approach(s, [o]); continue
            if abs(N.pos_of(*cell)[0] - s.x) > 4 or abs(N.pos_of(*cell)[1] - s.y) > 4:
                bad = a.danger(s) - {a.cell(s)}
                path = g.path(a.cell(s), lambda c: c == cell, avoid=bad)
                if path and len(path) > 1: a.step_toward(s, path[1], 3)
                else: self.m.hold('center', 2)
                continue
            face = LV.OPP[od]
            a.use_b(face)
            self.m.hold({'left': 'up', 'right': 'up', 'up': 'left', 'down': 'left'}[od], 12)
        return False

    def pick_item(self):
        """Walk onto the room item if it is out."""
        for i in range(40):
            s = self.a.snap()
            it = s.room_item()
            if it: break
            self.m.hold('center', 2)
        else:
            return False
        x, y = it
        goal = N.cell_of(x, y - 3)
        cand = [goal] + [(goal[0] + dc, goal[1] + dk) for dc in (-1, 0, 1) for dk in (-1, 0, 1)]
        g = self.a.grid()
        cell = next((c for c in cand if g.open(*c)), goal)
        self.a.goto(lambda c: c == cell, exact=cell)
        for i in range(200):                              # (holding an item up: wait until play again)
            s = self.a.snap()
            if s.room_item() is None and s.mode == 5 and s.lstate == 0: break
            if s.mode != 5 and s.level == 0: break
            self.m.hold('center', 2)
        return True

    # ---- a room, with retries
    def room(self, fn, label):
        """Run fn() from a checkpoint up to self.tries times; keep the attempt with the most hearts left."""
        cp = self.m.save('room')
        learned = {k: set(v) for k, v in self.a.learned.items()}
        hp0 = self.a.snap().hp
        best = None
        r = self.a.snap().room
        tries = self.tries * 2 if getattr(self, 'L', None) and r == self.L.boss else self.tries
        for t in range(tries):
            self.a.reset_guard()
            if t:
                self.m.load(cp); self.a.learned = {k: set(v) for k, v in learned.items()}
                self.m.hold('center', self.a.rnd.randrange(3, 40))
            try:
                ok = fn()
            except Exception as ev:
                self.note('  %s: %s' % (label, ev)); ok = False
            s = self.a.snap()
            score = (bool(ok) and s.mode != 0x11, s.hp, -self.m.frames)
            if best is None or score > best[0]:
                if best: pass
                best = (score, self.m.save('room_best%d' % t))
            if ok and s.hp >= hp0: break
            self.note('  %s try %d: ok=%s hearts %d -> %d' % (label, t + 1, ok, hp0, s.hp))
        if best[1][2] != self.m.frames: self.m.load(best[1])
        return best[0][0]

    # ---- the level
    def run(self, want=('triforce',), stop=None):
        """Play the level until every item in `want` is taken (the triforce ends it). stop(room, move): return early
        (before that move) when true. Checkpoints of every room entry are kept in self.cps."""
        self.L = LV.Level(self.m)
        self.blocked = getattr(self, 'blocked', {})
        came = None
        while True:
            s = self.a.snap()
            if s.level == 0: return True
            r = s.room
            self.cps.append((r, self.m.save('cp%03d' % len(self.cps))))
            self.learn_exits(r, came)
            taken = self.L.taken() | self.cellars_done
            if set(want) <= {self.L.item(x) for x in taken}:
                self.note('level %d: %s taken' % (self.L.n if hasattr(self.L, 'n') else s.level, ', '.join(want)))
                return True                              # (no plan is needed any more: it was a failure before)
            kw = dict(keys=s.item(Z.KEYS), bombs=s.item(Z.BOMBS), want=want, taken=taken, opened=self.L.opened())
            plan = LV.plan(self.L, r, blocked=self.blocked, came=came, **kw)
            if not plan:
                plan = LV.plan(self.L, r, **kw)              # (what was learned may be wrong: a block moved since)
            if not plan:
                self.note('no plan from room %02X' % r); return False
            mv = plan[0][1]
            if stop and stop(r, mv):
                self.note('stop before room %02X %s' % (r, mv)); return None
            def step():
                it = self.L.item(r)
                need = (mv[0] == 'stairs' or (mv[0] == 'door' and self.L.door(r, mv[1]) == 7 and not self.opened(mv[1]))
                        or (it in PICK and r not in taken and self.L.secret(r) in ('foes for item', 'all dead'))
                        or self.L.secret(r) in ('last boss',) or r == self.L.boss)
                gate = (mv[0] == 'stairs' or (mv[0] == 'door' and self.L.door(r, mv[1]) == 7 and not self.opened(mv[1]))
                        or self.L.secret(r) in ('last boss',) or r == self.L.boss)
                patra = any(o['type'] in (71, 72) for o in self.a.snap().objects())
                if patra and not gate:                     # (a Patra costs hearts; when nothing waits on it, pass:
                    self.note('  room %02X: Patra, passing' % r)   # Level 9 $16 and $27 cost 6 hearts each)
                else:
                    self.clear_room()                      # (always: skipping it left six blue Darknuts between Link
                    self.a.collect()                       # and a wall to bomb, Level 8 room $3E; cleared, no loss)
                    if it in PICK and r not in taken: self.pick_item()
                self.m.hold('center', 1)
                if mv[0] == 'door': return self.through(mv[1]) is not None
                return self.stairs(mv[1])
            ok = self.room(step, 'room %02X %s' % (r, mv))
            if mv[0] == 'stairs' and ok: self.cellars_done.add(mv[1])
            came = (LV.OPP[mv[1]] if mv[0] == 'door' else 'stairs') if ok else came
            s = self.a.snap()
            self.note('room %02X %s -> %02X, hearts %d/%d keys %d' % (r, mv, s.room, s.hp, s.hp_max, s.item(Z.KEYS)))
            if not ok: return False

    def learn_exits(self, r, came):
        """Which exits of room r can be reached from where Link entered (door fronts, the bomb spots of bombable walls,
        the stairs): the others go into self.blocked[(r, came)] for the plan. Only exits with walls of tiles between
        (no push block in the room: a block can open the way)."""
        if came is None or self.L.push_block(r): return
        g = self.a.grid()
        reach = g.reachable(self.a.cell())
        if len(reach) < 4: return                          # (still in the doorway: no judgement)
        nogo = set()
        for d, n, t in self.L.neighbours(r):
            spot = self.BOMB_FROM[d] if t == 4 else FRONT[d]
            if d != came and spot not in reach and FRONT[d] not in reach: nogo.add(d)
        if nogo:
            self.blocked[(r, came)] = nogo
            self.note('  room %02X from %s: no way to %s' % (r, came, ','.join(sorted(nogo))))

    # ---- push blocks, stairs, cellars
    def block(self):
        """The push block object (slot 11, type $68): (x, y, state) or None."""
        if self.m.peek(0x34F + 11) != 0x68: return None
        return self.m.peek(0x72 + 11), self.m.peek(0x86 + 11), self.m.peek(0xAE + 11)

    def push_block(self):
        """Push the room's block (all monsters dead first). Tries the four sides; True when it moved."""
        self.clear_room()
        b = self.block()
        if not b: return False
        bx, by, st = b
        if st: return True
        cp = self.m.save('push')
        for d, (lx, ly) in (('up', (bx, by - 3 + 16)), ('down', (bx, by - 3 - 16)),
                            ('right', (bx - 16, by - 3)), ('left', (bx + 16, by - 3))):
            cell = N.cell_of(lx, ly)
            if N.pos_of(*cell) != (lx, ly) or not self.a.grid().open(*cell): continue
            self.a.goto(lambda c: c == cell, exact=cell)
            for i in range(30):
                self.m.hold(d, 2)
                if self.m.peek(0x4CF) or (self.block() or (0, 0, 0))[2]: break
            for i in range(20):
                if self.m.peek(0x4CF): break
                self.m.hold('center', 2)
            if self.m.peek(0x4CF):
                self.note('  block pushed %s' % d); return True
            self.m.load(cp)
        return False

    def find_stairs(self):
        """A grid cell standing on a stairs tile ($70-$73) of the play area, or None."""
        t = Z.tiles(self.m)
        for k in range(0, N.ROWS, 2):                     # (the game takes stairs only on a 16-pixel square:
            for c in range(0, N.COLS, 2):                  # X & $0F = 0, Y & $0F = $0D)
                if t[k + 1][c] in (0x70, 0x71, 0x72, 0x73) and t[k + 1][c + 1] in (0x70, 0x71, 0x72, 0x73):
                    return (c, k)
        return None

    def stairs(self, cellar):
        """Down the room's stairs (pushing the block first if they are hidden), through the cellar (taking its item),
        and back up. Returns True when out of the cellar again."""
        r0 = self.a.snap().room
        st = self.find_stairs()
        b = self.block()
        if st is None or (b and b[2] == 0) or st not in self.a.grid().reachable(self.a.cell()):
            self.push_block()
            self.m.hold('center', 20)
            for i in range(30):
                st = self.find_stairs()
                if st: break
                self.m.hold('center', 2)
        if st is None: raise RuntimeError('no stairs in room %02X' % r0)
        for attempt in range(6):                           # (monsters can knock Link off the square: again)
            self.a.goto(lambda c: c == st, exact=st)
            for i in range(60):
                if self.m.peek(Z.MODE) != 5: break
                self.m.hold('center', 2)
            if self.m.peek(Z.MODE) != 5: break
            self.a.kill_all(limit=600)
        for i in range(400):                               # (mode 9: the cellar; Link walks in by himself)
            if self.m.peek(Z.MODE) == 9 and self.m.peek(0x13) == 9 and self.m.peek(Z.LINK_Y) == 0x5D: break
            self.m.hold('center', 2)
        if self.m.peek(Z.MODE) != 9:
            raise RuntimeError('stairs in room %02X: no cellar (mode %02X)' % (r0, self.m.peek(Z.MODE)))
        self.note('  in cellar %02X: x %d y %d' % (self.m.peek(Z.SCREEN), self.m.peek(Z.LINK_X), self.m.peek(Z.LINK_Y)))
        if getattr(self, 'debug_cellar', False): return 'cellar'
        if (self.L.A[cellar] & 0x7F) != (self.L.B[cellar] & 0x7F):
            return self.passage(r0, cellar) != r0
        return self.cellar(r0)

    def cellar(self, r0):
        """In a cellar (side view: floors $24, ladders $6F): take the item if there is one, then back up the ladder
        Link came down."""
        top = self.a.cell()
        it = None
        for i in range(90):                       # (the item object comes a moment after Link: Level 3's raft was
            it = self.a.snap().room_item()          # left behind when this looked at once)
            if it: break
            self.m.hold('center', 2)
        if it:
            goal = N.cell_of(it[0], it[1] - 3)
            self.a.goto(lambda c: c == goal, exact=goal, limit=2400)
            for i in range(200):
                s = self.a.snap()
                if s.room_item() is None and s.lstate == 0: break
                self.m.hold('center', 2)
            cel = self.a.snap().room
            got = self.a.snap().level and cel in LV.Level(self.m).taken()
            self.note('  cellar %02X item: %s' % (cel, 'taken' if got else 'NOT taken'))
            if not got: raise RuntimeError('cellar %02X: item not taken' % cel)
        self.a.goto(lambda c: c == top, exact=top, limit=2400)
        for i in range(200):
            self.m.hold('up', 2)
            if self.m.peek(Z.MODE) != 9: break
        ok = self.wait_play()
        return ok and self.m.peek(Z.SCREEN) == r0

    def passage(self, r0, cel):
        """A cellar joining two rooms (attr A != B: Level 5 $07): out by the other ladder. Returns the room reached."""
        t = Z.tiles(self.m)
        here = self.a.cell()
        tops = [c for c in range(0, 30) if t[3][c] == 0x6F and t[3][c + 1] == 0x6F]
        other = [c for c in tops if abs(c - here[0]) > 2]
        if not other: raise RuntimeError('passage %02X: one ladder' % cel)
        goal = (other[0], here[1])
        self.a.goto(lambda c: c == goal, exact=goal, limit=2400)
        for i in range(200):
            self.m.hold('up', 2)
            if self.m.peek(Z.MODE) != 9: break
        self.wait_play()
        r = self.m.peek(Z.SCREEN)
        self.note('  passage %02X: %02X -> %02X' % (cel, r0, r))
        return r
