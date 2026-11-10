; The VIC raises its raster IRQ every frame on the line in $D012, whether or not the handler writes $D012 again. The port
; fires one event per $D012 write (hook_d012w -> arm_dl), so a handler that leaves $D012 alone stopped the raster chain:
; the overworld's line-250 handler ($420F) arms nothing once no screen scroll runs ($0DF1/$0DF8 = 0), which is what
; happens during Link's death animation (mode $11); the main loop then waited for its line-250 flag ($C102) forever.
; vbi_b12 runs in the VBI (cart bank 12 mapped, only A pushed): with no event pending and the raster IRQ enabled
; ($D01A bit 0), the $D012 line is armed again for the coming frame, as on the C64; then the sound/input update.
        .include "atari.inc"
        .export vbi_b12
        .import snd_update, arm_dl, arm_dl_end, hl, hla, hr, hv, palidx
        .import ys_pos, ys_last, ys_act, ys_c, ys_ok, ex_smp, ex_ok, ex_t, ptop, cl_b, cl_c
        .segment "SND"

vbi_b12:
        lda     ev_due                  ; an event due from a nested DLI and no DLI since: at this VBI
        beq     :+
        lsr     ev_due
        lda     #1
        sta     ev_vbi
        txa                             ; (its DLI cleared its display list bit; dl_idx, left on that entry, kept the
        pha                             ; check below from re-arming once the game's handler armed nothing: the
        ldx     dl_idx                  ; raster chain stopped for good, bug 7. Cleared unless a new event is armed)
        lda     DLB,x
        bmi     @kx
        lda     #0
        sta     dl_idx
@kx:    pla
        tax
:       lda     dl_idx                  ; an event pending (entry 0: one the VBI deferred)?
        ora     ev_vbi
        bne     @r
        lda     DLB
        bmi     @r
        lda     VSH+$1A
        lsr     a
        bcc     @r                      ; raster IRQ disabled: the VIC would not fire
        txa
        pha
        tsx                             ; $0101 X, $0102/3 our return, $0104 A, $0105 P, $0106/7 the interrupted PC
        lda     $0106,x
        cmp     #<arm_dl
        lda     $0107,x
        sbc     #>arm_dl
        bcc     @arm
        lda     $0106,x
        cmp     #<arm_dl_end
        lda     $0107,x
        sbc     #>arm_dl_end
        bcc     @x                      ; the VBI interrupted arm_dl itself: it is arming an event (state half written)
@arm:   lda     VSH+$12
        jsr     arm_dl
@x:     pla
        tax
@r:     txa
        pha
        tya
        pha
        jsr     ys_upd
        jsr     cl_chk
        jsr     den_chk
        jsr     xv_pick
        jsr     hq_build
        pla
        tay
        pla
        tax
        jmp     snd_update

; Screen scrolls: show the displayed buffer's XDL variant for the steps the game is ahead of its picture (render.s
; xdl_vars, edge_fill): k = steps whose incoming rows/columns are drawn into its edge (xv_f) - steps in its picture;
; variant 2k, +1 while the C64's fine X-scroll ($0DFD, left/right) is 4 or its playfield Y-scroll (pf_y, up/down) is 7.
; Address XV + buffer * $400 + variant * 64.
xv_pick:
        lda     r_hidden
        eor     #1
        tax                             ; the buffer on screen (the flip, if any, is done)
        lda     xv_ok,x
        bne     @sp
        lda     ys_ok,x                 ; (the attract screens' fine scroll: the picture k lines on, ys_vars)
        and     #1
        bne     :+
        jmp     @none
:       lda     ys_pos
        sec
        sbc     ys_c,x
        cmp     #16
        bcc     :+
        lda     #15
:       sta     xv_t
        jmp     @set0
@sp:
        lda     xv_f,x
        sec
        sbc     xv_s,x
        cmp     #8
        bcc     :+
        lda     #7
:       asl     a                       ; v = 2k, +1 for the fine scroll: left/right the C64's fine X-scroll ($0DFD)
        sta     xv_t                    ; 4, up/down the playfield's Y-scroll 7 (resident arm_ev: pf_y)
        ldy     xv_dir,x
        cpy     #2
        bcc     @vert
        lda     $0DFD
        and     #4
        beq     @set0
        inc     xv_t
        bne     @set0
; Y-scroll 7 moves the playfield 4 lines down: half a step ahead while the picture moves down, behind while it moves
; up. The game's Y-scroll belongs to its newest step, the shown k may lag it: positions along the motion
; (p = v down, v xor 1 up) never go back for one picture (they jittered by 4 lines).
@vert:  lda     pf_y
        and     #4
        beq     :+
        inc     xv_t
:       lda     xv_t
        cpy     #0
        bne     :+
        eor     #1                      ; (up: p = 2k + 1 - fine)
:       cpx     xv_lb
        bne     @new                    ; another picture
        cmp     xv_lp
        bcs     @new
        lda     xv_lv                   ; behind the last one shown: keep that
        sta     xv_t
        jmp     @set0
@new:   sta     xv_lp
        stx     xv_lb
        lda     xv_t
        sta     xv_lv
@set0:  lda     xv_t
        and     #3
        lsr     a
        ror     a
        ror     a
        sta     VB_XDL                  ; (v & 3) * 64
        lda     xv_t
        lsr     a
        lsr     a
        sta     xv_t
        txa
        asl     a
        asl     a
        clc
        adc     xv_t
        adc     #>XV
        sta     VB_XDL+1                ; >XV + buffer * 4 + (v >> 2)
        lda     #^XV
        sta     VB_XDL+2
        rts
@none:  lda     #$FF
        sta     xv_lb                   ; (no scroll picture: the next one starts afresh)
        rts

; A screen cleared by the game (a new screen: the title -> the select screen, -> the story, a menu): the picture
; would show the old screen in the new screen's colours (they apply at once) until the renderer has caught up, up to
; ~70 frames on the CPU-bound title. 6 or more of the 12 sample cells (render.s shift_check) differ from the shown
; picture's (ex_smp, at each compose) and all 12 hold one character now: hidden at once (r_blank 6, render.s shows it
; again once caught up). Not in normal play (mode 5), nor while hidden already.
cl_chk: lda     ex_ok
        beq     @r
        lda     r_blank
        bne     @r
        lda     $14
        cmp     #5
        beq     @r
        lda     $81                     ; (a zero-page pointer, saved: the VBI interrupts anything)
        pha
        lda     $82
        pha
        lda     ptop                    ; screen base high byte (render.s rbase)
        lsr     a
        lsr     a
        and     #$3C
        sta     cl_b
        ldy     #0                      ; Y: samples that differ from the picture's
        ldx     #11
