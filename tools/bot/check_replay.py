#!/usr/bin/env python3
"""python3 tools/bot/check_replay.py LOG.json : replay the log from power-on and print the end state (compare with
what the bot reached)."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emu import replay
import zram as Z
d = json.load(open(sys.argv[1]))
t = time.time()
m = replay([[n, tuple(i)] for n, i in d['log']], folder=os.path.join(os.path.dirname(sys.argv[1]), 'altirra_check'))
print('replayed %d frames in %.0f s:' % (m.frames, time.time() - t), Z.state(m), 'triforce %02X' % m.peek(Z.TRIFORCE))
m.close()
