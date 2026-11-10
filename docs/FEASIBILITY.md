# Zelda C64 EasyFlash: feasibility for Atari 65XE + VBXE

## Verdict

**Feasibility: PARTLY PROVEN — the original game code runs natively on an Atari 65XE + VBXE (title, story and item-scroll attract verified in AltirraSDL); gameplay load, sound, input and the save path are still unmeasured.** The supplied image is a valid EasyFlash cartridge. The user verified its NTSC VICE 3.10 boot and title-to-registration flow; our local VICE 3.7.1 session now captures the title reliably, but automated F7 delivery has not advanced to registration. Gameplay video/sprite/CPU/memory requirements and save persistence are therefore still unmeasured. The banked-cartridge + save-only ATR proposal remains plausible but unvalidated.

## Source identity and evidence

| Item | Result | Evidence |
|---|---|---|
| Media | `Zelda_C64.crt`, C64 EasyFlash CRT, 131,392 bytes | `file Zelda_C64.crt`; archive README |
| CRT structure | 64-byte header; cartridge type 32 (EasyFlash); 16 CHIP records, each 8,192 payload bytes; 131,072 bytes = 128 KiB payload | Header/chunk parser run against source |
| Source SHA-256 | `f24fa24d705ad27226ad8047159815726f4a6bf60c86417be447e85949fdc032` | `sha256sum Zelda_C64.crt` |
| Working copy | `work/Zelda_C64.crt` matches source hash; `assets/original/Zelda_C64.crt` also matches | `sha256sum` |
| VICE | Kit VICE 3.7.1; NTSC resources read as `MachineVideoStandard=2`, `VICIIModel=3` in a monitor run | `build/vice-run-boot-1388909.log` |
| User-verified VICE flow | SDL2VICE 3.10, NTSC MOS6567R8; `x64sc Zelda_C64.crt` attaches EasyFlash, shows startup credit then title, F7 opens name registration, then F7 is used to proceed after name entry | User-provided Windows console log and interaction report |
| Local title capture | VICE 3.7.1, direct `-cartcrt` with `+cartreset`; screen shows title and “PUSH START BUTTON” | `evidence/boot-1.png` through `evidence/boot-4.png` |
| User VSF | `zelda.vsf`, VICE 3.10 C64SC, 1,228,043 bytes, SHA-256 `fc9c9ac6a79ac1318ff93e016204b60ca1d16f11b57e3f7f325a364661a99114` | User-provided snapshot; inspected read-only |
| EasyFlash support | VICE reports `EF: EAPI found (AM/M29F040 V1.4)` and attaches type ID 32 | `evidence/vice-startup.log` |
| Kit setup | `KIT/tools/selftest.sh --altirra` passed; includes Altirra VBXE startup and ATR SIO write/read-back tests | command output in session |

The pristine CRT and the separate `assets/original` copy retain the recorded source hash. A VICE experiment wrote to its disposable `work/` cartridge copy; that copy has been restored from the source and the hashes now match. Generated evidence and working state are ignored by project-local `.gitignore` rules. This does not establish whether the game's own save flow writes EasyFlash flash or another backing store.

## Boot/reference result

The kit C64 wrapper passes the CRT as `-autostart`; VICE logs `AUTOSTART: Error`, then attaches EasyFlash and resets. That wrapper is unsuitable for this CRT as currently configured. Direct VICE 3.7.1 launch with `-cartcrt` and `+cartreset` (no reset-on-attach) runs the CRT and reproduces the title screen. Captures `evidence/boot-1.png` through `boot-4.png` consistently show “PUSH START BUTTON”; NTSC resources are confirmed.

The user independently verified the following on Windows SDL2VICE 3.10: startup credit for about 2–3 seconds, title, F7 to name registration, Joy 2 directions move the cursor and fire selects letters, F5 cycles name slots 2 and 3 then Register, F7 opens “- S E L E C T -”, and F7 starts. The user requested test name `Luna`.

The supplied VSF is a valid VICE 3.10/C64SC snapshot with MAINCPU, C64MEM, CARTEF and VIC-II modules. It is loaded locally through the binary-monitor undump command: response PC `$C4DC` matches the VSF MAINCPU PC, and captured 64 KiB RAM matches C64MEM byte-for-byte (SHA-256 `9051d77abc9ebfe7895f4d8e722cd7702ca428620ecbe039f47b2ff929e4dc2c`). The loaded menu shows entries `MO` and `BAD`, with the selection marker beside `BAD`. F7 would start BAD.

