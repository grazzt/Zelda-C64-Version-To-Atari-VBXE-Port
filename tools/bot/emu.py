"""The bot's emulator layer: AltirraSDL (VBXE) with every input logged per frame, in-process checkpoints, and replay.

Every frame the bot runs goes through Emu.step(), with the input held during it (joystick direction, fire, console
key); the log is a list of runs (frames, input). A replay of the log from a cold boot (randdelay and randmem off:
a fixed power-on) gives the same game, so the movie is recorded from a replay of the finished log: no pokes, no state loads.

Checkpoints are AltirraSDL save states (STATE_SAVE/STATE_LOAD) plus the log length. Use them only in the process that
saved them: a state loaded into a fresh emulator left the game stuck in mode $08 (the port's VBXE-side state is not
all in it). `replay_check()` verifies that the log replays to the same game state the bot reached."""
import os, sys, hashlib, json
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CART = os.path.join(ROOT, 'build/zelda.car')
MEMN = 0x700                                     # RAM read back after every step: zero page to the inventory
PORT_PEEKS = ['PEEK $F06D 1', 'PEEK $FCF0 1']      # the port's in_ren and r_act (atari.inc): in_ren set with r_act
                                                  # clear is bug 6's stuck state (every game IRQ then took the trampoline)
DIRS = ('center', 'up', 'down', 'left', 'right', 'upleft', 'upright', 'downleft', 'downright')


def power_on_ram(e, seed=1986):
    """A fixed pseudo-random power-on RAM pattern in $0000-$7FFF (before the first frame): real power-on RAM is not
    zero, and the bot's runs keep one fixed start. (Until the bug 5 fix the port hung at power-on with all-zero RAM,
    HANDOFF bug 1; it now boots with any fill.)"""
    import random, base64
    rnd = random.Random(seed)
    data = bytes(rnd.randrange(256) for i in range(0x8000))
    for a in range(0, 0x8000, 0x1000):
        e.command('MEMLOAD $%04X %s' % (a, base64.b64encode(data[a:a + 0x1000]).decode()))


class Emu:
    def __init__(self, cart=CART, folder=None, state_dir=None):
        self.folder = folder or os.path.join(ROOT, 'build/altirra_bot')
        self.e = Altirra(cart, self.folder, options=['--adddevice', 'vbxe'], fresh=True)
        self.e.command('CONFIG randdelay off')          # (a fixed power-on: no random start-up delay, RAM not
        self.e.command('CONFIG randmem off')            # randomised; with randmem on, two idle boots differed by frame 50)
        self.e.frame(1)                                 # (reset from a frame boundary: a reset where the bridge
        self.e.command('COLD_RESET')                    # happened to pause gave runs that differed)
        power_on_ram(self.e)
        self.state_dir = state_dir or os.path.join(ROOT, 'build/bot_states')
        os.makedirs(self.state_dir, exist_ok=True)
        self.inp = ('center', False, '', '')        # (direction, fire, console key, keyboard key: 'space' = B)
        self.sent = None
        self.log = []                               # [[frames, (dir, fire, consol)], ...]
        self.frames = 0
        self.on_frame = None                        # called after every frame (recording)
        self.mem = None                             # RAM $0000-$06FF after the last step

    # ---- input and time
    def _pipe(self, cmds):
        """Commands sent together, replies read together: the bridge answers a batch in one host frame (~17 ms per
        round trip otherwise). A PEEK after a FRAME in the same batch sees the memory after that frame."""
        ch = self.e.channel
        ch.write(('\n'.join(cmds) + '\n').encode()); ch.flush()
        out = []
        for c in cmds:
            r = json.loads(ch.readline())
            if not r.get('ok'): raise RuntimeError('%s: %s' % (c.split()[0], r))
            out.append(r)
        return out

    def _input_cmds(self):
        if self.sent == self.inp: return []
        d, f, c, k = self.inp
        cmds = []
        if self.sent is None or self.sent[:2] != (d, f):
            cmds.append('JOY 0 %s%s' % (d, ' fire' if f else ''))
        if self.sent is None or self.sent[2] != c:
            cmds.append('CONSOL %s' % c if c else 'CONSOL')
        if self.sent is None or self.sent[3] != k:
            cmds.append('KEYRAW %s down' % k if k else 'KEYRAW all up')
        self.sent = self.inp
        return cmds

    def _send(self):
        cmds = self._input_cmds()
        if cmds: self._pipe(cmds)

    def set(self, d='center', fire=False, consol='', key=''):
        assert d in DIRS, d
        self.inp = (d, bool(fire), consol, key)

    def step(self, n=1):
        """n frames with the current input; afterwards self.mem holds RAM $0000-$06FF (read in the same batch)."""
        if n <= 0: return
        if self.log and self.log[-1][1] == self.inp: self.log[-1][0] += n
        else: self.log.append([n, self.inp])
        if self.on_frame:                           # (recording: frame by frame; FRAME n and n x FRAME 1 emulate
            for i in range(n):                      # the same, checked from a frame-aligned reset)
                r = self._pipe(self._input_cmds() + ['FRAME 1', 'PEEK $0000 %d' % MEMN] + PORT_PEEKS)
                self._got(r); self.frames += 1; self.on_frame(self)
        else:
            r = self._pipe(self._input_cmds() + ['FRAME %d' % n, 'PEEK $0000 %d' % MEMN] + PORT_PEEKS)
            self._got(r); self.frames += n

    def _got(self, r):
        self.mem = bytes.fromhex(r[-3]['data'])
        self.port = (int(r[-2]['data'], 16), int(r[-1]['data'], 16))   # (in_ren, r_act) at the frame boundary
        if self.port[0] and not self.port[1]:
            self.port_bad = getattr(self, 'port_bad', 0) + 1                 # (bug 6's stuck state)

    def hold(self, d='center', n=1, fire=False, consol='', key=''):
        self.set(d, fire, consol, key); self.step(n)

    # ---- memory
    def peek(self, a, n=1):
        if self.mem is not None and a + n <= MEMN:
            return self.mem[a] if n == 1 else self.mem[a:a + n]
        v = self.e.peek(a, n)
        return v[0] if n == 1 else bytes(v)

    def ram_hash(self):
        return hashlib.md5(self.peek(0x0000, 0x100) + self.peek(0x0300, 0x500) + self.peek(0x6530, 0x2C0)).hexdigest()[:12]

    # ---- checkpoints (this process only)
    def save(self, name):
        path = os.path.join(self.state_dir, name + '.altstate')
        self.e.command('STATE_SAVE ' + path)
        return (path, [list(r) for r in self.log], self.frames, self.inp)

    def load(self, cp):
        path, log, frames, inp = cp
        self.e.command('STATE_LOAD ' + path)
        self.e.command('KEYRAW all up')
        self.mem = None
        self.log = [list(r) for r in log]; self.frames = frames
        self.inp = inp; self.sent = None
        self._send()

    def close(self):
        self.e.close()


def replay(log, cart=CART, on_frame=None, folder=None, upto=None):
    """A new Emu with the log played from a cold boot (frame by frame when on_frame is given). Returns the Emu."""
    m = Emu(cart, folder=folder or os.path.join(ROOT, 'build/altirra_replay'))
    m.on_frame = on_frame
    done = 0
    for n, inp in log:
        if upto is not None and done + n > upto: n = upto - done
        m.set(*inp); m.step(n); done += n
        if upto is not None and done >= upto: break
    return m
