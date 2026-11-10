#!/usr/bin/env python3
"""Capture a deterministic NTSC EasyFlash boot through VICE's binary monitor."""

import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
from pathlib import Path
import signal
import socket
import struct
import subprocess
import time
import ctypes
import argparse


KIT = Path(_KIT)
ROM = KIT / "local/vice/usr/share/vice"
VICE = KIT / "local/vice/usr/bin/x64sc"
IMAGE = Path("work/Zelda_C64.crt").resolve()
OUT = Path("evidence")


def start_xvfb():
    xvfb = subprocess.Popen(["Xvfb", ":139", "-screen", "0", "800x600x24", "-nolisten", "tcp",
                             "-nolisten", "unix", "-listen", "local"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(100):
        if Path("/tmp/.X139-lock").exists():
            return xvfb, ":139"
        time.sleep(0.05)
    xvfb.terminate()
    raise RuntimeError("Xvfb failed to start on :139")


class XKeys:
    def __init__(self, display):
        self.x11 = ctypes.CDLL("libX11.so.6")
        self.xtst = ctypes.CDLL("libXtst.so.6")
        self.x11.XOpenDisplay.restype = ctypes.c_void_p
        self.x11.XStringToKeysym.restype = ctypes.c_ulong
        self.x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                                   ctypes.c_ulong]
        self.x11.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.handle = self.x11.XOpenDisplay(display.encode())
        if not self.handle:
            raise RuntimeError(f"could not connect to display {display}")
        self.xtst.XTestFakeMotionEvent(self.handle, -1, 200, 150, 0)
        self.x11.XSync(self.handle, 0)
        time.sleep(0.5)

    def send(self, key_name, down):
        sym = self.x11.XStringToKeysym(key_name.encode())
        code = self.x11.XKeysymToKeycode(self.handle, sym)
        if not code:
            raise RuntimeError(f"unknown X key {key_name}")
        self.xtst.XTestFakeKeyEvent(self.handle, code, int(down), 0)
        self.x11.XSync(self.handle, 0)

    def close(self):
        if self.handle:
            self.x11.XCloseDisplay(self.handle)
            self.handle = None


def recv_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        part = sock.recv(size - len(data))
        if not part:
            raise RuntimeError("VICE binary monitor disconnected")
        data.extend(part)
    return bytes(data)


def request(sock, seq, kind, payload=b""):
    sock.sendall(b"\x02\x02" + struct.pack("<IIB", len(payload), seq, kind) + payload)
    while True:
        header = recv_exact(sock, 12)
        if header[:2] != b"\x02\x02":
            raise RuntimeError(f"bad VICE response header: {header.hex()}")
        length, reply_kind, error, reply_seq = struct.unpack("<IBBI", header[2:])
        body = recv_exact(sock, length)
        if error:
            raise RuntimeError(f"VICE command ${kind:02X} failed with ${error:02X}")
        if reply_seq == seq:
            return reply_kind, body


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="capture title/item-demo frames at 0.5s intervals")
    parser.add_argument("--early", action="store_true", help="capture fresh boot at 0.1s intervals for first 2 seconds")
    parser.add_argument("--fresh-sequence", action="store_true", help="capture fresh boot/title/demo checkpoints with no input")
    parser.add_argument("--f7-probe", action="store_true", help="send one F7 during the initial verified title")
    options = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    cmd = [
        str(VICE), "-default", "-console", "+sound", "+remotemonitor",
        "-directory", str(ROM),
        "-kernal", str(ROM / "C64/kernal-901227-03.bin"),
        "-basic", str(ROM / "C64/basic-901226-01.bin"),
        "-chargen", str(ROM / "C64/chargen-901225-01.bin"),
        "-dos1541", str(ROM / "DRIVES/dos1541-325302-01+901229-05.bin"),
        "-model", "ntsc", "-ntsc", "-seed", "1", "+easyflashcrtwrite", "+cartreset", "-cartcrt", str(IMAGE),
        "-moncommands", str(Path("tools/analysis/joy_setup.mon").resolve()),
        "-binarymonitor", "-binarymonitoraddress", f"127.0.0.1:{port}",
    ]
    xvfb, display = start_xvfb()
    env = os.environ.copy()
    state = Path("work/vice-fresh-sequence-original" if options.fresh_sequence else "work/vice-fresh-demo-original").resolve()
    for folder in ("config", "cache", "data"):
        (state / folder).mkdir(parents=True, exist_ok=True)
    env.update(XDG_CONFIG_HOME=str(state / "config"), XDG_CACHE_HOME=str(state / "cache"),
               XDG_DATA_HOME=str(state / "data"))
    env.update(DISPLAY=display, GDK_BACKEND="x11", NO_AT_BRIDGE="1")
    env.pop("WAYLAND_DISPLAY", None)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env,
                            start_new_session=True, text=True)
    sock = None
    keys = None
    seq = 0
    try:
        deadline = time.monotonic() + 30
        while sock is None and time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError(f"VICE exited with status {proc.returncode}: {proc.stdout.read()}")
            try:
                sock = socket.create_connection(("127.0.0.1", port), timeout=1)
            except OSError:
                time.sleep(0.1)
        if sock is None:
            raise TimeoutError("VICE binary monitor did not become available")
        sock.settimeout(60)
        keys = XKeys(display)

        def send(kind, payload=b""):
            nonlocal seq
            seq += 1
            return request(sock, seq, kind, payload)[1]

        def joy(mask):
            # VICE binary monitor: zero-based port 1 is C64 joystick port 2.
            return send(0xA2, struct.pack("<HH", 1, (~mask) & 31))

        if options.f7_probe:
            # Startup credit appears first; title is reached after about 3s.
            time.sleep(3.0)
            send(0x81)
            capture_screen(sock, seq + 1, OUT / "f7-probe-title.png")
            send(0xAA)
            keys.send("F7", True)
            time.sleep(0.5)
            keys.send("F7", False)
            time.sleep(0.5)
            send(0x81)
            capture_screen(sock, seq + 1, OUT / "f7-probe-after.png")
            banks = send(0x82)
            OUT.joinpath("f7-probe-after-ram.bin").write_bytes(read_ram(send, banks))
            print("F7 probe captured from initial title")
            return

        # Fresh CRT starts at its reset vector. Let it run with no inputs and
        # capture representative attract-sequence checkpoints.
        checkpoints = (tuple(i / 10 for i in range(1, 21)) if options.early else
                       tuple(i / 4 for i in range(58, 69)) if options.demo else
                       (0.5, 1.0, 1.5, 2.0, 4.0, 8.0, 12.0, 14.0, 14.5, 15.0, 16.0, 18.0))
        last = 0.0
        for index, target in enumerate(checkpoints):
            time.sleep(target - last)
            last = target
            send(0x81)
            if options.demo or options.fresh_sequence:
                capture_screen(sock, seq + 1, OUT / f"fresh-sequence-{index:02d}-{target:04.1f}s.png")
                regs = send(0x31, b"\0")
                OUT.joinpath(f"fresh-sequence-{index:02d}-regs.bin").write_bytes(regs)
            elif options.early:
                capture_screen(sock, seq + 1, OUT / f"early-{index:02d}-{target:04.1f}s.png")
            else:
                regs = send(0x31, b"\0")
                OUT.joinpath(f"fresh-{index:02d}-registers.bin").write_bytes(regs)
                capture_screen(sock, seq + 1, OUT / f"fresh-{index:02d}.png")
                banks = send(0x82)
                OUT.joinpath(f"fresh-{index:02d}-ram.bin").write_bytes(read_ram(send, banks))
            if index < len(checkpoints) - 1:
                send(0xAA)
        print("Fresh boot checkpoints captured; no keys/joystick input sent")
    finally:
        if sock is not None:
            sock.close()
        if keys is not None:
            keys.close()
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
        output, _ = proc.communicate(timeout=10)
        OUT.joinpath("vice-startup.log").write_text(output)
        if xvfb.poll() is None:
            os.killpg(xvfb.pid, signal.SIGTERM)


