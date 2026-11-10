; Always-visible Atari runtime at $F100+ (copied from bank 8 at boot).
        .include "atari.inc"
        .export boot2
        .import vbi_b12
        .import __SAVE_LOAD__, __SAVE_SIZE__
        .export arm_dl, arm_now, arm_dl_end
        .export hook_bank_a, hook_bank_x, hook_bank_y, hook_gfx, fullscan, hook_idle, ryield
        .export ys_pos, ys_last, ys_act, ys_c, ys_ok, r_ysp, ex_smp, ex_ok, ex_t, cl_b, cl_c
        .export sh_qc, snap_vsh, copy_bands, merge_bands, sv_dirty, sv_t, sv_ws, sv_rs
        .import hc_rep, hc_vbi, hc_ev, hook_c21a, hook_c22a, hook_c23a, hook_d018
        .export zswap
        .export hook_d012w, hook_d012x, hook_d012cx, hook_d012r, hook_d012c, hook_d011r, hook_d011n, hook_d011w, hook_d011b8
DL      = $F0C0
        .segment "RESIDENT"

; The C64 character ROM (cart bank 10, $8000-$8FFF) -> VRAM CHROM, for pages that use the ROM font.
copy_chargen:
        lda     #$E8
        sta     VB_MEMC
        lda     #$80+(CHROM >> 12)
        sta     VB_MEMS
        lda     #10
        sta     mapped
        sta     $D500
        lda     #<$8000
        sta     @src+1
        lda     #>$8000
        sta     @src+2
        lda     #<WIN
        sta     @dst+1
        lda     #>WIN
        sta     @dst+2
        ldx     #16
        ldy     #0
@src:   lda     $8000,y
@dst:   sta     WIN,y
        iny
        bne     @src
        inc     @src+2
        inc     @dst+2
        dex
        bne     @src
        lda     #0
        sta     mapped
        sta     $D500
        sta     VB_MEMC
        rts

; Generated full-screen compare (characters in bank 10 at $9000, colours in bank 11 at $8000): sets ROWF[r] for every
; text row that differs from the shadows. Called by the renderer (bank 9) with the VBXE window on bank 0.
fullscan:
        lda     #10
        sta     r_bank
        sta     mapped
        sta     $D500
        jsr     $9000
        jsr     ryield                  ; (the main loop may need the CPU between the two halves)
        lda     #11
        sta     r_bank
        sta     mapped
        sta     $D500
        jsr     $8000
        lda     #9
        sta     r_bank
        sta     mapped
        sta     $D500
        rts

; ---- EasyFlash $DE00 -> MegaCart $D500 ----------------------------------------------------------------
; EF banks 0-7 = cart banks 0-7. EF banks 8-63 are the save flash (the game uses bank 16): cart off ($80), so Atari RAM
; $8000-$BFFF stands in for it (eapi.s writes it). A, X, Y and the flags are kept (callers branch on the flags).
hook_bank_x:
        php
        pha
        txa
        jmp     hb_c
hook_bank_y:
        php
        pha
        tya
        jmp     hb_c
hook_bank_a:
        php
        pha
hb_c:   cmp     #8
        bcc     :+
        lda     #$80
:       sta     cur_bank
        sta     mapped
        sta     $D500
        pla
        plp
        rts

; The game's per-frame screen update (bank 6 $BFB7, called from RAM $4320 with bank 6 mapped): flag it so the renderer never
; reads screen RAM while it is half rewritten.
hook_gfx:
        .ifdef LOOPRES
        inc     $F6F2
        .endif
        lda     #1
        sta     in_gfx
        jsr     $BFB7
        lda     #0
        sta     in_gfx
        lda     render_pend
        beq     @r
        lda     in_nmi
        bne     @r
        php                             ; the VBI render was skipped during the update: do it now, while the screen is consistent
        sei
        pha
        txa
        pha
        tya
        pha
        lda     #1
        sta     in_nmi
        lda     #0
        sta     render_pend
        jsr     do_render
        lda     #0
        sta     in_nmi
        pla
        tay
        pla
        tax
        pla
        plp
@r:     rts

; ---- VIC raster ($D012/$D011) -------------------------------------------------------------------------
; Current C64 raster line (low 8 bits) from ANTIC VCOUNT (2-line steps): Atari line 0 = C64 line 23, VBI (Atari 248) = line 8.
        .ifdef RING
get_now:
        lda     $D40B
        cmp     #120
        bcs     @w
        asl     a
        clc
        adc     #23
        rts
@w:     sec
        sbc     #120
        asl     a
        rts
        .endif


hook_d012w:
        php                             ; the line already pending written again (bank 7 $A3BF, the split handler
        cmp     VSH+$12                 ; running late): the C64's compare is unchanged, nothing happens (it used to
        bne     @new                    ; record a band and a colour-split event at a line not yet reached)
        pha
        lda     dl_idx
        ora     ev_vbi
        beq     @fired                  ; (the event has fired: a handler re-arming its own line, as normal)
        pla
        plp
        rts
