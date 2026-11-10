"""Audit-driven hardware patches for the EF banks. Every patch asserts the original bytes."""
import pickle, sys, os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
sys.path.insert(0, _KIT + '/tools/c64')
from code6502 import OPCODES

VSH, SSH = 0xF000, 0xF040
SKIP_PC = {0x8000, 0x800F, 0x8027, 0x802A, 0x8040, 0xC002, 0xC005, 0xC01B}   # C64 boot stub / credit loop: not replayed


def read_labels(path):
    labs = {}
    for ln in open(path):
        p = ln.split()
        if p[0] == 'al': labs[p[2].lstrip('.')] = int(p[1], 16)
    return labs


def decode(img, off):
    op = img[off]; mn, mode = OPCODES[op]
    return op, mn, mode, img[off + 1] | img[off + 2] << 8


def patch_instr(img, off, pc, labs, log):
    op, mn, mode, t = decode(img, off)
    if mode not in ('abs', 'absx', 'absy'): return
    new = None
    if 0xD000 <= t < 0xD400:
        r = t & 0x3F
        if r == 0x12 and mode == 'abs':
            h = {'STA': 'hook_d012w', 'STX': 'hook_d012x', 'LDA': 'hook_d012r', 'CMP': 'hook_d012c', 'CPX': 'hook_d012cx'}.get(mn)
            if h is None: raise SystemExit(f'unhandled {mn} $D012 at {pc:04X}')
            new = (0x20, labs[h])
        elif r == 0x30:
            new = (op, VSH + (0x3F if mn == 'LDA' else 0x2F))   # C64: reads $FF (no C128 2 MHz), writes ignored
        elif r == 0x11 and mn == 'LDA':
            new = (0x20, labs['hook_d011r'])
        elif r == 0x11 and mn == 'BIT' and mode == 'abs':
            new = (0x20, labs['hook_d011n'])
        elif r == 0x18 and mn in ('STA', 'STX', 'STY') and mode == 'abs':
            if mn != 'STA': raise SystemExit(f'unhandled {mn} $D018 at {pc:04X}')
            new = (0x20, labs['hook_d018'])                      # playfield screen base split (atari/src/scroll.s)
        elif 0x21 <= r <= 0x23 and mn in ('STA', 'STX', 'STY') and mode == 'abs':
            h = 'hook_c%02X%s' % (r, mn[2].lower())          # background colours: set live (atari/src/colour.s)
            if h.lower() not in {k.lower() for k in labs}: raise SystemExit(f'no {h} for {mn} $D0{r:02X} at {pc:04X}')
            new = (0x20, labs[next(k for k in labs if k.lower() == h.lower())])
        else:
            new = (op, VSH + (t - 0xD000))
    elif 0xD400 <= t < 0xD800:
        new = (op, SSH + (t - 0xD400))
    elif t == 0xDE00 and mn in ('STA', 'STX', 'STY') and mode == 'abs':
        new = (0x20, labs({'STA': 'hook_bank_a', 'STX': 'hook_bank_x', 'STY': 'hook_bank_y'}[mn]) if False else
               labs[{'STA': 'hook_bank_a', 'STX': 'hook_bank_x', 'STY': 'hook_bank_y'}[mn]])
    if new:
        img[off:off + 3] = bytes([new[0], new[1] & 0xFF, new[1] >> 8])
        log.append((pc, mn, mode, hex(t), '->', '%02X %04X' % new))


def _find_all(img, ctx):
    o = img.find(ctx)
    while o >= 0:
        yield o
        o = img.find(ctx, o + 1)


def raster_waits(banks, audit):
    """Raster reads the attract audit never reached, found by pattern: LDA $D011 + BMI/BPL/AND, LDA $D012 + CMP/SEC,
    CMP $D012 + BNE/BCC/BCS, BIT $D011 + BMI/BPL. They are unmistakably code; on the Atari they would read GTIA."""
    sites = []
    for b, img in enumerate(banks):
        for i in range(len(img) - 4):
            op, t, nx = img[i], img[i + 1] | img[i + 2] << 8, img[i + 3]
            hit = (op == 0xAD and t == 0xD011 and nx in (0x30, 0x10, 0x29)) or \
                  (op == 0xAD and t == 0xD012 and nx in (0xC9, 0x38, 0xCD, 0xDD, 0x69)) or \
                  (op == 0xCD and t == 0xD012 and nx in (0xD0, 0x90, 0xB0, 0xF0)) or \
                  (op == 0x2C and t == 0xD011 and nx in (0x30, 0x10))
            if hit and (b, 0x8000 + i) not in audit:
                sites.append((b, 0x8000 + i))
    return sites