def capture_screen(sock, seq, path):
    kind, body = request(sock, seq, 0x84, b"\x01\x00")
    fields, width, height = struct.unpack_from("<IHH", body)
    length = int.from_bytes(body[fields + 4:fields + 8], "little")
    pixels = body[fields + 8:fields + 8 + length]
    if len(pixels) == length - 4:
        height -= 1
        pixels = pixels[:width * height]
    if len(pixels) != width * height:
        raise RuntimeError(f"incomplete screenshot data: {width}x{height}, {len(pixels)} bytes")
    from c64_screen import write_png
    path.parent.mkdir(parents=True, exist_ok=True)
    write_png(path, [pixels[y * width:(y + 1) * width] for y in range(height)])


def read_ram(send, banks):
    count = int.from_bytes(banks[:2], "little")
    offset = 2
    ram_bank = None
    for _ in range(count):
        size = banks[offset]
        entry = banks[offset + 1:offset + 1 + size]
        name_len = entry[2]
        if entry[3:3 + name_len].decode() == "ram":
            ram_bank = int.from_bytes(entry[:2], "little")
        offset += size + 1
    if ram_bank is None:
        raise RuntimeError("VICE did not report a RAM bank")
    data = send(0x01, struct.pack("<BHHBH", 0, 0, 0xFFFF, 0, ram_bank))[2:]
    if len(data) != 0x10000:
        raise RuntimeError(f"expected 65536 RAM bytes, got {len(data)}")
    return data


if __name__ == "__main__":
    main()
