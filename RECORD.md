# RECORD: recreating the full playthrough movie

The movie `zelda_full_game.mp4` is a complete first-quest playthrough of this Atari 65XE + VBXE port of the C64
*The Legend of Zelda* conversion, played by the RAM-reading bot in `tools/bot/`. It runs from the title screen to the
end credits: all eight triforce pieces, Level 9, Ganon, Zelda, and "another quest will start from here". It was
recorded in AltirraSDL.

Every frame of the movie comes from replaying a joystick log from power-on. The port and the emulator setup are
deterministic, so the same cartridge and the same log give the same game, frame for frame.

| | |
| --- | --- |
| Input log | `tools/bot/runs/full_game.json.gz` (in this repo, 47 KB) |
| Frames | 422575: the bot's 422275 frames plus 300 frames of idle tail on the credits |
| Movie | from emulator frame 548 (the title appears) to the end: 422028 frames, 1:57:23 at 59.92 fps (Atari NTSC) |
| Picture | 1344x896: the 672x224 Altirra frame, scaled 2x horizontally and 4x vertically with nearest-neighbour, so the C64's pixels come out square. H.264 CRF 18 |
| Sound | the emulator's own POKEY output (bridge `AUDIO_RECORD`), 44.1 kHz, AAC 160 kbit/s |
| Final state | Zelda's room (`$32`), game mode `$13` (the ending), 13 hearts, magic sword, red ring, 8 triforce pieces |

## What you need

1. **The original C64 cartridge image**, at `assets/original/Zelda_C64.crt`. It is not in the repo (copyrighted
   source media). Required sha256: `f24fa24d705ad27226ad8047159815726f4a6bf60c86417be447e85949fdc032`.
2. **The port kit**, a separate toolkit (not in this repo). It provides cc65 (`ca65`/`ld65`), AltirraSDL 4.50.21
   nightly with the TCP bridge (`local/altirrasdl/usr/bin/AltirraSDL`, driven by `tools/atari/altirra.py`), the 6502 core
   and opcode tables used by the C64 host model (`tools/c64/mos6502.py`, `code6502.py`), and the VICE ROMs (the build
   reads the C64 KERNAL, BASIC and character ROMs from `local/vice/usr/share/vice/C64`). The tools find it at
   `$PORTKIT`, or else in a `port_kit` folder next to this repo. Load its environment with
   `source "$PORTKIT/tools/env.sh"`.
3. **The hardware-access audit** is in the repo: `tools/audit.json`, 312 hardware-access sites of the C64 original.
   It holds no bytes of the original: the code around RAM sites, which `tools/patches.py` looks for in the banks, is
   stored as references into the cartridge image and rebuilt from your `Zelda_C64.crt`
   (`tools/host/audit_export.py`).
4. **Python 3.12** with Pillow, and **ffmpeg** with libx264 and aac. These were measured with ffmpeg 6.1.1 and
   Pillow 12.3.

## Steps

```sh
cd zelda_port_vbxe
export PORTKIT=/path/to/port_kit
source "$PORTKIT/tools/env.sh"

# 1. Build the cartridge (about a second) and check that it is the one the log was played on.
python3 tools/build_atari.py
sha256sum build/zelda.car
#   must be 3a6345afedb499d3bf6ddd68a4c393605aa6bf71e1c2395640f8cb43116238d8
#   (the port's code has not changed since commit 8554b85, the bug 7 fix; the build gives the same
#   cartridge from tools/audit.json as it did from the audit pickles)

# 2. Record: 12 parallel parts, 300 idle frames after the bot's last input (the credits).
python3 tools/bot/record_par.py tools/bot/runs/full_game.json.gz build/zelda_full_game.mp4 12 300
```

`record_par.py` prints the frame the movie starts at, then writes `wrote build/zelda_full_game.mp4: ...` when it is
done. Each part logs to `build/_recpar/partNN.log`, with a line every 1800 frames and the game state at its end. The
last part must end in mode 19 (`$13`), level 9, screen 50 (`$32`).

## How the recording works

- **Single process (`record.py`).** `tools/bot/record.py LOG OUT [TAIL]` replays the log one frame at a time and takes a
  screenshot after each frame. That is about 10 frames a second, so about 12 hours for this movie.
- **Parallel (`record_par.py`).** `tools/bot/record_par.py LOG OUT [JOBS] [TAIL]` cuts the frames from the title to the
  end into JOBS equal parts. Each part is a separate process with its own emulator, in `build/altirra_recNN`.
  1. It replays the log from power-on to the part's start in large batches, at about 270 frames a second.
     `FRAME n` and n x `FRAME 1` emulate the same frames (see `emu.py`).
  2. It then records its own frames to `partNN.mp4` and `partNN.wav`.
  3. At the end, each part's sound is cut or padded to exactly its frame count at 59.92 fps. The videos are joined
     without re-encoding, and the sound is muxed in once.
  4. There may be a click at each join, because each part's sound starts in a fresh emulator: the replay reaches the
     same machine state, but sound that was still ringing across the join may not be captured exactly.
- **Cost.** 12 jobs keep 24 cores busy: 12 emulators plus 12 encoders with 2 threads each. In a 3000-frame test with
  2 jobs, each part recorded about 21 frames a second. The full movie with 12 jobs took 4625 s (1 h 17 min) on a
  24-thread machine. Under that load each part recorded about 14 frames a second, and the replay to a part's start ran
  at about 140 frames a second, so the last part (387k frames of replay first) finished last. The result was 278 MB,
  with video and sound both 7043.2 s, and no visible step at the joins.
- **Checking a replay without recording.** `tools/bot/serve.py LOG.json` replays a log, then serves the bot.
  `tools/bot/emu.py`'s `replay()` can also be used directly. Compare the end state with the `end` field of the log.

## Where the log came from (the bot)

The log was produced by `tools/bot/campaign.py`, in phases:

```
start, l1, l2, wsword, l3, l4, l5, l6, l7, l8, upgrade, l9
```

Each phase is `C.go(name)`. The bot ran in a long-lived session: `python3 tools/bot/serve.py [LOG.json]` holds the
emulator, and `python3 tools/bot/cli.py 'python code'` sends it snippets, with `C = campaign.Campaign(m)` in the shared
namespace. The bot reads only game RAM: positions, object types, room data and Ganon's stun state. It uses checkpoints
to retry rooms. A phase writes its log to `build/camp_<phase>.json`. `docs/DEVLOG.md`, sessions 11-15, describes the bot
and the game facts it relies on.

Re-running the bot is not a way to get *this* movie. It takes many hours, it takes different paths whenever its
retries go differently, and parts of the last two phases were driven step by step from the session:

- the upgrade caves, the magic sword and the ring;
- Ganon's fight through `Dungeon.ganon()`;
- the walk to Zelda.

Those steps are now in `p_upgrade` and `p_l9`, but these two phases have not been run end to end in one go. The
committed log is the canonical run. Recreate the movie from it.