Earlier local monitor-script `undump` attempts produced `Error - T64 snapshot support is not implemented`; those were invalid. The corrected binary-monitor undump is verified by matching PC/RAM and the visible selection menu. One F7 was then sent from the verified state; the post-F7 screen was black and RAM changed, so gameplay start remains inconclusive. No save was written; `Luna` has not been entered or saved.

**Immediate next milestone (before gameplay porting):** title/story/item attract references are captured. Registration entry is still unknown locally. F7 at initial title and a later title-looking frame both started story/demo; the 18s frame is manual/inventory demo, not a registration gate. Trace title/menu input and state transitions before another F7 attempt. Once registration is reached, create Link's profile `Luna` with Joy 2 cursor/fire and F5 slot/Register navigation. Capture final `- SELECT -` with Luna visible and stop before game-start F7.

Fresh no-input timing captures show title at 0.1–0.5s, story text starting near 1.0s and completing around 1.5s, then “ALL OF TREASURES” and item-list pages by ~2s. The item list continues cycling for tens of seconds, with transitions between title/story/demo pages.

Fresh-boot F7 observations: F7 at the initial title around 0.1s starts story/demo. F7 around 14s leads to story text. The 18s capture is still the item/manual demo, not a title prompt. A later 3-second probe was still at startup credit and produced a C64 startup/test screen. None reached registration; do not repeat blind timing guesses. Trace key polling and mode transitions to find the Register entry.

Latest F7 probes were mistimed or led to story/demo; they are not registration evidence. The demo captures are ignored evidence files and remain local, not part of the repo.

## Feasibility table

| Demand | Source needs | Atari 65XE + VBXE path | Verdict |
|---|---|---|---|
| Video/playfield and color | Unknown; no trusted gameplay capture or VIC register trace | ANTIC playfield, VBXE palette/overlay, compare against verified NTSC C64 frame | Unknown |
| Sprites | Unknown; no sprite multiplex/register trace | VBXE overlay/blitter can address many C64 sprite constraints; source formats and timing must be measured | Unknown |
| Raster/scroll | Unknown; no source IRQ or VIC-write trace | Translate raster/display behavior to ANTIC DLIs/scroll only after trace | Unknown |
| CPU/frame timing | Unknown; no interactive-state trace or busy-scene profile | 65XE CPU budget must be measured against game frame pacing | Unknown |
| RAM / banked ROM | Source CRT stores 128 KiB across EasyFlash banks; runtime RAM map unknown | Kit documents banked Atari carts up to 256 KiB/4 MiB, but current kit brief defaults to stock 64 KB/no banking. Project-approved banked-cart target needs explicit mapper choice, resident code/IRQ placement, and a live RAM budget | Unknown (capacity plausible, execution/layout unverified) |
| Sound | README advertises music + simultaneous effects; chip use and timing unknown | Translate SID behavior to POKEY after register/routine audit | Unknown |
| Input | README: movement = joystick 2; A = joystick 2 button; B = Space; music F1; skin tone F3; Select F5; Start F7; save/continue/restart F8. User confirms F7 reaches name registration in VICE 3.10 | Joystick and spare Atari keys can be adapted after inventorying the source reads; local matrix injection not verified | Partial (controls read; runtime use only user-verified for F7) |
| Persistent saves | README says F8 saves/continues/restarts; backing store not established | Preferred packaging is banked read-only game cartridge plus writable ATR only for save data. Kit self-test verified generic ATR SIO write/read-back, not this game's save flow | Unknown |

## Packaging assessment

The source payload is 128 KiB. That is larger than a simple 64 KiB flat cartridge image, but the kit documents banked Atari cartridge examples at 256 KiB and 4 MiB. This makes a banked cartridge a plausible storage target for the game image, not proof that a port will fit or run: code must execute safely across bank switches, IRQ code must remain resident or be duplicated, and the original C64 RAM image must avoid the Atari I/O hole and cartridge window conflicts.

