#!/usr/bin/env python3
"""python3 tools/bot/serve.py [LOG.json] : a long-lived bot session for development (save states only work inside one
emulator process). Replays LOG.json (if given), then runs Python snippets sent by tools/bot/cli.py in one namespace
(m = Emu, b = Bot, Z, N, ...). Socket: build/bot.sock."""
import sys, os, json, socket, io, traceback, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from emu import Emu, replay, ROOT
import zram as Z, nav as N
from bot import Bot, Event

ns = {'Z': Z, 'N': N, 'Event': Event, 'ROOT': ROOT, 'json': json}
if len(sys.argv) > 1:
    d = json.load(open(sys.argv[1]))
    ns['m'] = replay([[n, tuple(i)] for n, i in d['log']])
    ns['notes'] = d.get('notes', [])
else:
    ns['m'] = Emu(); ns['notes'] = []
ns['b'] = Bot(ns['m'])
sock = os.path.join(ROOT, 'build/bot.sock')
if os.path.exists(sock): os.unlink(sock)
srv = socket.socket(socket.AF_UNIX); srv.bind(sock); srv.listen(1)
live = open(os.path.join(ROOT, 'build/serve_live.log'), 'a')
print('ready', flush=True)
while True:
    c, _ = srv.accept()
    data = b''
    while not data.endswith(b'\0'):
        x = c.recv(65536)
        if not x: break
        data += x
    code = data.rstrip(b'\0').decode()
    class Tee(io.StringIO):
        def write(self, x):
            live.write(x); live.flush(); return super().write(x)
    out = Tee()
    with contextlib.redirect_stdout(out):
        try:
            if code.strip() == '__quit__':
                ns['m'].close(); c.sendall(b'bye'); c.close(); break
            exec(compile(code, '<cli>', 'exec'), ns)
        except BaseException:
            traceback.print_exc(file=out)
    try:
        c.sendall(out.getvalue().encode() or b'(ok)'); c.close()
    except OSError:
        pass
