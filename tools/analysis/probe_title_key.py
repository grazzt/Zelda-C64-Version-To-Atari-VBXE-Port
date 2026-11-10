#!/usr/bin/env python3
"""Probe the C64 title-screen F7 key through GTK/XTest and VICE binary monitor."""

import ctypes
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import time

from capture_boot import KIT, ROM, VICE, IMAGE, OUT, request


def save_screen(sock, seq, path):
    _, body = request(sock, seq, 0x84, b"\x01\x00")
    fields, width, height = struct.unpack_from("<IHH", body)
    length = int.from_bytes(body[fields + 4:fields + 8], "little")
    pixels = body[fields + 8:fields + 8 + length]
    if len(pixels) == length - 4:
        height -= 1
        pixels = pixels[:width * height]
    if len(pixels) != width * height:
        raise RuntimeError("VICE returned incomplete screenshot")
    sys.path.insert(0, str(KIT / "tools/c64"))
    from c64_screen import write_png
    path.parent.mkdir(parents=True, exist_ok=True)
    write_png(path, [pixels[y * width:(y + 1) * width] for y in range(height)])


def main():
    xvfb = subprocess.Popen(["Xvfb", ":139", "-screen", "0", "800x600x24", "-nolisten", "tcp",
                             "-nolisten", "unix", "-listen", "local"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(100):
        if Path("/tmp/.X139-lock").exists():
            break
        time.sleep(0.05)
    else:
        raise RuntimeError("Xvfb did not start")

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    cmd = [str(VICE), "-default", "+sound", "-directory", str(ROM),
           "-kernal", str(ROM / "C64/kernal-901227-03.bin"),
           "-basic", str(ROM / "C64/basic-901226-01.bin"),
           "-chargen", str(ROM / "C64/chargen-901225-01.bin"),
           "-dos1541", str(ROM / "DRIVES/dos1541-325302-01+901229-05.bin"),
           "-model", "ntsc", "-ntsc", "-seed", "1", "-cartreset", "-cartcrt", str(IMAGE),
           "-binarymonitor", "-binarymonitoraddress", f"127.0.0.1:{port}", "-warp"]
    env = os.environ.copy()
    env.update(DISPLAY=":139", GDK_BACKEND="x11", NO_AT_BRIDGE="1")
    env.pop("WAYLAND_DISPLAY", None)
    logpath = OUT / "vice-key-probe.log"
    logpath.parent.mkdir(parents=True, exist_ok=True)
    log = logpath.open("w")
    proc = subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    sock = None
    x11 = ctypes.CDLL("libX11.so.6")
    xtst = ctypes.CDLL("libXtst.so.6")
    x11.XOpenDisplay.restype = ctypes.c_void_p
    x11.XStringToKeysym.restype = ctypes.c_ulong
    x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
    x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    display = x11.XOpenDisplay(b":139")
    if not display:
        raise RuntimeError("could not connect to Xvfb")
    seq = 0
    try:
        for _ in range(300):
            if proc.poll() is not None:
                raise RuntimeError(f"VICE exited; inspect {logpath}")
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=0.2)
                break
            except OSError:
                time.sleep(0.1)
        if sock is None:
            raise TimeoutError("VICE binary monitor unavailable")
        sock.settimeout(60)

        def send(kind, payload=b""):
            nonlocal seq
            seq += 1
            return request(sock, seq, kind, payload)[1]

        send(0x81)
        for _ in range(12):
            send(0x71, struct.pack("<BH", 0, 60000))
        send(0x81)
        save_screen(sock, seq + 1, OUT / "title-before-f7.png")
        key = x11.XKeysymToKeycode(display, x11.XStringToKeysym(b"F7"))
        xtst.XTestFakeKeyEvent(display, key, 1, 0)
        x11.XSync(display, 0)
        time.sleep(0.15)
        send(0x71, struct.pack("<BH", 0, 60000))
        xtst.XTestFakeKeyEvent(display, key, 0, 0)
        x11.XSync(display, 0)
        for _ in range(12):
            send(0x71, struct.pack("<BH", 0, 60000))
        send(0x81)
        Path("evidence/f7-registers.bin").write_bytes(send(0x31, b"\0"))
        save_screen(sock, seq + 1, OUT / "after-f7.png")
        ram = send(0x82)
        count, offset, bank_id = int.from_bytes(ram[:2], "little"), 2, None
        for _ in range(count):
            size = ram[offset]
            entry = ram[offset + 1:offset + 1 + size]
            if entry[3:3 + entry[2]].decode() == "ram":
                bank_id = int.from_bytes(entry[:2], "little")
            offset += size + 1
        data = send(0x01, struct.pack("<BHHBH", 0, 0, 0xFFFF, 0, bank_id))[2:]
        Path("evidence/f7-ram.bin").write_bytes(data)
        print("F7 probe captured", len(data), "RAM bytes")
    finally:
        if sock is not None:
            sock.close()
        x11.XCloseDisplay(display)
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=10)
        log.close()
        if xvfb.poll() is None:
            os.killpg(xvfb.pid, signal.SIGTERM)
            xvfb.wait(timeout=5)


if __name__ == "__main__":
    main()
