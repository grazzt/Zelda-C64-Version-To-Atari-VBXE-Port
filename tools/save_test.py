#!/usr/bin/env python3
"""python3 tools/save_test.py [CART] : the game's save goes to the disk in D1: and comes back after a power cycle.
A blank 90 KB ATR in D1:, register LUNA (the game saves its name list), wait for the disk write (atari/src/save.s:
half a second after the game's last write; its status must be 1). Then a cold reset with the disk still in: the boot
must load the save (status $11) and the select screen show the same first name slot (LUNA) without registering it.
Screenshots build/_save1.png, build/_save2.png. (This AltirraSDL build mounts disks virtual read/write: what is
written stays on the disk until the emulator quits, never in the file; Windows Altirra writes the file when the
disk is set to read/write.)"""
import sys, os, shutil
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
sys.path.insert(0, os.path.join(_KIT, 'tools/atari'))
sys.path.insert(0, os.path.dirname(__file__))
from altirra import Altirra, working_copy
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cart = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build/zelda.car')
folder = os.path.join(ROOT, 'build/altirra_save')
atr = os.path.join(ROOT, 'build/save_test.atr')
SIG = b'ZELDA-VBXE-SAVE1'
from PIL import Image as _I
SELECT_HEAD = _I.open(os.path.join(ROOT, 'tools/ref_select_head.png')).convert('RGB').tobytes() if os.path.exists(
    os.path.join(ROOT, 'tools/ref_select_head.png')) else None


def blank_atr(path, sectors=720):
    size = sectors * 128
    hdr = bytes([0x96, 0x02, (size >> 4) & 0xFF, (size >> 12) & 0xFF, 0x80, 0x00, (size >> 20) & 0xFF]) + bytes(9)
    open(path, 'wb').write(hdr + bytes(size))


def machine(fresh):
    # (the bridge's MOUNT: virtual read/write, the disk keeps what is written until the emulator quits)
    e = Altirra(cart, folder, options=['--adddevice', 'vbxe'], fresh=fresh)
    e.command('CONFIG randdelay off')                     # (a fixed power-on: the scripted menu input lands the same)
    e.command('MOUNT 0 %s' % os.path.abspath(atr))
    e.command('COLD_RESET')
    return e


def to_select(e, register):
    labs = {ln.split()[2].lstrip('.'): int(ln.split()[1], 16) for ln in open(os.path.join(ROOT, 'build/labels.txt'))}
    def settle():                                         # (a pending disk write holds the machine ~1 s when it runs:
        for i in range(30):                               # input in it is lost)
            if not e.peek(labs['sv_dirty'], 1)[0]: break
            e.frame(10)
        else:
            return
        e.frame(10)
    def joy(d, n=6, w=10):
        settle(); e.command('JOY 0 ' + d); e.frame(n); e.command('JOY 0 center'); e.frame(w)
    def con(k, w):
        settle(); e.command('CONSOL ' + k); e.frame(4); e.command('CONSOL'); e.frame(w)
    e.frame(600); con('start', 150); con('start', 150)
    if register:
        for s in ['down', 'F'] + ['right'] * 9 + ['F'] + ['left'] * 7 + ['F', 'up', 'left', 'left', 'F']:
            if s == 'F':
                settle(); e.command('JOY 0 center fire'); e.frame(6); e.command('JOY 0 center'); e.frame(20)
            else:
                joy(s)
        e.frame(180)                                      # (END saves: the disk write half a second later holds the
        for i in range(3): con('select', 30)              # machine ~1 s, and input in it is lost)
        con('start', 120)


def name_slot(e, path):
    """White text pixels in the first name slot of the select screen (LUNA: ~60), and whether it is the select screen
    (its title row: white pixels in the "- S E L E C T -" heading)."""
    from PIL import Image
    e.screenshot(path)
    im = Image.open(path).convert('RGB')
    white = lambda box: sum(1 for p in im.crop(box).getdata() if p[0] > 200 and p[1] > 200 and p[2] > 200)
    sel = im.crop((200, 14, 450, 26)).tobytes() == SELECT_HEAD     # ("- S E L E C T -", the select screen's heading)
    return white((220, 56, 300, 72)), sel


def main():
    blank_atr(atr)
    labs = {ln.split()[2].lstrip('.'): int(ln.split()[1], 16) for ln in open(os.path.join(ROOT, 'build/labels.txt'))}
    st = lambda e: 'boot read %02X, last disk write %02X, pending %d' % (
        e.peek(labs['sv_rs'], 1)[0], e.peek(labs['sv_ws'], 1)[0], e.peek(labs['sv_dirty'], 1)[0])
    for attempt in range(3):                              # (the scripted menu input slips now and then)
        e = machine(True)
        to_select(e, True)
        e.frame(240)                                      # (the disk write: half a second after the last save write)
        slot1, head = name_slot(e, os.path.join(ROOT, 'build/_save1.png'))
        print('registered: name pixels %d, select screen %s, mode %02X |' % (slot1, head, e.peek(0x14, 1)[0]), st(e))
        if slot1 > 20 and head: break
        e.close()
    else:
        raise SystemExit('FAIL: never reached the select screen with LUNA')
    try:
        w_ok = e.peek(labs['sv_ws'], 1)[0] == 1
        e.command('COLD_RESET')                           # (power cycle: the disk keeps what was written to it)
        e.frame(600)
        for k in range(3):                                # START until the select screen (with a save, the next
            e.command('CONSOL start'); e.frame(4); e.command('CONSOL'); e.frame(150)   # START would start the game)
            slot2, head2 = name_slot(e, os.path.join(ROOT, 'build/_save2.png'))
            if head2: break
        seen = slot2 > 20 and head2 and abs(slot2 - slot1) <= 4
        r_ok = e.peek(labs['sv_rs'], 1)[0] == 0x11
        print('after a cold reset, not registering: name pixels %d, select screen %s: LUNA listed: %s |' % (slot2, head2, seen),
              st(e), '(11: loaded)')
    finally:
        e.close()
    print('PASS' if w_ok and r_ok and seen else 'FAIL')


if __name__ == '__main__':
    main()
