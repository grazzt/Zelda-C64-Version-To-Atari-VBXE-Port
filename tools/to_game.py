"""Shared helper: boot the cart in AltirraSDL and register LUNA, then start the game (Atari ~frame 2050).
from to_game import boot_game; e = boot_game()  ->  Altirra instance on the first overworld screen (caller closes it)."""
import os, sys
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra


def boot_game(cart=None, settle=300, tries=8):
    for t in range(tries):
        e = _boot(cart, settle)
        if e.peek(0x14, 1)[0] == 5: return e          # in the game (mode 5); else the scripted entry slipped
        print('boot_game: mode %02X, retrying' % e.peek(0x14, 1)[0], file=sys.stderr); e.close()
    raise SystemExit('boot_game: never reached the game')


def _boot(cart, settle):
    e = Altirra(cart or os.environ.get('CART', 'build/zelda.car'), 'build/altirra', options=['--adddevice', 'vbxe'])

    def joy(d, n=6, w=10):
        e.command('JOY 0 ' + d); e.frame(n); e.command('JOY 0 center'); e.frame(w)

    def con(k, w):
        e.command('CONSOL ' + k); e.frame(4); e.command('CONSOL'); e.frame(w)
    e.frame(600); con('start', 150); con('start', 150)
    for s in ['down', 'F'] + ['right'] * 9 + ['F'] + ['left'] * 7 + ['F', 'up', 'left', 'left', 'F']:
        if s == 'F':
            e.command('JOY 0 center fire'); e.frame(6); e.command('JOY 0 center'); e.frame(20)
        else:
            joy(s)
    for i in range(3): con('select', 30)
    con('start', 120); con('start', settle)
    return e