@l:     lda     cl_lo,x
        sta     $81
        lda     cl_hi,x
        clc
        adc     cl_b
        sta     $82
        tya
        pha
        ldy     #0
        lda     ($81),y
        sta     cl_c+1                  ; (this sample)
        pla
        tay
        lda     cl_c+1
        cpx     #11
        bne     :+
        sta     cl_c                    ; (the first sample's character)
:       cmp     cl_c
        bne     @x                      ; (not all one character: no clear)
        cmp     ex_smp,x
        beq     :+
        iny
:       dex
        bpl     @l
        cpy     #6
        bcc     @x
        lda     #6
        sta     r_blank
        lda     #0
        sta     VB_CORE
        lda     frame_ctr
        sta     ex_t
@x:     pla
        sta     $82
        pla
        sta     $81
@r:     rts
cl_lo:  .byte   $59, $E6, $51, $BD, $52, $BD, $2C, $EA, $0D, $37, $1B, $41
cl_hi:  .byte   $00, $00, $01, $01, $02, $02, $03, $02, $00, $00, $00, $00

; The C64's display enable ($D011 bit 4): off, the VIC shows only the border colour. The game switches it off
; between screens (START on the title, the menus) while it recolours and rewrites them: the port kept showing the old
; screen (in the new colours) until it had redrawn the new one, ~70 frames. Off: the overlay off (the border colour,
; palette entry 8, everywhere); on again: the overlay on, unless the port hides the picture itself (r_blank).
den_chk:
        lda     r_blank
        bne     @r
        lda     VSH+$11
        and     #$10
        beq     :+
        lda     #1
:       sta     VB_CORE
@r:     rts

; The attract screens' upward fine scroll position: + the Y-scroll steps since the last VBI (7 -> 0, then 7 again with
; a row shift); a step back (7) is not counted.
ys_upd: lda     VSH+$11
        and     #7
        tax
        lda     ys_last
        stx     ys_last
        sec
        sbc     ys_last
        and     #7
        beq     @st
        cmp     #7
        bcs     @r                      ; (7: one line down, no upward scroll step; the game skips steps when late)
        clc
        adc     ys_pos
        sta     ys_pos
        lda     #0
        sta     ys_act
@r:     rts
@st:    lda     ys_act
        cmp     #$FF
        beq     @r
        inc     ys_act
        rts

; This frame's colour-split queue for the DLIs (colour.s hc_rep): the live split entries (hc_vbi has aged them), sorted
; by their DLI line (VCOUNT = Atari line / 2), with the palette index and the colour ready.
hq_build:
        ldx     #0
        ldy     #3
@c:     lda     hl,y
        beq     @n
        lda     hla,y
        lsr     a
        sta     hq_line,x
        lda     hv,y
        and     #15
        sta     hq_col,x
        sty     hq_t
        lda     hr,y
        tay
        lda     palidx,y
        sta     hq_pal,x
        ldy     hq_t
        inx
@n:     dey
        bpl     @c
        stx     hq_n
        cpx     #2                      ; insertion sort by line (at most 4)
        bcc     @done
        ldx     #1
@o:     stx     hq_t
@i:     lda     hq_line-1,x
        cmp     hq_line,x
        bcc     @ok
        beq     @ok
        ldy     hq_line,x               ; swap entries x-1 and x
        sta     hq_line,x
        tya
        sta     hq_line-1,x
        lda     hq_pal,x
        ldy     hq_pal-1,x
        sta     hq_pal-1,x
        tya
        sta     hq_pal,x
        lda     hq_col,x
        ldy     hq_col-1,x
        sta     hq_col-1,x
        tya
        sta     hq_col,x
        dex
        bne     @i
@ok:    ldx     hq_t
        inx
        cpx     hq_n
        bcc     @o
@done:  lda     #0
        sta     hq_i
        rts
