# Development log: Zelda C64 to Atari 65XE + VBXE

> The development log of the port, kept during the work, session by session. Paths in it are relative to
> the repo; `$PORTKIT` is the port kit. Files under `build/`, `work/` and `evidence/` are local outputs
> and are not in the repo.

## Goal and agreed packaging

- Port the original C64 Zelda game to an Atari 65XE with VBXE; do not replace it with a look-alike game.
- Preferred delivery: banked Atari ROM cartridge for game code/assets, plus a writable ATR used only for save data. This is a target to validate, not yet a proven architecture.
- Source CRT is a 128 KiB EasyFlash image (16 × 8 KiB CHIP payloads). Atari kit examples document larger banked carts; runtime footprint/mapper compatibility still need measurement.
- Source-media SHA-256: `f24fa24d705ad27226ad8047159815726f4a6bf60c86417be447e85949fdc032`.
- Keep source media (`*.crt`, `*.zip`) out of Git. Keep generated evidence/work/build/screenshots out of Git. Never publish local credentials/config.

## Verified findings

- User booted the original on Windows SDL2VICE 3.10 with `x64sc Zelda_C64.crt`, NTSC MOS6567R8.
- User-observed flow: startup credit for roughly 2–3 seconds → title → press F7 → “Register your name” screen. In joystick port 2, move the joystick to move the cursor and press fire to select each character. Press F5 to move to name entry 2, F5 again to entry 3, F5 again to “Register”. Press F7 to reach “- S E L E C T -”, then F7 to start the game. User asked us to use `Luna` as the test name.
- The local kit self-test passed: `source $PORTKIT/tools/env.sh && "$PORTKIT/tools/selftest.sh" --altirra`. It included VBXE checks and ATR SIO write/read-back checks. This only validates generic kit storage/emulator behavior, not Zelda saves.
- CRT structure/hash were measured. Pristine source, `assets/original/Zelda_C64.crt`, and restored `work/Zelda_C64.crt` hashes currently match.
- Local VICE 3.7.1 NTSC resources were read as `MachineVideoStandard=2`, `VICIIModel=3`.
- Local VICE 3.7.1 direct launch with `-cartcrt <copy> +cartreset` runs the cartridge. `evidence/boot-1.png` through `boot-4.png` show the Zelda title and “PUSH START BUTTON”.
- Fresh boot sampled with no input: title at 0.1s and 0.5s; story starts around 1.0s and fills by 1.5s; “ALL OF TREASURES” and item-list pages follow by ~2s. The attract demo cycles through inventory pages; title/story reappear during the loop, with item pages again at 30/45s and a partial transition at 75s. Evidence: `evidence/early-*.png`, `evidence/demo-*.png`.
- Fresh-boot F7 probes: F7 at the initial title (0.1s) enters story/demo. F7 around 14s also entered story text. The 18s capture was still item/manual demo, not a title prompt. A later 3s F7 probe was still at startup credit and produced a C64 startup/test screen. These runs do not establish registration input. Stop timing-guess F7 presses; trace the actual registration trigger/state transition.

## Known tool behavior / failed attempts

- Kit `tools/c64/vice.py` and `vice_keys.py` treat their positional image as `-autostart` media. With the CRT, logs show `AUTOSTART: Error`, then cartridge attachment/reset. This did not prevent manual Windows VICE from running the game; it is a local driver mismatch.
- Local direct cartridge invocation: `-cartcrt` with `+cartreset` (disable reset-on-attach), NTSC options in the order `-default -model ntsc -ntsc`, and no monitor reset. The title capture is reproducible.
- The local capture harness uses XTest for C64 matrix F7. Confirm each keypress by reading the resulting state; F7 so far starts story/demo from title and has not opened registration.
- Latest `--f7-probe` waited 3s but the before-image was still the startup-credit screen, not title; after F7, the screen showed a dense C64 startup/test pattern. This run is invalid for game controls. Require a visually verified `PUSH START BUTTON` frame before sending F7.
- User clarified the registration name entry is joystick-controlled rather than typed, with F5 advancing name slots and the Register selection. Do not send keyboard letters; after registration is genuinely visible, use joystick navigation to select `Luna` and follow the documented F5/F7 sequence.
- User's exact clarified flow: at “Register your name”, Joy 2 directions move the cursor, Joy 2 fire selects a character; F5 moves to name slot 2, F5 to slot 3, F5 to “Register”; F7 opens “- S E L E C T -”; F7 starts the game. Test name: `Luna`.
- User supplied `zelda.vsf`, a VICE 3.10 `C64SC` snapshot (SHA-256 `fc9c9ac6a79ac1318ff93e016204b60ca1d16f11b57e3f7f325a364661a99114`) showing the `- SELECT -` menu. In the supplied screenshot, the two occupied names appear to be `MO` and `BAD`; the cursor appears beside `BAD`. This suggests F7 would start `BAD`, but the names/selection have not been independently verified from a successfully loaded VSF.
- The current VSF inspector successfully restores the snapshot through the VICE binary monitor. The returned undump PC is `$C4DC`, matching the VSF MAINCPU PC, and the captured 64 KiB RAM SHA-256 matches the C64MEM module exactly (`9051d77abc9ebfe7895f4d8e722cd7702ca428620ecbe039f47b2ff929e4dc2c`). Screenshot `evidence/zelda-vsf.png` shows the saved `- SELECT -` menu. Ignore stale `T64 snapshot support is not implemented` logs/screenshots from earlier monitor-script attempts.
- In the verified VSF screen, occupied entries read `MO` and `BAD`, with the selection pointer beside `BAD`. Therefore F7 targets `BAD`.
- One authorized F7 was sent after that verified snapshot load. The resulting frame was black and RAM changed, but no stable gameplay image was captured; the start result is inconclusive. Do not claim the game started based on that frame.
- Kit-tested VICE joystick setup: monitor command `resourceset "JoyPort2Device" "37"`; binary-monitor joystick command `0xA2` with little-endian `<HH>` `(1, (~mask)&31)`. Mask bits: up=1, down=2, left=4, right=8, fire=16; examples use `$FF` neutral, `$EF` fire, `$F7` right. Local direct CRT run confirms device 37 was set and `0xA2` accepted, but fire at title did not advance the screen; this specific game may start by F7 rather than joystick fire.
- We have not navigated the joystick letter selector, entered `Luna`, started gameplay locally, or tested F8. No save has been written or verified.
- An earlier VICE flash experiment modified only a disposable working copy. It was restored from the pristine CRT; all three copies hash-match now.

## Next actions

The current milestone is **pre-game reference capture only**. No Atari gameplay porting work begins until these references are captured.

1. Fresh NTSC title/story/item-attract references are captured. Demo pages progress through the item inventory; a partial transition appears later. Continue only if a particular demo segment needs better coverage.
2. Do not repeat blind F7 timing tests. The latest three-second probe was still on startup credit, so it did not test title input. Trace the fresh-boot key/state flow and confirm the actual rendered title before sending F7; F7 from a verified title previously began story/demo.
3. Once the registration-entry action/state is established, capture the prompt and use Joy 2/fire and F5 to enter `Luna`.
4. Capture the resulting `- SELECT -` menu with Luna visible. Stop before the final F7 that starts gameplay.
5. Save screenshots/RAM/I/O/registers and commands for each verified checkpoint; update `docs/FEASIBILITY.md` and this handoff, then commit.

Use the verified VSF (`zelda.vsf`) as a separate clean-state source when useful; its saved list currently shows MO and BAD, with BAD selected. Fresh-boot captures remain a distinct baseline. The earlier F7 attempt from the VSF yielded a black frame and is not a gameplay reference.

After this milestone, resume first-gameplay capture, save-flow tracing, and resource measurements. The Atari save format and banked-cartridge fit remain unverified.

## Files and evidence

- Feasibility report: `docs/FEASIBILITY.md` (currently UNKNOWN for gameplay/resource/save feasibility).
- Design decisions: `docs/superpowers/specs/2026-10-31-zelda-atari-port-design.md`.
- Milestone plan: `docs/superpowers/plans/2026-10-31-zelda-feasibility-plan.md`.
- Local capture harness: `tools/analysis/capture_boot.py`; VICE monitor sample: `tools/analysis/boot.mon`.
- Screenshot sequence: `evidence/boot-1.png` … `evidence/boot-4.png` (title verified). `evidence/registration.png` is a failed F7 probe and still shows the title; do not use it as registration evidence.
- VICE logs: `build/vice-run-boot-1405927.log`, `evidence/vice-startup.log`, `work/vice-keys-crt/vice-keys.log`.
- VSF diagnostics: `tools/analysis/inspect_zelda_vsf.py`, `tools/analysis/inspect_vsf_modules.py`, and `evidence/vsf-modules/`. `evidence/zelda-vsf.png` and `zelda-vsf-ram.bin` are verified pre-F7 snapshot captures; post-F7 screenshot is black and start state is unverified.

## Port progress log (2026-10-31, session 2): title + attract demo

Labels: **Measured** = run in the host model `tools/host/c64host.py` (Python C64+EasyFlash model, line-granular timing); **Design** = not yet built.

### Measured
- `tools/host/c64host.py` boots the real CRT to the animated title and the full attract loop (title -> story -> item pages), with no keys. `tools/host/vicrender.py` renders the VIC state to PNG. `tools/host/tracecore.py` records the PC of every I/O access.
- Boot is plain ROM-to-RAM copies from bank 7 (e.g. `$8000 -> $4018`, `$9F1E -> $C100`); no decompression. The reset path sets `$DE02=$87` (16K mode).
- The game writes `$01` only once (`$37`): I/O, cart and KERNAL stay visible. KERNAL is used only for the IRQ entry at `$FF48`.
- 6000 frames of attract touch only **181 hardware-access sites**: VIC (raster IRQ plus sprite multiplexer at `$C424-$C720`, setup at `$4105-$4263`), SID music (bank 0, `$9600-$9A29`, `$B255`), CIA1 keyboard scan (`$44C0-$4504`), and ~12 `STA $DE00` bank switches. Full table: `work/an/audit.pkl`, regenerate with the trace run.
- Attract raster IRQs: lines 8 and 250 each frame (82/88/120/136 only at page transitions). Vertical scroll uses `$D011` fine Y-scroll, changed at line 257. Charset at `$2800`, screen `$0800`, `$D018=$2E`, `$D016=$D8`.
- RAM pages used: `$00-$0F, $14-$18, $1C-$60, $65, $67-$68, $6D-$7F, $C0-$CF`. Free on Atari: `$D800-$DBFF` colour RAM is plain RAM, plus `$DC00+` and `$E000-$FFFF`.

### Design (not built yet)
- 256 KB MegaCart (`.car` type 30): banks 0-7 = EF banks 0-7 (ROML+ROMH = one 16K window), banks 8-15 = Atari code. Boot trampoline overwrites the unused C64 boot stub at `$8000` and the header at `$BFFA`.
- Hardware patches (assert original bytes): VIC/SID/CIA writes go to shadow pages at `$DC00+`; `$DE00` becomes the `$D500` bank write; `$D012` raster reads and waits are patched; two raster IRQs per frame become POKEY timer-1 IRQs (15 kHz = one scanline per tick), so they stay maskable.
- Renderer: VBXE 320x200 overlay. Cell-dirty scan of screen/colour RAM, blitting 8x8 tiles from an atlas (hires and multicolour variants, AND-mask trick for the per-cell colour). Fine Y-scroll via source offset of a per-frame blit; sprites via blitter on top. Open risk: CPU cost of the dirty scan (about 20K cycles per full scan; plan to rotate it).
- Next steps: (1) build infrastructure with ca65/ld65 and a proof-of-life cart in Altirra; (2) boot the original natively and diff RAM against the host model; (3) IRQ/timer layer; (4) renderer; (5) sprites; (6) keyboard (F7 = START).

No Atari code exists yet; the Atari side is entirely unbuilt.

### Milestone M2 reached (native execution): the original game runs on the Atari
- `tools/build_atari.py` builds `build/zelda.car` (256 KB MegaCart: EF banks 0-7 patched + Atari bank 8). `tools/patches.py` applies 171 audit-driven patches (VIC/SID writes -> shadow pages `$F000/$F040`, `$DE00` -> bank-switch stubs, `$D011/$D012` reads -> hooks, `$D030` reads `$FF`). Each patch site comes from `work/an/audit.pkl` (regenerate with the trace run; it now includes reads of `$D011/$D012/$D019`).
- Runtime (`atari/src/resident.s`, at `$F100`): replays the original reset path (`$B7BE`, then bank 7 `$AF15`), VBI NMI resyncs POKEY timer 1 (15 kHz = 1 scanline/tick) that emulates the C64 raster IRQs, KERNAL IRQ entry re-created at `$FF48`.
- **Verified (Measured):** after ~400 Atari frames, `tools/probe_atari.py 400` + `tools/render_atari_ram.py` renders the Atari's RAM as the correct title screen ("PUSH START BUTTON") with the correct charset, colour RAM and VIC state; game banks switch normally. No display output exists yet (ANTIC off, VBXE unused).
- Known gaps: RAM site `$CA32` not located in cart data (patch skipped, check); keyboard/joystick unpatched (attract needs none); SID music writes go to a shadow (silent); bank value `$10` write seen once at boot (EAPI probe).
- Next: VBXE renderer (M3), sprites (M4), then keyboard.

