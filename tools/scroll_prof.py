#!/usr/bin/env python3
"""python3 tools/scroll_prof.py DIR [N] [STEP] : PC profile (as tools/cprof.py) of a screen scroll: walk DIR from the first
overworld screen (down: from the screen north of it) until mode 7, then N samples every STEP CPU cycles (default 2003)."""
import sys, os, collections
sys.path.insert(0, os.path.dirname(__file__))
from to_game import boot_game
labs = []
for ln in open('build/labels.txt'):
    p = ln.split(); labs.append((int(p[1], 16), p[2]))
import re
other = set()
for f in ('boot.s', 'sound.s', 'input.s'):                 # bank 8 / 12 code shares $8000-$BFFF with the renderer (bank 9)
    other |= {'.' + m for m in re.findall(r'^([A-Za-z_][A-Za-z0-9_]*):', open('atari/src/' + f).read(), re.M)}
labs = [(a, n) for a, n in labs if not n.startswith('.__') and n not in other]
labs.sort()
def name(a):
    c = [n for x, n in labs if x <= a]
    if not c: return ''
    g = [n for n in c if not n.startswith('.@')]
    return (g[-1] if g else '') + (c[-1] if c[-1].startswith('.@') else '')
d = sys.argv[1]; n = int(sys.argv[2]) if len(sys.argv) > 2 else 600; st = int(sys.argv[3]) if len(sys.argv) > 3 else 2003
e = boot_game()
try:
    e.frame(30)
    if d == 'down':                                   # (the start screen's south edge is blocked: go up and back)
        e.command('JOY 0 up')
        while e.peek(0x14, 1)[0] != 7: e.frame(1)
        while e.peek(0x14, 1)[0] != 5: e.frame(1)
        e.command('JOY 0 center'); e.frame(30)
    e.command('JOY 0 ' + d)
    while e.peek(0x14, 1)[0] != 7: e.frame(1)
    e.command('JOY 0 center')
    h = collections.Counter(); hf = collections.Counter(); hr = collections.Counter()
    for i in range(n):
        e.command('CYCLES %d' % st); pc = e.registers()['PC']; bk = e.peek(0xFCC7, 1)[0]   # mapped: the cart bank in use
        h[(bk if 0x8000 <= pc < 0xC000 else -1, pc & 0xFFC0)] += 1
        if pc >= 0xF100 or 0xDD00 <= pc < 0xE000: hf[name(pc)] += 1
        if bk == 9 and 0x8000 <= pc < 0xC000: hr[name(pc)] += 1
    print('mode now %02X' % e.peek(0x14, 1)[0])
    for (bk, a), c in h.most_common(25): print('bank %2d %04X %5.1f%%' % (bk, a, 100 * c / n))
    tot = collections.Counter()
    for (bk, a), c in h.items():
        tot['renderer' if bk in (9, 10, 11) else 'resident' if a >= 0xF100 or 0xDD00 <= a < 0xE000 else 'idle wait' if 0x40C0 <= a < 0x40E0 else 'game IRQ (C4xx-CFxx)' if 0xC400 <= a < 0xD000 else 'game'] += c
    print('totals:', ', '.join('%s %d%%' % (k, 100 * v // n) for k, v in tot.most_common()))
    print('renderer:', ', '.join('%s %d%%' % (k, 100 * v // n) for k, v in hr.most_common(16)))
    print('resident:', ', '.join('%s %d%%' % (k, 100 * v // n) for k, v in hf.most_common(14)))
finally:
    e.close()
