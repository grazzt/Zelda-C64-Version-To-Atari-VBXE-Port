#!/usr/bin/env python3
"""Load the Zelda VSF via VICE binary monitor, capture state, and optionally start."""

import os
_REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))  # the repo root
_KIT = os.environ.get('PORTKIT') or os.path.join(os.path.dirname(_REPO), 'port_kit')  # the port kit
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import time
import ctypes
import argparse

KIT = Path(_KIT)
ROM = KIT / "local/vice/usr/share/vice"
VICE = KIT / "local/vice/usr/bin/x64sc"
SNAPSHOT = Path(os.environ.get('ZELDA_VSF', 'zelda.vsf')).resolve()
OUT = Path("evidence")


def read_exact(sock, count):
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise RuntimeError("VICE monitor disconnected")
        data.extend(chunk)
    return bytes(data)


class BinaryMonitor:
    def __init__(self, sock):
        self.sock = sock
        self.request_id = 0
        self.stopped = False

    def packet(self):
        header = read_exact(self.sock, 12)
        if header[:2] != b"\x02\x02":
            raise RuntimeError(f"invalid monitor header: {header.hex()}")
        length, kind, error, request_id = struct.unpack("<IBBI", header[2:])
        body = read_exact(self.sock, length)
        if error:
            raise RuntimeError(f"VICE command ${kind:02X} error ${error:02X}")
        if kind == 0x62:
            self.stopped = True
        elif kind == 0x63:
            self.stopped = False
        return request_id, kind, body

    def command(self, kind, body=b""):
        self.request_id += 1
        current = self.request_id
        self.sock.sendall(b"\x02\x02" + struct.pack("<IIB", len(body), current, kind) + body)
        while True:
            request_id, _, response = self.packet()
            if request_id == current:
                return response

    def wait_stopped(self, timeout=10):
        old_timeout = self.sock.gettimeout()
        self.sock.settimeout(timeout)
        try:
            while not self.stopped:
                self.packet()
        finally:
            self.sock.settimeout(old_timeout)


def named_bank(data, name):
    count = int.from_bytes(data[:2], "little")
    offset = 2
    for _ in range(count):
        size = data[offset]
        row = data[offset + 1:offset + 1 + size]
        label = row[3:3 + row[2]].decode()
        if label == name:
            return int.from_bytes(row[:2], "little")
        offset += size + 1
    raise RuntimeError(f"VICE has no {name} memory bank")


