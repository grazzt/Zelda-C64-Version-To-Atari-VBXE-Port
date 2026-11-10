#!/usr/bin/env python3
"""Read-only VICE VSF module dumper for the supplied Zelda snapshot."""

import os
from pathlib import Path
import struct

SNAPSHOT = Path(os.environ.get('ZELDA_VSF', 'zelda.vsf'))
OUT = Path("evidence/vsf-modules")
VSF_HEADER_SIZE = 58


def modules(data):
    offset = VSF_HEADER_SIZE
    while offset < len(data):
        if offset + 22 > len(data):
            raise ValueError(f"truncated module header at ${offset:X}")
        raw_name = data[offset:offset + 16]
        name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
        major, minor = data[offset + 16:offset + 18]
        size = struct.unpack_from("<I", data, offset + 18)[0]
        if size < 22 or offset + size > len(data):
            raise ValueError(f"invalid {name} module size {size} at ${offset:X}")
        yield name, major, minor, data[offset + 22:offset + size]
        offset += size
    if offset != len(data):
        raise ValueError("module table does not end at file boundary")


def main():
    data = SNAPSHOT.read_bytes()
    if not data.startswith(b"VICE Snapshot File\x1a"):
        raise ValueError("not a VICE snapshot")
    OUT.mkdir(parents=True, exist_ok=True)
    found = {}
    rows = []
    for name, major, minor, body in modules(data):
        found[name] = body
        rows.append(f"{name} v{major}.{minor}: {len(body)} bytes")
    OUT.joinpath("modules.txt").write_text("\n".join(rows) + "\n")

    c64mem = found["C64MEM"]
    OUT.joinpath("C64MEM-module.bin").write_bytes(c64mem)
    # VICE manual §9.2.2.15: CPUDATA, CPUDIR, EXROM, GAME, then 64 KiB RAM.
    if len(c64mem) < 4 + 0x10000:
        raise ValueError(f"C64MEM unexpectedly short: {len(c64mem)}")
    ram = c64mem[4:4 + 0x10000]
    OUT.joinpath("ram.bin").write_bytes(ram)
    print("C64MEM module bytes", len(c64mem), "RAM bytes", len(ram),
          "CPU port", c64mem[:4].hex())
    print("main CPU PC", hex(struct.unpack_from("<H", found["MAINCPU"], 12)[0]))
    print("modules written to", OUT)


if __name__ == "__main__":
    main()