### Milestone M3/M4 reached: title screen + scrolling story/item attract run on Atari + VBXE (2026-10-31)
**Measured in AltirraSDL 4.50.21 with VBXE** (`python3 tools/build_atari.py && python3 tools/shots_atari.py build/s 700 500 ...`; screenshots stay local under `build/`):
- Title screen renders with correct colours, animated colour cycling, animated waterfall sprites; it flows into the story page, which scrolls up smoothly (VIC YSCROLL mapped to a source offset of the compose blit), then the "ALL OF TREASURES" item pages scroll.
- Game timing: the colour-cycle/counter rates match the host model once the NMI cost was cut (game logic needs ~57% of an Atari frame; the renderer is kept to ~17%).
- Renderer design (`atari/src/render.s`, bank 9, called from the VBI NMI):
  - Glyph atlas in VRAM (hires + multicolour variants, AND-mask trick for the per-cell colour), rebuilt per 32-glyph segment when a checksum of the charset changes.
  - Dirty-cell scan of 2 text rows per frame against a shadow in VRAM, one blit per changed cell into a 320x216 background buffer.
  - Per frame: one chained blitter list: BG copy (XOR 1, so overlay value 0 never occurs for bg0) plus one "copy if non-zero" block per sprite, into a margined 416x284 display buffer; double-buffered via the XDL overlay address. If a visible sprite has the "behind characters" priority bit, a layered chain is used (fill, behind sprites, BG with bg0 transparent, front sprites).
  - Sprites: shape cache of pre-coloured 24x21 images keyed by (pointer, colour, multicolour); sprite state is snapshotted at the end of the C64 line-8 IRQ (hook on the `$D012` write), because only that state is visible on screen.
- Raster IRQs are one-shot POKEY timer-1 events armed relative to the current line (`hook_d012w`), re-armed at the VBI for line 8. Only the line-8 band is displayed; extra multiplexer bands (lines 82/88/120/136 at page changes) are not drawn.
- Bugs found and fixed along the way: audit missed `$D011/$D012/$D019` reads; C128 `$D030` probe must read `$FF`; periodic timer caused IRQ storms; renderer overrun re-entered the NMI; sprite cache overlapped the BG buffer; `sp_key2` clobbered X.

**Known gaps / next:**
- Visible tearing while text scrolls: when the game shifts screen RAM up one row, ~900 cells change at once; the dirty scan needs several frames. Plan: detect a one-row shift and do it as a single blit.
- A 4-way set-associative sprite cache attempt produced a black screen (not diagnosed; reverted). Direct-mapped is fine: the attract uses only 24 distinct shape pointers, no collisions mod 64.
- Not implemented: sound (SID writes go to a shadow), keyboard/joystick (F7 etc.), 38-column border, sprite-sprite/background collisions, extra raster bands, `$CA32` RAM patch site.
- Boot skips the C64 startup credit; load takes ~220 Atari frames mostly because the first frames' renderer work competes with the loader.

### Session 3 (scrolling / item page fixes) - Measured in AltirraSDL + VBXE
Fixed:
- **Item page garbage ("HEART/CONTAINER" then noise)**: the item pages use the C64 *character ROM* (charset at `$1000`), which the game never copies to RAM. The atlas now takes glyphs from a copy of the character ROM held in VRAM (`CHROM`), loaded at boot from cart bank 10. The ROM bytes come from the local VICE install (`PORTKIT/.../chargen-901225-01.bin`) at build time and are never committed.
- **BG corruption by sprites**: sprite block destination address used a carry that was clobbered by `sec/sbc`, so sprite blits landed in the background buffer. Rewritten with explicit 24-bit arithmetic.
- **Sprite multiplexing**: per-frame list of up to 4 sprite "bands" (one snapshot per C64 raster event, `BANDS` at `$F400`), each drawn clipped to the raster lines it is active for.
- **IRQ sequencing**: if the VBI NMI lands inside the line-250 handler the line-8 event used to be lost (game slowed / state drifted). A `vbi_flag` now re-arms the overdue event ~9 scanlines after the handler's `$D012` write (one scanline caused nested IRQs and a stack overflow).
- **Cost**: cell blits are now batched into one prefilled chained blitter list per frame; hot-row scanning rescans recently changed rows each frame; colour-only changes on blank glyphs are skipped (not for 40 frames after an atlas change). The game's per-frame screen update (`$BFB7`, called from RAM `$4320`) is hooked (`hook_gfx`) so the renderer does not read screen RAM mid-update, and a one-row scroll shift is detected and done as 3 blits (`shift_check`).
- Debug aids: `tools/check_bg.py N` (compare VRAM BG with a model render of Atari RAM), `ZDEFS="NO_SPRITES"/"NO_CONVERT"/"NO_ADD"/"NO_IMM" python3 tools/build_atari.py` build-time switches to bisect problems.

Still wrong / not done:
- During fast item scrolling a few cells can be stale for several frames: stray letters, a doubled label row, an icon missing for a frame. Cause: the dirty scan (hot rows 3 + 1 rotating, cap ~30 cells/frame) lags the game's burst writes; page changes still redraw progressively.
- The title->story transition shows leftover fragments for a few frames.
- Sprite shared colours (`$D025/26`) and the 38-column border are taken once per frame, not per band.
- No sound, no keyboard/joystick yet.

### Session 3b (colours, shift, IRQ ordering)
Fixed (Measured in AltirraSDL):
- **Same-coloured icons** (red/blue ring, arrow/silver arrow): sprite multicolour shared colours (`$D025/$D026`) are now read per band and baked into the cached sprite image; the cache key includes them (`SPK_S`).
- **Doubled/overlapping label rows on item pages**: the game moves rows in two steps on those pages, so the "one-row shift" detector fired on half-shifted screens and moved the background wrongly. It now verifies all 24x40 cells (`verify_shift`) before blitting a shift.
- **Missing icons**: band start line is now the game's previous `$D012` value (the line the handler was armed for) instead of our own timer target; `$D012` reads return a virtual raster relative to the running event (`virt_now`), because deferred handlers otherwise see a wrong line.
- Lesson: an attempted "arm only if next event is line 8" in the NMI stalled the game; reverted. `tools/stuck_check.py` detects stalled IRQ/stack collapse.
Still wrong:
- Stray BG fragments at fixed rows on item pages ("TR", "C", "N", a vine piece) that never get cleared; some labels still double for a frame or two during scrolling; flicker has not been measured, only reduced.
- Next ideas: track exact changed cells by hooking the game's row-copy/text-draw routines in bank 6 instead of scanning; compare frames against the host model with a per-band sprite renderer.

### Session 3c (scroll quality pass) - Measured in AltirraSDL + VBXE
Root causes found and fixed:
- **Stray fragments / ghost header rows ("TR", "C", "N", duplicated "ALL OF TREASURES")**: caused by the one-row-shift shortcut. `tools/first_stale.py` (steps frame by frame, reports the first cell whose BG pixels disagree with RAM while its shadow claims it is current) showed stale cells appear exactly on shift frames and never with the shortcut disabled. The shortcut is now off by default (`.ifndef WITH_SHIFT` in `shift_check`); all scrolling is plain dirty-cell updating.
- **Sprites missing in the title (waterfall)**: the title uses six raster events (8, 82, 88, 120, 136, 250); only four bands were kept. Bands are now 48 bytes, five kept, events at line >= 251 ignored.
- **Cache thrash / slow game**: sprite cache is 4-way, set chosen from pointer, colours and shared colours; the colour shadow stores the low nibble only so `$FF` can mean "invalid" (previously cells with real colour byte `$FF` redrew forever).
- **Timing**: when the VBI render is blocked by the game's per-frame screen update (`$BFB7`), the render now runs right after that update (`render_pend` + `hook_gfx`), so it sees a consistent screen.
- Removed the "fire the overdue line-8 event immediately" trick: it nested IRQs and collapsed the stack at ~frame 320. `tools/stuck_check.py` guards against that.
- Tools: `tools/check_bg.py`, `tools/first_stale.py`, `ZDEFS` build switches.
Remaining: a text row can still appear doubled for a frame or two while scrolling (the C64 itself duplicates a row for one frame at the Y-scroll wrap, plus our render lag); the game runs below C64 speed in the sprite-heavy title phase (about 50%); no sound; no keyboard/joystick.
Ideas if shift is wanted back: verify colours as well as characters before shifting, and find why BG row r+1 can differ from its shadow when the shift fires.

### Session 4 (2026-11-01): correct attract, coroutine renderer, black start-up - Measured in AltirraSDL + VBXE
**Game fixes (the "random letters", stray sprites, wrong colours):**
- RAM site `$CA32` (`STA $DE00` before `JSR $B75F`) was never patched: its search context included runtime table bytes. The game ran the wrong bank (title objects never cleared, sprites over the story text). `patches.py` now retries with a shorter context.
- 33 raster waits the attract audit never reached are patched by pattern (`raster_waits()`), plus a `BIT $D011` hook.
- `convert_shape` had leftover debug stores into `sv_skey`/`sv_s0`: wrong multicolour shared colours and endless shape reconversion.

**Renderer design now:**
- Display buffers D0/D1 keep BG; per compose only changed BG cells (CD0/CD1 bitmaps) and changed sprite bands are copied/erased/drawn. Block lists, old-piece lists (8-byte rects) and band caches all live in VRAM bank 1.
- Two XDLs; the VBI NMI flips once the blitter is idle (never mid-picture).
- The renderer is a coroutine on its own stack (`$0100-$019F`) in the main loop's wait (`$40CD` -> `hook_idle`); it yields (`ryield`) when the line-250 flag gives the main loop work, after a minimum slice of ~36 lines. Raster IRQs interrupting it go through `tramp` (bank + zero page restored).
- Row shifts are detected for any contiguous run of rows at any Y-scroll; the picture is held while the game is half way through a shift (chars, or colours, moved in parts), as the C64 never shows that state.
- Start-up: overlay off and border black until the title screen is complete (full compare with < 100 redraws, >= 48 distinct characters, title charset for 30 frames); the "Brought to you by Goldfinger" credit screen of the cart is never shown.

**Rates (per 60 frames, LOOPCOUNT build, `tools/rates.py`):** title 3-5 composes, main loop ~50-55 of 60; story 25-48 composes, 50-58 passes; item pages 10-17 composes, ~50 passes. The title is CPU-bound on the C64 (~6% idle), so its display rate is limited by the CPU left over.

**Tools:** `check_d.py` (DCHK: composed buffer vs BG, exact), `pairseq.py` (screenshot + RAM render pairs), `rates.py`, `cat_prof.py`/`rprof.py` (cycle-sampled profiles via `CYCLES`), `snap3.py`, `shotseq.py`, `stuck_check.py`.

**Next:** title/item display rate: per-compose cost (sprite derive ~20K cycles, zero-page swaps on interrupted IRQs), hook overhead (~25% of the title's CPU).

### Session 4b (2026-11-01): sound, display-list raster, static title sprites - Measured in AltirraSDL + VBXE
- **Sound** (`atari/src/sound.s`, cart bank 12, called from the VBI): the SID shadow (SSH, `$F040`) becomes POKEY sound every frame. SID voice 3 -> channels 1+2 joined (16 bit, 1.79 MHz; exact pitch), voices 1/2 -> channels 3/4 (8 bit, 64 kHz; ~0.7% pitch error, notes below 125 Hz an octave up). Software ADSR from the SID AD/SR registers (linear), pulse/tri/saw -> pure tone, noise -> 17-bit noise, master volume. Dividers by 24-bit division, only when a frequency changes (at most 2 per frame). Verified: POKEY dividers/volumes against the SID shadow (`AUDCTL=$50`). Every `$D500` write records `mapped` first so the VBI can map bank 12 and back.
- **Raster events from ANTIC DLIs** (POKEY is no longer a timer): C64 line 8 = the VBI (Atari 248), C64 50-262 = Atari 28-240; display list `DLB` at `$DE10`, one blank line per entry from Atari line 28 (`$D012` reads = from VCOUNT). A DLI that interrupts code with IRQs disabled retries 6 lines on; targets 0-5 lines ahead or up to 20 lines passed fire as soon as possible (ANTIC reads entries ahead). The display list must end before line 248: a JVB there made ANTIC skip every other frame.
- **Title**: sprite bands frozen after 60 title frames in a row (4+ bands), counted at each line-250 event; while frozen only the enable bits follow (same band layout only). Static waterfall and logo sprites, no flicker; title 5-11 composes/s.
- Start-up stays black until the title screen is complete (charset loaded, full compare with < 100 redraws, >= 48 distinct characters).
- **Title -> story**: black from the moment the title's fade starts (its `$D022/$D023` differ from the frozen title's) until the story screen begins (title layout gone, sprites off, the title's sprite bands out of `RBANDS`, colours set); no compose while black (`r_blank = 5`), first row shift or ~15 s also end it (`bl_end`). The end-of-items sign no longer freezes (freeze only for the title's band layout), and scene changes flush the sprite shape cache.