@fired: pla
@new:   plp                             ; (flags kept: the game branches on C after the store)
        .ifdef PROF
        pha
        lda     $D40B
        sta     $FCC6
        pla
        .endif
        pha
        lda     VSH+$12
        sta     r_ev                    ; the event this handler serves
        sta     hc_ev                   ; (its colour writes follow: a late line-8 handler runs the line-72 code
        pla                             ; itself, without an IRQ, when the raster has passed 72)
        sta     VSH+$12
        php
        pha
        txa
        pha
        tya
        pha
        .ifdef RING
        ldx     $F6FF                   ; debug ring: (event, new target, real line, frame)
        lda     r_ev
        sta     $F6A0,x
        lda     VSH+$12
        sta     $F6B0,x
        jsr     get_now
        sta     $F6C0,x
        lda     frame_ctr
        sta     $F6D0,x
        inx
        txa
        and     #15
        sta     $F6FF
        .endif
        lda     r_evl                   ; the event being handled now = start line of this sprite band
        cmp     r_ev
        lda     r_ev
        sta     r_evl
        bcc     :+                      ; below the previous event: the same frame
        ldx     #0                      ; at or above it: the raster wrapped, a new frame's band list (usually line 8;
        stx     band_n                  ; screen scrolls skip line 8: their frames run 70 -> 250 -> 70)
        inx
        stx     ev8f                    ; the coming picture's sprites are being set: render after this
:       cmp     #250
        bcc     :+
        jmp     @nosnap                 ; line 250 and below: the bottom border, nothing visible follows (no band)
:       lda     band_n
        cmp     #MAXBANDS
        bcc     :+
        jmp     @nosnap
:       tax
        lda     band_off,x
        tax                             ; X = band * 48
        lda     VSH+0
        sta     BANDS+0,x
        lda     VSH+1
        sta     BANDS+1,x
        lda     VSH+2
        sta     BANDS+2,x
        lda     VSH+3
        sta     BANDS+3,x
        lda     VSH+4
        sta     BANDS+4,x
        lda     VSH+5
        sta     BANDS+5,x
        lda     VSH+6
        sta     BANDS+6,x
        lda     VSH+7
        sta     BANDS+7,x
        lda     VSH+8
        sta     BANDS+8,x
        lda     VSH+9
        sta     BANDS+9,x
        lda     VSH+10
        sta     BANDS+10,x
        lda     VSH+11
        sta     BANDS+11,x
        lda     VSH+12
        sta     BANDS+12,x
        lda     VSH+13
        sta     BANDS+13,x
        lda     VSH+14
        sta     BANDS+14,x
        lda     VSH+15
        sta     BANDS+15,x
        lda     VSH+$10
        sta     BANDS+16,x
        lda     VSH+$15
        sta     BANDS+17,x
        lda     VSH+$17
        sta     BANDS+18,x
        lda     VSH+$1B
        sta     BANDS+19,x
        lda     VSH+$1C
        sta     BANDS+20,x
        lda     VSH+$1D
        sta     BANDS+21,x
        lda     VSH+$25
        sta     BANDS+22,x
        lda     VSH+$26
        sta     BANDS+23,x
        lda     VSH+$27
        sta     BANDS+24,x
        lda     VSH+$28
        sta     BANDS+25,x
        lda     VSH+$29
        sta     BANDS+26,x
        lda     VSH+$2A
        sta     BANDS+27,x
        lda     VSH+$2B
        sta     BANDS+28,x
        lda     VSH+$2C
        sta     BANDS+29,x
        lda     VSH+$2D
        sta     BANDS+30,x
        lda     VSH+$2E
        sta     BANDS+31,x
        txa
        clc
        adc     #B_PTR
        tax
        lda     VSH+$18                 ; sprite pointers at screen base + $3F8 (operands patched when it moves)
        lsr     a
        lsr     a
        and     #$3C
        clc
        adc     #3
        cmp     @p0+2
        beq     :+
        sta     @p0+2
        sta     @p1+2
        sta     @p2+2
        sta     @p3+2
        sta     @p4+2
        sta     @p5+2
        sta     @p6+2
        sta     @p7+2
:
@p0:    lda     $03F8+0
        sta     BANDS+0,x
@p1:    lda     $03F8+1
        sta     BANDS+1,x
@p2:    lda     $03F8+2
        sta     BANDS+2,x
@p3:    lda     $03F8+3
        sta     BANDS+3,x
@p4:    lda     $03F8+4
        sta     BANDS+4,x
@p5:    lda     $03F8+5
        sta     BANDS+5,x
@p6:    lda     $03F8+6
        sta     BANDS+6,x
