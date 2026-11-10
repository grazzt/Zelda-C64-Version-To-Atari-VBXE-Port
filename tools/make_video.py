#!/usr/bin/env python3
"""python3 tools/make_video.py [CART] [OUT.mp4] : a video of the port in AltirraSDL (VBXE), every frame at 60 fps.
The title (5 s, then cut to its fade), the whole attract demo (story scroll, item pages) until the title comes back, START, registering the name
GZ, the game: the sword from the first cave, then ~3.5 minutes of walking about and fighting (Link's hearts are
topped up when he is down to half a heart, so the video does not end at a game over).
Pictures: the emulator's screenshots (672x224), scaled x2 / x4 to 1344x896 (square C64 pixels), piped to ffmpeg (H.264).
Sound: the bridge has no audio capture, so it is synthesised from the POKEY registers read every frame (the port's
sound driver sets them once per frame from the SID shadow): square waves for pure tones, random levels for noise, at
the channel's frequency (AUDCTL clocks and joined channels), volume AUDC & 15. Close to, not exactly, the real sound."""
import sys, os, wave, subprocess, random
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cart = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build/zelda.car')
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'build/zelda_port.mp4')
GAMEPLAY = int(os.environ.get('GAMEPLAY_FRAMES', str(60 * 210)))
tmp = os.path.join(ROOT, 'build/_video')
os.makedirs(tmp, exist_ok=True)
W, H = 1344, 896
RATE = 44100
SPF = RATE / 60.0

e = Altirra(cart, os.path.join(ROOT, 'build/altirra_video'), options=['--adddevice', 'vbxe'])
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                       '-r', '60', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
                       os.path.join(tmp, 'video.mp4')], stdin=subprocess.PIPE)
audio = []
phase = [0.0, 0.0, 0.0, 0.0]
noise_val = [1.0, 1.0, 1.0, 1.0]
acc = [0.0]
nframes = [0]
shot = os.path.join(tmp, 'shot.png')


def synth(p):
    """One frame of sound from the POKEY registers."""
    acc[0] += SPF
    n = int(acc[0]); acc[0] -= n
    ctl = p['AUDCTL']
    base = 15699.9 if ctl & 1 else 63921.0
    clk = [1789773.0 if ctl & 0x40 else base, base, 1789773.0 if ctl & 0x20 else base, base]
    f = [p['AUDF1'], p['AUDF2'], p['AUDF3'], p['AUDF4']]
    c = [p['AUDC1'], p['AUDC2'], p['AUDC3'], p['AUDC4']]
    chans = []                                            # (period divider -> frequency, AUDC)
    if ctl & 0x10:
        nn = f[0] + 256 * f[1]
        chans.append((clk[0] / (2.0 * (nn + (7 if ctl & 0x40 else 1))), c[1], 1))
    else:
        chans.append((clk[0] / (2.0 * (f[0] + (4 if ctl & 0x40 else 1))), c[0], 0))
        chans.append((clk[1] / (2.0 * (f[1] + 1)), c[1], 1))
    if ctl & 0x08:
        nn = f[2] + 256 * f[3]
        chans.append((clk[2] / (2.0 * (nn + (7 if ctl & 0x20 else 1))), c[3], 3))
    else:
        chans.append((clk[2] / (2.0 * (f[2] + (4 if ctl & 0x20 else 1))), c[2], 2))
        chans.append((clk[3] / (2.0 * (f[3] + 1)), c[3], 3))
    mix = np.zeros(n)
    t = np.arange(n)
    for freq, audc, k in chans:
        vol = audc & 15
        if vol == 0 or audc & 0x10 or freq > RATE / 2 or freq < 20:
            continue
        dist = audc >> 5
        step = freq / RATE
        ph = phase[k] + step * (t + 1)
        if dist in (5, 7):                                # pure tone
            wavef = np.where((ph % 1.0) < 0.5, 1.0, -1.0)
        else:                                             # noise: a new random level each half period
            idx = np.floor(ph * 2).astype(int)
            first = int(np.floor(phase[k] * 2))
            levels = {}
            vals = np.empty(n)
            for i, j in enumerate(idx):
                if j not in levels:
                    levels[j] = noise_val[k] if j == first else (1.0 if random.random() < 0.5 else -1.0)
                vals[i] = levels[j]
            noise_val[k] = vals[-1] if n else noise_val[k]
            wavef = vals
        phase[k] = (phase[k] + step * n) % 1024.0
        mix += wavef * (vol / 15.0) * 0.22
    audio.append(np.clip(mix, -1, 1))


def frame(k=1):
    for i in range(k):
        e.frame(1)
        e.screenshot(shot)
        im = Image.open(shot).convert('RGB').resize((W, H), Image.NEAREST)
        ff.stdin.write(im.tobytes())
        synth(e.pokey())
        nframes[0] += 1


def silent(k=1):                                          # (not recorded)
    e.frame(k)


def peek(a): return e.peek(a, 1)[0]
def mode(): return peek(0x14)
def pos(): return peek(0x72), peek(0x86)


def con(key, w):
    e.command('CONSOL ' + key); frame(4); e.command('CONSOL'); frame(w)


def joy(d, n=6, w=10):
    e.command('JOY 0 ' + d); frame(n); e.command('JOY 0 center'); frame(w)


def fire(n=6, w=20):
    e.command('JOY 0 center fire'); frame(n); e.command('JOY 0 center'); frame(w)


def health():
    h = peek(0x066F)
    if (h & 15) == 0 and peek(0x0670) < 0x80:           # (down to half a heart: full again)
        e.poke(0x066F, (h & 0xF0) | (h >> 4)); e.poke(0x0670, 0xFF)