# CIA1 input reads: (bank, address of the column-select LDA # or None, its value, address of the LDA $DC0x, image)
INPUT_READS = [
    (7, None, None, 0x84AB, 0xDC04),        # RAM $44C3: LDA $DC00 (joystick 2)
    (7, 0x84BD, 0xFE, 0x84C2, 0xDC05),      # RAM $44DA: column 0 (F-keys)
    (7, 0x84CA, 0x7F, 0x84CF, 0xDC06),      # RAM $44E7: column 7 (SPACE)
    (0, 0x9A86, 0xFD, 0x9A8B, 0xDC07),      # F7 handler: column 1 (left SHIFT -> F8)
    (0, 0x9A90, 0xBF, 0x9A95, 0xDC08),      # column 6 (right SHIFT)
]


# EF bank switches the attract audit never reached (save/load, other game phases): (bank, address, opcode)
BANK_WRITES = [(7, a, 0x8D) for a in (0x8551, 0x868A, 0x86AA, 0x8BD6, 0x8C57, 0x918C, 0x9CED, 0x9D3C)] + \
              [(7, 0x99C5, 0x8C), (5, 0xB95C, 0x8D)]


# Hardware sites no audit reached (found by a static scan of the patched banks for VIC/SID accesses in plausible code;
# each checked by disassembly). The sound engine's paths for some effects (bank 0) wrote the SID directly: on the Atari
# $D400-$D41F is ANTIC (mirrored every 16), so e.g. $96AC STA $D412 (voice 3 control, a noise effect) set DLISTL: the
# display list moved, raster events stopped and the game froze (the music held its last note). (bank, pc, opcode, target)
STATIC_SITES = [
    (0, 0x96AC, 0x8D, 0xD412), (0, 0x9865, 0x8D, 0xD405), (0, 0x986A, 0x8D, 0xD406),
    (0, 0x9B79, 0x8D, 0xD030), (0, 0x9B7C, 0xAD, 0xD030),
    (0, 0xB282, 0x8D, 0xD416), (0, 0xB287, 0x8D, 0xD415), (0, 0xB28F, 0x8D, 0xD417), (0, 0xB297, 0x8D, 0xD418),
    (0, 0xB32F, 0x8D, 0xD416), (0, 0xB334, 0x8D, 0xD415), (0, 0xB33C, 0x8D, 0xD417), (0, 0xB344, 0x8D, 0xD418),
    (0, 0xBBE8, 0x8D, 0xD40C), (0, 0xBBEB, 0x8D, 0xD40D), (0, 0xBBF0, 0x8E, 0xD40B),
    (5, 0xBAD8, 0x8D, 0xD011), (5, 0xBC16, 0x8D, 0xD011),
    (7, 0x88B3, 0x8D, 0xD011), (7, 0xA3BF, 0x8D, 0xD012), (7, 0xAA27, 0x8D, 0xD022),
    (7, 0xAE9D, 0xAD, 0xD015), (7, 0xAEA2, 0x8D, 0xD015),
]


# Indexed stores whose index reaches the hardware (tools/hw_scan.py): (bank, pc, original bytes, resident hook)
SPECIAL_SITES = [
    (7, 0x83FC, bytes([0x9D, 0xFE, 0xCF]), 'hook_cffe'),   # STA $CFFE,X, X from a table: X-2 = a VIC register (dungeon)
    (0, 0x9DB0, bytes([0xAD, 0x11, 0xD0]), 'hook_d011w'),  # LDA $D011 of the up/down scroll's frame wait (RAM $117F)
    (0, 0xA649, bytes([0xAD, 0x11, 0xD0]), 'hook_d011w'),  # LDA $D011 of the left/right scroll's frame wait (RAM $1A18)
    (5, 0xBC38, bytes([0xAD, 0x11, 0xD0]), 'hook_d011b8'),  # LDA $D011 / BPL: wait for raster bit 8 (bug 4: menu hang)
]


