# Zelda for the Atari 65XE + VBXE

A port of the Commodore 64 conversion of *The Legend of Zelda* to an 8-bit Atari (65XE/130XE class) with a
[VBXE](https://www.atariwiki.org/wiki/Wiki.jsp?page=VBXE) video board. It is a port, not a remake. The original
6502 code of the C64 cartridge runs natively on the Atari, at its own addresses. Only its accesses to C64 hardware
(VIC-II, SID, CIA, EasyFlash bank switching) are patched, to an Atari runtime that emulates what they did.

**This repository contains no game code or data.** You need your own copy of the C64 cartridge image
(`Zelda_C64.crt`). The build reads it and patches it into an Atari cartridge image on your machine.

## Status

- The whole first quest plays to the end: all eight triforce pieces, Level 9, Ganon, Zelda and the credits. A
  RAM-reading bot (`tools/bot/`) played it through from power-on, and the input log of that run is in the repo.
  [RECORD.md](RECORD.md) explains how to turn that log into a movie of the game.
- Full speed on NTSC (60 Hz), with music and sound effects, smooth screen scrolls, and saves that survive power-off
  (on a disk in D1:).
- Tested in AltirraSDL with the VBXE device only. **It has not been run on real hardware.**

## How it works

| Part | What it does |
| --- | --- |
| Cartridge | A 256 KB MegaCart (`.car` type 30). Banks 0-7 are the C64 cartridge's eight EasyFlash banks (ROML+ROMH in one 16 KB window), patched. Banks 8-15 hold the Atari runtime. |
| Patches | `tools/patches.py` patches 333 hardware-access sites. VIC and SID writes go to shadow pages, `$DE00` bank writes become MegaCart bank switches, and raster reads and waits become hooks. The sites come from a hardware-access audit of the original (`tools/audit.json`, made by tracing the game in a C64 host model). |
| Raster IRQs | One-shot POKEY timer events and display-list interrupts, kept in order on the C64's raster clock (`atari/src/resident.s`). |
| Picture | The VBXE draws it (`atari/src/render.s`). C64 characters go into a glyph atlas in VRAM, and changed cells are blitted into a background buffer. Sprites are pre-coloured 24x21 shapes in a cache, drawn with the blitter (no multiplexing limits, no flicker). C64 colours are exact. |
| Sound | SID writes are translated to POKEY (`atari/src/sound.s`). |
| Input | The joystick in port 1 is the C64's joystick 2. The CIA keyboard reads are patched to per-column images (`atari/src/input.s`). |
| Saves | The game's EasyFlash EAPI save calls write to RAM (`atari/src/eapi.s`). Half a second after the last write, the RAM is flushed to an ATR disk in D1: with a polled SIO driver, and it is loaded again at boot (`atari/src/save.s`). |

## Controls

| Atari | Game |
| --- | --- |
| Joystick (port 1) | move |
| Fire | A button (sword) |
| SPACE | B button (the selected item) |
| START | START (F7 on the C64) |
| SELECT | SELECT (F5) |
| OPTION, or SHIFT+START | F8 |
| keys 1 / 3 / 5 / 7 / 8 | F1 / F3 / F5 / F7 / F8 |

## Building

Requirements:

- **`Zelda_C64.crt`**, the C64 cartridge, at `assets/original/Zelda_C64.crt` (sha256
  `f24fa24d705ad27226ad8047159815726f4a6bf60c86417be447e85949fdc032`). Not included.
- **The port kit**, a separate toolkit, not included. It provides cc65 (`ca65`/`ld65`), the 6502 core used by the C64
  host model, the VICE ROMs (KERNAL, BASIC, character ROM: the host model boots the cartridge, and the character ROM
  goes into the Atari cartridge), and AltirraSDL with a TCP automation bridge plus its Python driver (for the tests and
  the bot). The tools find it at `$PORTKIT`, or else in a `port_kit` folder next to this repo.
- Python 3.12 with Pillow (and numpy for some of the analysis tools). ffmpeg is needed only for recording movies.

```sh
export PORTKIT=/path/to/port_kit
source "$PORTKIT/tools/env.sh"
python3 tools/build_atari.py          # -> build/zelda.car (256 KB) and a blank build/zelda_save.atr
```

The build takes about a second. With the cartridge image above it gives `build/zelda.car` with sha256
`3a6345afedb499d3bf6ddd68a4c393605aa6bf71e1c2395640f8cb43116238d8`.

## Running

Start Altirra with the VBXE device (`--adddevice vbxe` in AltirraSDL, or enable VBXE in the Windows Altirra's
system settings), on a 65XE/130XE NTSC machine. Attach `build/zelda.car` as the cartridge. To keep saves, put
`build/zelda_save.atr` in D1:. The build never overwrites a save disk that is already there.

## The bot and the movie

`tools/bot/` is a bot that plays the game by reading its RAM: object positions and types, room data, inventory.
It drives the emulator through the AltirraSDL bridge, with path finding over the overworld and the dungeons,
checkpoints to retry rooms, and special handling for the bosses.

- `tools/bot/serve.py [LOG.json]` holds an emulator, and `tools/bot/cli.py 'python code'` sends it snippets.
- `tools/bot/campaign.py` plays the game in phases (`start, l1, l2, wsword, l3, l4, l5, l6, l7, l8, upgrade, l9`).
- `tools/bot/runs/full_game.json.gz` is the input log of one complete run (422,275 frames, about 1 h 57 min).
- `tools/bot/record_par.py` replays a log into an mp4 in parallel parts. See [RECORD.md](RECORD.md).

## Layout

| Path | Contents |
| --- | --- |
| `atari/src/` | The Atari runtime (ca65): boot, resident IRQ/NMI layer, VBXE renderer, scrolling, colours, sound, input, saves |
| `atari/atari.cfg` | ld65 memory map of the cartridge banks |
| `tools/build_atari.py`, `tools/patches.py` | The build: assembles the runtime, patches the original's banks, writes the `.car` |
| `tools/audit.json`, `tools/host/` | The hardware-access audit, and the C64 host model that produces it (`audit.py`, `audit_export.py`, `explore.py`) |
| `tools/bot/` | The bot, the replay and the movie recorders |
| `tools/*.py` | Test, profiling and screenshot tools used during the port (each script's docstring says what it does) |
| `tools/analysis/` | Early tools that inspect the original under VICE |
| `docs/` | The development log and the early feasibility study |

## Documentation

- [RECORD.md](RECORD.md): recreating the full playthrough movie.
- [docs/DEVLOG.md](docs/DEVLOG.md): the development log, session by session, with every measurement, bug and fix.
- [docs/FEASIBILITY.md](docs/FEASIBILITY.md): the first study of the original cartridge.

## Legal

*The Legend of Zelda* is a trademark of Nintendo. The C64 conversion is the work of its authors. This project is not
affiliated with or endorsed by either. The repository holds only original code, documentation and data made for the
port: the patcher, the Atari runtime, a list of hardware-access addresses, and an input log of the bot's run. You need a
legally obtained copy of the C64 cartridge image to build anything playable.
