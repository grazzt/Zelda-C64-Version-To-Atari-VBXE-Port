#!/usr/bin/env python3
"""python3 tools/probe_atari.py FRAMES... : run build/zelda.car (VBXE), print PC/bank/etc after each step, dump RAM."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    for n in map(int, sys.argv[1:]):
        e.frame(n); r = e.registers()
        print(n, 'PC %04X S %d' % (r['PC'], r['S']), 'nmi_ctr', e.peek(0xF082, 1).hex(), 'bank', e.peek(0xF080, 1).hex(),
              'd018', e.peek(0xF018, 1).hex(), 'irqvec', e.peek(0x314, 2).hex())
    open('build/atari_ram.bin', 'wb').write(e.peek(0, 0x10000))
finally:
    e.close()
