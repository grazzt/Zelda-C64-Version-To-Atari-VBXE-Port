#!/usr/bin/env python3
"""python3 tools/bot/cli.py 'code' (or code on stdin): run code in the serve.py session."""
import sys, os, socket
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
code = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
s = socket.socket(socket.AF_UNIX); s.connect(os.path.join(ROOT, 'build/bot.sock'))
s.sendall(code.encode() + b'\0')
out = b''
while True:
    x = s.recv(65536)
    if not x: break
    out += x
print(out.decode(), end='')