### Session 5 (2026-11-02): input, select/name screens, saves in RAM, game start - Measured in AltirraSDL + VBXE
**Verified:** title -> START -> `- S E L E C T -` -> START -> "REGISTER YOUR NAME" -> joystick + fire enters `LUNA` -> SELECT x3 -> START -> select screen lists LUNA (3 hearts) -> START -> overworld; Link walks. Attract (no input) unchanged. Script: `tools/play.py` (see below).
- **Input** (`atari/src/input.s`, bank 12, from the VBI): the game reads CIA1 only in 5 places, each after a constant column select, so they are patched to `LDA` of per-column images (`J_JOY`, `KC_FE/7F/FD/BF` at `$DC04-$DC08`; `patches.py INPUT_READS`). Joystick 0 = joy 2; START = F7, SELECT = F5, OPTION = F8 (also SHIFT+START), SPACE = B button, keys 1/3/5/7/8 = F1/F3/F5/F7/F8.
- **Saves**: the game saves through EasyFlash EAPI into EF bank 16 (`ZSAV\x01` header at `$8000`, data from RAM `$6001`). EF banks >= 8 now map to cart-off ($D500 = $80), so Atari RAM `$8000-$BFFF` is the "flash" (erased to $FF at boot). The EAPI driver the game copies from bank 0 `$B800` to `$1000` is replaced by `atari/src/eapi.s` (init, WriteFlash, EraseSector, SetBank, GetBank; the rest return C=1). **Not persistent**: lost at power-off. Next: write `$8000-$85FF` back to a save ATR (needs SIO with the OS off).
- **Missed patches** were the crash/hang causes: 10 `STA $DE00` save/load sites (`patches.py BANK_WRITES`), and sound-effect SID writes (`STA $D402/$D403` landed in ANTIC DLISTL/H: the display list moved into the cart window and raster events stopped). `tools/host/audit.py` drives the host model through an input script and merges every new hardware site into `work/an/audit.pkl`; RAM sites also record their code bytes (`work/an/audit_ctx.pkl`), since gameplay code is loaded into RAM after the attract snapshot (patching by attract RAM context would have matched zeros). Regenerate (after restoring the attract-only audit): `python3 tools/host/audit.py --merge "$(cat work/an/reg_luna.txt) s left*40 up*120 w60 fire*4 w30 SPACE w30 down*60 right*200 w30 up*200 w30 right*200 w30 down*300 w30 left*400 w30 fire w10 fire w10 F1 w30 F1 w30 F3 w30 F3 w30 F5 w60 F5 w60 F8 w90 F8 w90"`. Only the first overworld screens, the sword cave and the F8 menu are covered: **other game phases will still have unpatched SID/VIC writes** (symptom: hang, PC stuck in `nmi`, ANTIC DLIST not `$DE10`). Audit more phases as they are reached.
- `STX $D012` (RAM `$C55A`) -> `hook_d012x`.
- **Title freeze** now needs game mode `$14 = 0` (`frz_lay`): the select/name screens use the title's raster layout and showed the frozen waterfall sprites.
- **Behind-characters sprites** (name/letter cursors, `$D01B`): the VBXE blitter tests transparency after AND/XOR, so the old single "BG over" block (XOR 1) was opaque and hid them. Now three blocks through scratch VRAM `OVT` (`tpl_ova/b/c`): BG xor 1, then 1 where BG is even (bg0 / multicolour 01), then copy with AND $FE, 0 transparent. Debug switch `ZDEFS=NO_BEHIND`.
- Tools: `tools/play.py PREFIX "w600 start w150 s right6 fire6 key:NAME ..."` (screenshots under input), `tools/start_test.py [-p] T...` (START at frame T, reports select mode; `-p` profiles a hang), `tools/hangprof.py`. Bridge: `JOY 0 <dir> [fire]`, `CONSOL start|select|option`, bare `CONSOL` releases.
- Open: save persistence (ATR); audits of later game phases; sound timing/quality not checked in these screens.

### Session 6 (2026-11-03): overworld background flicker - Measured in AltirraSDL + VBXE
**Cause:** the overworld splits its colours with raster IRQs: the line-8 handler sets `$D022/$D023` = 9/1 for the HUD (at C64 line ~14), the line-72 handler 6/7 for the playfield (line 74). The renderer set the palette once per frame from one VIC snapshot, so the ground (bg2) flashed white whenever the snapshot held the HUD values.
**Fix (`atari/src/colour.s`):**
- Every `STA/STX/STY $D021-$D023` (patches.py -> `hook_c2Nr`) stores the shadow and writes the VBXE palette entry at once (BG/display buffers hold palette indices, so composed pictures need no change). `palette_update` now only sets the border (entry 8) and the sprite shared colours, IRQs off, and skips while `hc_busy`.
- Handlers run ~10 lines after their DLI (and are sometimes deferred), so a live write lands low. Each write is also recorded in a 4-entry split table (event line, register, value, Atari line = event - 21). Each live entry has its own DLI bit, set at every VBI (`hc_vbi`); the NMI first applies the splits on its line (`hc_rep`) and only then looks for a raster event (C=1: colour-only DLI, return). A known split with an unchanged value is not written live (a late handler would undo a later split). Entries live `HF_LIFE` = 8 frames without a write (raster events sometimes slip a frame). Line-8 (VBI) writes are recorded too (replay at Atari line 11): a deferred line-8 handler made the minimap dot flip.
- Display list now: `$10` (lines 8-9) then one entry per line from Atari line 10 (`DL_LAST` = 236); C64 lines 9-31 fire at Atari 10 (was 28).
- Tried and rejected: firing all raster events 8 lines early (`EV_LEAD`, kept at 0): the game stalled at its start (mode 2) every time.
- New resident RAM: `RES6` $DD10-$DDFF (unused CIA2 mirror range), `RES7` $DF00-$DF7F (EF I/O-2 RAM; EAPI table at $DF80), `RES8` $FF88-$FFF9 (under the KERNAL). All nearly full. `SR0/SR1` and `rv` in atari.inc are unused leftovers (SR1 overlaps RES3 on paper only).
**Measured:** Link standing, 120 frames: 4 frames differ (2 pairs, 2 lines at the HUD/playfield boundary, ~once per 2 s), before: 40,000+ pixel flashes every few frames. Walking 120 frames: 1 frame with a strip. Remaining cause (likely): a replay DLI landing while another palette write holds `hc_busy` is skipped.
**Found, not fixed (pre-existing, same in the e73117a build):** walking off the first screen (east) hangs in mode 7 (screen scroll): raster chain dead (`dl_idx` 0, `ev_vbi` 0, no DLI armed, `$C100` vector = `$1F8D`, gameplay code in RAM). The ground shows white there because the HUD colours stay set. Fixed in session 7.
- Tools: `tools/to_game.py` (`boot_game()`: register LUNA, start, retries if the scripted entry slips into another mode; `CART=` env), `flicker_game.py N` (changed pixels per frame, Link still), `walk_white.py N`, `stall_test.py N`, `edge_test.py`.