The writable ATR would contain only the persistent save data (and any minimal boot/service files required by the chosen implementation). The kit’s loader64 self-test verified SIO sector write/read-back with both the fast patch enabled and disabled. The actual user-facing physical setup and Zelda save-record size/write cadence remain unknown.

## Hints for the next port/analysis session

- Do not disassemble CRT bytes as though they were a flat CPU image. Boot the cartridge, capture its live RAM at the first interactive point, and trace execution and bank selection.
- VICE 3.7.1 supports `-cartcrt` and the EasyFlash mapper; logs show EasyFlash EAPI detection. The kit’s `vice.py`/`vice_keys.py` assumes the positional image is autostart media, so it logs `AUTOSTART: Error` and resets after attaching `.crt`. Direct `-cartcrt` with `+cartreset` works locally and yields the title; do not issue a monitor reset. The F7 XTest matrix event remains unverified in the local headless launch.
- User-confirmed VICE 3.10 flow: `x64sc Zelda_C64.crt` on NTSC; startup credit → title → F7 registration → Joy 2 directions + fire select letters → F5 cycles slots/Register → F7 “- S E L E C T -” → F7 starts. Supplied VSF screenshot appears to show `MO` and `BAD`, cursor by `BAD`; likely F7 target is `BAD`, pending actual snapshot-load confirmation. Do not press F7 before verifying names/selection from state.
- VSF parsing: snapshot is VICE 3.10 / C64SC. The module table contains C64MEM (4-byte CPU-port prefix + 64K RAM), MAINCPU (saved PC `$C4DC`), CARTEF and VIC-II. Local VICE 3.7.1 monitor `undump` attempts fail with `T64 snapshot support is not implemented`; current screenshot/RAM outputs are failed-load artifacts.
- Use NTSC VICE ordering `-default -model ntsc -ntsc`; confirm the live resources (`MachineVideoStandard=2`, `VICIIModel=3`).
- The 128 KiB payload is 16 × 8 KiB banks (CRT chip records list banks 0–7 at `$8000` and `$A000`). These are C64 EasyFlash banks, not directly transferable to an Atari mapper.
- Preserve the approved package direction for subsequent feasibility work: banked Atari ROM for game code/assets plus a writable ATR for save data only, subject to verified mapper/RAM/interrupt layout and durable save-write tests.
- Before classifying any row green/yellow/red, obtain a trustworthy first-playable screenshot/RAM/I/O/register capture and at least one busy-scene reference. Ask the user for optional VICE snapshots of a busy level/boss if scripted access is impractical.

## Reproduction notes

1. `source $PORTKIT/tools/env.sh`
2. `sha256sum Zelda_C64.crt work/Zelda_C64.crt assets/original/Zelda_C64.crt`
3. Parse the header/chunks with `python3 -c` or an equivalent script: header length at bytes 16–19, cartridge type at bytes 22–23, then each `CHIP` record's bank, load address, and payload length.
4. `python3 "$PORTKIT/tools/selftest.sh" --altirra`
5. VICE CRT attach evidence: `build/vice-keys-crt/vice-keys.log` (shows autostart failure followed by CRT attachment); `evidence/vice-startup.log` (direct `-cartcrt` launch and EasyFlash detection).

## Remaining measurements

The title and scrolling item attract demo are captured. The VSF state is separately verified (`MO`/`BAD`, BAD selected); an F7 from the monitor-saved VSF is not a valid gameplay test. Next, trace and reproduce registration entry, create Luna, and stop at `- SELECT -` before gameplay. After pre-game references, continue gameplay/resource/save measurements. Overall feasibility remains Unknown until those measurements are complete.

## Update: native port of the title/attract (2026-10-31)

Measured: the original 6502 code runs unmodified except for 171 audited hardware patches; EF banks 0-7 map one-to-one onto 16 KB MegaCart banks (256 KB cart type 30, banks 8-9 hold the Atari runtime/renderer). The attract needs only 181 hardware-access sites (VIC, SID, CIA, bank writes). Game logic uses ~57% of an Atari frame, the VBXE renderer ~17%, so title/attract fit. Gameplay scenes (more sprites, more raster bands, SID music, joystick, save/F8) remain unmeasured. See `docs/DEVLOG.md` for details and gaps.
