#!/usr/bin/env python3
"""python3 tools/host/audit_export.py : work/an/audit.pkl + audit_ctx.pkl -> tools/audit.json (committed).

The audit (tools/host/audit.py) records hardware-access sites of the C64 original: {(bank or -1 for RAM, pc):
{(kind, register): count}}, and for RAM sites the code bytes around them when they ran (pc-6 .. pc+9), which
tools/patches.py looks for in the banks. Those bytes are the original's code, so tools/audit.json does not hold them:
each context is stored as where it is found in the user's own cartridge image instead.
  - a context equal to the RAM after boot (host model, 400 frames) is left out: patches.py then locates the site from
    that RAM, exactly as when the context matches it;
  - otherwise it is a list of pieces: [bank, offset, length] (bytes of EF bank `bank`, ROML+ROMH, at `offset`) or a
    hex string (bytes that are not in the banks as they are: operands filled in at run time).
build_atari.py rebuilds the contexts from Zelda_C64.crt (tools/patches.py `load_audit`); this script checks that the
rebuilt contexts equal the recorded ones."""
import json, pickle, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/host')); sys.path.insert(0, str(ROOT / 'tools'))
from c64host import load_crt, C64
import patches


def pieces(ctx, orig):
    """ctx as bank references, with literal bytes only where no reference fits (the longest run found wins)."""
    out, i = [], 0
    while i < len(ctx):
        best = None
        for n in range(len(ctx) - i, 2, -1):
            for b in range(8):
                o = orig[b].find(ctx[i:i + n])
                if o >= 0: best = [b, o, n]; break
            if best: break
        if best:
            out.append(best); i += best[2]
        else:
            if out and isinstance(out[-1], str): out[-1] += ctx[i:i + 1].hex()
            else: out.append(ctx[i:i + 1].hex())
            i += 1
    return out


def main():
    crt = ROOT / 'assets/original/Zelda_C64.crt'
    roml, romh = load_crt(crt)
    orig = [bytes(roml[b] + romh[b]) for b in range(8)]
    host = C64(crt); host.run_frames(400); host.remap()
    audit = pickle.load(open(ROOT / 'work/an/audit.pkl', 'rb'))
    ctxs = pickle.load(open(ROOT / 'work/an/audit_ctx.pkl', 'rb'))
    sites = [[b, pc, [[k, r, n] for (k, r), n in sorted(kinds.items())]] for (b, pc), kinds in sorted(audit.items())]
    ctx = []
    for (b, pc), c in sorted(ctxs.items()):
        if (b, pc) not in audit or pc in patches.SKIP_PC: continue      # (never used by patches.apply)
        if bytes(host.ram[pc - 6:pc + 9]) == c: continue
        ctx.append([b, pc, pieces(c, orig)])
    lits = sum(len(p) // 2 for _, _, ps in ctx for p in ps if isinstance(p, str))
    out = ROOT / 'tools/audit.json'
    out.write_text(json.dumps({'sites': sites, 'ctx': ctx}, separators=(',', ':')).replace('],[', '],\n[') + '\n')
    a2, c2 = patches.load_audit(out, orig)
    assert a2 == {k: dict(v) for k, v in audit.items()}
    for k, v in c2.items(): assert ctxs[k] == v, hex(k[1])
    print('%s: %d sites, %d contexts as references (%d literal bytes)' % (out.relative_to(ROOT), len(sites), len(ctx), lits))


if __name__ == '__main__':
    main()
