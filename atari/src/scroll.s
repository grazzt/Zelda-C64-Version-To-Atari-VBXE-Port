; Screen scrolls: the playfield's screen base below the HUD.
; While the overworld scrolls (game mode 7) the C64 double-buffers the playfield: the raster handler at C64 line ~72
; (RAM $41E3 vertical, $1F8D horizontal) points $D018 at screen $0800 or $2000 ($0DFA) for the rows below the HUD, and
; the line-250 handler puts $D018 back to $0800 for the HUD. The renderer takes its screen base from one snapshot, so it
; would read the HUD's buffer for the whole screen. Every STA $D018 (tools/patches.py) comes here: a write by a handler
; for a raster event below the HUD (C64 lines 60-199) is the playfield's base (pf_d018, pf_line); it stays valid for
; PF_LIFE frames without a new write (pf_vbi ages it, called by hc_vbi). The renderer (render.s pf_snap) uses it for
; the text rows from psr on, the snapshot's $D018 for the rows above. Each flip of the base while the split is on is one
; scroll step (the playfield moves one text row or column: checked in the host model); pf_steps counts them, so the
; renderer can move BG by the steps it has not seen, however rarely it runs (the scroll leaves it little idle time).
; RAM $DFA0-$DFFF (EF I/O-2 RAM after the EAPI table at $DF80-$DF9D; the game never uses it).
        .include "atari.inc"
        .export hook_d018, pf_vbi, pf_d018, pf_life, pf_line, psn, psr, pf_top, ptop, sr_end
        .export pf_steps, pf_done, pf_new, pf_ff, pd_dir, pd_k, pd_pl, pd_t, pd_kc, pd_s
        .import hc_ev
        .segment "RES9"

PF_LIFE = 3

hook_d018:                              ; replaces STA $D018 (A, X, Y and the flags kept)
        sta     VSH+$18
        php
        pha
        lda     hc_ev
        cmp     #60
        bcc     @t
        cmp     #200
        bcs     @t
        sta     pf_line
        pla
        pha
        cmp     pf_d018
        beq     @l
        sta     pf_d018                 ; a new base while the split is on: the game has flipped to the next step
        lda     pf_life
        beq     @l
        inc     pf_steps
        lda     frame_ctr
        sta     pf_ff
@l:     lda     #PF_LIFE
        sta     pf_life
        bne     @x
@t:     pla                             ; the HUD's base (from the line-250 handler on, VSH+$18 holds the playfield's
        pha                             ; for part of the frame: a snapshot may catch either)
        sta     pf_top
@x:     pla
        plp
        rts

pf_vbi: lda     pf_life
        beq     :+
        dec     pf_life
:       rts

pf_d018: .byte  0
pf_top: .byte   $2E                     ; the last write for the top of the frame
ptop:   .byte   0                       ; renderer: the rows above psr use this $D018
sr_end: .byte   40                      ; renderer: scan_rng end column
pf_life: .byte  0                       ; frames the split stays valid without a write (0: no split)
pf_line: .byte  0                       ; C64 raster line of the event that wrote it
psn:    .byte   0                       ; renderer: playfield $D018 of this render
psr:    .byte   25                      ; renderer: first text row with the playfield base (25: none)
pf_steps: .byte 0                       ; scroll steps (playfield base flips), counted by the hook
pf_done: .byte  0                       ; renderer: steps taken over into pf_new
pf_new: .byte   0                       ; renderer: steps not yet applied to BG
pf_ff:  .byte   0                       ; frame of the last step (the game moves colour RAM during the next frame)
; renderer temps (render.s pf_do)
pd_dir: .byte   0
pd_k:   .byte   0
pd_pl:  .byte   0
pd_t:   .res    3
pd_kc:  .res    2
pd_s:   .res    3

        .segment "RES9"
rscal:  .res    6                       ; the renderer's scalars (atari.inc zrow .. ztmp): RAM private to it
        .assert rscal = zrow, lderror, "renderer scalars moved: fix atari.inc zrow .. ztmp"