def hold(d, cond, limit=600):
    e.command('JOY 0 ' + d)
    for i in range(limit):
        frame(); health()
        if cond(): break
    e.command('JOY 0 center')
    return cond()


try:
    # start-up (black until the title is complete): not recorded
    for i in range(200):
        silent(10)
        if peek(0xFD2D) == 0 and i > 20: break
    print('title at frame ~%d' % ((i + 1) * 10), flush=True)
    # the title and the whole attract demo, until the title is back
    c0 = peek(0xF021) & 15                                # (the title for 5 s, then on to the fade: the port's title
    frame(300)                                            # stays longer than the C64's)
    for i in range(3000):
        if os.environ.get('SKIP_DEMO') or peek(0xF021) & 15 != c0: break
        silent(1)
    start = nframes[0]
    while not os.environ.get('SKIP_DEMO'):
        frame()
        if nframes[0] - start > 3000:
            im = Image.open(shot).convert('RGB')
            if im.getpixel((200, 40)) == (178, 98, 88) and im.getpixel((330, 140)) != (0, 0, 0): break
        if nframes[0] - start > 9000: break
    print('demo done, %d frames' % nframes[0], flush=True)
    frame(150)
    # START -> select screen -> START -> register: G, Z
    con('start', 150); con('start', 150)
    for s in ['right'] * 6 + ['F'] + ['down', 'down'] + ['left'] * 3 + ['F']:
        if s == 'F': fire()
        else: joy(s)
    frame(90)
    for i in range(3): con('select', 30)
    con('start', 150)                                     # (the select screen, GZ listed)
    frame(90)
    con('start', 60)
    for i in range(600):
        if mode() == 5: break
        frame()
    print('game at %d frames' % nframes[0], flush=True)
    frame(60)
    g0 = nframes[0]
    # the sword: the cave on the first screen (route of tools/sword_fight_test.py)
    hold('left', lambda: pos()[0] <= 64)
    hold('up', lambda: mode() == 0x0B)
    frame(730)                                            # (the old man's text)
    hold('up', lambda: pos()[1] <= 180, 100)              # (from the entrance: up, right onto x 120, up to the sword)
    x0 = pos()[0]
    hold('right', lambda: pos()[0] >= x0 + 6, 60)
    hold('up', lambda: peek(0x0657) != 0, 150)
    frame(150)                                            # (Link holds the sword up)
    print('sword flag', peek(0x0657), flush=True)
    hold('left', lambda: pos()[0] <= 112, 40)
    hold('down', lambda: mode() == 5, 900)
    frame(30)
    # explore: head for a screen edge (swinging the sword, sidestepping when blocked), fight a while on each new
    # screen, then another exit (not straight back)
    rnd = random.Random(7)
    perp = {'left': ('up', 'down'), 'right': ('up', 'down'), 'up': ('left', 'right'), 'down': ('left', 'right')}
    back = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}
    prefs = ['right', 'right', 'up', 'right', 'up', 'left', 'up', 'left', 'down', 'right', 'down', 'left']
    leg, screens = 0, 0
    last = None

    def scrolled():
        if mode() in (6, 7):
            hold('center', lambda: mode() == 5, 400)
            return True
        return False

    def fight(n):                                         # (move about and swing for n frames)
        t0 = nframes[0]
        while nframes[0] - t0 < n and nframes[0] - g0 < GAMEPLAY:
            x, y = pos()
            d = rnd.choice(['up', 'down', 'left', 'right'] + ['right'] * (x < 60) + ['left'] * (x > 180) +
                           ['down'] * (y < 100) + ['up'] * (y > 180))
            fire(6, 4)
            e.command('JOY 0 ' + d)
            for i in range(rnd.randrange(8, 24)):
                frame(); health()
                if mode() != 5: break
            e.command('JOY 0 center')
            if mode() != 5: return

    while nframes[0] - g0 < GAMEPLAY:
        if mode() == 0x0B:                                # (walked into a cave: out again)
            hold('down', lambda: mode() == 5, 400); frame(30); continue
        if scrolled(): continue
        if mode() != 5:
            frame(10); continue
        d = prefs[leg % len(prefs)]
        if last and d == back[last]:
            leg += 1; continue
        ok = False
        for attempt in range(10):                         # (toward the edge, sidestepping when blocked)
            e.command('JOY 0 ' + d)
            p0, still = pos(), 0
            for i in range(90):
                frame(); health()
                if i % 30 == 29:
                    e.command('JOY 0 center fire'); frame(4); e.command('JOY 0 ' + d)
                if mode() != 5: break
                p = pos()
                still = still + 1 if p == p0 else 0
                p0 = p
                if still > 12: break
            e.command('JOY 0 center')
            if mode() in (6, 7):
                ok = True; break
            if mode() != 5: break
            side = perp[d][(attempt // 2) % 2]
            hold(side, lambda: mode() != 5, rnd.randrange(16, 48))
            if nframes[0] - g0 >= GAMEPLAY: break
        if ok:
            hold('center', lambda: mode() == 5, 400)
            screens += 1; last = d
            print('screen %d (%s) at %.0f s' % (screens, d, (nframes[0] - g0) / 60.0), flush=True)
            fight(rnd.randrange(300, 600))
        leg += 1
    frame(60)
    print('total %d frames (%.1f s)' % (nframes[0], nframes[0] / 60.0), flush=True)
finally:
    e.close()
    ff.stdin.close(); ff.wait()
    pcm = (np.concatenate(audio) * 32000).astype(np.int16) if audio else np.zeros(0, np.int16)
    with wave.open(os.path.join(tmp, 'audio.wav'), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(pcm.tobytes())
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(tmp, 'video.mp4'), '-i', os.path.join(tmp, 'audio.wav'),
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', out])
    print('wrote', out, flush=True)
