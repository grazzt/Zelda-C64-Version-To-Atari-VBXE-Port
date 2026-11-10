"""The whole game, phase by phase, in one serve.py session (save states only load in-process).

    import campaign; C = campaign.Campaign(m)        # m: a fresh Emu (power-on)
    C.go('start'); C.go('l1'); ...                   # each phase from the checkpoint the previous one left

After every phase: an in-process checkpoint (C.cps[name]) and the input log so far in build/camp_<name>.json
(replayable from power-on: record.py makes the movie from the last one). A phase that fails leaves the game where
it failed; C.redo(name) goes back to the checkpoint before it (after a fix: importlib.reload of the modules, then
C.rebind())."""
import json, os, time, importlib
import nav as N
from emu import ROOT
import zram as Z
import nav as NV, agent as AG, overworld as OW, dungeon as DG, level as LV, menus as MN

PHASES = []


def phase(fn):
    PHASES.append(fn.__name__); return fn


class Campaign:
    def __init__(self, m, log=print):
        self.m = m
        self.out = log
        self.notes = []
        self.cps = {}
        self.done = []
        self.t0 = time.time()
        self.rebind()

    def rebind(self):
        for mod in (NV, LV, AG, DG, OW, MN):
            importlib.reload(mod)
        learned = getattr(self, 'a', None) and self.a.learned
        self.a = AG.Agent(self.m, log=self.note)
        if learned: self.a.learned = learned
        self.ow = OW.Overworld(self.a, note=self.note)
        self.a.watch = self.watch
        self.expect = None                            # (the level the bot went into: the watchdog's reference)

    def watch(self, s):
        """Called with every decision's RAM snapshot: the level byte must stay the level the bot entered (seen once
        as 3 inside Level 1: corruption, or a state-load artefact). Saves the log for a replay from power-on."""
        bad = getattr(self.m, 'port_bad', 0)
        if bad and not getattr(self, '_portalarm', 0):
            self._portalarm = self.m.frames
            json.dump({'log': self.m.log, 'frames': self.m.frames}, open(os.path.join(ROOT, 'build/camp_port_bad_%d.json' % self.m.frames), 'w'))
            self.note('PORT STATE BAD: in_ren set with no render in progress (bug 6), log saved')
        fc, f = s.zp(0x17), self.m.frames                 # the game's frame counter must keep moving (bug 7: the
        last = getattr(self, '_fc', None)                 # raster chain stopped, the main loop waited forever)
        gap = f - getattr(self, '_fcs', f)                # (samples come only from guard(): over a long gap, here a
        self._fcs = f                                     # 377-frame item menu, the 8-bit counter wrapped round to
        if last is None or last[0] != fc or f < last[1] or not 0 <= gap <= 40:   # the same value: no judging then)
            self._fc = (fc, f)
        elif f - last[1] > 120 and s.mode in (5, 9, 0x0B):
            json.dump({'log': self.m.log, 'frames': f}, open(os.path.join(ROOT, 'build/camp_frozen_%d.json' % f), 'w'))
            self.note('GAME FROZEN: frame counter $17 still for %d frames, log saved' % (f - last[1]))
            self._fc = None
            raise RuntimeError('game frozen')
        if self.expect is None or s.mode not in (5, 9, 0x0B): return
        if s.level not in (0, self.expect):
            if not getattr(self, '_alarm', None):
                self._alarm = self.m.frames
                json.dump({'log': self.m.log, 'frames': self.m.frames, 'state': self.state()},
                          open(os.path.join(ROOT, 'build/camp_anomaly_%d.json' % self.m.frames), 'w'))
                self.note('ANOMALY level byte %d (expected %d), log saved' % (s.level, self.expect))

    def note(self, s):
        self.notes.append((self.m.frames, s))
        self.out('[%6d %5.0fs] %s' % (self.m.frames, time.time() - self.t0, s))

    def state(self):
        st = Z.state(self.m)
        st['tri'] = self.m.peek(Z.TRIFORCE)
        return st

    def dump(self, name):
        json.dump({'log': self.m.log, 'frames': self.m.frames, 'notes': self.notes, 'end': self.state(),
                   'phases': self.done}, open(os.path.join(ROOT, 'build/camp_%s.json' % name), 'w'))

    def go(self, name):
        prev = self.done[-1] if self.done else None
        if 'before_' + name not in self.cps:      # (not setdefault: its argument re-saved the state file under the
            self.cps['before_' + name] = self.m.save('before_' + name)     # kept entry, pairing it with a newer state)
        self.note('== %s ==' % name)
        self.a.reset_guard()                      # (checkpoints never cross a phase: one from Level 1 once came back
        try:                                      # on the overworld)
            r = getattr(self, 'p_' + name)()
        finally:
            self.a.reset_guard()
        if r is False:
            self.note('phase %s FAILED: %s' % (name, self.state())); return False
        if name not in self.done: self.done.append(name)
        self.cps[name] = self.m.save('ph_' + name)
        self.dump(name)
        self.note('phase %s done: %s' % (name, self.state()))
        return True

    def redo(self, name):
        cp = self.cps['before_' + name]
        self.m.load(cp)
        later = PHASES[PHASES.index('p_' + name) + 1:]          # (their checkpoints follow from the old run of this one)
        for p in later:
            self.cps.pop('before_' + p[2:], None); self.cps.pop(p[2:], None)
        self.done = self.done[:self.done.index(name)] if name in self.done else self.done
        self.notes = [n for n in self.notes if n[0] <= self.m.frames]

    # ---- pieces
    def attempt(self, fn, label, tries=6):
        """fn() from a checkpoint up to `tries` times (another start delay each time); keep the attempt that worked
        with the most hearts left (as Dungeon.room, for the overworld: the white sword's Lynel)."""
        cp = self.m.save('att')
        hp0 = self.a.snap().hp
        best = None
        for t in range(tries):
            self.a.reset_guard()
            if t:
                self.m.load(cp); self.m.hold('center', self.a.rnd.randrange(5, 60))
            try:
                ok = fn()
            except Exception as ev:
                self.note('  %s: %s' % (label, ev)); ok = False
            st = self.a.snap()
            score = (bool(ok) and st.mode != 0x11 and st.hp > 0, st.hp, -self.m.frames)
            if best is None or score > best[0]:
                best = (score, self.m.save('att_best%d' % t))
            if ok and st.hp >= hp0: break
            self.note('  %s try %d: ok=%s hearts %d -> %d' % (label, t + 1, ok, hp0, st.hp))
        if best[1][2] != self.m.frames: self.m.load(best[1])
        return best[0][0]

    def entrances(self):
        """{level: screen} from the overworld level block (call in the overworld). Some levels list a second screen
        (no door there: Level 5 $1B, only a passage up to $0B): the checked ones override."""
        e = {c: r for r, c in self.ow.caves().items() if 1 <= c <= 9}
        e.update({5: 0x0B, 6: 0x22})           # (Level 6: the door is on $22, not $30)
        return e

    def level(self, n, want, tries=3, stop=None):
        if self.m.peek(Z.LEVEL) != n:                  # (resuming inside the level: no travel)
            ent = self.entrances()[n]
            self.ow.travel(ent)
            lv = self.ow.enter(n)
            if lv != n:
                self.note('not into level %d (level %d)' % (n, lv)); return False
        self.expect = n
        D = DG.Dungeon(self.a, note=self.note, tries=tries)
        self.D = D
        try:
            r = D.run(want=want, stop=stop)
        finally:
            self.expect = None
            self.a.reset_guard()
        if r is not True: return False
        self.ow.wait_play()
        return True

    # ---- phases
    @phase
    def p_start(self):
        MN.to_game(self.m)
        self.ow.enter()
        sw = self.ow.take_cave_item()
        self.ow.leave_cave()
        return sw == 1

    @phase
    def p_l1(self):
        return self.level(1, ('triforce', 'bow', 'boomerang', 'heart container'))

    @phase
    def p_l2(self):
        return self.level(2, ('triforce', 'magic boomerang', 'heart container'))

    @phase
    def p_wsword(self):
        self.ow.travel(0x1A)
        def go():
            self.ow.travel(0x0A)
            if self.ow.enter() != 0 or self.m.peek(Z.MODE) not in (5, 0x0B): return False
            sw = self.ow.take_cave_item()
            self.ow.leave_cave()
            return sw == 2
        return self.attempt(go, 'white sword')

    @phase
    def p_l3(self):
        return self.level(3, ('triforce', 'raft', 'heart container'))

    def raft(self, screen, cell, d, via=None):
        """Sail from a dock: stand on `cell` of overworld `screen` and walk `d` (the raft takes Link across). via:
        (screen, direction) to come in from (screen $55 is split by a channel: its dock is reached from $56)."""
        if via:
            self.ow.travel(via[0]); self.ow.leave(via[1])
        if self.m.peek(Z.SCREEN) != screen: self.ow.travel(screen)
        self.a.goto(lambda c: c == cell, exact=cell)
        s0 = self.m.peek(Z.SCREEN)
        for i in range(300):
            self.m.hold(d, 2)
            if self.m.peek(Z.SCREEN) != s0 and self.m.peek(Z.MODE) == 5: break
        self.ow.wait_play()
        self.m.hold(d, 40)                        # (off the raft and onto land: the landing is in the water's tiles)
        r = self.m.peek(Z.SCREEN)
        self.note('raft from %02X %s: now %02X' % (s0, d, r))
        return r != s0

    @phase
    def p_l4(self):
        if not self.m.peek(Z.RAFT):
            self.note('no raft'); return False
        if self.m.peek(Z.LEVEL) == 0 and self.m.peek(Z.SCREEN) != 0x45:
            if not self.raft(0x55, (16, 9), 'up', via=(0x56, 'left')): return False
        return self.level(4, ('triforce', 'ladder', 'heart container'))

    @phase
    def p_l5(self):
        if self.m.peek(Z.LEVEL) == 0 and self.m.peek(Z.SCREEN) == 0x45:
            if not self.raft(0x45, (16, 19), 'down'): return False
        return self.level(5, ('triforce', 'recorder', 'heart container'))

    def farm(self, need, limit=40, around=(0x54, 0x53, 0x52, 0x62, 0x63, 0x64, 0x65, 0x55)):
        """Rupees up to `need`: go round the screens in `around` (monsters come back each time), fighting and picking
        up the drops (a screen with only a Zora, $44, gave nothing in 40 rounds)."""
        for i in range(limit):
            if self.m.peek(Z.RUPEES) >= need: return True
            self.a.reset_guard()
            try:
                self.ow.travel(around[i % len(around)])
            except RuntimeError as e:
                self.note('  farm: %s' % e); continue
            self.a.kill_all(limit=1500)
            for j in range(30):                          # (drops appear as the monsters die)
                self.a.collect(limit=200); self.m.hold('center', 4)
                if not self.a.snap().drops(): break
            self.note('  farm round %d: rupees %d' % (i, self.m.peek(Z.RUPEES)))
        return self.m.peek(Z.RUPEES) >= need

    def cave_pos(self, screen=None):
        """Where a screen's cave is (NES: Link's position on leaving it): X = attr A & $F0, Y = $4D + 16 (attr F & 7)."""
        r = self.m.peek(Z.SCREEN) if screen is None else screen
        return self.m.peek(0x687E + r) & 0xF0, 0x4D + 16 * (self.m.peek(0x6AFE + r) & 7)

    def burn_or_bomb(self):
        """The room's secret tile object (NES: object slot 11, type $64 a tree, $63 a rock wall, at its square): stand
        32 px from it on its row or column (the candle's fire stops 32 px ahead; it must end within 16 px of the
        object, and opens it in its last frame), use the candle or a bomb, wait for stairs or a cave mouth."""
        t = self.m.peek(0x34F + 11)
        if t not in (0x63, 0x64): return False
        tx, ty = self.m.peek(0x72 + 11), self.m.peek(0x86 + 11)
        item = 4 if t == 0x64 else 1
        g = self.a.grid()
        reach = g.reachable(self.a.cell())
        ky = min(range(N.ROWS), key=lambda k: abs(N.pos_of(0, k)[1] - ty))
        cands = [((tx - 32) // 8, ky, 'right'), ((tx + 32) // 8, ky, 'left')]
        kx = tx // 8
        cands += [(kx, k, 'down') for k in range(N.ROWS) if abs(N.pos_of(0, k)[1] + 32 - ty) < 8]
        cands += [(kx, k, 'up') for k in range(N.ROWS) if abs(N.pos_of(0, k)[1] - 32 - ty) < 8]
        opened = lambda: any(v in (0x24, 0x70) for r in Z.tiles(self.m) for v in r)
        for c, k, d in cands * 3:                         # (once a try did nothing: again)
            if (c, k) not in reach: continue
            if not self.a.select(item): return False
            self.a.goto(lambda q: q == (c, k), exact=(c, k))
            self.m.hold('center', 4)
            self.a.use_b(d)
            for i in range(80):
                self.m.hold('center', 4); self.a._tiles = None
                if opened(): break
            if not opened(): continue
            self.note('  %s at %d,%d: %s' % ('tree burnt' if t == 0x64 else 'wall bombed', tx, ty,
                      'opened' if any(v in (0x24, 0x70) for r in Z.tiles(self.m) for v in r) else 'nothing'))
            return True
        return False

    def open_secret(self):
        """A cave under an Armos statue ($34: the bait shop): wake that statue from above and kill the Armos; its
        square becomes stairs ($70-$73). (Bombable walls and bushes: not needed so far.)"""
        if self.burn_or_bomb(): return True
        x, y = self.cave_pos()
        c = N.cell_of(x, y); t = Z.tiles(self.m)
        for dy in (0, 2):                                 # (the cave exit Y can be a row above the statue: $34)
            if t[c[1] + 1 + dy][c[0]] in (0xC0, 0xC1, 0xC2, 0xC3): c = (c[0], c[1] + dy); break
        else: return False
        x, y = N.pos_of(*c)
        above = (c[0], c[1] - 3)
        self.a.goto(lambda q: q == above, exact=above)
        for i in range(10): self.m.hold('down', 2)
        ar = [o for o in self.a.snap().objects() if o['type'] == 30]
        if not ar: return False
        sl = ar[0]['slot']
        for i in range(600):
            s = self.a.snap()
            if s.pg(0x34F + sl) != 30: break
            if self.a.guard(s): continue
            o = s.obj(sl); f = self.a.aligned(s, o, 26)
            if f: self.a.swing(f)
            else: self.a.approach(s, [o])
        self.m.hold('center', 40); self.a._tiles = None
        self.note('  Armos at %d,%d: %s' % (x, y, 'stairs' if Z.tiles(self.m)[c[1] + 1][c[0]] == 0x70 else 'nothing'))
        return True

    def buy(self, screen, x, addr, price, near=None):
        """Buy the item standing at X `x` in the shop on `screen` (the price is taken by touching it)."""
        if self.m.peek(Z.RUPEES) < price:
            self.ow.travel(near or screen)               # (monsters to get the rest from, next to the shop)
            if not self.farm(price, limit=40): self.note('not enough rupees'); return False
        self.ow.travel(screen)
        self.open_secret()
        if self.ow.enter() != 0: return False
        v = self.ow.take_cave_item(x=x, addr=addr, wait=220)    # (the wares show after the text)
        self.ow.leave_cave()
        self.note('bought %04X at %02X: %d, rupees %d' % (addr, screen, v, self.m.peek(Z.RUPEES)))
        return bool(v)

    @phase
    def p_l6(self):
        if self.m.peek(Z.LEVEL) == 0 and not self.m.peek(Z.ARROWS):
            if not self.buy(0x44, 152, Z.ARROWS, 80, near=0x54): return False
        return self.level(6, ('triforce', 'wand', 'heart container'))

    @phase
    def p_l7(self):
        if self.m.peek(Z.LEVEL) == 0:
            if not self.m.peek(0x065D):                  # (bait, for the hungry Goriya: shop $34, third ware)
                if not self.farm(60, limit=150): return False
                if not self.buy(0x34, 152, 0x065D, 60, near=0x44): return False
            self.ow.travel(0x42)
            self.m.hold('up', 24)                         # (off the screen's edge: items are ignored there)
            if not self.a.select(5): self.note('could not select the recorder'); return False
            self.a.use_b()                                # (the recorder drains the lake: Level 7's stairs)
            self.m.hold('center', 300)
            self.a._tiles = None
            self.note('recorder at $42')
        return self.level(7, ('triforce', 'red candle', 'heart container', '5 rupees'))

    @phase
    def p_l8(self):
        if self.m.peek(Z.LEVEL) == 0:
            self.ow.travel(0x6D)
            self.open_secret()                            # (Level 8: under a bush on $6D, the red candle burns it)
        return self.level(8, ('triforce', 'book', 'magic key', 'heart container'), tries=6)

    def cave_take(self, screen, x, addr, what):
        """Open the secret cave on `screen`, take the thing standing at X `x` (88/120/152) until `addr` changes."""
        self.ow.travel(screen)
        if not self.open_secret(): self.note('  %s: no secret opened on %02X' % (what, screen))
        if self.ow.enter() != 0: return False
        v0 = self.m.peek(addr)
        v = self.ow.take_cave_item(x=x, addr=addr, wait=250)
        self.ow.leave_cave(); self.a.reset_guard()
        self.note('%s at %02X: %02X -> %02X' % (what, screen, v0, v))
        return v != v0

    def grave(self, screen, x, y):
        """Push the gravestone at (x, y) up from below; its stairs lead to the cave."""
        self.ow.travel(screen)
        cell = N.cell_of(x, y + 13)
        self.a.kill_all(limit=600)
        if not self.a.goto(lambda c: c == cell, exact=cell): return False
        for i in range(30): self.m.hold('up', 2)
        self.m.hold('center', 20)
        if self.m.peek(Z.MODE) == 0x0B: return True      # (pushed and straight down its stairs)
        return self.ow.enter() == 0

    @phase
    def p_upgrade(self):
        """Before Level 9 (white sword, 11 hearts, no ring: its Patras and wizzrobes took 2 hearts a touch):
        two 100-rupee secrets, heart containers from the take-any caves, the magic sword, the blue ring."""
        R, H = Z.RUPEES, 0x66F
        if self.m.peek(H) >> 4 < 11:
            self.attempt(lambda: self.cave_take(0x6B, 120, R, 'money'), 'money 6B')
            self.attempt(lambda: self.cave_take(0x7B, 152, H, 'heart'), 'heart 7B')
        self.attempt(lambda: self.cave_take(0x62, 120, R, 'money'), 'money 62')
        self.attempt(lambda: self.cave_take(0x47, 152, H, 'heart'), 'heart 47')
        if self.m.peek(Z.SWORD) < 3:
            def sword():
                if not self.grave(0x21, 144, 144): return False
                v = self.ow.take_cave_item(x=120, addr=Z.SWORD, wait=250)
                self.ow.leave_cave(); self.a.reset_guard()
                return v == 3
            self.attempt(sword, 'magic sword')
        if not self.m.peek(0x662):
            self.buy(0x34, 120, 0x662, 250, near=0x44)
        self.fairy()
        return self.m.peek(Z.SWORD) == 3

    def fairy(self, screen=0x43):
        """Hearts refilled at the fairy fountain ($43, west of Level 7): stand at the pond's bottom edge."""
        self.ow.travel(screen)
        self.a.goto(lambda c: c == (15, 13), exact=(15, 13))
        for i in range(10): self.m.hold('up', 2)
        for i in range(120):
            self.m.hold('center', 8)
            hp, mx = Z.hearts(self.m)
            if hp >= mx and i > 10: break
        self.a.reset_guard()
        self.note('fairy at %02X: %s' % (screen, self.state()))

    def cross17(self):
        """$17 is split by a one-tile river (column 12-13 in 8 px cells): the stairs up to $07 are on the west bank.
        From the east bank stand at cell (14,10) and walk left: the ladder bridges it."""
        a = self.a
        if not a.goto(lambda c: c == (14, 10), exact=(14, 10)): return False
        for i in range(40):
            self.m.hold('left', 2)
            if self.m.peek(0x72) <= 76: break
        a.reset_guard(); a._tiles = None
        return self.ow.leave('up') == 0x07

    @phase
    def p_l9(self):
        if self.m.peek(Z.LEVEL) == 0:
            self.ow.travel(0x17)                          # (Level 9: $17 east bank, ladder over the river, up the
            self.attempt(self.cross17, 'river on 17')     # stairs to $07, west to $05)
            self.ow.travel(0x05)
            def go9():
                self.a.kill_all(limit=2000)
                self.open_secret()                        # (a rock wall on $05: a bomb opens it)
                return self.ow.enter(9) == 9
            self.attempt(go9, 'level 9 entry')
        self.level(9, ('red ring',))                      # (first: Patra's orbiters take 2 hearts a touch, only the
        self.level(9, ('silver arrows',))                 # sword hurts them, and the arrows lie behind Patra's room)
        if not self.level(9, ('triforce of power',)):     # (Ganon in $42: Dungeon.ganon)
            return False
        return self.zelda()

    def zelda(self):
        """From Ganon's room up into $32 and up to Zelda (her fires go when Link comes): the ending, mode $13."""
        for i in range(60):
            x = self.m.peek(Z.LINK_X)
            if x == 120: break
            self.m.hold('right' if x < 120 else 'left', 1)
        for i in range(240):
            self.m.hold('up', 2)
            if self.m.peek(Z.MODE) == 0x13: break
        self.note('Zelda: mode %02X' % self.m.peek(Z.MODE))
        for i in range(60):
            self.m.hold('center', 100)                   # (the ending and the credits, to "another quest")
        return self.m.peek(Z.MODE) == 0x13