# Plain byte patches: (bank, pc, original bytes, new bytes, why)
BYTE_PATCHES = [
    # RAM $40FC (boot): PAL/NTSC detection, up to 24576 raster reads for a line past 271 (PAL only); the port is NTSC.
    # On the port each read is the raster emulation: ~2 s of the start-up (the title came ~5 s after the C64's).
    # Store 0 (NTSC) in $7E02 and return.
    (7, 0x80E9, bytes([0xA2, 0x00]), bytes([0x60, 0x00]), 'NTSC: no PAL detection loop'),
]


def static_patches(banks, labs, log):
    skip = {int(x, 16) for x in os.environ.get('STATIC_SKIP', '').split()}     # (debug: bisect the static sites)
    for b, at, op, t in STATIC_SITES:
        if at in skip: continue
        o = at - 0x8000
        if bytes(banks[b][o:o + 3]) != bytes([op, t & 0xFF, t >> 8]):
            assert banks[b][o] == 0x20 or banks[b][o + 2] >= 0xF0, (b, hex(at), bytes(banks[b][o:o + 3]).hex())
            continue                                      # (already patched from the audit)
        patch_instr(banks[b], o, at, labs, log)
    for b, at, want, new, why in BYTE_PATCHES:
        o = at - 0x8000
        assert bytes(banks[b][o:o + len(want)]) == want, (b, hex(at), bytes(banks[b][o:o + len(want)]).hex())
        banks[b][o:o + len(new)] = new
        log.append((at, 'bytes', '', want.hex(), '->', why))
    for b, at, want, hook in SPECIAL_SITES:
        o = at - 0x8000
        got = bytes(banks[b][o:o + 3])
        if want[0] == 0xAD and want[2] == 0xD0 and got[0] == 0x20:    # (a raster read the audit patched already)
            want = got
        assert got == want, (b, hex(at), got.hex())
        banks[b][o:o + 3] = bytes([0x20, labs[hook] & 0xFF, labs[hook] >> 8])
        log.append((at, 'special', '', want.hex(), '->', hook))


def bank_patches(banks, labs, log):
    for b, at, op in BANK_WRITES:
        o = at - 0x8000
        if banks[b][o] == 0x20: continue                  # (already patched from the audit)
        assert bytes(banks[b][o:o + 3]) == bytes([op, 0x00, 0xDE]), (b, hex(at))
        patch_instr(banks[b], o, at, labs, log)


def input_patches(banks, log):
    """LDA $DC00/$DC01 -> LDA of the per-column image the VBI builds (atari/src/input.s, J_JOY.. in atari.inc)."""
    for b, sel, val, at, img in INPUT_READS:
        o = at - 0x8000
        if sel is not None:
            assert bytes(banks[b][sel - 0x8000:sel - 0x8000 + 5]) == bytes([0xA9, val, 0x8D, 0x00, 0xDC]), hex(sel)
        want = bytes([0xAD, 0x00 if sel is None else 0x01, 0xDC])
        assert bytes(banks[b][o:o + 3]) == want, hex(at)
        banks[b][o + 1:o + 3] = bytes([img & 0xFF, img >> 8])
        log.append((at, 'LDA', 'abs', hex(want[1] | want[2] << 8), '->', '%04X' % img))


def load_audit(path, orig):
    """tools/audit.json (tools/host/audit_export.py) -> (audit, ctxs) as apply() takes them. The contexts are rebuilt
    from orig (the 8 original EF banks, ROML+ROMH): pieces are [bank, offset, length] or literal hex."""
    import json
    d = json.load(open(path))
    audit = {(b, pc): {(k, r): n for k, r, n in kinds} for b, pc, kinds in d['sites']}
    ctxs = {(b, pc): b''.join(bytes.fromhex(p) if isinstance(p, str) else orig[p[0]][p[1]:p[1] + p[2]] for p in ps)
            for b, pc, ps in d['ctx']}
    return audit, ctxs


