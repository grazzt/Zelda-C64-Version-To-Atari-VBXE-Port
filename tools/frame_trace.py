#!/usr/bin/env python3
"""python3 tools/frame_trace.py [CART] [FRAMES] : where each frame's CPU time goes while Link walks about the first
screen. Samples the PC every 498 cycles (60 per NTSC frame) and classifies it (game, game IRQ code $C400-$CFFF, idle =
the main loop's wait, renderer = cart banks 9-11, resident hooks by routine); per frame also whether the game's main
loop completed a pass ($17). Prints the averages of frames with and without a pass, and the worst frames."""
import sys, os, re, collections
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
labs = []
for ln in open(os.path.join(ROOT, 'build/labels.txt')):
    p = ln.split(); labs.append((int(p[1], 16), p[2].lstrip('.')))
other = set()
for f in ('vicirq.s', 'boot.s', 'sound.s', 'input.s'):
    other |= set(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*):', open(os.path.join(ROOT, 'atari/src', f)).read(), re.M))
res = sorted((a, n) for a, n in labs if not n.startswith('__') and not n.startswith('@') and n not in other and a >= 0xD000)
b9 = sorted((a, n) for a, n in labs if not n.startswith('__') and not n.startswith('@') and n not in other and 0x8000 <= a < 0xC000)
def rname(a, tab=res):
    c = [n for x, n in tab if x <= a]
    return c[-1] if c else '?'
cart = sys.argv[1] if len(sys.argv) > 1 else None
nf = int(sys.argv[2]) if len(sys.argv) > 2 else 240
e = boot_game(cart)
try:
    e.frame(60)
    moves = [('left', 30), ('right', 30), ('up', 20), ('down', 20), ('right', 30), ('left', 30)] * 4
    plan = [d for d, k in moves for i in range(k)]
    frames = []
    c0 = e.peek(0x17, 1)[0]
    for f in range(nf):
        e.command('JOY 0 ' + plan[f % len(plan)])
        cat = collections.Counter(); tl = []
        for k in range(60):
            e.command('CYCLES 498'); pc = e.registers()['PC']; bk = e.peek(0xFCC7, 1)[0]
            tl.append(('r:' + rname(pc, b9) if bk == 9 else 'b%d' % bk) if 0x8000 <= pc < 0xC000 else
                      ('h:' + rname(pc) if pc >= 0xD000 and not (0xE000 <= pc < 0xF000) else 'G' if pc < 0xC400 else 'GI'))
            if 0x8000 <= pc < 0xC000 and bk in (9, 10, 11): cat['renderer'] += 1
            elif 0x8000 <= pc < 0xC000 and bk == 12: cat['VBI sound/input'] += 1
            elif pc >= 0xD000 and not (0xE000 <= pc < 0xF000): cat['res:' + rname(pc)] += 1
            elif 0x40C0 <= pc < 0x40E0: cat['idle'] += 1
            elif 0xC400 <= pc < 0xD000: cat['game IRQ'] += 1
            else: cat['game'] += 1
        c = e.peek(0x17, 1)[0]; frames.append(((c - c0) % 256, cat, tl)); c0 = c
    e.command('JOY 0 center')
    for label, sel in (('frames with a pass', [x for x in frames if x[0] >= 1]), ('frames without', [x for x in frames if x[0] == 0])):
        tot = collections.Counter()
        for p, cat, tl in sel: tot.update(cat)
        n = max(1, len(sel))
        print('%s: %d' % (label, len(sel)))
        print('   ' + ', '.join('%s %.1f' % (k, v / n) for k, v in tot.most_common(14)), '(samples of 60 per frame)')
    print('passes in %d frames: %d' % (nf, sum(x[0] for x in frames)))
    for i, (p, cat, tl) in enumerate(frames):              # timelines around the frames without a pass
        if p == 0 and i > 0:
            for j in (i - 1, i):
                out, last, n = [], None, 0
                for t in frames[j][2] + [None]:
                    if t == last: n += 1; continue
                    if last: out.append('%s*%d' % (last, n) if n > 1 else last)
                    last, n = t, 1
                print('frame %d (%s): %s' % (j, 'pass' if frames[j][0] else 'NO PASS', ' '.join(out)))
finally:
    e.close()