### Session 7 (2026-11-03): screen-to-screen scrolling - Measured in AltirraSDL + VBXE
**Hang (mode 7) cause:** the overworld scroll's raster handlers are RAM code loaded for the scroll and were never audited: `$1F8D` (horizontal) / `$41E3` (vertical) at C64 line ~72 and `$1FD2`/`$420F` at line 250 write `$D012`, `$D016`, `$D018`, `$D011` unpatched, and `$1FB2` busy-waits with `CPX $D012` (would never end). Host audit of walks off the first screen in all directions + a death/continue screen: 64 new sites merged (`work/an/walk1.txt`, `walk2.txt`; the session-5 audit is kept as `audit_s5.pkl`). `CPX $D012` -> `hook_d012cx` (RES7). Moving between screens works: east, west, north, south, and the cave in/out.
**How the C64 scrolls (host model):** the playfield (text rows 3-24) is double-buffered: the line-72 handler points `$D018` at screen `$0800` or `$2000` (`$0DFA`), the HUD stays on `$0800`. Every flip moves the playfield exactly one step: one row (vertical, Y-scroll stays 3) or one column (horizontal, playfield columns 4-35 only; plus a 4-pixel fine X-scroll `$0DFD` 0/4 every other frame). `$0DF7` = direction Link walks (0 down, 1 up, 2 left, 3 right). Colour RAM (single) is rewritten in two halves, complete one frame after the flip. C64: mode 7 lasts ~64 frames (vertical, 22 steps) / ~83 (horizontal, 32 steps), CPU ~90% busy.
**Renderer (`atari/src/scroll.s`, RAM `$DFA0-$DFFF` = RES9; `render.s` pf_*):**
- Every `STA $D018` -> `hook_d018`: a write for a raster event at C64 lines 60-199 is the playfield's base (`pf_d018`, valid 3 frames without a write: `pf_vbi` from `hc_vbi`), other writes the HUD's (`pf_top`; VSH+$18 holds the playfield value from line 72 to 250, so a snapshot cannot tell). A changed base while the split is on = one step (`pf_steps`).
- `pf_snap` (each render): `psn`/`ptop` bases, `psr` = first playfield row (3); `rbase` gives each row's screen base (row_ptrs, sh_ptrs). The full compare (screen at `$0800`) forces the playfield rows when their base differs; the periodic every-4th-render full compare is off while split.
- `pf_shift`: the steps not yet applied are done as blits of BG, screen shadow and colour shadow (vertical: whole width, bottom-up with negative step for downward moves; horizontal: columns 4-35, right-to-left for rightward moves), then the incoming rows/columns are scanned at once and the playfield rows made hot. The old `shift_check` is skipped while split.
- Renders are long and rare during scrolls (the game leaves no idle time): after every `ryield` `pf_check` takes a new flip at once (the main loop rewrites the old buffer only while the renderer yields). Colour-only differences are not drawn for 2 frames after a step (`pf_cwait`: colour RAM still holds the old step; drawing it made half-bushes / hires-vs-multicolour flips).
**Measured:** all four directions scroll with a correct picture (HUD intact, no stale cells in full-size mid-scroll shots); route west-east-east-west completes 4 scrolls (`tools/walk_test.py`). Standing still 120 frames: 0 changed frames (was 4). Attract: the split never turns on. `stall_test` 3/3. Scroll duration: mode 7 ~90-96 frames vertical / ~108 horizontal against the C64's 64 / 83: the game is CPU-bound there; profile (`tools/scroll_prof.py up`): game 37-45%, hooks/IRQ emulation 25-33% (raster polling `virt_now`/`hook_d011r` ~9%), renderer ~26% (drawing incoming cells ~6%).
**Not done:** the 4-pixel horizontal half steps (fine X-scroll of the playfield: would need a second XDL segment from row 3 shifted by `$D016&7`, with playfield sprites compensated); scroll speed (see profile). `boot_game` registration still slips into Elimination Mode in ~1 of 4 runs with either build (timing of the scripted name entry): retries raised to 8.
- Tools: `tools/walk_test.py [-s PREFIX] "dir*N ..."` (mode changes + Link's position per step), `tools/scroll_shots.py DIR [N STEP]` (screenshot grid of a scroll), `tools/scroll_prof.py DIR [N STEP]` (cycle-sampled profile of a scroll, bank from `mapped`), `tools/host/audit.py --dump FILE`.

### Session 8 (2026-11-05): Link's death froze the game - Measured in AltirraSDL + VBXE
**Cause:** the VIC raises its raster IRQ every frame on the `$D012` line, even when the handler never writes `$D012` again. The port fired one event per `$D012` write, so a handler that leaves `$D012` alone stopped the raster chain. The overworld's line-250 handler `$420F` arms the scroll handler only while a scroll runs (`$0DF1|$0DF8 != 0`). Otherwise it just sets the main loop's flag `$C102` and relies on that repeat. This happens during the death animation (mode `$11`, set by bank 6 `$B06B`/RAM `$32F8` when health `$066F` low nibble and `$0670` run out). The main loop then waited for `$C102` forever: frozen picture, vector `$420F`, `$D012` = 250.
**Fix (`atari/src/vicirq.s`, cart bank 12, called by the VBI before the sound update):** if no event is pending (`dl_idx`, `ev_vbi`, entry-0 DLI bit) and the raster IRQ is enabled (`$D01A` shadow bit 0), the `$D012` shadow line is armed again for the coming frame. Skipped when the VBI interrupted `arm_dl` itself (its state is half written; an orphan DLI bit would fire every frame). No resident RAM used (those segments are full).
**Measured:** `tools/death_test.py` (health cut to a sliver, walk until an enemy kills Link): death animation (red screen) -> CONTINUE/SAVE/RETRY (mode 8) -> START -> back on the start screen (mode 5). Before: stuck in mode `$11`. Unchanged: `stuck_check 3000` ok, `stall_test 3` 3/3, `flicker_game 120` 0 changed frames, `walk_test` west-east-east-west 4 scrolls.

### Session 8b (2026-11-05): sprites during scrolls, renderer zero page - Measured in AltirraSDL + VBXE
- **Link on the wrong side during screen scrolls:** the scroll's raster chain skips line 8 (frames run 70 -> 250 -> 70), and a new frame's sprite band list only started at the line-8 event, so the list filled (5 bands) and stopped recording: the displayed sprites froze for the whole scroll (Link stayed at the edge he left by, then jumped). `hook_d012w` now starts a new band list at any event at or above the previous event's line (`r_evl`). Also `derive_band` read sprite X from `BANDS` (live) instead of `RBANDS`. Verified: Link moves across with the scroll (left scroll every 3 frames).
- **Renderer zero page moved from `$F0-$FF` (shared with the game, swapped at every yield/resume/interrupting IRQ: `zswap`, ~4% CPU) to `ZR` = `$D2-$E1`**: host model: those bytes never change through title, registration, walks/scrolls, cave, menus, death, and poisoning them every frame from power-on leaves the game's RAM identical (also free: `$8A-$99`; `$30-$3F` and `$F0-$FF` are used). Not covered: dungeons and later phases (`ZDEFS=ZPCHK` now checks the renderer's block across interrupting IRQs). Frees ~210 resident bytes (RES3 has ~$A0 free) and `$F0F0-$F0FF`.
- **Measured rates (r_hidden flips and main-loop passes per 60 frames; C64 host model: 60 passes):** standing 23-32 flips / 46-59 passes, walking ~25-30 flips; screen scroll 3-8 flips per 50 frames (the display jumps several rows/columns at once; vertical scroll: 21 display changes in 130 frames). Run-to-run variance is large (boot timing): compare builds over several runs.
- **Why scrolls are slow (profile, left scroll):** game 44%, renderer 27%, hooks 25% (raster polling `virt_now` 6% is the game's own wait). The game leaves no idle time, so renders are VBI fallbacks (every 4th VBI, IRQs off); each scroll step costs a BG shift blit (~45 KB) plus a full playfield copy BG -> display buffer, and the CPU spins in `vx_wait` for both (8% of all CPU). Plan: hardware scroll of the playfield through the XDL (narrow 256-pixel overlay for rows 3-24 = C64 columns 4-35, linear buffer with pitch 256 so a horizontal step is +-8 bytes of overlay address and the incoming column lands in the bytes that just left the screen; a vertical step is +-8 lines; rebase after the scroll), so a step costs no big blits and the 4-pixel half steps come for free.
- Remaining one-frame artefact: at the end of a vertical scroll the top playfield row can show the new characters with the old colours for one frame.

### Session 8c (2026-11-05): freeze when Link is hit (with the sword) - Measured in AltirraSDL + VBXE
- **Cause:** hardware sites no audit reached. The sound engine's voice-3 effect dispatcher (bank 0 `$9640+`) restarts the voice through `$96A0` when a new effect has a lower number than the running one (`$7E51`): with the sword, a swing's effect is still in `$7E51` when the hit's effect starts, and `$96AC STA $D412` (SID voice 3 control, `$81` = noise + gate) went to the Atari's `$D412` = ANTIC DLISTL (mirrored every 16 bytes): the display list moved, raster events stopped, the game froze and POKEY held its last note. Without the sword the dispatcher takes the equal-number branch, so hits never froze.
- **Fix:** `tools/hw_scan.py` (static scan of the patched banks for VIC/SID/CIA1 accesses in plausible code; run by `build_atari.py`, warns) found 23 unpatched real sites: 16 SID writes in bank 0 (sound effects), `$D030` probe write/read, `$D011` writes (bank 5 `$BAD8`/`$BC16`, bank 7 `$88B3`), `STA $D012` (bank 7 `$A3BF`), `STA $D022` (bank 7 `$AA27`), `$D015` read/write (bank 7 `$AE9D`/`$AEA2`). They are patched from `patches.py STATIC_SITES` (original bytes asserted). 306 -> 329 patches.
- **Measured** (`tools/sword_fight_test.py [CART] [ROUNDS]`: fetch the sword, go one screen east, wander and fight; `SWING=` swing probability; `PRIME=1` skips the cave and holds `$7E51` at `$0F` instead): previous build froze (primed: after 5 hits, ANTIC DLIST `$DEED`; real sword, `SWING=0.15`: after 3 hits, CPU lost in zero page, IRQ storm); fixed build: real sword 24 hits in 60 rounds, no freeze.
- **`$D012` written again with the line already pending is now a no-op** (`hook_d012w`): the overworld split handler (bank 7 `$A370+`) arms line `$48` with `STX $D012` and, when it runs late, writes `$48` again (`$A3BF`, newly patched). The second write used to record a sprite band and a colour-split event at a line not yet reached (boundary strip flicker: 10 of 120 still frames). The C64's compare is unchanged by such a write. A handler re-arming its own (already fired) line still goes through the normal path. Flicker check (`flicker_game 120`, several runs): 0-5 changed frames, as before these patches (0-2): the known HUD/playfield boundary strip of session 6.
- `STATIC_SKIP="A3BF ..."` (env, build time) leaves static sites unpatched, to bisect.
- Open: one attract `stuck_check 3000` run of 11 on this build reported "IRQs stopped at 1629" (not reproduced in 10 further runs; 0 of 6 on the previous build). Watch for it.

### Session 8d (2026-11-05): sword beam / Link sprites wrong or missing - Measured in AltirraSDL + VBXE
- **Cause:** the overworld composes its sprite images in RAM buffers that keep their pointers: `$0E00-$0FFF` (pointers `$38-$3F`) and `$2040-$23FF` (`$81-$8F`, which is also the second screen buffer during scrolls). Host trace of the writes: RAM `$CD5F`/`$CD78` (self-modifying copy loops), bank 1 `$BDBE`, plus scroll-time screen loops. The shape cache is keyed by pointer and re-checked only every 32 frames, with an additive checksum (a vertically flipped image has the same sum), so after Link turned, swung or the beam took a buffer the old image stayed: Link facing the wrong way, vanishing, the beam drawn as Link.
- **Fix (`render.s verify_used`, replaces `verify_slot` and the 32-frame recheck):** once per render, every pointer of an enabled sprite in the published bands is compared exactly with a copy of its 63 bytes in VRAM (`PCOPY` = `$4000-$7FFF`, 64 bytes per pointer, byte 63 = render stamp `vu_gen`, so each pointer is checked once per render); a difference updates the copy, drops every cache slot with that pointer and bumps `r_gen`. Cost: one 63-byte compare per distinct pointer in use per render (~1000 cycles).
- `$0657` = 1 once the sword is picked up (host diff at the pickup). `tools/sword_fight_test.py` now sets it by default (`CAVE=1`: the real cave route) and steers by Link's object position (`$72`/`$86` = sprite coordinates - (56, 13)): sprite 0 is not always Link (the VIC shadow can hold the HUD band's sprites).
- Fixed: `tools/hw_scan.py` treated `(zp,X)`/`(zp),Y` as 3-byte instructions (the opcode table names them `indx`/`indy`); still 0 unpatched sites.
- Verified: turn-and-shoot strip (4 directions x 3, every frame): previous build loses Link for whole stretches and mixes images; fixed build shows him every frame with the sword the right way. stuck_check 2/2, flicker 0/0, walk 4 scrolls, stall 2/2, sword fight PASS.