def apply(banks, ram_image, labs, audit, ctxs=None):
    """banks: list of 8 bytearrays (16K). ram_image: host RAM after boot (for locating RAM-resident code).
    ctxs: {(-1, pc): code bytes pc-6..pc+9 recorded when the site ran} (tools/host/audit.py), for code loaded later."""
    log = []
    orig = [bytes(b) for b in banks]
    for (b, pc), kinds in sorted(audit.items(), key=lambda x: (x[0][1], x[0][0])):
        if pc in SKIP_PC: continue
        if b >= 0:
            patch_instr(banks[b], pc - 0x8000, pc, labs, log)
        elif ctxs and (b, pc) in ctxs and bytes(ram_image[pc - 6:pc + 9]) != ctxs[(b, pc)]:
            # code that is not in RAM after boot (loaded per game phase): every copy of its bytes in the banks is a
            # source of it (the same routine can sit in several banks); the context holds the instruction itself
            ctx = ctxs[(b, pc)]
            hits = [(i, o + 6) for i in range(8) for o in _find_all(orig[i], ctx)]
            if not hits:
                ctx = ctx[3:12]
                hits = [(i, o + 3) for i in range(8) for o in _find_all(orig[i], ctx)]
            if not hits:
                print('WARN: RAM site %04X (recorded bytes) not found in the banks' % pc); continue
            if len(hits) > 1: print('note: RAM site %04X has %d sources:' % (pc, len(hits)), ['%d:%04X' % (i, o + 0x8000) for i, o in hits])
            for i, o in hits:
                patch_instr(banks[i], o, pc, labs, log)
        else:
            hits = []
            for lo, hi in ((6, 9), (5, 7)):   # shorter context: bytes after the code may be runtime tables ($CA32)
                ctx = bytes(ram_image[pc - lo:pc + hi])
                hits = [(i, orig[i].find(ctx) + lo) for i in range(8) if orig[i].find(ctx) >= 0]
                if len(hits) == 1 and orig[hits[0][0]].find(ctx, orig[hits[0][0]].find(ctx) + 1) < 0: break
            if len(hits) != 1:
                print('WARN: RAM site %04X located %d times' % (pc, len(hits))); continue
            i, o = hits[0]
            patch_instr(banks[i], o, pc, labs, log)
    input_patches(banks, log)
    bank_patches(banks, labs, log)
    static_patches(banks, labs, log)
    for b, pc in raster_waits(orig, audit):
        patch_instr(banks[b], pc - 0x8000, pc, labs, log)
    # the game's per-frame screen update call (RAM $4320: JSR $BFB7) -> resident wrapper
    ctx = bytes(ram_image[0x431A:0x4320]) + bytes([0x20, 0xB7, 0xBF])
    hits = [(i, orig[i].find(ctx)) for i in range(8) if orig[i].find(ctx) >= 0]
    assert len(hits) == 1, hits
    i, o = hits[0]
    o += 6
    assert bytes(banks[i][o:o + 3]) == bytes([0x20, 0xB7, 0xBF])
    banks[i][o + 1:o + 3] = bytes([labs['hook_gfx'] & 0xFF, labs['hook_gfx'] >> 8])
    log.append((0x4320, 'JSR', 'abs', '$BFB7', '->', 'hook_gfx'))
    # the main loop's wait for the line-250 flag (RAM $40CD: LDA $C102 / BEQ $40CD) -> render in the idle time
    ctx = bytes([0xAD, 0x02, 0xC1, 0xF0, 0xFB, 0xA9, 0x00, 0x8D, 0x02, 0xC1])
    assert bytes(ram_image[0x40CD:0x40D7]) == ctx
    hits = [(i, orig[i].find(ctx)) for i in range(8) if orig[i].find(ctx) >= 0]
    assert len(hits) == 1, hits
    i, o = hits[0]
    banks[i][o:o + 3] = bytes([0x20, labs['hook_idle'] & 0xFF, labs['hook_idle'] >> 8])
    log.append((0x40CD, 'LDA', 'abs', '$C102', '->', 'hook_idle'))
    return log
