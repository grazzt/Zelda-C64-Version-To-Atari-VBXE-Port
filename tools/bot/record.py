#!/usr/bin/env python3
"""python3 tools/bot/record.py LOG.json OUT.mp4 [TAIL_FRAMES] : the movie of a bot run.
Replays the input log from power-on (emu.replay: the same game the bot played), frame by frame: each frame's screenshot
(672x224, scaled to 1344x896: square C64 pixels) to ffmpeg, the sound from the emulator itself (bridge AUDIO_RECORD:
POKEY output, 44.1 kHz). Video at 59.92 fps, the Atari's NTSC frame rate, so picture and sound stay together.
The first frames, while the port hides the start-up screens, are cut (the movie starts at the title)."""
import gzip, sys, os, json, subprocess, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image
from emu import replay, ROOT
import zram as Z

log_path = sys.argv[1]
out = sys.argv[2]
tail = int(sys.argv[3]) if len(sys.argv) > 3 else 120
d = json.load(gzip.open(log_path, 'rt') if log_path.endswith('.gz') else open(log_path))
log = [[n, tuple(inp)] for n, inp in d['log']]
if tail: log.append([tail, ('center', False, '')])
tmp = os.path.join(ROOT, 'build/_rec')
os.makedirs(tmp, exist_ok=True)
W, H = 1344, 896
FPS = '59.92'
shot = os.path.join(tmp, 'shot.png')
wav = os.path.join(tmp, 'audio.wav')
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H),
                       '-r', FPS, '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
                       os.path.join(tmp, 'video.mp4')], stdin=subprocess.PIPE)
state = {'started': False, 'first': None, 'n': 0, 't': time.time()}


def on_frame(m):
    if not state['started']:
        if m.frames < 200 or m.peek(0xFD2D) != 0: return          # (r_blank: the port shows the title)
        state['started'] = True; state['first'] = m.frames
        m.e.command('AUDIO_RECORD start path=%s' % wav)
    m.e.screenshot(shot)
    ff.stdin.write(Image.open(shot).convert('RGB').resize((W, H), Image.NEAREST).tobytes())
    state['n'] += 1
    if state['n'] % 1800 == 0:
        print('  %d frames recorded (%.0f s)' % (state['n'], time.time() - state['t']), flush=True)


m = replay(log, on_frame=on_frame)
try:
    m.e.command('AUDIO_RECORD stop')
    print('end state', Z.state(m))
finally:
    m.close()
    ff.stdin.close(); ff.wait()
# (audio starts with the first recorded frame; trim to the video's length)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(tmp, 'video.mp4'), '-i', wav, '-c:v', 'copy',
                '-c:a', 'aac', '-b:a', '160k', '-shortest', out], check=True)
print('wrote %s: %d frames from game frame %d (%.1f s)' % (out, state['n'], state['first'], state['n'] / 59.92))
