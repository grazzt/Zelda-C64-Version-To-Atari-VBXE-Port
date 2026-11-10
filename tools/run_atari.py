#!/usr/bin/env python3
"""python3 tools/run_atari.py OUT.png [frames]  -- run build/zelda.car in AltirraSDL with VBXE, screenshot."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
emu = Altirra(ROOT / 'build/zelda.car', ROOT / 'build/altirra', options=['--adddevice', 'vbxe'])
try:
    emu.frame(int(sys.argv[2]) if len(sys.argv) > 2 else 60)
    emu.screenshot(sys.argv[1]); print(emu.registers())
finally:
    emu.close()