### Session 8e (2026-11-05): smooth screen scrolls (XDL lag shift + edge fill) - Measured in AltirraSDL + VBXE
- **Why scrolls were jerky:** the game leaves no idle time while the overworld scrolls, so a render (BG shift per step, then a compose) takes ~10 frames; the display flipped every ~11 frames and jumped several steps. LOOPCOUNT timeline (it fits again): steps every ~3 frames, shifts follow within 1-2 frames, composes ~1 per 10 frames.
- **Now:** the displayed picture is shifted in hardware by the steps the game is ahead of it, every frame:
  - `render.s xdl_vars` (at each compose while the playfield split is on): 16 XDL variants of the hidden buffer at `XV` = `$3000` + buffer*`$400` + v*64: blank lines, the HUD (24 lines, unmoved), the playfield (176 lines). Left/right: narrow overlay (256 px = C64 columns 4-35), source 8*(v>>1) px further, 4 px back for odd v (the C64's fine X-scroll `$0DFD`, not shown before). Up: source 8k lines lower. Down: 8k lines from `STRIP` (`$8000` + buffer*`$3200`, 40 lines x 320) then the picture.
  - `edge_fill` (after every BG shift): copies the incoming rows/columns of the steps since the shown buffer's compose from BG into that buffer's edge, where the shifted view shows them (step S+j: column 4-j / 35+j in the border columns and margin, row 24+j in the margin below, or strip line (5-j)*8); only steps not drawn yet. `xv_f` = steps drawn. Most steps ahead: up 6, down 5, left/right 7 (margins).
  - `edge_refresh` (from `pf_check`, once per step, 2 frames after it): rescans the two newest incoming rows/columns (colour RAM follows the step a frame later) and copies them again.
  - `vicirq.s xv_pick` (VBI): VB_XDL = the shown buffer's variant for k = `xv_f - xv_s` (and the fine X-scroll for left/right). No VRAM access from the VBI.
- **Measured** (130 frames from the scroll start, display changes / longest freeze): committed build left 16/14, right 2, up 18/21, down 13/40; now left 77/7, right 65/21, up 27/20, down 37/24 (the long gaps include the frames before the C64 itself starts moving). Regression: stuck_check 2/2, walk 4 scrolls, flicker 4/2 (noise 0-5 before), stall 2/2, sword fight PASS, death -> continue PASS.
- **Not done:** vertical scrolls still lag when composes are very slow (the margin/strip allow 5-6 steps ahead; beyond that the picture waits for the next compose). Composes during scrolls are slow because each step's BG shift (3 blits, ~56 KB) is waited for by the CPU inside the renderer's short slices (`vx_wait`, `pf_do`), and after a step every playfield row is made hot. Next: start the big BG blit without waiting (shadows first), and drop the all-rows-hot marking while the edge is filled; then the per-frame cost of normal play (scan, atlas check, band derivation).

### Session 8f (2026-11-05): scroll pauses, normal-play rate - Measured in AltirraSDL + VBXE
- **Scroll steps cheaper:** `pf_do` shifts the screen/colour shadows first and starts the big BG shift without waiting (the incoming-cell scan runs meanwhile; `flush_cells` waits). After a step every playfield row is rescanned once (was 8 times; the incoming cells' colours: `edge_refresh`). Up/down longest pause 20/24 -> 19/15 frames (130 frames from the scroll start; left 78, right 75, up 36, down 28 display changes).
- **Full compare adaptive:** every 4th render while the last one found changed rows, every 16th while the screen is still (`r_fq`). Banks 10/11: 11% -> 3% of the CPU while walking. The generated compare now yields (`JSR ryield`) at rows 5/10/15/20 (`build_atari.py gen_compare`; one half was ~100 scanlines without a yield).
- **`distinct()` ran in the game:** the title-fade check (`r_ttl` stays set after the title) counted the characters of the whole screen at every full compare (4%). Now title/attract mode (`$14 = 0`) only.
- `atlas_check` checksum loop faster (same 16-bit sum); `verify_used` yields between bands.
- **Measured** (`tools/perf_walk.py [CART]`: 380 frames walking about the first screen + 120 standing; passes = the game's `$17`, the C64 does 60): before this session's work walking 47-56 passes / 20-27 flips, standing 43-53 / 22-32; now walking 50-54 / 33-35, standing 52-54 / 37-38. No VBI fallback renders in normal play (LOOPCOUNT: all renders idle). Regression: stuck_check 2/2, walk 4 scrolls, flicker 4/4 (noise 0-5), stall 2/2, sword fight PASS, death PASS.
- **Not done / next:** the game still misses ~6 passes per second while walking although the renderer only runs in its idle time: tried yielding at once outside the title (no measurable change, reverted), so the misses are frames where the game's own work plus the interrupt overhead runs past a frame. Resident hooks ~26% of the CPU: band snapshot in `hook_d012w` (~5%), colour-split DLIs `hc_rep` (~4%), band publish `cb_copy` (~3%). Profile a missed pass frame by frame next. `vu_check` (exact sprite shape compare) ~4%, `build_bands` ~7% (42-byte band compares against the VRAM band caches).

### Session 9 (2026-11-05): renderer zero page was the game's; faster sprite conversion; no border band - Measured
- **Wrong assumption fixed:** `$D2-$E1` (renderer zero page since session 8b) is game object data once enemies are about: `tools/host/explore.py` (random exploration in the host model, every zero-page write trapped) found writers at RAM `$4D9B`, `$4DE3`, `$2910`, `$35BF`, `$3616`, `$5043`, bank 5 `$8920`. The scripted audits never had enough objects. Game and renderer were corrupting each other (it also crashed a yield inside `convert_shape`, and is the likely cause of the rare attract stall at frame 1629 and odd enemy behaviour). No 16-byte block is free: 4 explorations x 25000 frames leave only scattered never-written bytes, and the poison test (randomise every frame, compare RAM hashes) rejects `$36-$3D`, `$BD-$C0`, `$F6/$F7`. The renderer's zero page is now `$81/82 $83/84 $95/96 $97/98 $A9/AA` (pointers: zscr zcol zshs zshc, zcnt/zb) and `$AB $AC $D2 $D3 $5F $60` (scalars), all never written and poison-safe. `ZPCHK` removed (explore.py does it better).
- `tools/host/explore.py SEED FRAMES [--poison A,B,..] [--hashes F] [--zpout F]`: also reports modes/screens reached, new hardware sites vs the audit, crashes, and game writes to `$E000-$FFFF` (the port's resident RAM). Run it after any change of the port's RAM use.
- **Missed game passes, what they were:** `tools/frame_trace.py` (60 PC samples per frame, frames with/without a main-loop pass, timelines): long renderer stretches without a yield while the game's line-250 flag waits: `convert_shape` (~17000 cycles per sprite shape; frequent now that rewritten shapes are converted), the full compare halves, `atlas_check`.
  - `convert_shape`: multicolour via two 16-entry nibble tables built per conversion (`cv_m0/cv_m1` at `$F6A0`), a fast path for empty hires bytes, a yield per row.
  - Bands from line 250 on are not snapshot (the lower border: never shown); a third less band snapshot/publish/derive work.
- **Measured** (`perf_walk`): walking 53-54 passes / 38-39 flips per 60 frames, standing 52-55 / 39-40 (session start: 47-56 / 20-27). Regression: walk 4 scrolls x4, stuck_check 3/3, flicker 4/0, stall 2/2, sword fight PASS, death PASS, scrolls left 85 / right 79 / up 27 / down 22 display changes.
- `explore.py` now checks the renderer's 16 zero-page bytes (RZP list = atari.inc), heads for unvisited screens (`$ED` = screen index, row*16 + column; start `$78`), tops Link's health up every frame and no longer presses F8 (its menu's CONTINUE restarts at the start screen). Seeds 6-9, 40000-80000 frames each (fights, deaths/continues, caves, up to 12 screens): no writes to the renderer's zero page, no game writes to `$E000-$FFFF`, no crash, no hardware site outside the audit + `STATIC_SITES`. Random wandering gets stuck on obstacles (4-12 screens): dungeons are not reached yet; a route (or a passability-aware explorer) is needed for them.

### Session 9b (2026-11-05): colour-split DLIs from a queue - Measured
- ~10 DLIs per frame in the overworld (temporary counters): ~2.5 raster events, ~3 deferral retries (the event's DLI arrives with IRQs masked: re-armed 6 lines on), 4-5 colour-split lines. Each ran `hc_rep`'s search of the 4 split entries (~130 cycles): `hc_rep` was the largest hook (~6-7% of the CPU, `frame_trace`).
- Now `vicirq.s hq_build` (VBI, bank 12) queues the live splits sorted by DLI line with palette index and colour (`hq_line/hq_pal/hq_col`, `$F8F0-$F8FE`, free bytes after RBANDS); `hc_rep` only applies the queue entries of its line. A split written during a frame is replayed from the next VBI on (its live write sets it at once, as before).
- Measured: walking 56.2-56.5 passes / 38-39 flips per 60 frames (53-54 before), standing 55-55.5 / 41.5-42.5; `flicker_game` 0/0 (4 before). Regression: stuck_check 2/2, walk 4 scrolls x2, stall 58/58, sword fight PASS, death PASS, scrolls left 77 / right 79 / up 25 / down 23 display changes (longest gaps 10/8/16/13).
- Next for full speed: the deferral retries (3 DLIs per frame), `hook_d012w`'s band snapshot and `cb_copy` (~2.5% each).
- **Lost frames = lost line-250 events:** game passes equal the line-250 events exactly (temporary counter: 51-59 per 60 frames), so the misses were the raster chain slipping, not game work. A temporary event ring (hook_d012w writes + DLI/VBI dispatches) showed the line-250 event (Atari line 228) deferred 6 lines at a time past the display list end, then dispatched at the next frame's first line, so its handler's line-8 arm waited a whole frame. A deferral log (interrupted PC) found the cause: the event's DLI arrived inside a colour-split DLI's `hc_rep` (a line or two earlier) and every NMI masks IRQs, so it looked "masked" (545 of ~700 deferrals). Now `nmi` (resident) sets `ev_due` instead and dispatches it when the outer `hc_rep` returns; `vicirq.s` turns a still-due event into the VBI event. Remaining deferrals: inside the game's IRQ path (`irq`, `hook_d012w`: real), nested in the rest of `nmi` (~50), `cb_copy`/`snap_vsh` with IRQs off.
- Measured (`perf_walk`, 5 runs): walking 54-59 passes per 60 frames (~57; 56 before), standing 53.5-60 (~58; 55 before). Regression: stuck_check 2/2, walk x2, flicker 2/0, stall 58/58, sword fight PASS, death PASS, scrolls 73/73/24/20.

### Session 9c (2026-11-05): first dungeon reached; an indexed VIC store patched - Measured
- **Route to the LEVEL-3 dungeon** (from the user's Altirra save state `zeldadungeon.atstate2`, read only: its RAM gave screen `$ED = $74`, Link at (128, 141); the state itself only loads with the exact cart it was made with, CRC in its `savestate.json`): start screen `$77`, west to `$76`, Link's object (`$72/$86`) placed at (24, 117) and walked left to `$75`, at (24, 45) and left to `$74`, at (128, 141) and up (modes `$10, 2, 3, 4, 5`, dungeon screen `$7C`). The rows were found in the host model by trying each one (snapshot/restore of the model state). `tools/host/make_dungeon_state.py` writes `work/an/states/dungeon3_entry.pkl`; `explore.py --state FILE` explores from it; `tools/dungeon_test.py [CART] [ROUNDS]` drives the port in and fights.
- **Host exploration in the dungeon** (3 seeds x 40000 frames, 2-8 rooms): no writes to the renderer's zero page, none to `$E000-$FFFF`, no crash. New sites: RAM `$4414` = bank 7 `$83FC` `STA $CFFE,X`, a raster-timed write (line `$58`) whose target X comes from a table: X >= 2 = a VIC register (`$D000` seen). `hw_scan` could not see it (base below `$D000`). Now `JSR hook_cffe` (resident RES3: shadow, `$D012`/`$D018`/`$D021-$D023` through their hooks; `patches.py SPECIAL_SITES`), and `hw_scan` also flags indexed stores whose base + X/Y can reach the hardware (the other 9 are RAM arrays at `$CFE2-$CFEA`/`$CFFD` with small indexes: `KNOWN_OK`). 330 patches.
- **Port in the dungeon:** `dungeon_test.py` 100 rounds in room `$7C` (bats, sword): no freeze, room and sprites drawn right (`build/_dg*.png`).
- Full speed (session 9b): game passes 56-58 of 60; the remaining losses are the line-250 event delayed past the VBI by IRQ-masked stretches (`render_snap`/`cb_copy`, the game's own IRQ path) 2-4 times a second. Next: a late line-8 arm should fire at once (the C64 handler would have been done), and shorten the masked band copies.

### Session 10 (2026-11-06): full speed (60/60), colour-split glitches - Measured
- **Raster events kept in order on the C64 clock** (`resident.s arm_ev`, RES3, from `hook_d012w`): a handler that runs late (its event deferred while IRQs were masked) and arms a line the C64 raster would already have reached since its event (d = C64 lines since the served event's line, `virt_now` - `r_ev`, mod 262; dt = lines to the target, the next frame's if not below it) gets it as soon as possible (`arm_now`), not a frame later. This covers the line-250 handler deferred to the VBI arming line 8, and a line-72 event pushed down the screen arming 250 after line 228.
- **Deferral retries 6 lines from now, not from the event's own entry** (`nmi @defer`, `nmi_vbi @vdef` -> `arm_now`, an entry point of `arm_dl` so the VBI's "interrupted arm_dl" check still covers it): a deferral DLI that ran a few lines late set an entry ANTIC had passed, and the event slipped a whole frame; the VBI's fallback (`DLB[0]`) was set after the sound update, which can run past line 8.
- **A stale `ev_due`**: a nested event DLI's `ev_due` stayed set when the outer DLI was on the event's line too, and the next colour DLI fired the pending line-250 event at Atari line 90. Now cleared at every dispatch (`nmi @ev`).
- **Measured** (`perf_walk`, 3+ runs): walking 60.0 passes / 35-36 flips per 60 frames, standing 60.0 / 39-40 (session start 54.8-58.4 / 37-39). Debug method: `ZDEFS=T250` build (no `hook_cffe`, its RES3 room holds a ring of dispatched events at `$F6C0-$F6FF`, index `$F69D`), polled every frame.
- **Colour splits filed under the wrong event** (one-frame white band or whole white playfield, `flicker_game` 1-14 changed frames per 300 standing still, before and after the above):
  - a late line-8 handler does not return to wait for line 72: the C64 code sees the raster past it and runs the line-72 code in the same IRQ (no dispatch), so its playfield colours (`$D022/$D023` = 6/7) were filed under line 8 (replayed at Atari line 11: the HUD white). `hook_d012w` now sets `hc_ev` = the event served (`r_ev`; the line-72 code writes `$D012` before its colours, the line-8 code after); `irq` sets it at every dispatch; `hc_rep` no longer sets it (it also caught events then deferred, while the running handler was still writing).
  - `hc_rep` skipped queue entries whose line had passed (a DLI that read VCOUNT a line late): it now applies them late; a late handler that finds the value known does not write it live, so a skipped entry left the HUD colour for the frame.
  - `flicker_game 300`: 0 changed frames.
- `tools/scroll_rate.py [CART] [DIRS]`: per direction (down: from the screen north of the start) frames whose picture changed in 130, longest pause, scroll length (C64: ~64 vertical / ~83 horizontal), passes per 60 during the scroll.

### Session 10b (2026-11-06): picture rate - Measured
- Where a render's time goes (`r_fin` = 1 from compose's `verify_used` to the picture's flip request; timeline build `ZDEFS=RTL`: ring of render start / compose / draw / ready with frame and VCOUNT at `$F6C0/$F6D5/$F6EA`): the game's pass ends ~VCOUNT 46, the scan of the next render then 10-30 VCOUNT, compose to `verify_used` ~8, the drawing part ~36 (band caches, then erase/draw/save); the window up to line 228 is ~68 VCOUNT, so a render fits a frame only when its scan is short. In the drawing part: `build_bands` 18%, `derive_band` 11% (each band record holds all 8 sprites' positions: any sprite move re-derives both bands), `convert_shape` 6% (rare but ~10000 cycles).
- Changes:
  - `shift_check` every 4th render in game mode 5 (normal play: the overworld scrolls through the playfield split, rows are not shifted; its quick 12-cell test was ~6% of the CPU).
  - `build_bands`: the 42-byte record compare/copy with one index through `zscr`, unrolled (~14 cycles a byte, was ~20).
  - Sprite shape cache keyed by content: `vu_check` keeps a Fletcher-16 of each pointer's 63 bytes (`PSUM`, VRAM `$3A000`, updated only when the data changes) and no longer drops the pointer's slots; `sp_match` also compares the slot's sum with it. The game rewrites Link's frames under one pointer.
  - `render_snap` no longer copies the bands again when the line-250 event has published them (`cb_pend` = 0).
  - Tried and dropped: from `verify_used` on, not yielding until line 240 (`r_fin`, now only a profiling marker): no gain, and the game's pass starting later brought back the one-frame playfield-top colour band (`flicker_game` 6 of 300).
  - Resident debug counters under `LOOPRES` (with them `LOOPCOUNT` builds overflowed RES2); render counters stay `LOOPCOUNT` (`$F6F7`: shape data rewritten under its pointer).
- Measured (`perf_walk`): walking 39.9-40.3 flips per 60 frames (35-36 before), standing 43-44 (39-40); passes 60. Tried without gain: full compare always every 16th render.
- **Two more one-frame colour bands at the playfield top** (white over the playfield colour for its first ~16 lines; they came and went with timing: the skipped band copy above made them visible, 1-2 per 300 frames):
  - a DLI that comes while a colour hook is mid-write (`hc_busy`) leaves the palette alone, so its queued splits waited for the next DLI, and the hook does not write a value the table already knows: now `hc` applies the due queue entries itself when its write is done (`colour.s hc_rq`, the queue part of `hc_rep`);
  - splits filed under C64 lines 250+ (the lower border; a late line-250 handler running the line-8 code) are not recorded any more: in the full 4-entry table they evicted the line-72 one. (`rgb_b` moved to RES3 for the room.)
  - `flicker_game 300` x3: 0 changed frames.
- Not done: per-sprite (not per-band) derivation reuse; band derivations alternating between two states standing still (a 2-version band cache); the resident hooks (~20% of the CPU: band snapshot, band publish, colour DLIs).

### Session 10c (2026-11-06): up/down scroll pauses - Measured
- **Why vertical scrolls paused** (frame traces of `pf_steps`/`pf_done`/`xv_s`/`xv_f` per frame, and the `RTL` timeline: start, scanned, FULL/fulldone, hotdone, flush, compose, draw, ready): a render took ~26 frames during a down scroll, its scan phase 22 of them: `scan_chunk`'s Y-scroll-7 full compare (meant for the title's scroller) ran during the overworld scroll too, since the snapshot catches the playfield's Y-scroll 7 or the HUD's 3 and `r_ys7` kept restarting it; with the split on it rescans all 22 playfield rows (they come from the other screen buffer), ~17 frames of the little CPU a scroll leaves the renderer (~30%). No compose for 30-40 frames: the picture reached the most steps its margin/strip allow (6 up, 5 down) and stood still.
- Changes (render.s): no full compares at all while the split is on (the steps shift BG and its shadows; hot rows and the edge rescans catch the rest); steps are taken (`pf_check`) while compose waits for the last picture's flip (`@fw`) and at the per-band yields of `verify_used` and `build_bands` (before compose chooses its BG copy: a step forces the full copy, `r_dv`), so the shown picture's edge keeps up and `pf_done` no longer trails the game by 3 steps during a compose. `xdl_vars` works on `xv_b` (the buffer), not `r_hidden` directly.
- **Measured** (`tools/scroll_rate.py`, 2 runs, frames with a picture change / longest pause within the scroll): up 21-22 / 10-20 -> 36 / 5-6, down 21-22 / 15 -> 31-33 / 6-11 (the 11 is in the first frames, before the game's first step at ~frame 19), left 80-84 / 7-9 -> 74-79 / 6-7, right 74-77 / 4 -> 76-78 / 6-9 (start). Scrolls take a little longer (up 92 -> 94-96 frames, left/right 110 -> 116-119; the C64: ~64 / ~83): the renderer now uses more of the scroll's CPU.
- Tried and dropped: building the shown buffer's XDL variants when a scroll step comes and it has none (`xdl_shown`: a picture composed before the split came on could not move, ~20 frames at some horizontal scroll starts): its variants showed a 3-4 line band of the HUD at the playfield top.

### Session 10d (2026-11-06): the playfield's fine Y-scroll; no HUD strip in vertical scrolls - Measured
- **What the C64 does** (host model, `$D011/$D018` writes by raster line): during an up/down scroll the line-72 handler sets the playfield's Y-scroll, the line-250 handler puts 3 back for the HUD. Downward (Link walking down): each 2-frame step is the buffer flip with Y-scroll 7 (the new step's picture 4 lines down: half a step back), then 3. Upward: 7 on some frames (setup, and on the port before a step: half a step ahead). With 7 the VIC shows 4 idle (black) lines between the HUD and the playfield's first row.
- **The port's strip**: a compose used the snapshot's Y-scroll for the whole picture; when it caught the playfield's 7 the HUD moved 4 lines and its last lines showed at the playfield's top (also in the session-start build).
- Now: with the split on, compose uses the HUD's Y-scroll (3); `resident.s arm_ev` keeps the playfield's (`pf_y`: `$D011` as handlers above line 200 leave it); the vertical XDL variants are v = 2k + fine like left/right (`xdl_vars`: fine = 4 blank lines after the HUD, the playfield segments 4 lines shorter); `vicirq.s xv_pick` takes fine from `pf_y`, and never shows a position along the motion (p = v down, v xor 1 up) behind the last one shown for the same picture (the game's Y-scroll belongs to its newest step, the shown k may lag it: without this the picture jittered by 4 lines). `render_frame`'s "Y-scroll changed meanwhile: scan again" retry is off with the split on (it changes every frame).
- **Measured** (`scroll_rate`, a per-frame motion estimate of the playfield, `hudband` = minimap blue below the HUD): up 36 -> 45 picture changes, down 31-33 -> 44, both now moving in 4-line steps one way (one -4 at the end of the up scroll); HUD strip frames 24 per 4 scrolls -> 0; left/right unchanged (77-78 / 7-8). Regression: perf 60 passes, stuck ok, walk 4 scrolls, flicker 0.

### Session 10e (2026-11-06): faster screen scrolls - Measured
- **Where scroll time went** (`scroll_prof`, host model raster-read counts by PC): the renderer's blitter waits (`vx_wait`, no yield: a BG shift waits for the last compose's chain, most of a frame) kept the CPU from the game; and the game's frame waits after each buffer flip (RAM `$1A18` left/right: until line `>= $F4` or `< $2A`; `$117F` up/down: `>= $FA` or `< $3D`; 100-230 raster reads per frame) burned up to half a frame in `virt_now`.
- Changes:
  - `vx_wait` yields (`ryield`) while the blitter is busy (the game does not touch VRAM or the blitter; `VB_MEMS` is not changed by anything else).
  - `hook_d011w` (resident): the `LDA $D011` of those two frame waits (`patches.py SPECIAL_SITES`, bank 0 `$9DB0` / `$A649`, copied to RAM `$1000+`) resumes a suspended render while the line-250 flag is clear and the raster is before VCOUNT 70; it yields at the flag, inside the window they wait for. (Hooking every `LDA $D011` with IRQs on made things worse: renders resumed in the middle of the game's screen updates.)
  - `xdl_shown` again (session 10c's try showed a HUD band then; with the HUD's Y-scroll for split pictures the geometry matches): a scroll step with a shown picture without variants builds them, so a scroll's first steps no longer wait for a compose (up to ~20 frames).
  - Room for it: `snap_vsh` moved to KENT, `band_off` to RES7, `hook_d012r` an alias of `virt_now`.
- **Measured** (`scroll_rate`, 3 runs; frames from the scroll's start to mode 5, C64 ~83 horizontal / ~64 vertical): left/right 117-119 -> 95-99, up 94-96 -> 87-90, down 90-92 -> 84-88; game passes during left/right scrolls ~41 -> ~50 per 60; longest pause within a scroll <= 6 frames (more only in the frames before the game's first step); HUD strip 0. `walk_test` route: left scroll 108 -> 86 frames, right 112 -> 100. Regression: perf 60, stuck ok, walk 4 scrolls (one run: Link killed by an enemy on the way, mode 8; 3 more runs fine), flicker 0, stall 60, sword, death, dungeon PASS.
- Not done: one backward 8-line jump per vertical scroll at a flip (the new picture's edge for the step after its compose is filled only once it is shown: `edge_fill` serves the shown buffer); vertical scrolls are still ~35% longer than the C64's (game passes ~41 per 60 there).

### Session 10f (2026-11-06): saves that survive power-off (a disk in D1:) - Measured
- **Design**: the game saves through EAPI into RAM `$8000-$85FF` with the cart off (session 5). `atari/src/save.s` (segment SAVE, loaded in cart bank 12, run at RAM `$B000`: boot2 copies it there through CHBUF; RAM `$8600-$BFFF` under the cart window is never used by the game) holds the port kit's native polled SIO driver (`port_kit/templates/loader64/src/sio_native.s`, OS ROM off) and:
  - `SV_LOAD` (boot2, before POKEY/NMIs are set up): sector 4 = the signature `ZELDA-VBXE-SAVE1`, sectors 5-16 = `$8000-$85FF`. No disk, a blank disk or a bad sector: the "flash" stays erased (`$FF`); `sv_rs` = the read's status ($11: a save loaded).
  - `SV_FLUSH` (resident `sv_go` from `hook_idle` when no render is under way and `sv_dirty`): half a second after the game's last write (`eapi.s` sets `sv_dirty`/`sv_t` on every write/erase), NMIs off, signature + 12 sectors (~1 s: the picture holds, the music stops; input meanwhile is lost), then POKEY for sound again (AUDCTL, SKCTL, IRQEN, the sound driver's divider cache) and NMIs on. `sv_ws` = the last write's status. Up to 4 tries per sector (in-game, the first command after a while often had no ACK in time: `$8A`).
  - `eapi.s`: writes to `$B000+` are ignored and a ROMH erase stops at `$AFFF` (the save code; the game uses ROML only).
  - Room: `render_snap` moved into the renderer (bank 9); the save state bytes live in RES2 (`$F090` was not free: the SID patches map `$D4xx` mirrors to SSH + offset, and the game writes one there).
- **Test** `tools/save_test.py [CART]`: a blank ATR mounted in D1: (bridge `MOUNT`), register LUNA (retried: the scripted menu input slips now and then), the disk write (status 1), a cold reset with the disk still in: the boot loads it (`sv_rs` $11) and the select screen lists LUNA without registering. PASS 4 of 5 runs (the other: the registration input slipped 3 times). AltirraSDL here mounts disks virtual read/write (`"Disk 0" = "V..."`): writes stay on the disk until the emulator quits, never in the file, so the test power-cycles with a cold reset; `--bootrw` for the disk changed the menu timing. On Windows Altirra the disk must be set to read/write for the file to change.
- `tools/build_atari.py` writes a blank `build/zelda_save.atr` (90 KB) when there is none.
- Regression: perf 60 / 38.7 / 43, walk 4 scrolls, flicker 0, stall 60, sword, death, dungeon PASS; `stuck_check` once "IRQs stopped at 1168" (the attract demo, no input: no save ran, `sv_dirty` stayed 0 in a trace of that stretch), then 7 runs ok (and 3 of the previous build ok): an intermittent attract-mode stall, as the rare one noted in session 9; not chased further.

### Session 10g (2026-11-06): screen transitions without leftovers; smooth attract scroll; faster start-up - Measured
Frame-by-frame captures of the attract loop and the menus (START on the title, START on the select screen), compared with the host model (`vicrender`, no sprites) and its `$D011/$D018/$D02x` write logs.
- **Title fade:** the C64 cycles `$D021` from main-loop code at any raster line (one-frame colour bands are the C64's own), then shows the title dim (`$D022/$D023` = 6/B) for ~200 frames, black for ~200, then the story. The port went black at the fade's start for ~650 frames (`r_blank 5`, session 4b) and kept the title's frozen sprites (waterfall, logo) over the black and the story's start. Now: no fade blanking (`.ifdef OLDBLANK`), no title sprite freeze (removed: `frz_chk`/`frz_en`; the title barely changes either way, 5 changed frames of 200, no flicker), the sprites follow the game (they dim with the fade, go off with the story).
- **Old screen in new colours:** the game rewrites the screen and sets the new screen's colours 2 frames later; colours apply at once, the picture follows when the renderer has redrawn it (~25-70 frames: the old title in white or cyan).
  - `$D011` display enable (bit 4): the C64 switches the display off between screens (START on the title) and the port ignored it. Now `vicirq.s den_chk`: off -> overlay off (the border colour), on -> overlay on unless the port hides the picture itself.
  - A rewritten screen is hidden (black, `r_blank 6`) until the picture has caught up: `shift_check`'s 12 sample cells count changes (`sh_qc`); 6+ with no row shift outside normal play -> full compare and hide; `vicirq.s cl_chk` hides at once when 6+ samples differ from the shown picture's (`ex_smp`, copied at each compose) and all 12 now hold one character (a cleared screen). Shown again from the first full compare with nothing left to draw (`r_dirty` 0), at most ~45 frames.
  - In menus, caves and the death/continue screens (game modes other than 0 and 5) a full compare every 2nd render: their new screens are mostly blank, the samples miss them, and the select screen showed under the name screen for ~20 frames.
- **Stale sprite bands:** a render under way at line 250 defers the band publish; the later merge kept older bands while their start lines increased, so the select/name screens (one band) kept the title's three later bands (its waterfall sprites) forever. `bfull` = the last complete frame's band count (line 250, `copy_bands`); `merge_bands` keeps no older bands beyond it.
- **Attract fine scroll:** the story/item pages move 1 pixel every 2 frames on the C64; the port moved in 3-5 pixel bursts with ~10 still frames (after each row shift the renderer is busy ~8 frames). Now the VBI counts the game's Y-scroll steps (`vicirq.s ys_upd`, `ys_pos`) and shows the shown picture moved by the steps since its compose (`render.s ys_vars`: 16 XDL variants, k lines down; the variants' fixed bytes are written once per buffer, `ys_ok` bit 7). `vmot` per-frame motion: mostly -1 every 2 frames; short stalls are the game's own (~55 passes / 23 pixels per 60 frames; the C64 60 / 30).
- **Start-up** (title visible at frame ~690 -> ~460; the C64 ~300, after the 3 s credit screen the port hides): `patches.py BYTE_PATCHES` turns the boot's PAL/NTSC detection (RAM `$40FC`, 24576 raster reads via the raster emulation) into a store of 0 (NTSC) + RTS; renders do nothing while the start-up is hidden and the title's character set (`$D018 = $2E`) is not in use (building the credit screen's glyphs from the VBI took ~99% of the CPU and stretched the game's delay loops); the hidden start-up's full compare every 4th render.
- Four grey frames before the title: palette entry 8 (COLBK) set black in `boot2` before ANTIC starts.
- RAM: new state in RES2/RES5 bytes (`$F040-$F43F` takes the patched VIC/SID mirror writes).

### Session 11 (2026-11-07): a bot that plays the game (memory map, path finding, to Level 1) - Measured
Goal: a movie of the whole game played by a bot that reads RAM (no frame analysis). This session: up to Level 1.
- **RAM map** (`tools/bot/zram.py`): the C64 game is a conversion of the NES code, its RAM follows the NES map (Data
  Crystal "The Legend of Zelda/RAM map") with zero page shifted +2 and pages 3-7 unchanged. Checked in the port: mode
  `$14` (NES `$12`; 5 play, 6/7 scroll, `$0B` play underground, `$11` death), level `$12`, map screen `$ED` (start `$77`,
  Level 1 entrance `$37`, Level 1 first room `$73`), objects X `$72+i` / Y `$86+i` (slot 0 = Link), direction `$9A+i`,
  enemy type `$034F+i` (slot 1 = `$0350`), enemy HP `$0485+i` (`$10` per wooden-sword hit), inventory `$0657+`
  (sword, bombs, ...), rupees `$066D`, keys `$066E`, hearts `$066F/$0670`. Play-area tiles: `$6530`, column-major,
  32 x 22 (the screen's playfield exactly).
- **Collision** (measured by putting each tile code into `$6530` in front of Link: `tools/bot/walk_ow.json`): only
  Link's lower half collides, on an 8-pixel grid: X = 8c, Y = 61 + 8k, cell (c, k) open when tiles (c, k+1) and
  (c+1, k+1) are walkable. Overworld: about half the codes walkable (`$24` = cave/door mouth); `$74/$75` and `$BC-$C3`
  stop Link off-grid (special: treated as blocked). Dungeon tiles not measured yet.
- **Bot** (`tools/bot/`): `emu.py` (every input logged per frame, in-process checkpoints, replay), `menus.py`
  (title -> register GZ -> game, waits on the mode byte), `nav.py` (grid, A* path, exits), `bot.py` (walk with
  replanning when blocked, line up and swing at enemies within 40 px, leave a screen), `run_l1.py` (sword, A* over
  screens with a learned map `ow_map.json`, a checkpoint per screen: a death or a heart lost reloads it with another
  start delay, the Level 1 door), `record.py` (replay the log frame by frame: screenshots + the emulator's own
  sound, AUDIO_RECORD, 59.92 fps).
- **Emulator rules the bot depends on** (AltirraSDL bridge, measured):
  - Deterministic only with `CONFIG randmem off` (random power-on RAM: two idle boots differed by frame 50), a cold
    reset from a frame boundary (`FRAME 1` first: a reset where the bridge happened to pause gave runs that differed),
    and a fixed RAM pattern loaded before the first frame (`MEMLOAD`, see bug 1). Then `FRAME n` = n x `FRAME 1`
    (600-frame runs, 4 groupings, same RAM hash), and a replay of the input log reaches the bot's end state exactly
    (checked: Level 1 room `$73`, same position, hearts, rupees), checkpoint loads included.
  - `STATE_SAVE/STATE_LOAD` work within one emulator process (256 loads in the tile test); a state loaded into a fresh
    process left the game stuck in mode `$08` (probably VBXE-side state not in the state file): do not.
  - Each `FRAME` command costs ~20 ms on top of 2.2 ms per frame: the bot steps 1-4 frames at a time near targets.
  - Bridge commands found (not in the kit's list): `STATE_SAVE/LOAD/DROP`, `HISTORY n` (last 4096 instructions, with
    effective addresses), `BP_SET addr`, `WATCH_SET addr mode=r|w|rw` (hits not reported back), `MEMLOAD addr base64`,
    `CYCLES n`, `CLOCK`, `DISASM addr n`, `EVAL`, `CALLSTACK`, `MEMSEARCH`, `RAWSCREEN`, `AUDIO_RECORD start path=|stop|status`.
- **Port bugs found:**
  1. **Hang at power-on with zeroed RAM**: with `randmem off` (RAM all 0) the title never comes: at frame ~136 the
     game's bank (`cur_bank`) is 0 and stays there, the main code runs bank 0 bytes at `$8571+`, `JSR $1E18` into
     cleared RAM -> BRK -> `jmp ($0316)` = `$0000` -> a BRK/IRQ loop. Zero page `$00-$07` decides it: any two or more of
     them non-zero at power-on and it boots (bisected with RAM fills at frame 1). Not root-caused yet: the renderer reads
     those bytes (next item), so the likely cause is a timing race between the hidden start-up renders and the game's
     bank switching. Real power-on RAM is not reliably random: this could hang a real machine. The bot loads a fixed
     pseudo-random pattern instead (`emu.power_on_ram`).
  2. **Renderer glyph source unset during the hidden start-up**: bank 9 `$8603/$8670` `LDA ($81),Y` with `$81/$82` =
     `$0000` (frame ~27, before the game has set up the VIC): glyphs built from zero page. Harmless to the picture
     (hidden), but it reads `$00-$07` (see 1).
  3. (from session 10g's video) Lake water bright green instead of dark blue for ~10-70 frames on some screens.

  (All three resolved in session 13 below.)

### Session 12 (2026-11-07): the bot through Levels 1-2, the white sword, into Level 3; two port bugs that block the game - Measured
Goal: the bot plays the whole game (memory only); stop if the game breaks. It broke: bug 5 below makes the game
unwinnable on this build (bombs, arrows, boomerang, candle fire). The run stops in Level 3; movie `build/zelda_progress.mp4`.
- **RAM map from the NES disassembly** (github aldonunez/zelda1-disassembly: `Variables.inc`, `ObjVars.inc`, banks
  `Z_00-07.asm`): every NES variable at the same address in pages 3-7 and `$6000-$7FFF`, zero page +2. Level block at
  `$687E` (six 128-byte tables) and level info at `$6B7E` decode exactly as `FindDoorTypeByDoorBit`, `InitMode4` and
  `CheckSecretTrigger` read them (`tools/bot/level.py`). Room flags: `LevelInfo_WorldFlagsAddr` (Levels 1-6 share one
  map and one flag table, `$06FF`). Object types from the `UpdateObject` jump table (`agent.py NAMES`). Cellars: mode 9,
  side view, floors `$24`, ladders `$6F`; stairs are taken only on a 16-pixel square (`X & $0F = 0`, `Y & $0F = $0D`).
- **Bot, second generation** (`tools/bot/agent.py`, `dungeon.py`, `level.py`, `overworld.py`):
  - one RAM read per decision;
  - fights with dodging (velocities from successive reads, 16-frame prediction), striking cells and Darknut shield rules;
  - a checkpoint every 60 frames: lost hearts reload it, up to 8 times, then the one before;
  - Dijkstra over rooms, keys, opened doors and items; push blocks, stairs and cellars, bomb walls, Dodongo (bombs in
    its path per `Dodongo_TryEatBomb`), the item menu, dropped items;
  - overworld travel with cave mouths avoided unless entering.

  `serve.py`/`cli.py` keep one emulator for development (states only load in-process).
- **Emulator speed**: the bridge answers once per host frame (~17 ms) but takes batched commands: `Emu.step` sends input +
  `FRAME n` + `PEEK $0000 1792` together and caches RAM `$0000-$06FF` (one round trip per step; replay 41 s -> 28 s).
- **Port bug 4: the item menu can hang the game.** START in some rooms (Level 3 room `$4C`, often; Level 2's boss room
  when START comes ~10 frames after a cursor move): menu state (`$E3`, NES `MenuState`) stays 6 or 8, the game's
  frame counter `$17` stops. The main loop spins at bank 11 `$BC38` `JSR hook_d011r / BPL $BC38`, the C64 wait for raster
  bit 8 (then line `$38`). `virt_now` gives bit 8 only for Atari lines 234-239 (VCOUNT 117-119); when the line-250
  handler's work covers that window the poll never sees it. Possibly related: the renderer's scratch byte `ztmp = $60` is NES
  `$5E` `SubmenuScrollProgress` (bug 5). Repro logs: `build/bug_menu_hang.json` (closing, `$E3` = 8), `build/bug_menu_hang2.json`
  (opening, `$E3` = 6). The bot reloads and retries when `$17` stops (`agent.select`).
- **Port bug 5 (blocks the game): the renderer's zero page is game data.** `atari.inc` `zscr $81/82`, `zcol $83/84`,
  `zshs $95/96`, `zshc $97/98`, `zcnt/zb $A9/AA`, `zrow $AB`, `zy $AC` = NES `ObjX/ObjY/ObjDir` of object slots 15-18
  (Link's boomerang, bombs/fire `$10/$11`, arrow/rod `$12`); `zc/zk $D2/D3` = `ObjShoveDir` 16-17; `zmc/ztmp $5F/$60` =
  `CurScanRoomId`, `SubmenuScrollProgress`. The 2026-11-05 exploration that found them "never written" used no
  sub-weapons. Measured: a bomb placed at (203, 141) reads (9, 141) one frame later and (9, 233) the next; `$82/$96`
  change every frame with no bomb out. Bombs explode in random places (bomb walls never open, Dodongo works by luck),
  arrows and the boomerang fly from corrupted positions (Gohma, Ganon). Fix needs RAM: only ~2 NES zero-page bytes are
  never used (`$4F`, `$F0-$F2` unreferenced; `$4E` is a timer, `$27-$4E` are decremented every frame), so the renderer's
  pointers must be swapped with the game's at every render start/end, yield/resume and interrupting IRQ (as `zswap` did
  before 39a05c2), but `zswap` must be resident (the renderer yields from banks 10/11 in `fullscan`) and RESIDENT/RES2/RES7
  have 16/2/3 bytes free. Scalars can move to RES9's free tail (`$DFFA-$DFFF`).
- Level 3's cellar list (level info `$6BB2`) is all `$FF` in the cartridge, C64 original included (`Zelda_C64.crt`
  offset `$19735`), though room `$0F` holds the raft with A = B = `$69`. Unresolved whether the stairs reach it (the NES
  search runs past the list); the bot did not get the raft.
- Level 2's start and boss: Dodongos killed with bombs at their mouths; white sword from cave `$0A` (5 hearts).
- **Bug 5 fixed (renderer zero page).** The renderer's 10 pointer bytes (`$81-$84 $95-$98 $A9/$AA`) are exchanged with
  the game's whenever the CPU passes between them:
  - `resident.s zswap` (RES5, `$F0C3`, in the old title-freeze space, never written in 70k frames of play) swaps them
    with `zsave`;
  - it is called by `render.s render_frame_z` (each idle-time or VBI render, start and end), `ryield` and `ir_resume`.

  The six scalars (`zrow`..`ztmp`) are plain RAM at RES9's end (`$DFFA-$DFFF`, link-time assert in `scroll.s`). To free
  RES2 bytes, `ys_pos/ys_last/ys_act/ex_ok/ex_t/sv_ws/sv_rs` moved to RESIDENT.

  Not swapped around game IRQs that interrupt a render: the 2026-11-05 explorations trapped every zero-page write and
  found none to these bytes, IRQ handlers included. Swapping there too cost up to half the compose rate (`ZDEFS=LOOPCOUNT`,
  composes per 120 frames walking right 62 -> 32); without it the rate is as before (47-64).

  Checked: a bomb dropped at (137, 141) stays there as the game sees it (`$82/$96`, or `zsave` while a render holds the
  CPU, `in_ren` `$F06D` = 1) until it explodes; before, it read (11, 235), (248, 234), (172, 232) ... with the game's
  bytes live. A PEEK at a frame end can still show the renderer's values (use `zsave` when `in_ren` = 1).

  The game changes as soon as it no longer reads renderer leftovers, so input logs recorded on the old build
  (`build/bot_*.json`, the movies) do not replay on this one (Link has no sword at frame 5000).
- Bug 4 (menu hang) is still there with bug 5 fixed: in a stress test (START, wait, START, 12 times) the menu sticks in
  state 9, its scroll-up (the C64 menu has one more state than the NES: 7 scroll down, 8 open, 9 scroll up). The old build
  failed the same test (the menu stopped closing from the second cycle).

### Session 13 (2026-11-08): port bugs 1-4 fixed - Measured
- **Bug 4 (item menu hang) fixed.** The game's frame wait at EF bank 5 `$BC38` (`JSR hook_d011r / BPL $BC38`: wait for
  raster bit 8, C64 lines 256-262) never saw bit 8: the port shows it for 6 Atari lines (VCOUNT 117-119), and the
  line-250 event's `copy_bands` covers all of them while the menu scrolls (PC samples of a hung game: `$FBD0-$FC80` at
  VCOUNT 116-119, the wait loop everywhere else). New `resident.s hook_d011b8` (`patches.py SPECIAL_SITES`) waits until
  bit 8 or the next VBI (`frame_ctr` changed: C64 line 8, the frame has wrapped) and returns N = 1. The other raster
  waits (every `JSR hook_d011r/hook_d011n` site in the banks) poll wide windows. `hook_d011r` is shorter (`ASL / LSR thi /
  ROR`); `ys_pos .. sv_rs` moved to RES6 for room. Measured: menu stress test (open, wait, close, 24 cycles with varied
  delays) 24/24 (before: hung at the 2nd cycle).
- **Bug 1 (zero-RAM power-on hang) was bug 5.** The hidden start-up renders wrote their pointers into the game's zero
  page; with the bug 5 fix the port boots with RAM all `$00`, `$FF`, `$55`, `$AA` or random (8 fills, identical title
  at frame 400); the pre-bug-5 cartridge still hangs with zero RAM. `emu.power_on_ram` stays (one fixed start for the bot).
- **Bug 2 is not a defect:** before the game sets the VIC, `$DD00`/`$D018` select VIC bank 0 with the character set at
  `$0000`, so the renderer builds glyphs from `$0000-$07FF`, as a C64's VIC would show them. Reads only (hidden screen);
  it was only suspicious because of bug 1.
- **Bug 3 (lake water / HUD brown turning teal) fixed.** Palette entry 3 (`$D022`: the HUD's brown, the playfield's
  blue) held (0, yellow's G, yellow's B) for up to ~70 frames. CPU history around the first bad frame (bridge
  `CONFIG history on`, `HISTORY 4096` per 7500 cycles, palette stores found by PC): a colour-split DLI (`colour.s
  hc_rep`) was interrupted by the next line's DLI (NMIs nest); the inner one wrote the same queue entry again (`hq_i`
  not moved on yet), leaving `CSEL` at entry 3, and the outer's `CG/CB` went there. `hc_rq` now sets `hc_busy` while it
  writes (a nested DLI leaves the palette alone) and compares the queue with VCOUNT read live, so the outer pass sets
  what the nested DLI skipped. `palette_update` (renderer: border, sprite shared colours) also sets `hc_busy` around its
  writes (a DLI could interleave there too). Calling `hc_rq` from `palette_update` as well was tried: a render in the
  vertical blank then set the new frame's whole queue at once, and the title came 60 frames later; not done.
  Measured (screenshot every frame, pixels with R < 20 and G > 150): sword, then screens 77-67-68-58-48-38-37: 224 of
  1513 frames teal before, 0 of 1492 after; overworld tour before the fix: 1706 of 10383 frames.
- Debugging aids: `CONFIG history on` makes `HISTORY n` work (effective addresses only for indexed/indirect modes:
  absolute stores have to be matched by PC). Stray AltirraSDL processes from old sessions (20+ CPU hours each) were
  slowing every run: check `ps` for orphans.


### Session 14 (2026-11-08): the whole game by the bot, stopped by a crash on Death Mountain (bug 6) - Measured
Goal: the full-game movie (bot from RAM, stop on any port error). It stopped at frame 46966: the game crashes.
- **Bot driver** `tools/bot/campaign.py`: phases (`start`, `l1`, `l2`, `wsword`, `l3`, ...) run in one serve.py
  session (`C = campaign.Campaign(m); C.go('l1')`), an in-process checkpoint and `build/camp_<phase>.json` (the input
  log, replayable from power-on) after each; `C.redo(name)` goes back. A watchdog checks the level byte against the
  level entered. Reached: sword (frame 2223), Level 1 (27864, 4 hearts), Level 2 (43949, 5 hearts, triforce `$03`).
  Each phase end checked by a replay from power-on (`camp_l1.json`: same RAM hash).
- **Bot fixes:** the guard's checkpoint files were named by frame modulo 8: a newer state could overwrite one still in
  use, so a reload paired an old log with a newer state (the movie would not replay; once a state with level byte 3
  and Aquamentus at Y 0 inside Level 1). Unique names now, files removed when dropped. Checkpoints never cross a phase
  (one from Level 1's triforce room was reloaded on the overworld). A death is never accepted (reload the oldest
  checkpoint); unavoidable hits are taken after 600 reloads (Aquamentus: 1825 reloads before). Blocked cells are not
  learned when a monster is next to them; a screen's learned cells are dropped when it cannot be left (red tektites
  had walled off the passage from `$1A` to `$0A`).
- **Overworld caves decoded** (level block `$68FE` B >> 2 - `$10` = cave k, wares `$6A7E + 3k`, prices `+60`; NES
  `InitCave`): arrows 80 at `$25 $44 $4A $6F`; bait 100 at `$12 $26 $46 $4D` (60 at `$34`, with the blue ring 250);
  blue candle 60 at `$0C $15 $5E $66`; letter `$0E $11`; potions `$02 $04 $0D $18 $27 $29 $33 $4B $64 $78`; white
  sword `$0A`, magical sword `$21`. Level screens: 1 `$37`, 2 `$3C`, 3 `$74`, 4 `$45`, 5 `$0B`/`$1B`, 6 `$22`/`$30`,
  7 `$19`/`$42`, 8 `$6C`/`$6D`, 9 `$00`/`$05` (two listed for some: the real entrance still to check).
- **Port bug 6 (blocks the game): crash on screen `$1A`.** Walking up the one-cell passage (tiles `$74/$75`, column
  26) towards the white sword cave `$0A`, the game stops at frame 46966: frame counter `$17` frozen, the CPU in zero
  page (PC `$0014`, S `$05`, D flag set). Reproduces from power-on with `build/bug_crash_1a.json` (replayed by FRAME
  steps: the same frame every time). The bot's state and the replay agree. Traces (bridge `CYCLES` slices, `HISTORY`):
  the crash point moves with the slicing (an `RTS` at `$BC29` to `$0038`; an `RTS` path to `$00F6` in the VBI's bank 12
  call `vbi_b12` -> `ys_upd` `$844D`, where the step after the return executed code that was not bank 12's), so
  something goes wrong shortly before and the crash lands wherever the CPU is. Suspect: the cartridge bank under
  interrupt code (`nmi_vbi` maps bank 12 with `STA $D500` but not `mapped`; anything that restores `mapped` inside it
  leaves the VBI in the game's bank), or the variables moved to RES6 in session 13 (`ys_pos` .. `sv_rs`, `$DDF6+`).
  Not checked against older builds: their games diverge from the log within the first minute (logs only replay on the
  build that recorded them). Movie of the run to the crash: `build/zelda_run2_to_crash.mp4`.

- **Bug 6 fixed: root cause.** The idle render's exit (`resident.s idle_render`, after `JSR $8003`) cleared `in_nmi`
  before it put the game's stack back and cleared `r_act`. The VBI is an NMI (SEI does not hold it): one arriving in that
  window (`$FACB-$FAD5`) saw no render running and ran its fallback render (`do_render`) on the renderer's stack. That
  render's `ryield` (which only checked `r_act`) suspended it as if it were the idle render; `hook_idle` later resumed it
  (`ir_resume`: `in_ren` = 1); when it ended it returned into the old exit past its `STA in_ren`, so `in_ren` stayed 1
  with no render in progress. From then on every game IRQ was taken for an interrupted render: the IRQ hook redirected
  its return to `tramp`, which maps the renderer's bank 9 and returns to the game's PC; the first IRQ landing in banked
  game code (here bank 1 `$BE17`) ran bank 9's `$FF` fill into a `BRK`, then `JMP ($0316)` = `$0000`. Measured on the
  old build (bot log replayed frame by frame): `in_ren` 1 with `r_act` 0 from frame 46966 on, the frame of the crash.
  Fix: `in_nmi` is cleared last in that exit (after `TXS` and `r_act` = 0), and `ryield` switches only when `in_ren` = 1
  (an idle render on its own stack). Same instructions, same cycles. Found with a gap-free CPU history (bridge
  `CYCLES 1500` + `HISTORY 1000` per slice, merged by cycle); the first trace attempts misled: `CYCLES n` can stop inside
  an instruction, so `REGS` once showed an RTS half done (PCL pulled, PCH not: PC in zero page, S + 1).
  Checked: the bot replayed the campaign on the fixed build (sword, Levels 1 and 2, the `$1A` passage, the white sword
  at frame 50798; `camp_wsword.json` replays to the same end state), with a per-step watchdog on (`in_ren`, `r_act`)
  (`emu.py PORT_PEEKS`, `campaign.py watch`): never bad; the same watchdog on the old build's log flags frame 46966.
  Menu stress test 24/24. The old logs do not replay on the fixed build (the race had fired before, unnoticed, and
  changed the game's timing; likely also the Level 1 state with level byte 3 and Aquamentus at Y 0).
- **Port bug 7 (game frozen, Level 4 room `$51`): a raster event lost, the raster chain stopped.** At the room's entry the
  game's frame counter `$17` stopped; the main loop waited in `hook_idle` for the line-250 flag forever. Gap-free CPU
  history from the room's checkpoint: the event for C64 line `$7E` (display list entry `$60`) fired its DLI while the
  game's split hook (`colour.s hc`, SEI) was in `hc_rq` (RES8, `$FF93+`). The NMI's "nested in a colour DLI's hc_rep" test
  only looked at the interrupted PC (page `$FF`, from `hc_rep` on), took it for an outer colour DLI and left the event in
  `ev_due` for it; there was none, so `vbi_b12` dispatched it at the next VBI (`ev_vbi`), which (unlike the DLI path)
  left `dl_idx` on the event's entry, its bit already cleared. The game's handler armed nothing at that time, and
  `vbi_b12`'s own re-arm (for handlers that leave `$D012` alone) saw `dl_idx` set and did nothing: no raster event again.
  Fixes: the NMI counts its own `hc_rep` calls (`in_cdli`) and defers by that, not by the PC (a DLI over the game's
  `hc_rq` is re-armed 6 lines on, as other deferrals); `vbi_b12` clears a stale `dl_idx` (its bit clear) when it
  dispatches an `ev_due`. Checked: campaign replayed from power-on past room `$51` (frame 77174, no stall), menu stress
  test 24/24. Bot: a watchdog raises when `$17` stands still for 120 frames in play (`campaign.py watch`).
- Bot, this session also: overworld `attempt()` (retries from a checkpoint, the white sword's Lynel); Manhandla is five
  16-px parts (the middle one only when last); boss rooms get twice the room tries; `step_toward` lines up on the
  cross axis before entering a 1-cell gap (Level 1 room `$33`); the guard drops its checkpoints on a room or mode change
  (one from room `$69` was reloaded inside its cellar); a cellar item must show as taken in the room flags; stairs that
  do not lead to a cellar raise (the room is retried). Raft: dock on screen `$55` at cell (16, 9), reached from `$56`
  (a channel splits the screen), walk up: Link rides to `$45` (Level 4).

### Session 15 (2026-11-09/10): the bot plays the whole game, to Zelda and the credits - Measured
- **The complete game by the bot**: `build/camp_l9.json` (422275 frames, phases start, l1, l2, wsword, l3-l8, upgrade,
  l9) ends in Zelda's room `$32`, mode `$13`, the ending and the credits ("another quest will start from here").
  Movie: `build/zelda_full_game.mp4` (`tools/bot/record.py`, replay from power-on). No port crash or freeze in this
  session; one "GAME FROZEN" alarm was the watchdog's own fault (below), checked by a frame-by-frame replay of its log.
- Gohma (L8 `$1E`, red): no guard in the fight (each reload undid the arrow in flight); B is ignored in the bottom
  doorway (151 shots lost there): the standing spot is capped at Y 181; lined up within 6 px.
- Level 9 entry: `$17` is split by a one-tile river; the ladder crosses it from cell (14, 10) going left; stairs up to
  `$07`, west to `$05`, bomb the rock. `travel` plans over every exit when the remembered ones give no route;
  `leave()` pushes only from an edge cell (it walked Link into Level 6's door on `$22`).
- Level 9 without upgrades was lost: Patra's orbiters (types 37/38, HP `$60`) take only the sword (measured: not the
  wand beam, arrows or bombs) and a touch cost 2 hearts; the wizzrobe room `$07` stalled the guard. So an **upgrade
  phase** after Level 8: money caves `$6B`, `$62` (+100 each; touch the rupee at X 120), take-any caves `$7B`, `$47`
  (heart container on the right, X 152), the magic sword under the grave at (144, 144) on `$21` (pushed up, Link goes
  straight down its stairs), the blue ring at `$34` (X 120, 250), the fairy on `$43`. Then Level 9: red ring (cellar
  `$00`), silver arrows (cellar `$4F`, a route round Patra's room `$21`), Ganon, Zelda.
- Patra rooms that gate nothing are passed (`$16`, `$27`); orbiters are predicted round Patra (angle and radius) in
  `track`/`risk`.
- **Ganon** (type 62, HP `$F0`, magic sword `$40` a hit): the hit after HP `$30` sets HP back to `$F0` and his state
  (`$AE`+slot) to `$FB`, counting down ~1 per 2 frames while he stands still: then a silver arrow from in line with his
  32x32 body kills him. His ashes stay a type-62 object; the Triforce of Power showing is the sign. The guard is off in
  the fight and reset after it (the next guarded move rewound to before the fight). Zelda: line up at X 120 in `$32`,
  walk up; her fires go.
- Watchdog fix: `$17` is sampled only from `guard()`; over a 377-frame item menu the 8-bit counter wrapped to the same
  value: no judging across sample gaps over 40 frames.

### Session 15b (2026-11-10): the movie; a public copy for GitHub - Measured
- **Movie**: `tools/bot/record_par.py tools/bot/runs/full_game.json.gz build/zelda_full_game.mp4 12 300` took 4625 s
  (12 parts of 35169 frames; ~14 recorded frames a second each under that load). 422028 frames, video and sound
  7043.2 s, joins without a visible step; the last part ended in mode `$13`, level 9, screen `$32`.
- **Audit in the repo**: `tools/audit.json` (made by `tools/host/audit_export.py` from `work/an/audit.pkl` +
  `audit_ctx.pkl`) is what `build_atari.py` reads now (`patches.load_audit`). It holds no bytes of the original: RAM-site
  contexts equal to the RAM after boot are left out (patches.py then locates them from that RAM, as before), the
  others are `[bank, offset, length]` references into the cartridge, rebuilt from `Zelda_C64.crt`. Same cartridge:
  `3a6345af...`. After an `audit.py --merge`, run `audit_export.py` (it checks the round trip).
- **No local paths in the tools**: the port kit is `$PORTKIT`, or else `port_kit` next to the repo; the repo root is
  found from each script's own path; the VICE snapshot of `tools/analysis/` is `$ZELDA_VSF` (default `zelda.vsf`).
- **GitHub copy**: `python3 tools/export_github.py` writes `github/` (ignored here; its own repository): the tracked
  files without `readme.txt`, `GUIDE.md`, `docs/superpowers/`, `tools/ref_select_head.png`; `docs/DEVLOG.md` becomes
  `docs/DEVLOG.md` without the repository-setup section; local paths and the server's details are scrubbed. It fails
  if any media, local path, server address, the token or a key-like string is left.
