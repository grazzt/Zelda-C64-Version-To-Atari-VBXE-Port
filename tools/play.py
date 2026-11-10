#!/usr/bin/env python3
"""Drive the cart with an input script and take screenshots.

python3 tools/play.py OUTPREFIX "w600 s start w60 s right8 fire w30 s"
  wN        run N frames
  s         screenshot OUTPREFIX<frame>.png
  start/select/option[N]   hold the console key N frames (default 4), then release
  up/down/left/right/fire[N] (and combos like upfire) hold joystick 0 N frames (default 4), then centre
  key:NAME[N]              hold Atari key NAME (bridge KEYRAW name) N frames
  peek:ADDR:LEN            print memory
"""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import re, sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra

DIRS = ('upleft', 'upright', 'downleft', 'downright', 'up', 'down', 'left', 'right', 'center')


def main():
    out, script = sys.argv[1], sys.argv[2].split()
    e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
    t = 0

    def run(n):
        nonlocal t
        e.frame(n); t += n
    try:
        for tok in script:
            m = re.fullmatch(r'([a-z:$0-9A-F_]+?)(\d*)', tok)
            word, n = m.group(1), int(m.group(2)) if m.group(2) else None
            if tok.startswith('peek:'):
                _, a, l = tok.split(':')
                print(t, a, e.peek(int(a.lstrip('$'), 16), int(l)))
            elif word == 'w':
                run(n)
            elif word == 's':
                p = f'{out}{t:05d}.png'; e.screenshot(p); print('shot', p)
            elif word in ('start', 'select', 'option'):
                print(e.command(f'CONSOL {word}')); run(n or 4); print(e.command('CONSOL'))
            elif word.startswith('key:'):
                e.command(f'KEYRAW {word[4:]} down'); run(n or 4); e.command('KEYRAW all up')
            else:
                fire = word.endswith('fire')
                d = word[:-4] if fire else word
                d = d or 'center'
                assert d in DIRS, tok
                print(e.command(f'JOY 0 {d}' + (' fire' if fire else ''))); run(n or 4); e.command('JOY 0 center')
        print('frames', t)
    finally:
        e.close()


main()