@p7:    lda     $03F8+7
        sta     BANDS+7,x
        lda     r_ev
        sta     BANDS+8,x               ; start
        lda     VSH+$12
        sta     BANDS+9,x               ; end (the next event's line)
        inc     band_n
@nosnap:
        lda     r_ev                    ; the line-250 handler: this frame's visible bands are complete
        cmp     #250
        bcc     @normal
        jsr     frz_tick
        lda     #0
        sta     ev8f
        lda     r_act
        beq     :+
        lda     band_n
        sta     bfull                   ; (the complete frame's band count, for merge_bands)
        lda     #1
        sta     cb_pend                 ; a render is reading RBANDS: publish when it has finished
        bne     @normal
:       jsr     copy_bands
@normal:
        jsr     arm_ev
@armed:
        .ifdef PROF
        lda     $D40B
        sec
        sbc     $FCC6
        bcs     :+
        adc     #131
:       clc
        adc     $FCC4
        sta     $FCC4
        bcc     :+
        inc     $FCC5
:
        .endif
        pla
        tay
        pla
        tax
        pla
        plp
        rts
; Raster for $D012/$D011 reads. The C64 raster is phase-locked to ANTIC's: C64 line 8 = Atari line 248 (the VBI), so the
; C64 picture lines 50-250 are the Atari lines 28-228 the overlay shows. A = low 8 bits, thi = bit 8.
virt_now:
        lda     $D40B
        cmp     #120
        bcs     @top
        asl     a                       ; Atari line < 240: C64 line = Atari line + 22
        adc     #22
        sta     r_now
        lda     #0
        rol     a
        sta     thi
        lda     r_now
        rts
@top:   sbc     #120                    ; Atari line 240-261: C64 lines 0-21
        asl     a
        sta     r_now
        lda     #0
        sta     thi
        lda     r_now
        rts
hook_d012r = virt_now
hook_d012c:                             ; replaces CMP $D012
        pha
        jsr     virt_now
        pla
        cmp     r_now
        rts
; LDA $D011 in the screen scrolls' frame waits (RAM $1A18 left/right, $117F up/down: tools/patches.py SPECIAL_SITES):
; the game has flipped its buffer and polls until the raster leaves the picture, up to half a frame. A suspended
; render resumes there until the line-250 flag (inside the window they wait for), as in the main loop's own wait;
; not once the flag is set (the pass has work).
hook_d011w:
        lda     $C102
        bne     hook_d011r
        lda     r_act
        beq     hook_d011r
        lda     $D40B                   ; (only with time to spare: a render overshooting the window costs the game
        cmp     #70                     ; a frame)
        bcs     hook_d011r
        jsr     ir_resume
hook_d011r:                             ; replaces LDA $D011: shadow with bit 7 = virtual raster bit 8 (N, Z as LDA)
        jsr     virt_now
        lda     VSH+$11
        asl     a
        lsr     thi                     ; (thi is 0 or 1)
        ror     a
        rts
; LDA $D011 of the frame wait at EF bank 5 $BC38 (JSR here / BPL $BC38: wait for raster bit 8, the C64 lines 256-262).
; Bit 8 is visible for 6 Atari lines only (VCOUNT 117-119), and the line-250 event's copy_bands can cover them all (the
; item menu's scroll: many bands): the game then waited forever (HANDOFF bug 4). Waits here until bit 8 or the next
; VBI (C64 line 8: the frame has wrapped), then returns N = 1 (A = garbage | $80; the caller only branches).
hook_d011b8:
        lda     frame_ctr
        sta     b8_f
:       jsr     hook_d011r
        bmi     :+
        lda     frame_ctr
        cmp     b8_f
        beq     :-
:       ora     #$80
        rts


; ---- interrupts --------------------------------------------------------------------------------------
nmi_vbi:
        pha
        .ifdef DLIDBG
        lda     $D40B
        sta     $F6F0
        lda     $D40F
        sta     $F6F1
        .endif
        sta     $D40F                   ; NMIRES
        jsr     hc_vbi                  ; colour-split table: age it (colour.s)
        .ifdef PCPROF
        txa
        pha
        tsx
        lda     $0105,x                 ; interrupted PC high byte
        sta     $F6A0
        lda     $0104,x
        sta     $F6A1
        stx     $F6A2
        lda     cur_bank
        sta     $F6A3
        pla
        tax
        .endif
        inc     frame_ctr               ; (the game's raster events run on the virtual clock, not on the VBI)
        lda     r_flip                  ; a composed frame whose blits are done: show it from the next frame on
        cmp     #1
        bne     @nf
        lda     VB_BLGO
        bne     @nf
        lda     #0
        sta     VB_XDL+1
        sta     VB_XDL+2
        sta     r_flip
        lda     r_hidden
        beq     :+
        lda     #$20
:       sta     VB_XDL
        lda     r_hidden
        eor     #1
        sta     r_hidden
        lda     r_blank
        cmp     #3
        bne     @nf
        lda     #1
        sta     VB_CORE                 ; the title screen is complete: overlay on
        lda     #0
        sta     r_blank
        lda     #$FF
        sta     r_pal                   ; (the border colour again)
@nf:
        lda     #1
        sta     want_r                  ; the main loop's wait (hook_idle) renders
        inc     vbi_age
        lda     #12                     ; the SID shadow -> POKEY (sound driver in cart bank 12)
        sta     $D500
        jsr     vbi_b12                 ; VIC raster IRQ repeat (vicirq.s), then the sound/input update
        lda     mapped
        sta     $D500
        lda     ev_vbi                  ; the C64 line-8 event is the VBI
        beq     @nev
        txa
        pha
        tsx
        lda     $0103,x
        and     #$04
        bne     @vdef
        lda     #0
        sta     ev_vbi
        pla
        tax
        pla
        jmp     irq
@vdef:  lda     r_tgt                   ; IRQs disabled: 6 lines on (the first display list line, or later if the VBI
        jsr     arm_now                 ; ran past it)
        pla
        tax
@nev:
        lda     in_nmi
        bne     :+
        lda     vbi_age
        cmp     #4
        bcs     :++
:       pla
        rti                             ; a render is running, or the game idles often enough to render there
:       lda     in_gfx
        beq     @render
        lda     #1
        sta     render_pend             ; the game is rewriting the screen: render when it has finished (hook_gfx)
        pla
        rti
@render:
        lda     #1
        sta     in_nmi
        txa
        pha
        tya
        pha
        sei
        lda     #0
        sta     render_pend
        jsr     do_render
        lda     #0
        sta     in_nmi
        pla
        tay
        pla
        tax
        pla
        rti

; Run the renderer (bank 9) with the game's bank preserved. Interrupts must be off. (render_frame exchanges the
; renderer's zero-page pointers with the game's itself: zswap.)
do_render:
        .ifdef LOOPRES
        inc     $F6FB                   ; debug: VBI renders
        .endif
        lda     #0
        sta     want_r
        sta     vbi_age
        jsr     snap_vsh
        lda     $D40B
        sta     r_rstart
        .ifdef PROF
        sta     $FCC1
        .endif
        lda     #9
        sta     r_bank
        sta     mapped
        sta     $D500
        jsr     $8003                   ; render_frame (bank 9)
        lda     cur_bank
        sta     mapped
        sta     $D500
        .ifdef PROF
        lda     $D40B
        sec
        sbc     $FCC1
        bcs     :+
        adc     #131
:       clc
        adc     $FCC2
        sta     $FCC2
        bcc     :+
        inc     $FCC3
:
        .endif
        rts

irq:    pha
        txa
        pha
        tya
        pha
        inc     irq_ctr
        lda     r_tgt                   ; the event this handler serves: its colour writes are replayed at its line
        sta     hc_ev                   ; (hc_rep only set it for DLIs it recognised itself, not for events dispatched
                                        ; after a nested DLI or from the VBI: a line-72 split filed under line 8)
        .ifdef T250
        jsr     dlog
        .endif
        .ifdef DLIDBG
        ldx     $F6EE                   ; debug ring: dispatch line, target, frame, deferrals so far
        lda     $D40B
        sta     $F6A0,x
        lda     r_tgt
        sta     $F6B0,x
        lda     frame_ctr
        sta     $F6C0,x
        lda     $F6FE
        sta     $F6D0,x
        inx
        txa
        and     #15
        sta     $F6EE
        .endif
        lda     in_ren
        beq     @go
        lda     in_girq
        bne     @go                     ; nested in the game's handler (or at the trampoline's entry): game state is live
        inc     in_girq
        tsx                             ; the renderer was interrupted: S+4 = P, S+5/6 = PC
        lda     $0104,x
        sta     s_p
        lda     $0105,x
        sta     s_pcl
        lda     $0106,x
        sta     s_pch
        lda     #<tramp
        sta     $0105,x
        lda     #>tramp
        sta     $0106,x
@go:    pla
        tay
        pla
        tax
        pla
        jmp     $FF48                   ; the C64 KERNAL IRQ entry, re-created in KENT


        .segment "RES7"
band_off: .byte  0, 48, 96, 144, 192, 240
sh_qc:  .byte   0                       ; render.s shift_check: sampled cells that changed
; STX $D012 (RAM $C55A): as STA
hook_d012x:
        pha
        txa
        jsr     hook_d012w
        pla
        rts
        .segment "RES7"
; CPX $D012 (RAM $1FB2: the horizontal-scroll handler's busy-wait for line $4A): X against the virtual raster, A kept
hook_d012cx:
        pha
        jsr     virt_now
        pla
        cpx     r_now
        rts
        .segment "RES2"
hook_d011n:                             ; replaces BIT $D011 (followed by BMI/BPL): N = virtual raster bit 8, A kept
        pha
        jsr     virt_now
        lda     thi
        beq     :+
        pla
        bit     c_80
        rts
:       pla
        bit     c_00
        rts
c_80:   .byte   $80
c_00:   .byte   $00
in_cdli: .byte  0                       ; nmi: a colour DLI's hc_rep is running (nested DLIs count up)
nmi:
        .ifdef RING
        inc     $F6F0                   ; debug: NMIs
        .endif
        bit     $D40F                   ; NMIST bit 7: display list interrupt = a raster event
        bmi     :+
        jmp     nmi_vbi
:
        pha
        sta     $D40F                   ; NMIRES
        txa
        pha
        inc     in_cdli
        jsr     hc_rep                  ; colour splits on this line (colour.s); C = 1: no raster event here
        dec     in_cdli
        bcc     @ev
        lda     ev_due                  ; (the event's own DLI came while hc_rep ran: it is due now)
        beq     @dd
@ev:    lda     #0
        sta     ev_due                  ; (no longer due: a nested DLI's ev_due when the outer DLI was on the event's
        ldx     dl_idx                  ; line too stayed set, and the next colour DLI fired the line-250 event early)
        lda     DLB,x
        and     #$7F
        sta     DLB,x
        tsx
        lda     $0103,x                 ; the interrupted code's P: IRQs disabled? (the C64 IRQ would wait)
        and     #$04
        bne     @nest
        lda     #0
        sta     dl_idx
        pla
        tax
        pla
        jmp     irq                     ; the emulated raster IRQ (same stack frame as an IRQ)
@nest:  lda     in_cdli                 ; interrupted inside a colour DLI's hc_rep (an NMI masks IRQs too): not the
        beq     @defer                  ; game's, so no deferral: the outer DLI dispatches it when hc_rep returns
        inc     ev_due                  ; (the colour DLI is a line or two before the event's: ~545 of ~700 deferrals,
        bne     @dd                     ; and the line-250 event deferred past the display list lost a frame). A count,
                                        ; not the interrupted PC: the game's split hook (colour.s hc) runs hc_rq there
                                        ; too, with no outer DLI to dispatch (bug 7: the event waited for the VBI)
@defer: lda     r_tgt                   ; try again 6 lines from now (from the event's own line it could be a line
        jsr     arm_now                 ; ANTIC has passed when this DLI ran late: the event slipped a whole frame)
@dd:    pla
        tax
        pla
        rti


; ---- virtual raster clock ---------------------------------------------------------------------------------
; The game's raster IRQs run on a virtual C64 raster: time spent in our renderer is excluded, and every event is
; scheduled relative to the event being handled (never to the Atari VBI), so a slow render delays the game instead of
; making it lose raster events.

; Sample the real clock: t_fc = NMI frame count, t_vr = VCOUNT relative to the VBI (0..130, 2 scanlines each).
; Arm the raster event for C64 line A: the DLI bit on that line of the display list (C64 line 8: the VBI itself).
arm_now:                                ; (C64 line A as soon as possible: 6 lines from now; the vertical blank: the
        sec                             ; first display list line)
        .byte   $24                     ; (BIT zp: skips the CLC)
arm_dl:
        clc
        php
        sta     r_tgt
        ldx     dl_idx                  ; one event at a time: clear the previous one
        beq     :+
        lda     DLB,x
        and     #$7F
        sta     DLB,x
:       lda     #0
        sta     dl_idx
        sta     ev_vbi
        plp
        bcc     @tgt
        lda     $D40B
        cmp     #123
        bcs     @vb0
        asl     a
        ora     #1
        bcc     @a6
@vb0:   lda     #1
        bne     @a6
@tgt:   lda     r_tgt                   ; Atari line of C64 line T
        cmp     #8
        beq     arm_vb
        bcc     @low
        cmp     #32
        bcs     :+
        lda     #10                     ; C64 9-31 (above the picture): the first display list line
        bne     @chk
:       sec
        sbc     #22+EV_LEAD             ; C64 32-262: Atari T-22, less EV_LEAD lines: our path from the DLI to the
                                        ; handler's own work (NMI, KERNAL entry, the $D012 hook's sprite snapshot)
                                        ; takes about that long, so its writes (colour splits) land on the C64's line
        jmp     @chk
@low:   clc
        adc     #240                    ; C64 0-7: Atari T+240
@chk:   sta     r_dl
        lda     $D40B                   ; ANTIC reads entries ahead: a target 0-5 lines ahead
        cmp     #124                    ; is set 6 lines ahead (a few lines late, not a frame)
        bcs     arm_set
        asl     a
        ora     #1
        sta     r_now                   ; (current line, rounded up)
        lda     r_dl
        sec
        sbc     r_now                   ; target - now: 0-5 ahead, or passed by up to 20 (our handlers run a little
        bcs     :+                      ; later than the C64's): as soon as possible; passed further: next frame
        cmp     #256-20
        bcc     arm_set
        bcs     @asap
:       cmp     #6
        bcs     arm_set
@asap:  lda     r_now
@a6:    clc
        adc     #6
        sta     r_dl
arm_set:
        lda     r_dl
        cmp     #246                    ; (Atari lines 246-247 have no entry: at the VBI)
        bcs     arm_vb
        cmp     #10
        bcs     :+
        lda     #10                     ; (no entry before line 10)
:       sec
        sbc     #9                      ; display list entry
        tax
        stx     dl_idx
        lda     DLB,x
        ora     #$80
        sta     DLB,x
        rts
arm_vb:   lda     #1
        sta     ev_vbi
        rts
arm_dl_end:

; The game's IRQ handler returns here (RTI) when it interrupted the renderer: renderer bank back, then resume.
tramp:  sei
        sta     s_a
        lda     #0
        sta     in_girq
        stx     s_x
        sty     s_y
        lda     r_bank
        sta     mapped
        sta     $D500
        lda     s_pch
        pha
        lda     s_pcl
        pha
        lda     s_p
        pha
        lda     s_a
        ldx     s_x
        ldy     s_y
        rti



; The main loop's wait for the line-250 flag ($40CD: LDA $C102): render here, once per frame after the line-8 event, with
; raster IRQs enabled, so the renderer uses the game's idle time and never delays its raster events.
hook_idle:
        lda     r_act
        beq     @new
        jsr     ir_resume               ; a suspended render resumes (for at least its slice if the game has work)
        jmp     @out
@new:   lda     sv_dirty                ; (no render under way: the game's save can go to the disk, save.s)
        beq     :+
        jsr     sv_go
:       lda     want_r
        beq     @out
        lda     ev8f
        bne     @go
        lda     vbi_age
        cmp     #2
        bcc     @out                    ; (before line 8 the sprites still show the previous picture)
@go:    lda     in_nmi
        bne     @out
        jsr     idle_render
@out:   lda     $C102
        beq     :+
        inc     r_pass                  ; the main loop runs a pass now
        .ifdef LOOPRES
        inc     $F6FD                   ; debug: main-loop passes
        .endif
        lda     $C102
:       rts

; The disk save (save.s, RAM $B000 under the cart window): cart off, `mapped` first so an NMI restores the same.
sv_go:  lda     #$80
        sta     mapped
        sta     $D500
        jsr     SV_RUN+3
        lda     cur_bank
        sta     mapped
        sta     $D500
        rts
sv_dirty: .byte 0                       ; the game wrote its save "flash" (eapi.s) since the last disk write
sv_t:   .byte   0                       ; frame of that write
ys_c:   .byte   0, 0                    ; per display buffer: ys_pos of its picture (render.s ys_vars)
ys_ok:  .byte   0, 0                    ; per display buffer: its offset variants are built
r_ysp:  .byte   0                       ; render.s: ys_pos at this render's snapshot
ex_smp: .res    12, 0                   ; the 12 shift_check sample cells as the last composed picture has them

; The renderer runs as a coroutine on its own stack ($0100-$019F) in the main loop's idle time: it yields (ryield) as
; soon as the line-250 flag gives the main loop work, and resumes in its next wait. So rendering never costs the game
; a frame, and raster IRQs keep running throughout.
idle_render:
        .ifdef LOOPRES
        inc     $F6FC                   ; debug: idle renders
        .endif
        php
        sei
        txa
        pha
        tya
        pha
        tsx
        stx     gs_s
        lda     #0
        sta     want_r
        sta     vbi_age
        sta     ev8f
        lda     #1
        sta     in_nmi                  ; (no VBI render while one is in progress)
        sta     in_ren
        sta     r_act
        lda     #9
        sta     r_bank
        sta     mapped
        sta     $D500
        ldx     #$9F
        txs
        cli
        jsr     $8003                   ; render_frame (bank 9)
        sei
        lda     #0
        sta     in_ren
        sta     vbi_age                 ; (the VBI fallback counts from the end of this render)
        ldx     gs_s
        txs
        sta     r_act
        sta     in_nmi                  ; last (bug 6): the VBI is an NMI, SEI does not hold it. With in_nmi clear while
                                        ; S was still the renderer's and r_act set, a VBI here ran a fallback render on
                                        ; the renderer stack; its ryield suspended it as an idle render, ir_resume later
                                        ; set in_ren for it, and in_ren stayed 1 after it ended: every game IRQ then went
                                        ; through the trampoline (bank 9 mapped under banked game code: a crash)
        lda     cur_bank
        sta     mapped
        sta     $D500
        lda     cb_pend
        beq     @rg
        lda     #0
        sta     cb_pend
        lda     r_ev
        cmp     #250
        bcc     :+
        jsr     copy_bands              ; between line 250 and 8: the last frame's bands are complete
        jmp     @rg
:       jsr     merge_bands
@rg:    pla
        tay
        pla
        tax
        plp
        rts

; Renderer: give the CPU back to the main loop if it has work (called at safe points, renderer stack).
ryield: lda     $C102
        beq     @no
        lda     in_ren                  ; (an idle render on its own stack, not a VBI fallback render; r_act alone let
        beq     @no                     ; a fallback render nested in an idle render's exit suspend itself: bug 6)
        lda     $D40B                   ; a resumed render keeps the CPU for at least ~24 lines (its share of a
        sec                             ; frame when the game never idles, as on the title screen)
        sbc     r_vres
        bcs     :+
        adc     #131
:       cmp     #18
        bcs     @y
@no:    rts
@y:
:       php
        sei
        pha
        txa
        pha
        tya
        pha
        tsx
        stx     rs_s
        lda     #0
        sta     in_ren
        jsr     zswap                   ; the game's zero page back
        lda     cur_bank
        sta     mapped
        sta     $D500
        ldx     gs_s
        txs
        pla
        tay
        pla
        tax
        plp
        rts                             ; returns from hook_idle's call (idle_render or ir_resume)

ir_resume:
        php
        sei
        txa
        pha
        tya
        pha
        tsx
        stx     gs_s
        jsr     zswap                   ; the renderer's zero page
        lda     #1
        sta     in_ren
        lda     $D40B
        sta     r_vres
        lda     r_bank
        sta     mapped
        sta     $D500
        ldx     rs_s
        txs
        pla
        tay
        pla
        tax
        pla
        plp
        rts                             ; back into the renderer after its jsr ryield

; This frame's bands so far over the last complete ones. Older later bands are kept only while their start lines keep
; increasing (a frame whose raster IRQ ran late merges two events: band counts differ from frame to frame).
merge_bands:
        lda     band_n
        beq     cb_rts
        cmp     rband_n
        bcc     :+
        sta     rband_n
        jmp     cb_copy
:       jsr     cb_copy
        ldx     band_n
@k:     cpx     rband_n
        bcs     cb_rts
        cpx     bfull                   ; (older bands only as many as the last complete frame had: the select and
        bcs     @cut                    ; name screens kept the title's three later bands, its waterfall sprites)
        ldy     band_off,x
        lda     RBANDS+B_START,y
        ldy     band_off-1,x
        cmp     RBANDS+B_START,y
        beq     @cut
        bcc     @cut
        inx
        bne     @k
@cut:   stx     rband_n
        rts

; Publish this frame's bands to RBANDS (the renderer's copy): one unrolled 48-byte block per recorded band.
; (The title's sprites were frozen once, static after 60 title frames: no longer, they follow the game.)
copy_bands:
        lda     band_n
        sta     bfull
        sta     rband_n
        bne     cb_copy
cb_rts: rts
cb_copy:
        ldx     #0
        ldy     band_n
@b:     .repeat 42, k
        lda     BANDS+k,x
        sta     RBANDS+k,x
        .endrepeat
        txa
        clc
        adc     #BAND_SZ
        tax
        dey
        beq     @done
        jmp     @b
@done:  rts

        .segment "BOOT2"
; Boot-only code in RAM at $E000 (later the VBXE window): never runs again.
; ---- original reset path, replayed natively ----------------------------------------------------------
boot2:  lda     #$2F
        sta     $00
        lda     #$37
        sta     $01
        lda     #0
        sta     rband_n                 ; no completed sprite bands yet
        sta     r_frz
        sta     r_fcnt
        sta     want_r
        sta     ev8f
        sta     cb_pend
        sta     ev_due
        sta     vbi_age
        sta     in_ren
        sta     in_girq
        sta     r_act
        sta     vb_lo
        sta     vb_hi
        sta     t_armed
        sta     r_evl
        sta     fc_fire
        sta     vr_fire
        lda     #$FF
        sta     VSH+$3F
        sta     $DC00                   ; CIA1: no joystick/key activity (C64 idle value)
        sta     $DC01
        lda     #$80
        sta     $D500                   ; cart off: RAM $8000-$BFFF is the EF save flash (hook_bank_a), erased = $FF
        ldx     #$40
        ldy     #0
        lda     #$FF
@ff:    sta     $8000,y
        iny
        bne     @ff
        inc     @ff+2
        dex
        bne     @ff
        ldx     #0                      ; the disk save code (cart bank 12 -> RAM $B000 under the cart, via CHBUF)
@sp:    lda     #12
        sta     $D500
        ldy     #0
@s1:    lda     __SAVE_LOAD__,y
        sta     CHBUF,y
        iny
        bne     @s1
        lda     #$80
        sta     $D500
@s2:    lda     CHBUF,y
@d2:    sta     SV_RUN,y
        iny
        bne     @s2
        inc     @s1+2
        inc     @d2+2
        inx
        cpx     #>(__SAVE_SIZE__ + 255)
        bne     @sp
        jsr     SV_RUN                  ; a save on the disk in D1: back into the "flash" (cart off)
        lda     #0
        sta     cur_bank
        sta     mapped
        sta     $D500                   ; EF bank 0
        ; POKEY: sound only (raster events come from DLIs): channels 1+2 joined at 1.79 MHz, 3 and 4 at 64 kHz
        lda     #$50
        sta     $D208                   ; AUDCTL
        lda     #0
        ldx     #7
:       sta     $D200,x
        dex
        bpl     :-
        ldx     #$14
:       sta     s_lvl,x                 ; sound state
        dex
        bpl     :-
        lda     #3
        sta     $D20F                   ; SKCTL
        lda     #$FF
        ldx     #4
:       sta     J_JOY,x                 ; no input until the first VBI reads it
        dex
        bpl     :-
        lda     #8
        sta     cur_line
        jsr     $B7BE                   ; original: sets VIC, copies tables
        jsr     copy_chargen
        lda     #9
        sta     mapped
        sta     $D500
        jsr     $8000                   ; render_init (bank 9)
        ; ANTIC: blank lines only (the VBXE overlay supplies the picture): entry 0 = lines 8-9, then one entry per line
        ; from Atari line 10, so a DLI can mark any C64 raster line from 32 on (the emulated raster IRQ); C64 9-31 (above
        ; the picture) fire at line 10, early enough for handlers like the overworld's HUD colours (line 14)
        lda     #$10
        sta     DLB
        ldx     #1
        lda     #0
:       sta     DLB,x
        inx
        cpx     #DL_LAST+1
        bne     :-
        lda     #$41
        sta     DLB,x
        lda     #<DLB
        sta     DLB+1,x
        sta     $D402
        lda     #>DLB
        sta     DLB+2,x
        sta     $D403
        lda     #0
        sta     dl_idx
        sta     ev_vbi
        lda     #0                      ; (palette entry 8 black until the renderer sets the border colour: the default
        sta     VB_PSEL                 ; grey showed for 4 frames before the title)
        lda     #8
        sta     VB_CSEL
        lda     #0
        sta     VB_CR
        sta     VB_CG
        sta     VB_CB
        lda     #8
        sta     $D01A                   ; COLBK = palette entry 8 = C64 border colour
        lda     #$20
        sta     $D400                   ; DMACTL: display list DMA only
        lda     #7
        sta     cur_bank
        sta     mapped
        sta     $D500
        lda     #0
        sta     $D20E                   ; IRQEN: no POKEY IRQs (all four channels are for sound)
        lda     #$C0
        sta     $D40E                   ; NMIEN: DLI + VBI
        jmp     $AF15                   ; original start of the loader in bank 7

        .segment "RES3"

; Every line-250 event: count title frames (4+ bands) in a row. Entering or leaving the title layout is a scene change:
; the renderer flushes its sprite shape cache (the game rewrites sprite data under the same pointers).
frz_tick:
        jsr     frz_lay
        bcs     @t
        lda     r_fcnt
        beq     :+
        sta     r_scn
        lda     #0
        sta     r_fcnt
        sta     r_frz
:       rts
@t:     lda     r_fcnt
        bne     :+
        sta     r_scn                   ; (A = 0 here: set it non-zero below)
        inc     r_scn
:       inc     r_fcnt
        bne     :+
        dec     r_fcnt
:       rts


        .segment "RES3"
; Arm the event for the $D012 just written, keeping the game's raster events in order on the C64's clock: a handler that
; runs late (its event deferred while IRQs were masked: the game's own long handlers, the band copies) and arms a line
; the C64 raster would already have reached since its event (d = C64 lines since the event's line >= dt = lines from
; it to the target, the next frame's if the target is not below it) gets it as soon as possible, not a frame later.
; Waiting lost a main-loop pass: the line-250 handler deferred to the VBI arming line 8, or a line-72 event pushed down
; the screen arming 250 when the display had passed line 228 (2-4 per second while walking).
arm_ev: lda     r_ev                    ; (a handler above line 200: the playfield's Y-scroll, render.s xv_pick)
        cmp     #200
        bcs     :+
        lda     VSH+$11
        sta     pf_y
:       jsr     virt_now                ; r_now/thi: the C64 line now
        sec
        sbc     r_ev
        sta     ae_d
        lda     thi
        sbc     #0
        bcs     :+
        lda     ae_d                    ; (wrapped: + 262)
        adc     #<262
        sta     ae_d
        lda     #0
        adc     #0
:       sta     ae_d+1
        lda     VSH+$12
        sec
        sbc     r_ev
        ldy     #0
        bcc     @nf
        bne     @cmp                    ; target below the event: dt = T - r_ev
        lda     #<262                   ; (the same line: the next frame's)
        iny
        bne     @cmp
@nf:    adc     #<262                   ; (T - r_ev + 256, C = 0) + 6: the next frame's
        bcc     @cmp
        iny
@cmp:   sta     ae_t
        lda     ae_d
        cmp     ae_t
        sty     ae_t
        lda     ae_d+1
        sbc     ae_t
        lda     VSH+$12
        bcs     @late
        jmp     arm_dl                  ; (on time: at its line)
@late:  jmp     arm_now

        .segment "RES3"
; STA $CFFE,X (bank 7 $83FC, RAM $4414): a raster-timed write (at line $58) whose target comes from a table, X >= 2 =
; VIC register X-2 (seen in a dungeon: $D000). Shadow and hooks as the patched direct writes; X 0/1 = RAM $CFFE/$CFFF.
; (The caller jumps on: the flags may change.)
hook_cffe:
        .ifdef T250                     ; (debug build ZDEFS=T250: no hook_cffe, so no dungeons; its room holds a ring of
        rts                             ; the raster events dispatched, read by polling $F6C0-$F6FF, index $F69D)
dlog:   ldx     $F69D                   ; debug ring: dispatched target, VCOUNT, frame, hc_ev
        sta     $F6C0,x
        lda     $D40B
        sta     $F6D0,x
        lda     frame_ctr
        sta     $F6E0,x
        lda     hc_ev
        sta     $F6F0,x
        inx
        txa
        and     #15
        sta     $F69D
        rts
        .else
        cpx     #2
        bcs     :+
        sta     $CFFE,x
        rts
:       cpx     #$14
        beq     @d012
        cpx     #$1A
        beq     @d018
        cpx     #$23
        bcc     @sh
        cpx     #$26
        bcs     @sh
        cpx     #$24
        bcc     @c21
        beq     @c22
        jmp     hook_c23a
@c22:   jmp     hook_c22a
@c21:   jmp     hook_c21a
@d012:  jmp     hook_d012w
@d018:  jmp     hook_d018
@sh:    cpx     #$42
        bcs     :+                      ; (beyond the 64 registers: a VIC mirror, never used)
        sta     VSH-2,x
:       rts
        .endif


        .segment "RES5"                 ; (where the title-freeze code was)
cl_b:   .byte   0                       ; (vicirq.s cl_chk temporaries)
bfull:  .byte   0                       ; the band count of the last complete frame (line 250)
cl_c:   .byte   0, 0

; Exchange the renderer's zero-page pointers with zsave (renderer <-> game): at a render's start and end (render.s
; render_frame), its yields and resumes. Not around a game IRQ that interrupts a render: the game's IRQ handlers never
; write these bytes (traced), and the extra exchanges halved the compose rate. A, X, Y used. (~350 cycles)
zswap:  ldx     #9
:       ldy     zs_adr,x
        lda     $0000,y
        pha
        lda     zsave,x
        sta     $0000,y
        pla
        sta     zsave,x
        dex
        bpl     :-
        rts
zs_adr: .byte   zscr, zscr+1, zcol, zcol+1, zshs, zshs+1, zshc, zshc+1, zcnt, zb
zsave:  .res    10

        .segment "RES6"
ys_pos: .byte   0                       ; vicirq.s: the attract screens' upward fine scroll, pixels (counted at the VBI)
ys_last: .byte  0                       ; (its Y-scroll at the last VBI)
ys_act: .byte   $FF                     ; frames since it last moved
ex_ok:  .byte   0                       ; (valid) / ex_t: frame of a hide (render.s, vicirq.s cl_chk)
ex_t:   .byte   0
sv_ws:  .byte   0                       ; last disk write's SIO status (1 ok; $8A no drive ...), 0 none yet
sv_rs:  .byte   0                       ; the boot-time read's status

        .segment "KENT"
        pha
        txa
        pha
        tya
        pha
        tsx
        lda     $0104,x
        and     #$10
        beq     @irq
        jmp     ($0316)
@irq:   jmp     ($0314)


; C = 1 if this frame's bands are the title screen's layout (lines 8, 82, then 88 or 120 ...) and the game is in its
; title/attract mode (zero page $14 = 0; the select and name screens, mode 1, use the same raster layout).
frz_lay:
        lda     $14
        bne     @n
        lda     band_n
        cmp     #4
        bcc     @r
        lda     BANDS+BAND_SZ+B_START
        cmp     #82
        bne     @n
        lda     BANDS+2*BAND_SZ+B_START
        cmp     #88
        beq     @r                      ; (equal: C = 1)
        cmp     #120
        beq     @r
@n:     clc
@r:     rts

snap_vsh:                               ; (KENT: room)
        ldx     #31
:       lda     VSH+$10,x
        sta     VSN,x
        dex
        bpl     :-
        rts


        .segment "VECT"
        .word   nmi
        .word   $F100
        .word   irq
