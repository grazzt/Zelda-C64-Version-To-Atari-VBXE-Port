#!/usr/bin/env python3
"""python3 tools/snap3.py FRAME PREFIX : in one session: screenshot, RAM render (VIC model) and both display buffers."""
import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
import sys, subprocess
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
from altirra import Altirra
from PIL import Image
P = 416
e = Altirra('build/zelda.car', 'build/altirra', options=['--adddevice', 'vbxe'])
def vram(a, n):
    out = b''
    while n:
        k = min(n, 0x1000 - (a & 0xFFF)); e.poke(0xD65F, 0x80 + (a >> 12)); out += e.peek(0xE000 + (a & 0xFFF), k); a += k; n -= k
    return out
try:
    e.frame(int(sys.argv[1])); pre = sys.argv[2]
    e.screenshot(pre + '_shot.png')
    open(pre + '_ram.bin', 'wb').write(e.peek(0, 0x10000))
    print('flip', e.peek(0xF65A, 1)[0], 'hidden', e.peek(0xF084, 1)[0], 'render active', e.peek(0xFCF0, 1)[0], 'ys', e.peek(0xF011, 1)[0] & 7)
finally:
    e.close()
subprocess.run([sys.executable, 'tools/render_atari_ram.py', pre + '_ram.bin', pre + '_ramr.png'])
a = Image.open(pre + '_shot.png').convert('RGB'); b = Image.open(pre + '_ramr.png').convert('RGB').resize((a.width, a.height))
W = Image.new('RGB', (a.width, a.height * 2)); W.paste(a, (0, 0)); W.paste(b, (0, a.height)); W.save(pre + '_cmp.png')
