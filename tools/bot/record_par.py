"""python3 tools/bot/record_par.py LOG.json OUT.mp4 [JOBS] [TAIL_FRAMES] : record.py, in JOBS parallel parts.

record.py replays the log frame by frame with a screenshot each frame: ~10 frames a second, one core (a whole game of
422k frames took ~12 hours). Here the frames from the title to the end are cut into JOBS equal parts; each part is a
separate process with its own emulator: the log replayed from power-on up to the part's start in big FRAME batches
(~270 frames a second; FRAME n and n x FRAME 1 emulate the same, emu.py), then frame by frame with screenshots to its
own video (x264) and its own sound (AUDIO_RECORD). At the end each part's sound is cut or padded to its frame count
exactly, the videos are joined without re-encoding (same encoder settings), and the sound goes in once.
Parts: build/_recpar/ (partNN.mp4, partNN.wav, partNN.json, partNN.log)."""
import sys, os, json, subprocess, time, base64, io, gzip

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emu import replay, ROOT
import zram as Z

W, H = 1344, 896
FPS = 59.92
TMP = os.path.join(ROOT, 'build/_recpar')


def load_log(path, tail):
    d = json.load(gzip.open(path, 'rt') if path.endswith('.gz') else open(path))
    log = [[n, tuple(inp)] for n, inp in d['log']]
    if tail: log.append([tail, ('center', False, '')])
    return log


def find_start(log):
    """The first frame the movie shows: frame 200 or later, once the port has dropped r_blank ($FD2D: the title)."""
    m = replay(log, folder=os.path.join(ROOT, 'build/altirra_rec_start'), upto=200)
    try:
        acc = 0
        for n, inp in log:
            if acc + n <= m.frames: acc += n; continue
            m.set(*inp)
            for i in range(acc + n - max(acc, m.frames)):
                if m.peek(0xFD2D) == 0: return m.frames
                m.step(1)
            acc += n
        return m.frames
    finally:
        m.close()


def part(k, a, b, log_path, tail):
    """Frames a+1 .. b (the screenshot after each frame), into partK.mp4 / partK.wav."""
    from PIL import Image
    log = load_log(log_path, tail)
    name = os.path.join(TMP, 'part%02d' % k)
    m = replay(log, folder=os.path.join(ROOT, 'build/altirra_rec%02d' % k), upto=a)
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                           '-s', '%dx%d' % (W, H), '-r', '%.2f' % FPS, '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
                           '-crf', '18', '-pix_fmt', 'yuv420p', '-threads', '2', name + '.mp4'], stdin=subprocess.PIPE)
    st = {'n': 0, 't': time.time()}

    def on_frame(m):
        data = base64.b64decode(m.e.command('SCREENSHOT')['data'])
        ff.stdin.write(Image.open(io.BytesIO(data)).convert('RGB').resize((W, H), Image.NEAREST).tobytes())
        st['n'] += 1
        if st['n'] % 1800 == 0:
            print('  part %d: %d of %d frames (%.0f s)' % (k, st['n'], b - a, time.time() - st['t']), flush=True)

    try:
        m.e.command('AUDIO_RECORD start path=%s' % (name + '.wav'))
        m.on_frame = on_frame
        acc = 0
        for n, inp in log:
            s, e = max(acc, a), min(acc + n, b)
            if s < e:
                m.set(*inp); m.step(e - s)
            acc += n
            if acc >= b: break
        m.e.command('AUDIO_RECORD stop')
        json.dump({'k': k, 'a': a, 'b': b, 'n': st['n'], 'end': Z.state(m)}, open(name + '.json', 'w'))
        print('part %d done: %d frames, %s' % (k, st['n'], Z.state(m)), flush=True)
    finally:
        m.close()
        ff.stdin.close(); ff.wait()


def main():
    log_path, out = sys.argv[1], sys.argv[2]
    jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    tail = int(sys.argv[4]) if len(sys.argv) > 4 else 120
    os.makedirs(TMP, exist_ok=True)
    log = load_log(log_path, tail)
    total = sum(n for n, i in log)
    t0 = time.time()
    first = find_start(log)
    print('frames %d, the movie from frame %d (found in %.0f s)' % (total, first, time.time() - t0), flush=True)
    a0 = first - 1                                      # (part 0 shows the frame after a0 = the first frame)
    cuts = [a0 + (total - a0) * k // jobs for k in range(jobs + 1)]
    procs = []
    for k in range(jobs):
        lf = open(os.path.join(TMP, 'part%02d.log' % k), 'w')
        procs.append(subprocess.Popen([sys.executable, os.path.abspath(__file__), '--part', str(k), str(cuts[k]),
                                       str(cuts[k + 1]), log_path, str(tail)], stdout=lf, stderr=subprocess.STDOUT))
    bad = [k for k, p in enumerate(procs) if p.wait() != 0]
    if bad: raise SystemExit('parts failed: %s (see %s/partNN.log)' % (bad, TMP))
    vids, wavs, n = [], [], 0
    for k in range(jobs):
        info = json.load(open(os.path.join(TMP, 'part%02d.json' % k)))
        name = os.path.join(TMP, 'part%02d' % k)
        dur = info['n'] / FPS                            # (the sound of a part: exactly as long as its frames)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', name + '.wav', '-af', 'apad,atrim=0:%.6f' % dur,
                        '-ar', '44100', name + '_fit.wav'], check=True)
        vids.append(name + '.mp4'); wavs.append(name + '_fit.wav'); n += info['n']
    for lst, files in (('vids.txt', vids), ('wavs.txt', wavs)):
        open(os.path.join(TMP, lst), 'w').write(''.join("file '%s'\n" % f for f in files))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', os.path.join(TMP, 'vids.txt'),
                    '-c', 'copy', os.path.join(TMP, 'video.mp4')], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', os.path.join(TMP, 'wavs.txt'),
                    '-c', 'copy', os.path.join(TMP, 'audio.wav')], check=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(TMP, 'video.mp4'), '-i',
                    os.path.join(TMP, 'audio.wav'), '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', out],
                   check=True)
    print('wrote %s: %d frames from game frame %d (%.1f s of movie) in %.0f s' % (out, n, first, n / FPS,
                                                                               time.time() - t0), flush=True)


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--part':
        part(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6]))
    else:
        main()