class XKeys:
    def __init__(self, display=":0"):
        self.x = ctypes.CDLL("libX11.so.6")
        self.t = ctypes.CDLL("libXtst.so.6")
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XStringToKeysym.restype = ctypes.c_ulong
        self.x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.t.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.t.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                                ctypes.c_int, ctypes.c_ulong]
        self.x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.display = self.x.XOpenDisplay(display.encode())
        if not self.display:
            raise RuntimeError(f"cannot connect to display {display}")
        self.t.XTestFakeMotionEvent(self.display, -1, 200, 150, 0)
        self.x.XSync(self.display, 0)
        time.sleep(0.5)

    def send(self, name, down):
        sym = self.x.XStringToKeysym(name.encode())
        code = self.x.XKeysymToKeycode(self.display, sym)
        if not code:
            raise RuntimeError(f"unknown X keysym {name}")
        self.t.XTestFakeKeyEvent(self.display, code, int(down), 0)
        self.x.XSync(self.display, 0)

    def close(self):
        self.x.XCloseDisplay(self.display)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--press-f7", action="store_true", help="press F7 after capturing the restored state")
    parser.add_argument("--resume", action="store_true", help="send monitor Exit and capture the resumed game screen")
    options = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    args = [
        str(VICE), "-default", "+sound", "-directory", str(ROM),
        "-kernal", str(ROM / "C64/kernal-901227-03.bin"),
        "-basic", str(ROM / "C64/basic-901226-01.bin"),
        "-chargen", str(ROM / "C64/chargen-901225-01.bin"),
        "-dos1541", str(ROM / "DRIVES/dos1541-325302-01+901229-05.bin"),
        "-model", "ntsc", "-ntsc", "-seed", "1", "+cart",
        "-binarymonitor", "-binarymonitoraddress", f"127.0.0.1:{port}",
    ]
    state = Path("work/vice-vsf-binary").resolve()
    for folder in ("config", "cache", "data"):
        (state / folder).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(XDG_CONFIG_HOME=str(state / "config"), XDG_CACHE_HOME=str(state / "cache"),
               XDG_DATA_HOME=str(state / "data"))
    with (OUT / "zelda-vsf-vice.log").open("w") as log:
        proc = subprocess.Popen(args, env=env, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        sock = None
        try:
            deadline = time.monotonic() + 30
            while sock is None and time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f"VICE exited with {proc.returncode}")
                try:
                    sock = socket.create_connection(("127.0.0.1", port), timeout=1)
                except OSError:
                    time.sleep(0.1)
            if sock is None:
                raise TimeoutError("VICE binary monitor did not start")
            sock.settimeout(60)
            monitor = BinaryMonitor(sock)
            monitor.command(0x81)
            monitor.wait_stopped()
            # Confirm binary monitor channel with a register read.
            monitor.command(0x31, b"\0")
            path = str(SNAPSHOT).encode()
            if len(path) > 255:
                raise ValueError("snapshot path exceeds VICE protocol limit")
            undump_body = monitor.command(0x42, bytes([len(path)]) + path)
            OUT.joinpath("zelda-vsf-undump-response.bin").write_bytes(undump_body)
            undump_pc = int.from_bytes(undump_body[:2], "little")
            saved_cpu_off = SNAPSHOT.read_bytes().index(b"MAINCPU")
            saved_pc = int.from_bytes(SNAPSHOT.read_bytes()[saved_cpu_off + 22 + 12:saved_cpu_off + 22 + 14], "little")
            if undump_pc != saved_pc:
                raise RuntimeError(f"VSF load PC ${undump_pc:04X} != saved PC ${saved_pc:04X}")
            registers = monitor.command(0x31, b"\0")
            banks = monitor.command(0x82)
            ram_bank = named_bank(banks, "ram")
            io_bank = named_bank(banks, "io")
            ram = monitor.command(0x01, struct.pack("<BHHBH", 0, 0, 0xFFFF, 0, ram_bank))[2:]
            io = monitor.command(0x01, struct.pack("<BHHBH", 0, 0xD000, 0xDFFF, 0, io_bank))[2:]
            OUT.joinpath("zelda-vsf-registers.bin").write_bytes(registers)
            OUT.joinpath("zelda-vsf-ram.bin").write_bytes(ram)
            OUT.joinpath("zelda-vsf-io.bin").write_bytes(io)
            screen = monitor.command(0x84, b"\x01\x00")
            write_screen(screen, OUT / "zelda-vsf.png")
            print(f"VSF loaded at PC ${undump_pc:04X}; pre-input state captured")
            if options.resume:
                monitor.command(0xAA)
                time.sleep(1.0)
                monitor.command(0x81)
                monitor.wait_stopped()
                regs = monitor.command(0x31, b"\0")
                OUT.joinpath("zelda-vsf-resumed-registers.bin").write_bytes(regs)
                screen = monitor.command(0x84, b"\x01\x00")
                write_screen(screen, OUT / "zelda-vsf-resumed.png")
            if options.press_f7:
                # Intentionally do not resume/press in this branch until a
                # monitor-saved VSF's restored UI has been independently
                # confirmed; the prior snapshot contains a monitor prompt.
                raise RuntimeError("refusing F7: VSF restore point is at a monitor prompt")
                keys = XKeys(os.environ.get("DISPLAY", ":0"))
                keys.send("F7", True)
                time.sleep(0.5)
                keys.send("F7", False)
                keys.close()
                # Resume the same restored machine naturally. Sample after a
                # short wall-clock delay; no monitor instruction stepping.
                monitor.command(0xAA)
                time.sleep(1.5)
                monitor.command(0x81)
                monitor.wait_stopped()
                post_regs = monitor.command(0x31, b"\0")
                OUT.joinpath("zelda-vsf-after-f7-registers.bin").write_bytes(post_regs)
                post_screen = monitor.command(0x84, b"\x01\x00")
                write_screen(post_screen, OUT / "zelda-vsf-after-f7.png")
                banks = monitor.command(0x82)
                post_ram = monitor.command(
                    0x01, struct.pack("<BHHBH", 0, 0, 0xFFFF, 0, named_bank(banks, "ram"))
                )[2:]
                OUT.joinpath("zelda-vsf-after-f7-ram.bin").write_bytes(post_ram)
        finally:
            if sock is not None:
                sock.close()
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)


def run_cycles(monitor, count):
    remaining = count
    while remaining:
        block = min(remaining, 65_535)
        monitor.command(0x71, struct.pack("<BH", 0, block))
        monitor.wait_stopped()
        remaining -= block


def write_screen(data, path):
    fields, width, height = struct.unpack_from("<IHH", data)
    length = int.from_bytes(data[fields + 4:fields + 8], "little")
    pixels = data[fields + 8:fields + 8 + length]
    if len(pixels) == length - 4:
        height -= 1
        pixels = pixels[:width * height]
    if len(pixels) != width * height:
        raise RuntimeError("VICE returned incomplete display buffer")
    sys.path.insert(0, str(KIT / "tools/c64"))
    from c64_screen import write_png
    write_png(path, [pixels[y * width:(y + 1) * width] for y in range(height)])


if __name__ == "__main__":
    main()
