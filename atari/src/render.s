; VBXE renderer for the C64 text screen: runs in bank 9, called from the VBI NMI (render_frame) and once at boot (render_init).
        .include "atari.inc"
        .import fullscan, ryield, snap_vsh, copy_bands, merge_bands, sh_qc
        .import ys_pos, ys_last, ys_act, ys_c, ys_ok, r_ysp, ex_smp, ex_ok, ex_t
        .import rgb_r, rgb_g, rgb_b, palidx, hc_busy
        .import pf_d018, pf_life, pf_line, psn, psr, pf_top, ptop, sr_end
        .import pf_steps, pf_done, pf_new, pf_ff, pd_dir, pd_k, pd_pl, pd_t, pd_kc, pd_s
        .import zswap
        .segment "B9CODE"
        jmp     render_init
        jmp     render_frame_z

; Every render (idle-time or VBI) with the renderer's own zero-page pointers, the game's restored after (resident.s zswap:
; the pointers are game object data, HANDOFF bug 5).
render_frame_z:
        jsr     zswap
        jsr     render_frame
        jmp     zswap

WINB    = $80                   ; VB_MEMS value for VRAM bank 0 (4 KB units)

; ---------------------------------------------------------------------------------------------------------------
vx_wait:
        lda     VB_BLGO
        beq     :+
        jsr     ryield                  ; (the blitter is busy: the game may have work; a BG shift waiting for the
        jmp     vx_wait                 ; last compose's blits could keep the CPU most of a frame)
:       ldx     #8
:       dex
        bne     :-
        lda     VB_BLGO
        bne     vx_wait
        rts

; Load the 21-byte template at tpl_ptr (A=lo, X=hi) into VRAM block BLK (window must be at bank 0).
load_tpl:
        sta     zscr
        stx     zscr+1
        ldy     #20
:       lda     (zscr),y
        sta     WIN+BLK,y
        dey
        bpl     :-
        rts

set_bl: lda     #<BLK
        sta     VB_BL
        lda     #>BLK
        sta     VB_BL+1
        lda     #0
        sta     VB_BL+2
        rts

; ---------------------------------------------------------------------------------------------------------------
render_init:
        lda     #0
        sta     r_fin
        lda     #MEMC_ON
        sta     VB_MEMC
        lda     #WINB
        sta     VB_MEMS
        ; palette 0: fixed fg colours at 4*(c+1)+3
        lda     #0
        sta     VB_PSEL
        ldx     #0
@pal:   txa
        clc
        adc     #1
        asl     a
        asl     a
        ora     #2
        sta     VB_CSEL
        lda     rgb_r,x
        sta     VB_CR
        lda     rgb_g,x
        sta     VB_CG
        lda     rgb_b,x
        sta     VB_CB
        inx
        cpx     #16
        bne     @pal
        lda     #$FF
        ldx     #5
:       sta     r_pal,x                 ; force the first palette update
        dex
        bpl     :-
        ; XDL
        ldx     #xdl_end-xdl-1          ; one XDL per display buffer (D0 at 0, D1 at $20); the VBI selects one
:       lda     xdl,x
        sta     WIN,x
        sta     WIN+$20,x
        dex
        bpl     :-
        lda     #0
        sta     VB_XDL
        sta     VB_XDL+1
        sta     VB_XDL+2
        sta     xv_ok
        sta     xv_ok+1
        lda     #3
        sta     r_fq                    ; (full compares every 4th render until the screen is still)
        ; clear BG and both display buffers to value 1 (bg0)
        jsr     set_bl
        lda     #<tpl_clear_bg
        ldx     #>tpl_clear_bg
        jsr     load_tpl
        jsr     blit
        .repeat 4, k                    ; blitter width is 9 bits (max 512): clear each buffer in two halves
        .if k = 0
        lda     #<tpl_clear_d0
        ldx     #>tpl_clear_d0
        .elseif k = 1
        lda     #<tpl_clear_d0b
        ldx     #>tpl_clear_d0b
        .elseif k = 2
        lda     #<tpl_clear_d1
        ldx     #>tpl_clear_d1
        .else
        lda     #<tpl_clear_d1b
        ldx     #>tpl_clear_d1b
        .endif
        jsr     load_tpl
        jsr     blit
        .endrepeat
        ldx     #0
        txa
:       sta     BLANKT,x
        inx
        bne     :-
        ldx     #0                      ; hot-row counters
        txa
:       sta     r_hot,x
        inx
        cpx     #52
        bne     :-
        ; prefill the cell chain: 36 copies of tpl_cell with NEXT set
        lda     #<(WIN+CBLK)
        sta     zshs
        lda     #>(WIN+CBLK)
        sta     zshs+1
        lda     #36
        sta     zcnt
@pf:    ldy     #20
:       lda     tpl_cell,y
        sta     (zshs),y
        dey
        bpl     :-
        ldy     #20
        lda     #8
        sta     (zshs),y
        lda     zshs
        clc
        adc     #21
        sta     zshs
        bcc     :+
        inc     zshs+1
:       dec     zcnt
        bne     @pf
        lda     #0
        sta     r_fsc
        sta     r_ttl
        sta     r_hold
        lda     #$FF
        sta     r_cbase
        lda     #0
        sta     r_holdn
        .ifdef DCHK
        sta     $F676
        .endif
        sta     r_ys7
        sta     r_flip
        sta     r_dv
        sta     r_dv+1
        sta     r_cdn
        sta     r_cdn+1
        sta     sr_n
        sta     sr_n+1
        sta     r_gen
        sta     ov_lo
        sta     ov_hi
        sta     vslot
        sta     dv_lo
        sta     dv_hi
        lda     #VB1                    ; old-piece lists empty
        sta     VB_MEMS
        lda     #0
        .repeat 10, k
        sta     WIN + OB_OFF + k*OB_SZ
        sta     WIN + OB_OFF + k*OB_SZ + 1
        sta     WIN + OB_OFF + k*OB_SZ + 2
        .endrepeat
        lda     #$FF                    ; band caches empty
        .repeat 5, k
        sta     WIN + BC_OFF + k*176 + 44
        .endrepeat
        lda     #0
        ldx     #0
:       sta     CD0,x
        sta     CD0+$80,x
        inx
        bpl     :-
        ; compose block lists in VRAM bank 1: restore blocks, then sprite blocks
        lda     #$80+(CL >> 12)
        sta     VB_MEMS
        ldx     #0
@cl:    lda     cl_lo,x
        sta     zshs
        lda     cl_hi,x
        sta     zshs+1
        ldy     #20
        cpx     #CL_SPR
        bcs     @cls
:       lda     tpl_restore,y
        sta     (zshs),y
        dey
        bpl     :-
        bmi     @cln
@cls:
:       lda     tpl_sprite,y
        sta     (zshs),y
        dey
        bpl     :-
@cln:   inx
        cpx     #CL_N
        bne     @cl
        lda     #WINB
        sta     VB_MEMS
        ; sprite cache keys invalid
        ldx     #0
        lda     #$FF
:       sta     WIN+SPK_COL,x
        sta     WIN+SPK_S,x
        lda     #0
        sta     WIN+SPK_RR,x
        lda     #$FF
        inx
        cpx     #64
        bne     :-
        ; shadows: screen 0, colour $FF (everything dirty)
        ldx     #0
:       lda     #0
        sta     WIN+SHS,x
        sta     WIN+SHS+$100,x
        sta     WIN+SHS+$200,x
        sta     WIN+SHS+$300,x
        lda     #$FF
        sta     WIN+SHC,x
        sta     WIN+SHC+$100,x
        sta     WIN+SHC+$200,x
        sta     WIN+SHC+$300,x
        inx
        bne     :-
        ; atlas: build all 8 segments from whatever the charset area holds now
        lda     #0
        sta     r_hidden
        sta     r_scanrow
        sta     r_aseg
        ldx     #0
@seg:   stx     r_tmp
        jsr     build_segment
        ldx     r_tmp
        inx
        cpx     #8
        bne     @seg
        ldx     #15
        lda     #$FF
:       sta     r_chsum,x               ; every segment differs from the first real checksum
        dex
        bpl     :-
        lda     #0
        sta     VB_CORE                 ; overlay off: black until the title screen is complete (r_blank)
        lda     #1
        sta     r_blank
        lda     #WINB
        sta     VB_MEMS
        lda     #0
        sta     VB_MEMC
        rts

; one blit from the block at BLK
blit:   jsr     vx_wait
        lda     #1
        sta     VB_BLGO
        jmp     vx_wait

; (from resident.s: only the renderer calls it)
; The renderer's snapshot of the VIC registers and sprite bands (the latest complete frame, or this frame's bands so far).
render_snap:
        php
        sei
        jsr     snap_vsh
        lda     ys_last                 ; (the fine-scroll position of this snapshot: the VBI's, plus the Y-scroll
        sec                             ; steps since)
        sbc     VSN+$01
        and     #7
        clc
        adc     ys_pos
        sta     r_ysp
        lda     r_ev
        cmp     #250
        bcc     :+
        lda     cb_pend                 ; (the line-250 event published them, unless a render was reading RBANDS)
        beq     :++
        jsr     copy_bands
        jmp     :++
:       jsr     merge_bands
:       lda     #0
        sta     cb_pend
        lda     r_pass
        sta     r_p0
        plp
        rts

; ---------------------------------------------------------------------------------------------------------------
render_frame:
        .ifdef DCHK
        inc     $F676                   ; debug: a render is in progress
        jsr     @in
        dec     $F676
        rts
@in:
        .endif
        lda     #MEMC_ON
        sta     VB_MEMC
        lda     #WINB
        sta     VB_MEMS
        lda     #3
        sta     r_try
        .ifdef RTL
        pha
        lda     #1
        sta     $F0BA                   ; (debug: in the scan phase)
        jsr     rtl
        pla
        .endif
@again: jsr     render_snap             ; VIC registers and sprite bands of this moment
        lda     r_blank                 ; hidden start-up before the title's character set is in use: nothing to do
        cmp     #1                      ; (the cart's credit screen is never shown: building its glyphs and cells,
        bne     :+                      ; from the VBI while the game sat in its delay loops, took ~99% of the CPU
        lda     VSN+$08                 ; and stretched those loops)
        cmp     #$2E
        beq     :+
        lda     frame_ctr
        sta     r_t2e
        lda     #0
        sta     VB_MEMC
        rts
:       jsr     pf_snap                 ; (and the playfield's screen base while the screen scrolls)
        lda     $D40B
        sta     $F0B5
        jsr     palette_update
        lda     $D40B
        sta     $F0B6
        jsr     atlas_check
        jsr     ryield
        lda     $D40B
        sta     $F0B7
        lda     in_gfx
        beq     :+
        lda     #0
        sta     VB_MEMC
        rts                             ; the game is rewriting the screen: keep showing the last frame
:       lda     r_blank                 ; hidden start-up: a full compare every 4th render, no sprites, to get the
        cmp     #1                      ; title screen into BG (every render starved the game: 14 passes per 60
        bne     @h6                     ; frames, the title came ~6 s late); also hidden after a rewrite (6)
        inc     r_rcnt
        lda     r_rcnt
        and     #3
        beq     @hf
        bne     :+
@h6:    cmp     #6
        bne     :+
        lda     frame_ctr               ; (hidden at most ~45 frames: a screen that keeps changing never settles)
        sec
        sbc     ex_t
        cmp     #45
        bcc     @hf
        lda     #2
        sta     r_blank
        bne     :+
@hf:    lda     #1
        sta     r_fsc
:       lda     psr
        cmp     #25
        bcs     :+
        jsr     pf_shift                ; the playfield has its own screen base: the overworld scrolls
        jmp     :++
:       jsr     shift_check
:       jsr     scan_chunk
        .ifdef RTL
        pha
        lda     #0
        sta     $F0BA
        lda     #5
        jsr     rtl
        pla
        .endif
        lda     psr                     ; (not with the split on: the playfield's Y-scroll changes every frame)
        cmp     #25
        bcc     :+
        lda     VSH+$11                 ; the screen scrolled meanwhile: snapshot and scan again (text and sprites
        eor     VSN+$01                 ; must belong to the same moment)
        and     #7
        beq     :+
        .ifdef RTL
        pha
        lda     #6
        jsr     rtl
        pla
        .endif
        dec     r_try
        beq     :+
        jmp     @again
:       jsr     ryield
        lda     $D40B
        sta     $F0B8
        jsr     compose
        lda     $D40B
        sta     $F0B9
        lda     #0
        sta     VB_MEMC
        rts

; ---------------------------------------------------------------------------------------------------------------
; End of the black screen after the title: the next composed frame (all of BG, after a full compare) switches the
; overlay on again.
bl_end: lda     #2
        sta     r_blank
        lda     #0
        sta     r_ttl
        sta     r_dv
        sta     r_dv+1
        lda     #1
        sta     r_fsc
        rts

; border -> palette entry 8 when its shadow changed (bg0..2 are set live by the game's writes: colour.s), sprite
; shared colours. IRQs off around the palette writes (an emulated IRQ's colour hook would interleave its own), none
; while a colour hook is half way (a VBI render interrupted it). hc_busy is set meanwhile: a DLI's colour splits
; (colour.s hc_rep, an NMI: SEI does not stop it) would write their entries between our select and colour writes, and
; ours would land in the entry after theirs (as in HANDOFF bug 3). A split skipped meanwhile is set by the next DLI.
; (Not hc_rq here: in the vertical blank it set the whole new frame's queue at once; the title came 60 frames later.)
palette_update:
        lda     hc_busy
        bne     :+
        php
        sei
        inc     hc_busy
        jsr     pu_body
        dec     hc_busy
        plp
:       rts
pu_body:
        lda     r_blank                 ; the title's fade (its colours $D022/$D023 change) blanks the screen until
        bne     @pb                     ; the scroller starts (its first row shift)
        lda     r_frz
        beq     @nt
        lda     VSN+$13
        asl     a
        asl     a
        asl     a
        asl     a
        sta     r_tk
        lda     VSN+$12
        and     #15
        ora     r_tk
        ldx     r_ttl
        bne     :+
        sta     r_tc                    ; (the frozen title's colours)
        inc     r_ttl
        bne     @pal
:       cmp     r_tc
        beq     @pal
@bl:
        .ifdef OLDBLANK
        lda     #5
        sta     r_blank
        .else
        jmp     @pal                    ; (no blanking: the fade, the dim title and the black as the C64)
        .endif
        lda     #0
        sta     VB_CORE
        sta     r_bto
        lda     frame_ctr
        sta     r_t2e
        jmp     @pal
@nt:    lda     r_ttl                   ; (title unfrozen meanwhile: blank once its colours are black)
        beq     @pal
        lda     VSN+$12
        ora     VSN+$13
        and     #15
        beq     @bl
        bne     @pal
@pb:    cmp     #5                      ; blanked after the title: show the story screen as soon as it starts (title
        bne     @pal                    ; layout gone, no sprites, its colours set), after ~15 s at most
        lda     r_frz
        ora     VSH+$15                 ; (sprite enables: not in the snapshot)
        bne     :+
        lda     rband_n                 ; and the title's sprite bands have left the drawn ones
        cmp     #4
        bcs     :+
        lda     VSN+$12
        and     #15
        beq     :+
        jsr     bl_end
        jmp     @pal
:       lda     frame_ctr
        sec
        sbc     r_t2e
        bpl     @pal
        lda     r_t2e
        eor     #$80
        sta     r_t2e
        inc     r_bto
        lda     r_bto
        cmp     #7
        bcc     @pal
        jsr     bl_end
@pal:   ldx     #0                      ; (border only)
@l:     lda     VSN+$10,x
        and     #15
        cpx     #0
        bne     :+
        ldy     r_blank                 ; (border black while the start-up screens are hidden)
        beq     :+
        lda     #0
:
        cmp     r_pal,x
        beq     @n
        sta     r_pal,x
        tay
        stx     ztmp
        lda     #0
        sta     VB_PSEL
        lda     palidx,x
        sta     VB_CSEL
        lda     rgb_r,y
        sta     VB_CR
        lda     rgb_g,y
        sta     VB_CG
        lda     rgb_b,y
        sta     VB_CB
        ldx     ztmp
@n:     dex
        bpl     @l
        ldx     #1
@sp:    lda     VSN+$15,x
        and     #15
        cmp     r_pal+4,x
        beq     @sn
        sta     r_pal+4,x
        tay
        txa
        clc
        adc     #4
        sta     VB_CSEL
        lda     #0
        sta     VB_PSEL
        lda     rgb_r,y
        sta     VB_CR
        lda     rgb_g,y
        sta     VB_CG
        lda     rgb_b,y
        sta     VB_CB
@sn:    dex
        bpl     @sp
        rts

; ---------------------------------------------------------------------------------------------------------------
; Atlas: 8 segments of 32 glyphs; one segment checksum per frame; a changed one is rebuilt and the whole screen marked dirty.
; A = segment (0..7). Sets zscr to 256 bytes of the C64 character set for it: the RAM address, or - when the VIC would read the
; character ROM ($1000-$1FFF in VIC banks 0 and 2) - a RAM copy of that part of the ROM. Leaves the window on bank 0.
set_charsrc:
        sta     sw_t2
        lda     $DD00
        eor     #3
        and     #3
        sta     sw_t3                   ; VIC bank
        lda     VSN+$08
        and     #$0E
        asl     a
        asl     a
        sta     sw_t4                   ; character set address high byte inside the bank
        lda     sw_t3
        and     #1
        bne     @ram                    ; banks 1 and 3 have no character ROM
        lda     sw_t4
        cmp     #$10
        beq     @rom
        cmp     #$18
        bne     @ram
@rom:   sec
        sbc     #$10
        clc
        adc     sw_t2                   ; high byte of the offset into the 4 KB ROM
        adc     #>WIN
        sta     zscr+1
        lda     #0
        sta     zscr
        lda     #$80+(CHROM >> 12)
        sta     VB_MEMS
        ldy     #0
:       lda     (zscr),y
        sta     CHBUF,y
        iny
        bne     :-
        lda     #<CHBUF
        sta     zscr
        lda     #>CHBUF
        sta     zscr+1
        lda     #WINB
        sta     VB_MEMS
        rts
@ram:   lda     sw_t3
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a                       ; bank * $40 00
        clc
        adc     sw_t4
        clc
        adc     sw_t2
        sta     zscr+1
        lda     #0
        sta     zscr
        rts

charbase_hi:                            ; -> A = high byte of the C64 character set address
        lda     VSN+$08
        and     #$0E
        asl     a
        asl     a
        rts

atlas_check:
        lda     #0
        sta     at_f
        lda     VSN+$08                 ; where the character set is: VIC bank + $D018 bits
        and     #$0E
        sta     sw_t2
        lda     $DD00
        and     #3
        asl     a
        asl     a
        asl     a
        asl     a
        ora     sw_t2
        cmp     r_cbase
        beq     :+
        sta     r_cbase                 ; it moved: check every segment now, invalidate the screen once
        lda     #8
        sta     at_n
        bne     @seg
:       lda     frame_ctr               ; one segment per 4 frames since the last check (renders may be rare)
        sec
        sbc     at_last
        lsr     a
        lsr     a
        bne     :+
        rts
:       cmp     #1                      ; (at most 1 per render: renders may be far apart)
        bcc     :+
        lda     #1
:       sta     at_n
        lda     frame_ctr
        sta     at_last
@seg:   lda     r_aseg
        and     #7
        sta     ztmp
        inc     r_aseg
        lda     ztmp
        jsr     set_charsrc
        lda     #0
        sta     zcnt                    ; checksum hi
        tay
        clc                             ; (checksum lo in A: the same 16-bit sum, faster)
@s:     adc     (zscr),y
        bcc     :+
        inc     zcnt
        clc
:       iny
        bne     @s
        sta     zb                      ; checksum lo
        lda     ztmp
        asl     a
        tax
        lda     zb
        cmp     r_chsum,x
        bne     @diff
        lda     zcnt
        cmp     r_chsum+1,x
        beq     @nx
@diff:
        .ifdef LOOPCOUNT
        inc     $F6F5                   ; debug: atlas segment rebuilds
        lda     ztmp
        sta     $F6E0
        lda     r_chsum,x
        sta     $F6E1
        lda     r_chsum+1,x
        sta     $F6E2
        lda     zb
        sta     $F6E3
        lda     zcnt
        sta     $F6E4
        lda     zscr+1
        sta     $F6E5
        .endif
        lda     zb
        sta     r_chsum,x
        lda     zcnt
        sta     r_chsum+1,x
        ldx     ztmp
        jsr     build_segment
        lda     at_f                    ; the first change: check every other segment now too (a charset being
        bne     :+                      ; loaded then costs one redraw of the screen, not eight)
        lda     #8
        sta     at_n
:       inc     at_f
@nx:    dec     at_n
        bne     @seg
        lda     at_f
        bne     :+
        rts
:       lda     #40
        sta     r_noblank
        lda     #WINB
        sta     VB_MEMS
        ldx     #0                      ; glyphs changed: every cell is drawn again
        lda     #$FF
:       sta     WIN+SHC,x
        sta     WIN+SHC+$100,x
        sta     WIN+SHC+$200,x
        sta     WIN+SHC+$300,x
        inx
        bne     :-
        rts

; Build both glyph variants of segment X (0..7) from the C64 character set. Clobbers zscr, zshs, zb, zcnt, zy, ztmp.
build_segment:
        stx     zy                      ; segment
        txa
        and     #1
        asl     a
        asl     a
        asl     a                       ; (seg&1)*8 -> high byte offset $800
        sta     zrow
        lda     #0
        sta     zmc                     ; pass 0: hires, 1: multicolour
@pass:  lda     zy
        jsr     set_charsrc
        ; window bank: ATLAS_H bank 16, ATLAS_M bank 20, + seg>>1
        lda     zy
        lsr     a
        clc
        adc     #16+$80
        ldx     zmc
        beq     :+
        adc     #4
:       sta     VB_MEMS
        lda     #0
        sta     zshs
        lda     #>WIN
        clc
        adc     zrow
        sta     zshs+1
        ldy     #0                      ; source index (wraps after 256)
@byte:  lda     (zscr),y
        sta     zb
        sty     zcnt
        lda     zmc
        bne     @mc
        ldy     #0
@hb:    asl     zb
        lda     #0
        bcc     :+
        lda     #$FF
:       sta     (zshs),y
        iny
        cpy     #8
        bne     @hb
        beq     @adv
@mc:    ldy     #0
        lda     #4
        sta     ztmp
@mp:    lda     zb
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        tax
        lda     mctab,x
        sta     (zshs),y
        iny
        sta     (zshs),y
        iny
        asl     zb
        asl     zb
        dec     ztmp
        bne     @mp
@adv:   lda     zshs
        clc
        adc     #8
        sta     zshs
        bcc     :+
        inc     zshs+1
:       ldy     zcnt
        iny
        bne     @byte
        inc     zmc
        lda     zmc
        cmp     #2
        bne     @pass
        ; blank-glyph flags for this segment's 32 glyphs
        lda     zy
        jsr     set_charsrc
        lda     zy
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        tax                             ; first glyph of the segment
        ldy     #0
@g:     lda     #0
        sta     sw_t3
        lda     #8
        sta     zcnt
@bb:    lda     (zscr),y
        ora     sw_t3
        sta     sw_t3
        iny
        dec     zcnt
        bne     @bb
        lda     sw_t3
        beq     :+
        lda     #0
        beq     @st
:       lda     #1
@st:    sta     BLANKT,x
        inx
        tya
        bne     @g
        rts
mctab:  .byte   0, 2, 3, $FF

; ---------------------------------------------------------------------------------------------------------------
; Scan 5 text rows per frame against the shadow; draw changed cells into BG with one blit each.
scan_chunk:
        lda     #WINB
        sta     VB_MEMS
        lda     r_noblank
        beq     :+
        dec     r_noblank
:       lda     #0
        sta     r_dirty
        sta     sw_cells
        sta     sw_full
        ; after a row shift, and on scroll step frames (Y-scroll 7): exact full compare, every changed row is redrawn now
        lda     r_fsc
        beq     :+
        lda     #0
        sta     r_fsc
        jmp     @fsc
:       lda     psr                     ; (not while the overworld scrolls: the steps move BG, hot rows do the rest;
        cmp     #25                     ; nor its Y-scroll-7 compare below, for the title's scroller: with the split
        bcs     :+                      ; on the snapshot catches 3 or 7, and each full compare took ~17 frames of
        jmp     @nofull                 ; the little time a scroll leaves: no compose, the picture stood still)
:
        inc     r_rcnt                  ; and every 4th render while the screen changes (the last full compare found
        lda     r_rcnt                  ; rows to redraw), every 16th while it is still: a whole-screen change (title
        and     r_fq                    ; set-up, a cave, a menu) is found at once
        bne     :+
        jmp     @fsc
:       lda     VSN+$01
        and     #7
        cmp     #7
        beq     :+
        lda     #0
        sta     r_ys7
        jmp     @nofull
:       lda     r_ys7
        cmp     #2
        bcc     :+
        jmp     @nofull                 ; only the two frames after the scroll step
:       inc     r_ys7
@fsc:   lda     ptop
        and     #$F0
        .ifdef RTL
        pha
        lda     #7
        jsr     rtl
        pla
        .endif
        cmp     #$20                    ; the generated compare assumes the screen at $0800
        beq     :+
        jmp     @nofull
:
        ldx     #24
        lda     #0
:       sta     ROWF,x
        dex
        bpl     :-
        jsr     fullscan
        ldx     #24                     ; next full compares: every 4th render if rows differed, else every 16th
        lda     #0
:       ora     ROWF,x
        dex
        bpl     :-
        cmp     #1
        lda     #15
        bcc     :+
        lda     #3
:       ldx     $14                     ; (menus, caves, the death and continue screens: every 2nd render; their
        beq     :+                      ; new screens are mostly blank, the quick test's samples miss them, and the
        cpx     #5                      ; old screen showed under the new one for ~20 frames; the game leaves the
        beq     :+                      ; renderer time there)
        lda     #1
:       sta     r_fq
        lda     psn                     ; (it compares the screen at $0800: rows with another playfield base are all
        eor     ptop                    ; scanned)
        and     #$F0
        beq     :++
        ldx     psr
        lda     #1
:       cpx     #25
        bcs     :+
        sta     ROWF,x
        inx
        bne     :-
:       lda     #0
        sta     fs_cells
        sta     zrow
@fr:    jsr     ryield
        jsr     pf_check
        ldx     zrow
        lda     ROWF,x
        beq     :+
        jsr     scan_row
:       inc     zrow
        lda     zrow
        cmp     #25
        bcc     @fr
        .ifdef RTL
        pha
        lda     #8
        jsr     rtl
        pla
        .endif
        ldx     #24                     ; everything was just verified: no row needs watching
        lda     #0
:       sta     r_hot,x
        dex
        bpl     :-
        lda     r_blank                 ; hidden start-up: BG is now the whole screen; show it once the title's
        beq     @tr                     ; character set has been in use for 30 frames
        cmp     #1
        bne     @fsd
        lda     VSN+$08
        cmp     #$2E
        beq     :+
        lda     frame_ctr
        sta     r_t2e                   ; (not yet: restart the wait)
        jmp     @fsd
:       lda     fs_cells                ; and the screen is settled: this compare needed few redraws
        cmp     #100
        bcs     @fsd
        jsr     distinct                ; and it is the real picture (the title uses many characters), not the
        cmp     #48                     ; half-written screen the game shows while it sets it up
        bcc     @fsd
        jsr     distinct                ; and it is the real picture (the title uses many characters), not the
        cmp     #48                     ; half-written screen the game shows while it sets it up
        bcc     @fsd
        lda     frame_ctr
        sec
        sbc     r_t2e
        cmp     #30
        bcc     @fsd
        lda     #2
        sta     r_blank
        bne     @fsd
@tr:    lda     $14                     ; (title/attract only: r_ttl stays set from the title, and distinct() is slow)
        bne     @fsd
        lda     r_ttl                   ; the title's screen cleared (the fade to the story): black until the scroller
        beq     @fsd                    ; starts (its first row shift)
        .ifdef OLDBLANK
        jsr     distinct
        cmp     #8
        bcs     @fsd
        lda     #5
        sta     r_blank
        lda     #0
        sta     VB_CORE
        .endif
@fsd:   lda     r_blank                 ; hidden after a rewrite: shown again from the first full compare that found
        cmp     #6                      ; nothing left to draw (this render composes it, the VBI switches it on)
        bne     @nofull
        lda     r_dirty
        bne     @nofull
        lda     #2
        sta     r_blank
@nofull:
        ; up to 5 hot rows (rows that changed recently), starting after the last one served
        lda     #3
        sta     sw_n2
        lda     #25
        sta     sw_cnt
@hl:    jsr     ryield
        jsr     pf_check
        ldx     r_hotp
        inx
        cpx     #25
        bcc     :+
        ldx     #0
:       stx     r_hotp
        lda     r_hot,x
        beq     @hn
        sec
        sbc     #1
        sta     r_hot,x
        stx     zrow
        jsr     scan_row
        lda     sw_full
        bne     @hdone
        lda     r_dirty
        cmp     #40
        bcs     @hdone
        dec     sw_n2
        beq     @hdone
@hn:    dec     sw_cnt
        bne     @hl
        .ifdef RTL
        pha
        lda     #9
        jsr     rtl
        pla
        .endif
@hdone: lda     sw_full
        bne     @flush
        ; one rotating row so nothing is ever missed
        jsr     ryield
        jsr     pf_check
        ldx     r_scanrow
        stx     zrow
        inc     r_scanrow
        lda     r_scanrow
        cmp     #25
        bcc     :+
        lda     #0
        sta     r_scanrow
:       jsr     scan_row
        .ifdef RTL
        pha
        lda     #10
        jsr     rtl
        pla
        .endif
@flush: jmp     flush_cells

; A = number of different character codes in the 1 KB of screen RAM (saturating at 255). Uses DSET (32 bytes).
distinct:
        ldx     #31
        lda     #0
:       sta     DSET,x
        dex
        bpl     :-
        sta     sw_t2
        sta     zscr
        lda     VSN+$08
        lsr     a
        lsr     a
        and     #$3C
        sta     zscr+1
        lda     #4
        sta     sw_t4
@pg:    ldy     #0
@c:     lda     (zscr),y
        tax
        lsr     a
        lsr     a
        lsr     a
        sta     sw_t3
        txa
        and     #7
        tax
        lda     bitm,x
        sta     ztmp
        ldx     sw_t3
        and     DSET,x
        bne     @n
        lda     ztmp
        ora     DSET,x
        sta     DSET,x
        inc     sw_t2
        bne     @n
        dec     sw_t2
@n:     iny
        bne     @c
        inc     zscr+1
        dec     sw_t4
        bne     @pg
        lda     sw_t2
        rts

; Run the queued cell blits (prefilled chain at CBLK) and empty the queue. Preserves Y and the row pointers.
flush_cells:
        ldx     sw_cells
        beq     @none
        dex
        lda     cb_lo,x
        sta     zcnt
        lda     cb_hi,x
        sta     zb
        ldy     #20
        lda     #0
        sta     (zcnt),y                ; end of the chain
        jsr     vx_wait                 ; the previous frame's compose chain reads BG
        lda     #<CBLK
        sta     VB_BL
        lda     #>CBLK
        sta     VB_BL+1
        lda     #0
        sta     VB_BL+2
        lda     #1
        sta     VB_BLGO
        jsr     vx_wait
        ldy     #20
        lda     #8
        sta     (zcnt),y                ; chain link restored for the next frame
        lda     #0
        sta     sw_cells
        jsr     set_bl
@none:  rts

; Self-healing: redraw 12 cells per frame unconditionally, cycling through the whole screen (about 1.4 s per pass), so a cell
; that ever goes stale is repaired.
force_refresh:
        lda     #12
        sta     sw_cnt
@f:     lda     sw_cells
        cmp     #36
        bcs     @fd
        lda     r_frow
        sta     zrow
        jsr     row_ptrs
        ldy     r_fcol
        lda     (zscr),y
        sta     zc
        sta     (zshs),y
        lda     (zcol),y
        and     #$0F
        sta     (zshc),y
        sta     zk
        sty     zy
        jsr     draw_cell
        inc     r_fcol
        lda     r_fcol
        cmp     #40
        bcc     :+
        lda     #0
        sta     r_fcol
        inc     r_frow
        lda     r_frow
        cmp     #25
        bcc     :+
        lda     #0
        sta     r_frow
:       dec     sw_cnt
        bne     @f
@fd:    rts

; Scan text row zrow (0..24) against the shadow; draw changed cells; a changed row becomes hot.
row_ptrs:
        ldx     zrow
        lda     rowoff_lo,x
        sta     zscr
        sta     zcol
        sta     zshs
        sta     zshc
        lda     rowoff_hi,x
        sta     ztmp
        jsr     rbase                   ; (d018>>4)*4 = screen base high byte
        clc
        adc     ztmp
        sta     zscr+1
        lda     ztmp
        clc
        adc     #$D8
        sta     zcol+1
        lda     ztmp
        clc
        adc     #>(WIN+SHS)
        sta     zshs+1
        lda     ztmp
        clc
        adc     #>(WIN+SHC)
        sta     zshc+1
        rts

scan_row:
        jsr     row_ptrs
        lda     #40
        sta     sr_end
        ldy     #0
; (row_ptrs done) columns Y .. sr_end-1
scan_rng:
@cell:  lda     (zscr),y
        cmp     (zshs),y
        bne     @dirty
        lda     (zcol),y
        and     #$0F
        cmp     (zshc),y                ; the colour shadow holds the low nibble; $FF = invalid (atlas rebuilt)
        beq     @next
        lda     (zshc),y
        cmp     #$FF
        beq     @dirty                  ; invalid: the BG pixels are stale, redraw regardless
        jsr     pf_cwait
        bne     @next                   ; (colour RAM is still moving to the new scroll step: look again later)
        lda     (zscr),y                ; colour-only change: invisible on a blank glyph, just remember it
        tax
        lda     BLANKT,x
        beq     @dirty
        lda     (zcol),y
        and     #$0F
        sta     (zshc),y
        jmp     @next
@dirty: lda     sw_cells
        cmp     #36
        bcc     :+
        tya                             ; chain full: run it now and carry on
        pha
        jsr     flush_cells
        pla
        tay
:       inc     r_dirty
        ldx     zrow
        lda     #8
        sta     r_hot,x                 ; keep watching this row
        lda     (zscr),y
        sta     zc
        sta     (zshs),y
        lda     (zcol),y
        and     #$0F
        sta     (zshc),y
        sta     zk
        sty     zy
        jsr     draw_cell
        ldy     zy
@next:  iny
        cpy     sr_end
        bne     @cell
        rts

; Draw cell: zc = char, zk = colour (0-15), zy = column, zrow = row.
draw_cell:
        ; multicolour glyph if MCM on and colour >= 8
        lda     #0
        sta     zmc
        lda     zk
        and     #8
        beq     @hi
        lda     VSN+$06
        and     #$10
        beq     @hi
        lda     #$40
        sta     zmc
@hi:    lda     zk
        ldx     zmc
        beq     :+
        and     #7
:       clc
        adc     #1
        asl     a
        asl     a
        ora     #3
        sta     ztmp                    ; AND mask = palette index of the colour
        ldx     sw_cells
        lda     cb_lo,x
        sta     zcnt
        lda     cb_hi,x
        sta     zb                      ; (zcnt) = block in the prefilled chain
        ; src = $010000 + (mc?$4000:0) + c*64
        ldy     #0
        lda     zc
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        sta     (zcnt),y
        iny
        lda     zc
        lsr     a
        lsr     a
        clc
        adc     zmc
        sta     (zcnt),y
        ; dst = rowbase + col*8
        ldx     zrow
        lda     zy
        asl     a
        asl     a
        asl     a
        sta     sw_t2
        lda     zy
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        sta     r_carry
        ldy     #6
        lda     rb_lo,x
        clc
        adc     sw_t2
        sta     (zcnt),y
        iny
        lda     rb_mid,x
        adc     r_carry
        sta     (zcnt),y
        iny
        lda     rb_hi,x
        adc     #0
        sta     (zcnt),y
        ldy     #15
        lda     ztmp
        sta     (zcnt),y
        inc     sw_cells
        ; the cell changes in BG: both display buffers must copy it again
        inc     fs_cells                ; (cells drawn: start-up settle test)
        bne     :+
        dec     fs_cells
:
        .ifdef LOOPCOUNT
        inc     $F6F0
        bne     :+
        inc     $F6F1
:
        .endif
        .ifdef DCHK
        lda     #0
        sta     $F675
        .endif
        ldx     zrow
        lda     rowoff_lo,x
        clc
        adc     zy
        sta     e_k
        and     #7
        tay
        lda     bitm,y
        sta     e_bit
        lda     rowoff_hi,x
        adc     #0
        lsr     a
        ror     e_k
        lsr     a
        ror     e_k
        lsr     a
        ror     e_k
        ldy     e_k
        lda     CD0,y
        ora     e_bit
        sta     CD0,y
        lda     CD1,y
        ora     e_bit
        sta     CD1,y
        lda     r_cdn
        cmp     #255
        beq     :+
        inc     r_cdn
:       lda     r_cdn+1
        cmp     #255
        beq     :+
        inc     r_cdn+1
:       rts

; ---------------------------------------------------------------------------------------------------------------
; Compose the hidden display buffer. It still holds the BG and the sprite pieces drawn into it two frames ago, per band
; (OB lists). Copy the BG cells that changed since; for each band whose pieces changed (its band cache has another
; version), erase the old pieces and draw the new ones. Bands cover disjoint raster lines, so their pieces never overlap,
; and an unchanged band costs nothing.
compose:
        lda     r_blank
        cmp     #1
        beq     :+
        cmp     #6
        beq     :+
        cmp     #5
        bne     :++
:       rts                             ; (nothing is shown: no compose, more time for the game)
:
        .ifdef LOOPCOUNT
        lda     r_flip
        beq     :+
        inc     $F6F4                   ; debug: compose skipped, flip pending
:       lda     r_hold
        beq     :+
        inc     $F6F3                   ; debug: compose skipped, holding
:
        .endif
@fw:    lda     r_flip                  ; an idle render waits for the VBI to show the last frame (idle time)
        beq     :+
        lda     r_act
        beq     :+
        jsr     ryield
        jsr     pf_check                ; (screen scrolls: take the steps meanwhile; no chain is built yet)
        jmp     @fw
:       lda     r_flip
        ora     r_hold
        beq     :+
        rts                             ; the last frame is not on screen yet (or the screen is half shifted)
:
        .ifdef LOOPCOUNT
        inc     $F6F9                   ; debug: composes
        .endif
        .ifdef RTL
        pha
        lda     #2
        jsr     rtl
        pla
        .endif
        lda     #WINB
        sta     VB_MEMS
        jsr     vx_wait
        lda     VSN+$01
        and     #7
        ldx     psr                     ; (the split on: the HUD's Y-scroll, 3; the playfield's fine Y-scroll is the
        cpx     #25                     ; XDL variant's, xv_pick: one Y-scroll for the whole picture moved the HUD 4
        bcs     :+                      ; lines and showed its last lines at the playfield's top)
        lda     #3
:       sta     r_cys
        lda     #CL_MAXR
        sta     r_rb
        lda     #CL_SPR
        sta     r_sb
        lda     ov_hi                   ; blocks that held an over template last frame: sprite template again
        beq     @nr
        lda     #VB1
        sta     VB_MEMS
        ldx     ov_lo
@rt:    lda     cl_lo,x
        sta     zshc
        lda     cl_hi,x
        sta     zshc+1
        ldy     #20
:       lda     tpl_sprite,y
        sta     (zshc),y
        dey
        bpl     :-
        inx
        cpx     ov_hi
        bne     @rt
        lda     #0
        sta     ov_lo
        sta     ov_hi
@nr:    lda     r_scn                   ; scene change: every cached sprite shape is converted again
        beq     :+
        lda     #0
        sta     r_scn
        lda     #WINB
        sta     VB_MEMS
        ldx     #63
        lda     #$FF
@fl:    sta     WIN+SPK_COL,x
        dex
        bpl     @fl
        inc     r_gen
:       jsr     verify_used             ; sprite images the game rewrote in RAM: their conversions are dropped
        lda     #1
        sta     r_fin                   ; (the drawing part: profiling marker)
        .ifdef RTL
        pha
        lda     #3
        jsr     rtl
        pla
        .endif
        jsr     build_bands             ; band caches up to date; their headers -> bver/bcnt/bst/ben
        lda     #VB1
        sta     VB_MEMS                 ; block lists and old-piece lists live in VRAM bank 1
        ldx     #CL_MAXR-1              ; the last restore block links to the sprite blocks again
        lda     cl_lo,x
        sta     zshc
        lda     cl_hi,x
        sta     zshc+1
        ldy     #20
        lda     #8
        sta     (zshc),y
        lda     #0
        sta     mode_all
        ldx     r_hidden
        .ifdef FULLALWAYS
        jmp     @full
        .endif
        lda     r_dv,x
        bne     :+
        jmp     @full
:       lda     r_cdn,x
        cmp     #36
        bcc     :+
        jmp     @full
:       cmp     #0
        beq     :+
        .ifdef DCHK
        txa
        ora     #$20
        jsr     dlog
        .endif
        jsr     restore_cells           ; cells change: every band is drawn again (a cell copy may cover a piece)
        inc     mode_all
:       jsr     band_marks
        jsr     erase_marked
        jmp     @draw
@full:
        .ifdef DCHK
        txa
        ora     #$10
        jsr     dlog
        .endif
        jsr     full_copy
        ldx     #4
        lda     #1
:       sta     bmark,x
        dex
        bpl     :-
@draw:  lda     #0
        sta     sv_layer
        ldx     #4
:       lda     bmark,x
        and     bbeh,x
        ora     sv_layer
        sta     sv_layer
        dex
        bpl     :-
        lda     sv_layer
        beq     :+
        lda     #1
        jsr     draw_marked             ; behind-characters pieces, then the characters over them
        jsr     over_marked
:       lda     #0
        jsr     draw_marked
        jsr     save_marked
        ; terminate the chain at the last block used
        lda     #VB1
        sta     VB_MEMS
        ldx     r_sb
        cpx     #CL_SPR
        beq     @nospr
        dex
        lda     cl_lo,x
        sta     zshc
        lda     cl_hi,x
        sta     zshc+1
        ldy     #20
        lda     #1                      ; copy if non-zero, end of chain
        sta     (zshc),y
        jmp     @go
@nospr: ldx     r_rb
        cpx     #CL_MAXR
        beq     @none                   ; nothing to blit at all
        ldx     #CL_MAXR-1
        lda     cl_lo,x
        sta     zshc
        lda     cl_hi,x
        sta     zshc+1
        ldy     #20
        lda     #0                      ; end of chain
        sta     (zshc),y
@go:    ldx     r_rb
        cpx     #CL_MAXR
        bne     :+
        ldx     #CL_SPR                 ; no restore blocks: start at the first sprite block
:       lda     cla_lo,x
        sta     VB_BL
        lda     cla_mid,x
        sta     VB_BL+1
        lda     #0
        sta     VB_BL+2
        lda     #1
        sta     VB_BLGO                 ; runs while the CPU returns to the game
@none:  ; the frame is complete once the blitter is idle: the VBI then shows it
        lda     #DT+11
        sec
        sbc     r_cys
        tax                             ; D line shown at the top of the picture
        ldy     r_hidden
        lda     dr_lo,x
        clc
        adc     #48
        sta     r_fx
        lda     dr_mid,x
        adc     dbase_mid,y
        sta     r_fx+1
        lda     dr_hi,x
        adc     dbase_hi,y
        sta     r_fx+2
        lda     #WINB                   ; the hidden buffer's XDL points at the composed picture
        sta     VB_MEMS
        ldx     #6
        lda     r_hidden
        beq     :+
        ldx     #$26
:       lda     r_fx
        sta     WIN,x
        lda     r_fx+1
        sta     WIN+1,x
        lda     r_fx+2
        sta     WIN+2,x
        jsr     xdl_vars                ; (screen scrolls: the picture shifted by the steps the game is ahead)
        lda     r_blank                 ; the first complete title frame: the VBI switches the overlay on with it
        cmp     #2
        bne     :+
        lda     #3
        sta     r_blank
:       lda     #WINB                   ; the sample cells as this picture has them (vicirq.s cl_chk: a cleared
        sta     VB_MEMS                 ; screen hides the picture at once)
        ldx     #11
:       ldy     pc_row,x
        lda     rowoff_lo,y
        clc
        adc     pc_col,x
        sta     zshs
        lda     rowoff_hi,y
        adc     #>(WIN+SHS)
        sta     zshs+1
        ldy     #0
        lda     (zshs),y
        sta     ex_smp,x
        dex
        bpl     :-
        lda     #1
        sta     ex_ok
        lda     #0
        sta     r_fin
        .ifdef RTL
        pha
        lda     #4
        jsr     rtl
        pla
        .endif
        lda     #1
        sta     r_flip                  ; the VBI shows it once the blitter is idle
        .ifdef DCHK
        sta     $F675
        .endif
        rts

; Screen scrolls (playfield split on). Renders are rare while the overworld scrolls (the game leaves no idle time), so
; a composed picture is soon several scroll steps behind the game. Its XDL variants show it shifted by k steps (the
; VBI, vicirq.s xv_pick, picks k = steps whose incoming rows/columns edge_fill has drawn), so the playfield moves every
; step, as on the C64, with the C64's 4-pixel fine X-scroll ($0DFD) in between. Variant v of buffer b at
; XV + b*$400 + v*64: blank lines, the HUD (24 lines), then the playfield (176 lines):
;   left/right: narrow overlay (256 pixels = C64 columns 4-35), source 8 * (v >> 1) pixels further, 4 back if v is odd;
;     the incoming columns are in the buffer's border columns and margin (edge_fill);
;   up: k = min(v, 6): source 8k lines lower (the incoming rows below the picture, in the margin);
;   down: k = min(v, 5): 8k lines from the strip (STRIP + b*$3200, the incoming rows, newest on top), then the picture.
xdl_vars:
        ldx     r_hidden
        stx     xv_b
        lda     pf_done                 ; the steps in this picture (also without the split: a scroll can start
        sta     xv_s,x                  ; before the next compose, xdl_shown)
        sta     xv_f,x
        lda     #0
        sta     xv_ok,x
        lda     psr
        cmp     #25
        bcc     xv_body
        jmp     ys_vars
; The shown buffer's variants, when a scroll step comes and it has none (composed before the split came on: its
; picture stood still until the next compose's flip, up to ~20 frames at a scroll's start): its picture address from
; its XDL, its steps (xv_s) from its compose. (Same geometry: pictures with the split on use the HUD's Y-scroll.)
xdl_shown:
        lda     r_hidden
        eor     #1
        tax
        stx     xv_b
        lda     #WINB
        sta     VB_MEMS
        ldy     #6
        txa
        beq     :+
        ldy     #$26
:       lda     WIN,y
        sta     r_fx
        lda     WIN+1,y
        sta     r_fx+1
        lda     WIN+2,y
        sta     r_fx+2
xv_body:                                ; (X = xv_b)
        lda     #0
        sta     ys_ok,x                 ; (the attract screens' variants are overwritten here)
        lda     $0DF7
        and     #3
        tay
        lda     pc_dir4,y
        sta     xv_dir,x
        lda     #$80+(XV >> 12)
        sta     VB_MEMS
        lda     #0
        sta     zshs
        txa
        asl     a
        asl     a
        ora     #>WIN
        sta     zshs+1                  ; zshs = this buffer's variants
        lda     r_fx                    ; e_src = the playfield's top left (row 3: 24 lines below the picture's top)
        clc
        adc     #<(24*DPITCH)
        sta     e_src
        lda     r_fx+1
        adc     #>(24*DPITCH)
        sta     e_src+1
        lda     r_fx+2
        adc     #0
        sta     e_src+2
        lda     #0
        sta     e_k                     ; variant
@v:     ldy     #0
:       lda     xv_head,y               ; blank lines, then the HUD segment
        sta     (zshs),y
        iny
        cpy     #13
        bne     :-
        ldy     #6
        lda     r_fx
        sta     (zshs),y
        iny
        lda     r_fx+1
        sta     (zshs),y
        iny
        lda     r_fx+2
        sta     (zshs),y
        lda     e_src
        sta     e_dst
        lda     e_src+1
        sta     e_dst+1
        lda     e_src+2
        sta     e_dst+2
        lda     #176
        sta     e_w+1                   ; playfield lines
        ldy     #13
        ldx     xv_b
        lda     xv_dir,x
        cmp     #2
        bcc     :+
        jmp     @hor
:       tax
        lda     e_k                     ; k = min(v >> 1, the most for this way); v odd: the C64's fine Y-scroll 7
        lsr     a                       ; (4 blank lines, the VIC's idle lines, then the playfield 4 lines lower)
        php
        cmp     xv_max,x
        bcc     :+
        lda     xv_max,x
:       sta     e_h
        plp
        bcc     :+
        pha
        lda     #$24                    ; overlay off, 4 lines
        sta     (zshs),y
        iny
        lda     #$00
        sta     (zshs),y
        iny
        lda     #3
        sta     (zshs),y
        iny
        lda     #176-4
        sta     e_w+1
        pla
:       cpx     #1
        beq     @down
        tax                             ; up: the source 8k lines lower (k * $0D00)
        lda     e_dst+1
        clc
        adc     xv_k0d,x
        sta     e_dst+1
        bcc     @pf
        inc     e_dst+2
        bcs     @pf
@down:  asl     a
        asl     a
        asl     a
        beq     @pf
        sta     e_w                     ; 8k lines from the strip
        lda     e_w+1                   ; (176, or 172 after the blank lines)
        sec
        sbc     e_w
        sta     e_w+1
        lda     #$62
        sta     (zshs),y
        iny
        lda     #$08
        sta     (zshs),y
        iny
        lda     e_w
        sec
        sbc     #1
        sta     (zshs),y
        iny
        lda     #0
        sta     (zshs),y
        iny
        ldx     xv_b
        lda     xs_base,x
        ldx     e_h
        clc
        adc     xs_k,x
        sta     (zshs),y
        iny
        lda     #0
        sta     (zshs),y
        iny
        lda     #<320
        sta     (zshs),y
        iny
        lda     #>320
        sta     (zshs),y
        iny
        lda     #1
        sta     (zshs),y
        iny
        lda     #$FF
        sta     (zshs),y
        iny
@pf:    lda     #1                      ; normal width
        jsr     xv_pf
        jmp     @next
@hor:   ldx     xv_b                ; offset = (left ? +8k : -8k) - fine, k = v >> 1, fine = 4 if v odd
        lda     e_k
        and     #$FE
        asl     a
        asl     a                       ; 8k
        sta     e_w
        lda     #0
        sta     e_w+1
        lda     xv_dir,x
        cmp     #2
        beq     :+
        lda     #0                      ; right: -8k
        sec
        sbc     e_w
        sta     e_w
        lda     #0
        sbc     #0
        sta     e_w+1
:       lda     e_k
        and     #1
        beq     :+
        lda     e_w
        sec
        sbc     #4
        sta     e_w
        lda     e_w+1
        sbc     #0
        sta     e_w+1
:       lda     e_dst                   ; e_dst += 32 (narrow window) + offset
        clc
        adc     #32
        sta     e_dst
        bcc     :+
        inc     e_dst+1
        bne     :+
        inc     e_dst+2
:       lda     e_dst
        clc
        adc     e_w
        sta     e_dst
        lda     e_dst+1
        adc     e_w+1
        sta     e_dst+1
        lda     e_w+1
        and     #$80
        beq     :+
        lda     #$FF
:       adc     e_dst+2
        sta     e_dst+2
        lda     #176
        sta     e_w+1
        ldy     #13
        lda     #0                      ; narrow
        jsr     xv_pf
@next:  lda     zshs
        clc
        adc     #64
        sta     zshs
        bcc     :+
        inc     zshs+1
:       inc     e_k
        lda     e_k
        cmp     #16
        beq     :+
        jmp     @v
:       ldx     xv_b
        lda     #1
        sta     xv_ok,x
        lda     #WINB
        sta     VB_MEMS
        rts
; The attract screens scroll up in 1-pixel steps (the story, the item pages: the C64 one line every 2 frames). A
; picture is composed now and then (the scan catches up after each row shift: ~8 frames without one), so the VBI
; shows it moved by the pixels the game scrolled since (vicirq.s xv_pick: ys_pos - ys_c): 16 variants of the buffer's
; XDL, the picture k lines further down, at XV + buffer * $400 + k * 64. (X = xv_b)
ys_vars:
        lda     ys_ok,x                 ; (bit 0: valid now; bit 7: the variants' fixed bytes are written)
        and     #$80
        sta     ys_ok,x
        lda     $14
        bne     @r
        lda     ys_act                  ; (only while the screen scrolls)
        cmp     #60
        bcs     @r
        lda     r_ysp
        sta     ys_c,x
        lda     #$80+(XV >> 12)
        sta     VB_MEMS
        lda     #0
        sta     zshs
        sta     e_k
        txa
        asl     a
        asl     a
        ora     #>WIN
        sta     zshs+1
@v:     ldx     xv_b
        lda     ys_ok,x                 ; (the rest of each variant stays: only the address is new; xv_ok: the split
        bne     :++                     ; variants may have overwritten the area since)
        ldy     #12
:       lda     xdl,y
        sta     (zshs),y
        dey
        bpl     :-
:       ldy     #6
        ldx     e_k
        lda     r_fx
        clc
        adc     dpk_lo,x
        sta     (zshs),y
        iny
        lda     r_fx+1
        adc     dpk_hi,x
        sta     (zshs),y
        iny
        lda     r_fx+2
        adc     #0
        sta     (zshs),y
        lda     zshs
        clc
        adc     #64
        sta     zshs
        bcc     :+
        inc     zshs+1
:       inc     e_k
        lda     e_k
        cmp     #16
        bne     @v
        ldx     xv_b
        lda     #$81
        sta     ys_ok,x
        lda     #WINB
        sta     VB_MEMS
@r:     rts
dpk_lo: .repeat 16, k
        .byte   <(k * DPITCH)
        .endrepeat
dpk_hi: .repeat 16, k
        .byte   >(k * DPITCH)
        .endrepeat

; the playfield segment, the end of the list: e_w+1 lines from e_dst, width A (0 narrow, 1 normal), at (zshs),y
xv_pf:  pha
        lda     #$62
        sta     (zshs),y
        iny
        lda     #$88                    ; (end)
        sta     (zshs),y
        iny
        lda     e_w+1
        sec
        sbc     #1
        sta     (zshs),y
        iny
        lda     e_dst
        sta     (zshs),y
        iny
        lda     e_dst+1
        sta     (zshs),y
        iny
        lda     e_dst+2
        sta     (zshs),y
        iny
        lda     #<DPITCH
        sta     (zshs),y
        iny
        lda     #>DPITCH
        sta     (zshs),y
        iny
        pla
        sta     (zshs),y
        iny
        lda     #$FF
        sta     (zshs),y
        rts
xv_head: .byte  $20, $00, SKIP-1                ; blank lines
        .byte   $62, $08, 23, 0, 0, 0, <DPITCH, >DPITCH, 1, $FF   ; the HUD: 24 lines (address at 6-8), normal width
xv_k0d: .byte   0, $0D, $1A, $27, $34, $41, $4E   ; k * $0D (8k lines of DPITCH, high byte)
xv_max: .byte   6, 5, 7, 7                      ; most steps shown ahead: up, down, left, right (margins, strip)
xs_base: .byte  >STRIP, >(STRIP+$3200)          ; strip of each buffer (40 lines of 320)
xs_k:   .byte   0, $28, $1E, $14, $0A, $00      ; (5 - k) * 8 lines of 320 (high byte): the strip's visible part

; Copy the incoming rows/columns of the steps since the shown buffer's compose from BG into its edge, where its
; shifted XDL variant shows them. Step S+j (S = the buffer's steps, j = 1 .. k, k = min(L, most), L = pf_done - S)
; always lands at the same place: right: column 4-j, left: 35+j, up (incoming at the bottom): row 24+j, down: strip
; line (5-j)*8; in BG it is L-j rows/columns in from the incoming edge. edge_fill copies the steps not drawn yet
; (xv_f - S + 1 .. k) and sets xv_f (the VBI shows that many); ef_copy copies steps ef_j0 .. ef_j1.
edge_fill:
        lda     frame_ctr
        sta     ef_last
        jsr     ef_setup
        bcs     @r
        lda     xv_f,x
        sec
        sbc     xv_s,x
        clc
        adc     #1
        sta     ef_j0
        lda     ef_k
        sta     ef_j1
        cmp     ef_j0
        bcc     @r                      ; (all drawn)
        jsr     ef_copy
        ldx     ef_b
        lda     xv_s,x
        clc
        adc     ef_k
        sta     xv_f,x
@r:     rts
; C = 1: nothing to do. Else X = ef_b = the shown buffer, ef_l = L, ef_k = k.
ef_setup:
        lda     r_hidden
        eor     #1
        tax
        stx     ef_b
        lda     xv_ok,x
        beq     @no
        lda     pf_done
        sec
        sbc     xv_s,x
        beq     @no
        sta     ef_l
        ldy     xv_dir,x
        cmp     xv_max,y
        bcc     :+
        lda     xv_max,y
:       sta     ef_k
        clc
        rts
@no:    sec
        rts
; copy steps ef_j0 .. ef_j1 (n = j1 - j0 + 1) of buffer ef_b
ef_copy:
        lda     ef_j1
        sec
        sbc     ef_j0
        clc
        adc     #1
        asl     a
        asl     a
        asl     a
        sta     ef_n8                   ; 8n
        jsr     vx_wait
        jsr     set_bl
        lda     #<tpl_edge
        ldx     #>tpl_edge
        jsr     load_tpl
        ldx     ef_b
        lda     xv_dir,x
        cmp     #2
        bcc     @vert
        lda     ef_n8                   ; left/right: 8n wide, 176 lines from row 3
        sec
        sbc     #1
        sta     WIN+BLK+12
        lda     #175
        sta     WIN+BLK+14
        lda     xv_dir,x
        cmp     #3
        bne     @left
        lda     #4                      ; right: BG column 4+L-j1 -> column 4-j1
        clc
        adc     ef_l
        sec
        sbc     ef_j1
        sta     ef_sc
        lda     #4
        sec
        sbc     ef_j1
        sta     ef_dc
        jmp     @hc
@left:  lda     #35                     ; left: BG column 35-L+j0 -> column 35+j0
        sec
        sbc     ef_l
        clc
        adc     ef_j0
        sta     ef_sc
        lda     #35
        clc
        adc     ef_j0
        sta     ef_dc
@hc:    lda     #32                     ; BG line of row 3
        sta     ef_sl
        lda     #DT+32                  ; D line of row 3
        sta     ef_dl
        lda     #0
        sta     ef_dh
        jmp     @go
@vert:  lda     ef_n8                   ; up/down: 320 wide, 8n lines
        sec
        sbc     #1
        sta     WIN+BLK+14
        lda     #<319
        sta     WIN+BLK+12
        lda     #>319
        sta     WIN+BLK+13
        lda     #0
        sta     ef_sc
        sta     ef_dc
        lda     xv_dir,x
        bne     @dn
        lda     #24                     ; up: BG row 24-L+j0 -> row 24+j0 (in the margin below the picture)
        sec
        sbc     ef_l
        clc
        adc     ef_j0
        asl     a
        asl     a
        asl     a
        clc
        adc     #8
        sta     ef_sl
        lda     ef_j0
        asl     a
        asl     a
        asl     a
        clc
        adc     #DT+200                 ; D line of row 24+j0 = DT + 8 + 8*(24+j0) (9 bits: ef_dh)
        sta     ef_dl
        lda     #0
        rol     a
        sta     ef_dh
        jmp     @go
@dn:    lda     #3                      ; down: BG row 3+L-j1 -> strip line (5-j1)*8
        clc
        adc     ef_l
        sec
        sbc     ef_j1
        asl     a
        asl     a
        asl     a
        clc
        adc     #8
        sta     ef_sl
        jsr     ef_src
        lda     #<320
        sta     WIN+BLK+9
        lda     #>320
        sta     WIN+BLK+10
        lda     #5
        sec
        sbc     ef_j1
        asl     a
        asl     a
        asl     a
        tay                             ; strip line
        lda     m320_mid,y
        ldx     ef_b
        clc
        adc     xs_base,x
        sta     WIN+BLK+7
        lda     m320_lo,y
        sta     WIN+BLK+6
        lda     #0
        adc     #0
        sta     WIN+BLK+8
        jmp     blit
@go:    jsr     ef_src
        lda     ef_dc                   ; destination x = (column + 6) * 8 (column -3 .. 42: 16 bits)
        clc
        adc     #6
        sta     ef_t
        lda     #0
        asl     ef_t
        rol     a
        asl     ef_t
        rol     a
        asl     ef_t
        rol     a
        sta     ef_t+1
        ldx     ef_dl                   ; destination D line (ef_dh: 256 more)
        ldy     ef_b
        lda     ef_dh
        bne     @hl
        lda     dr_lo,x
        clc
        adc     ef_t
        sta     WIN+BLK+6
        lda     dr_mid,x
        adc     ef_t+1
        sta     ef_t+1
        lda     dr_hi,x
        jmp     @dh
@hl:    lda     dr_lo+256,x
        clc
        adc     ef_t
        sta     WIN+BLK+6
        lda     dr_mid+256,x
        adc     ef_t+1
        sta     ef_t+1
        lda     dr_hi+256,x
@dh:    adc     dbase_hi,y
        sta     WIN+BLK+8
        lda     ef_t+1
        clc
        adc     dbase_mid,y
        sta     WIN+BLK+7
        bcc     :+
        inc     WIN+BLK+8
:       jmp     blit

; Once per scroll step, 2 frames after it (colour RAM is complete by then: the game moves it in two halves after the
; flip, pf_cwait): rescan the two newest incoming rows/columns in BG, then copy the edge again.
edge_refresh:
        lda     frame_ctr
        sta     ef_last
        lda     pf_ff
        cmp     ef_rs
        bne     :+
        rts                             ; (this step's edge is rescanned already)
:       lda     frame_ctr
        sec
        sbc     pf_ff
        cmp     #2
        bcs     :+
        rts                             ; (its colours may not be there yet)
:       lda     pf_ff
        sta     ef_rs
        lda     r_hidden
        eor     #1
        tax
        lda     xv_ok,x
        bne     :+
        rts
:       lda     pf_done
        sec
        sbc     xv_s,x
        bne     :+
        rts
:       cmp     #2
        bcc     :+
        lda     #2
:       sta     ef_k                    ; rows/columns to rescan (1 or 2), at BG's incoming edge
        lda     xv_dir,x
        cmp     #2
        bcs     @h
        tay                             ; rows: up 25-k .. 24, down 3 .. 2+k
        lda     #3
        cpy     #0
        bne     :+
        lda     #25
        sec
        sbc     ef_k
:       sta     zrow
@r:     jsr     scan_row
        inc     zrow
        dec     ef_k
        bne     @r
        jsr     flush_cells
        jmp     ef_redo
@h:     cmp     #3                      ; columns: right 4 .. 3+k, left 36-k .. 35
        bne     :+
        lda     #4
        bne     @c0
:       lda     #36
        sec
        sbc     ef_k
@c0:    sta     ef_sc
        clc
        adc     ef_k
        sta     ef_dc                   ; (end column)
        lda     psr
        sta     zrow
:       jsr     row_ptrs
        lda     ef_dc
        sta     sr_end
        ldy     ef_sc
        jsr     scan_rng
        inc     zrow
        lda     zrow
        cmp     #25
        bne     :-
        lda     #40
        sta     sr_end
        jsr     flush_cells
ef_redo:                                ; copy the rescanned steps (the newest two: j = L-1 .. L) if they are shown
        jsr     ef_setup
        bcs     @r
        lda     xv_f,x
        sec
        sbc     xv_s,x
        sta     ef_j1                   ; drawn steps
        beq     @r
        lda     ef_l
        sec
        sbc     #1
        bne     :+
        lda     #1
:       sta     ef_j0
        lda     ef_j1
        cmp     ef_j0
        bcc     @r
        jmp     ef_copy
@r:     rts

; source: BG line ef_sl, column ef_sc -> block bytes 0-2
ef_src: lda     ef_sc                   ; column * 8 (16 bits)
        sta     ef_t
        lda     #0
        asl     ef_t
        rol     a
        asl     ef_t
        rol     a
        asl     ef_t
        rol     a
        sta     ef_t+1
        ldx     ef_sl
        lda     ef_t
        clc
        adc     bgl_lo,x
        sta     WIN+BLK+0
        lda     bgl_mid,x
        adc     ef_t+1
        sta     WIN+BLK+1
        lda     bgl_hi,x
        adc     #0
        sta     WIN+BLK+2
        rts
tpl_edge:                               ; BG -> display buffer (value xor 1), copy
        .byte   0,0,0, <320,>320, 1, 0,0,0, <DPITCH,>DPITCH, 1, 0,0, 0, $FF,1,0,0,0, 0
bgl_lo: .repeat 216, k
        .byte   <(BG + k*320)
        .endrepeat
bgl_mid: .repeat 216, k
        .byte   >(BG + k*320) & $FF
        .endrepeat
bgl_hi: .repeat 216, k
        .byte   ^(BG + k*320)
        .endrepeat
m320_lo: .repeat 41, k
        .byte   <(k*320)
        .endrepeat
m320_mid: .repeat 41, k
        .byte   >(k*320)
        .endrepeat

; Piece entries (16 bytes): 0 key, 1 display-buffer line, 2/3 column, 4 width-1, 5 height-1 (the covered rectangle),
; 6-8 sprite cache source, 9 block width-1, 10 rows-1, 11 zoom, 12 flags (1 = behind the characters).
; Old-piece list of band X in this buffer (bank 1) -> zshs: 0/1 version, 2 count, 3/4 band start/end, entries at +8.
ob_ptr: txa
        ldy     r_hidden
        beq     :+
        clc
        adc     #5
:       tay
        lda     obo_lo,y
        sta     zshs
        lda     obo_hi,y
        sta     zshs+1
        rts

; Mark the bands whose pieces in this buffer differ from their band cache (or all of them, if band lines moved).
band_marks:
        ldx     #4
@b:     stx     mi
        jsr     ob_ptr
        ldx     mi
        lda     mode_all
        bne     @m
        ldy     #0
        lda     (zshs),y
        cmp     bver_lo,x
        bne     @d
        iny
        lda     (zshs),y
        cmp     bver_hi,x
        bne     @d
        lda     #0
        beq     @s
@d:     ldy     #2                      ; changed: if both have pieces and the band's lines moved, redraw every band
        lda     (zshs),y
        beq     @m
        lda     bcnt,x
        beq     @m
        iny
        lda     (zshs),y
        cmp     bst,x
        bne     @all
        iny
        lda     (zshs),y
        cmp     ben,x
        beq     @m
@all:   inc     mode_all
        ldx     #4
        bne     @b
@m:     lda     #1
@s:     sta     bmark,x
        dex
        bpl     @b
        rts

; Erase (restore BG under) the old pieces of the marked bands.
erase_marked:
        ldx     #4
@b:     jsr     ryield
        lda     bmark,x
        beq     @nb
        stx     mi
        jsr     ob_ptr
        ldy     #2
        lda     (zshs),y
        sta     sw_t3
        lda     zshs
        clc
        adc     #8
        sta     zcol
        lda     zshs+1
        adc     #0
        sta     zcol+1
@e:     lda     sw_t3
        beq     @eb
        jsr     ent_src
        jsr     ent_dst
        ldy     #4
        lda     (zcol),y
        sta     e_w
        lda     #0
        sta     e_w+1
        iny
        lda     (zcol),y
        sta     e_h
        jsr     emit_restore
        lda     zcol
        clc
        adc     #8
        sta     zcol
        bcc     :+
        inc     zcol+1
:       dec     sw_t3
        jmp     @e
@eb:    ldx     mi
@nb:    dex
        bpl     @b
        rts

; zcol = entry at offset sw_t2 of band cache sw_b (all in VRAM bank 1, which stays mapped).
ce_load:
        ldx     sw_b
        lda     bco_lo,x
        clc
        adc     sw_t2
        sta     zcol
        lda     bco_hi,x
        adc     #0
        sta     zcol+1
        rts

; Blocks for the pieces of the marked bands whose flags bit 0 equal A (band order, then the cache's sprite order).
draw_marked:
        sta     sw_t4
        lda     #0
        sta     sw_b
@b:     jsr     ryield
        ldx     sw_b
        lda     bmark,x
        bne     :+
        jmp     @nb
:       lda     bcnt,x
        bne     :+
        jmp     @nb
:       sta     sw_t3
        lda     #48
        sta     sw_t2
        lda     #8
        sta     mj                      ; (front pass: old-piece list offset; the pieces are saved here too)
@e:     jsr     ce_load
        lda     sw_t4
        bne     @ns
        ldx     sw_b
        jsr     ob_ptr
        lda     zshs                    ; old-piece entry: just the rectangle (bytes 1-5)
        clc
        adc     mj
        sta     zshs
        bcc     :+
        inc     zshs+1
:       ldy     #5
:       lda     (zcol),y
        sta     (zshs),y
        dey
        bne     :-
        lda     mj
        clc
        adc     #8
        sta     mj
@ns:    ldy     #12
        lda     (zcol),y
        and     #1
        cmp     sw_t4
        bne     @n
        ldx     r_sb
        cpx     #CL_SPR+CL_NSPR
        bcs     @n
        inc     r_sb
        lda     cl_lo,x
        sta     zshc
        lda     cl_hi,x
        sta     zshc+1
        ldy     #6
        lda     (zcol),y
        ldy     #0
        sta     (zshc),y
        ldy     #7
        lda     (zcol),y
        ldy     #1
        sta     (zshc),y
        ldy     #8
        lda     (zcol),y
        ldy     #2
        sta     (zshc),y
        jsr     ent_dst
        ldy     #6
        lda     e_dst
        sta     (zshc),y
        iny
        lda     e_dst+1
        sta     (zshc),y
        iny
        lda     e_dst+2
        sta     (zshc),y
        ldy     #9
        lda     (zcol),y
        ldy     #12
        sta     (zshc),y
        ldy     #10
        lda     (zcol),y
        ldy     #14
        sta     (zshc),y
        ldy     #11
        lda     (zcol),y
        ldy     #18
        sta     (zshc),y
        ldy     #20
        lda     #9                      ; copy if non-zero + NEXT (compose ends the chain)
        sta     (zshc),y
@n:     lda     sw_t2
        clc
        adc     #16
        sta     sw_t2
        dec     sw_t3
        beq     @nb
        jmp     @e
@nb:    inc     sw_b
        lda     sw_b
        cmp     #5
        beq     :+
        jmp     @b
:       rts

; For each behind-characters piece of the marked bands: the BG over it again with bg0 transparent.
over_marked:
        lda     #0
        sta     sw_b
@b:     jsr     ryield
        ldx     sw_b
        lda     bmark,x
        bne     :+
        jmp     @nb
:       lda     bcnt,x
        bne     :+
        jmp     @nb
:       sta     sw_t3
        lda     #48
        sta     sw_t2
@e:     jsr     ce_load
        ldy     #12
        lda     (zcol),y
        and     #1
        bne     :+
@nj:    jmp     @n
:       ldx     r_sb
        cpx     #CL_SPR+CL_NSPR-2       ; (three blocks)
        bcs     @nj
        lda     ov_hi
        bne     :+
        stx     ov_lo
:       jsr     ent_src
        jsr     ent_dst
        lda     #0
        sta     sw_t4
@ob:    ldx     r_sb                    ; block sw_t4 of tpl_ova/b/c
        inc     r_sb
        lda     r_sb
        sta     ov_hi
        lda     cl_lo,x
        sta     zshc
        lda     cl_hi,x
        sta     zshc+1
        ldx     sw_t4
        lda     ov_tpl,x
        tax
        ldy     #0
:       lda     tpl_ova,x
        sta     (zshc),y
        inx
        iny
        cpy     #21
        bne     :-
        lda     sw_t4
        cmp     #2
        beq     @oc
        ldy     #0                      ; A, B: BG -> TMP
        lda     e_src
        sta     (zshc),y
        iny
        lda     e_src+1
        sta     (zshc),y
        iny
        lda     e_src+2
        sta     (zshc),y
        jmp     @ow
@oc:    ldy     #6                      ; C: TMP -> display
        lda     e_dst
        sta     (zshc),y
        iny
        lda     e_dst+1
        sta     (zshc),y
        iny
        lda     e_dst+2
        sta     (zshc),y
@ow:    ldy     #4
        lda     (zcol),y
        ldy     #12
        sta     (zshc),y
        ldy     #5
        lda     (zcol),y
        ldy     #14
        sta     (zshc),y
        inc     sw_t4
        lda     sw_t4
        cmp     #3
        bne     @ob
@n:     lda     sw_t2
        clc
        adc     #16
        sta     sw_t2
        dec     sw_t3
        beq     @nb
        jmp     @e
@nb:    inc     sw_b
        lda     sw_b
        cmp     #5
        beq     :+
        jmp     @b
:       rts

; The marked bands' old-piece list headers (the entries were saved by the front draw pass).
save_marked:
        lda     #0
        sta     sw_b
@b:     jsr     ryield
        ldx     sw_b
        lda     bmark,x
        beq     @nb
        jsr     ob_ptr
        ldx     sw_b
        ldy     #0
        lda     bver_lo,x
        sta     (zshs),y
        iny
        lda     bver_hi,x
        sta     (zshs),y
        iny
        lda     bcnt,x
        sta     (zshs),y
        sta     sw_t3
        iny
        lda     bst,x
        sta     (zshs),y
        iny
        lda     ben,x
        sta     (zshs),y
@nb:    inc     sw_b
        lda     sw_b
        cmp     #5
        bne     @b
        rts

; e_dst / e_src of entry (zcol): display buffer address of its rectangle, and the BG under it.
ent_dst:
        ldy     #1
        lda     (zcol),y
        tax
        iny
        lda     dr_lo,x
        clc
        adc     (zcol),y
        sta     e_dst
        iny
        lda     dr_mid,x
        adc     (zcol),y
        sta     e_dst+1
        lda     dr_hi,x
        adc     #0
        sta     e_dst+2
        ldx     r_hidden
        lda     e_dst+1
        clc
        adc     dbase_mid,x
        sta     e_dst+1
        lda     e_dst+2
        adc     dbase_hi,x
        sta     e_dst+2
        rts
ent_src:
        ldy     #1
        lda     (zcol),y
        tax
        iny
        lda     bgr_lo,x
        clc
        adc     (zcol),y
        sta     e_src
        iny
        lda     bgr_mid,x
        adc     (zcol),y
        sta     e_src+1
        lda     bgr_hi,x
        adc     #0
        sta     e_src+2
        lda     e_src                   ; the column is x + 24: BG column = column - 48
        sec
        sbc     #48
        sta     e_src
        lda     e_src+1
        sbc     #0
        sta     e_src+1
        lda     e_src+2
        sbc     #0
        sta     e_src+2
        rts

; Sprite images the game rewrote in RAM. The overworld composes its sprite images in buffers that keep their pointers
; ($0E00-$0FFF = $38-$3F, $2040-$23FF = $81-$8F: rewritten when Link turns or swings, when the sword beam takes a
; buffer that held Link ...), so a shape cached by pointer goes stale (Link facing the wrong way, the beam drawn as
; Link). Once per render each pointer of an enabled sprite in the published bands is compared, exactly, with a copy of
; its 63 bytes (VRAM PCOPY: 64 bytes per pointer, byte 63 = the render that checked it); a difference updates the copy
; and drops every cached conversion of that pointer (they are converted again when used; band caches re-derive).
verify_used:
        inc     vu_gen
        bne     :+
        inc     vu_gen                  ; (never 0)
:       lda     zcol
        pha
        lda     zcol+1
        pha
        ldx     #0
@band:  cpx     rband_n
        bcs     @done
        stx     vu_b
        lda     rband_off,x
        tay
        lda     RBANDS+B_EN,y
        beq     @nb
        sta     vu_en
        tya
        clc
        adc     #B_PTR
        sta     vu_o
@spr:   lsr     vu_en
        bcc     @ns
        ldy     vu_o
        lda     RBANDS,y
        jsr     vu_check
@ns:    inc     vu_o
        lda     vu_en
        bne     @spr
@nb:    jsr     ryield                  ; (the main loop may need the CPU)
        jsr     pf_check                ; (screen scrolls: steps taken before compose chooses its BG copy: a step
        ldx     vu_b                    ; makes it a full copy, r_dv; waiting for the compose left the picture still)
        inx
        bne     @band
@done:  pla
        sta     zcol+1
        pla
        sta     zcol
        lda     #WINB
        sta     VB_MEMS
        rts

vu_check:
        sta     sv_ptr
        rol     a                       ; window: PCOPY bank + ptr >> 6
        rol     a
        rol     a
        and     #3
        ora     #$80+(PCOPY >> 12)
        sta     VB_MEMS
        lda     sv_ptr
        and     #63
        lsr     a
        lsr     a
        ora     #>WIN
        sta     zcol+1
        lda     sv_ptr
        and     #3
        lsr     a
        ror     a
        ror     a
        sta     zcol                    ; zcol = this pointer's copy ((ptr & 63) * 64 in its 4 KB bank)
        ldy     #63
        lda     (zcol),y
        cmp     vu_gen
        beq     @r                      ; (checked in this render already)
        lda     vu_gen
        sta     (zcol),y
        jsr     shape_ptr               ; zscr = the shape's 63 bytes in RAM
        ldy     #62
@c:     lda     (zscr),y
        cmp     (zcol),y
        bne     @diff
        dey
        bpl     @c
@r:     rts
@diff:
        .ifdef LOOPCOUNT
        inc     $F6F7                   ; debug: shape data rewritten under its pointer
        .endif
        lda     #0                      ; the copy, and the content key: Fletcher-16 (position-sensitive: the game's
        sta     sv_sum                  ; animation frames may hold the same bytes in other rows)
        sta     sv_sum2
        ldy     #62
@cp:    lda     (zscr),y
        sta     (zcol),y
        clc
        adc     sv_sum
        sta     sv_sum
        adc     sv_sum2
        sta     sv_sum2
        dey
        bpl     @cp
        lda     #$80+(PSUM >> 12)       ; PSUM[ptr]: the cache's slots stay valid; a slot matches only the content it
        sta     VB_MEMS                 ; was converted from (the game rewrites Link's frames under one pointer: each
        ldx     sv_ptr                  ; rewrite used to drop the conversion, so alternating frames were converted
        lda     sv_sum                  ; again and again, ~10000 cycles each)
        sta     WIN+(PSUM & $FFF),x
        lda     sv_sum2
        sta     WIN+(PSUM & $FFF)+$100,x
        inc     r_gen                   ; band caches that used it are stale
        rts

; zshc = band cache of band sw_b (VRAM bank 2): 0-41 band record, 42 Y-scroll, 43 cache generation, 44 entries ($FF: none
; valid), 45/46 version, 48+ entries (16 bytes, up to 8).
bc_ptr: lda     #VB1
        sta     VB_MEMS
        ldx     sw_b
        lda     bco_lo,x
        sta     zshc
        lda     bco_hi,x
        sta     zshc+1
        rts

; Band caches up to date for this frame's bands (derived again if the band record, Y-scroll or the sprite cache changed);
; bands beyond rband_n are empty. Headers -> bver_lo/hi, bcnt, bst, ben.
build_bands:
        lda     #0
        sta     sw_b
@band:  jsr     ryield
        jsr     pf_check                ; (as in verify_used)
        jsr     bc_ptr
        ldx     sw_b
        cpx     rband_n
        bcc     @live
        ldy     #44                     ; no such band this frame: empty, version 0
        lda     #$FF
        sta     (zshc),y
        lda     #0
        sta     bcnt,x
        sta     bbeh,x
        sta     bver_lo,x
        sta     bver_hi,x
        sta     bst,x
        sta     ben,x
        jmp     @nb
@live:  lda     rband_off,x             ; zscr = its record in RBANDS (compare and copy with one index, unrolled:
        sta     zscr                    ; ~14 cycles a byte, was ~20)
        lda     #>RBANDS
        sta     zscr+1
        ldy     #44
        lda     (zshc),y
        bmi     @d0
        ldy     #42
        lda     (zshc),y
        cmp     r_cys
        bne     @d0
        iny
        lda     (zshc),y
        cmp     r_gen
        bne     @d0
        ldy     #0
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d0
        iny
        jmp     @c0
@d0:    jmp     @der
@c0:
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d1
        iny
        jmp     @c1
@d1:    jmp     @der
@c1:
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        lda     (zscr),y
        cmp     (zshc),y
        bne     @d2
        iny
        jmp     @hdr
@d2:    jmp     @der
@der:   jsr     derive_band
        jsr     bc_ptr
        ldx     sw_b
        lda     rband_off,x
        sta     zscr
        lda     #>RBANDS
        sta     zscr+1
        ldy     #0
        .repeat 42
        lda     (zscr),y
        sta     (zshc),y
        iny
        .endrepeat
        lda     r_cys
        sta     (zshc),y                ; 42
        iny
        lda     r_gen
        sta     (zshc),y                ; 43
        inc     dv_lo                   ; a new version (never 0)
        bne     :+
        inc     dv_hi
:       lda     dv_lo
        ora     dv_hi
        bne     :+
        inc     dv_lo
:       ldy     #45
        lda     dv_lo
        sta     (zshc),y
        iny
        lda     dv_hi
        sta     (zshc),y
@hdr:   ldx     sw_b
        ldy     #44
        lda     (zshc),y
        sta     bcnt,x
        iny
        lda     (zshc),y
        sta     bver_lo,x
        iny
        lda     (zshc),y
        sta     bver_hi,x
        ldy     #40
        lda     (zshc),y
        sta     bst,x
        iny
        lda     (zshc),y
        sta     ben,x
        ldy     #47
        lda     (zshc),y
        sta     bbeh,x
@nb:    inc     sw_b
        lda     sw_b
        cmp     #5
        beq     :+
        jmp     @band
:       rts

; Emit one restore block (copy BG -> display buffer, src step 320, dst step 416) from e_src, e_dst, e_w (2), e_h.
emit_restore:
        dec     r_rb
        ldx     r_rb
        lda     cl_lo,x
        sta     zshc
        lda     cl_hi,x
        sta     zshc+1
        ldy     #0
        lda     e_src
        sta     (zshc),y
        iny
        lda     e_src+1
        sta     (zshc),y
        iny
        lda     e_src+2
        sta     (zshc),y
        ldy     #6
        lda     e_dst
        sta     (zshc),y
        iny
        lda     e_dst+1
        sta     (zshc),y
        iny
        lda     e_dst+2
        sta     (zshc),y
        ldy     #12
        lda     e_w
        sta     (zshc),y
        iny
        lda     e_w+1
        sta     (zshc),y
        iny
        lda     e_h
        sta     (zshc),y
        rts

; The whole BG -> hidden buffer (after a scroll shift or many changes).
full_copy:
        lda     #<BG
        sta     e_src
        lda     #>BG & $FF
        sta     e_src+1
        lda     #^BG
        sta     e_src+2
        ldx     r_hidden
        lda     #<(DT*DPITCH+48)
        sta     e_dst
        lda     #>(DT*DPITCH+48)
        clc
        adc     dbase_mid,x
        sta     e_dst+1
        lda     dbase_hi,x
        adc     #0
        sta     e_dst+2
        lda     #<319
        sta     e_w
        lda     #>319
        sta     e_w+1
        lda     #215
        sta     e_h
        jsr     emit_restore
        ldx     r_hidden
        lda     #1
        sta     r_dv,x
        lda     #0
        sta     r_cdn,x
        lda     #<CD0                   ; the buffer is current: forget its pending cells
        sta     zscr
        lda     #>CD0
        cpx     #0
        beq     :+
        lda     #<CD1
        sta     zscr
        lda     #>CD1
:       sta     zscr+1
        ldy     #124
        lda     #0
:       sta     (zscr),y
        dey
        bpl     :-
        rts

; Copy into the hidden buffer the BG cells that changed since it was last drawn (bit map CD0/CD1).
restore_cells:
        ldx     r_hidden
        lda     r_cdn,x
        beq     @done
        lda     #0
        sta     r_cdn,x
        lda     #<CD0
        sta     zcol
        lda     #>CD0
        cpx     #0
        beq     :+
        lda     #<CD1
        sta     zcol
        lda     #>CD1
:       sta     zcol+1
        lda     #0
        sta     sw_t2                   ; byte index
@byte:  ldy     sw_t2
        lda     (zcol),y
        beq     @nb
        sta     sw_t3
        lda     #0
        sta     (zcol),y
        lda     #0
        sta     sw_t4                   ; bit
@bit:   lsr     sw_t3
        bcc     @nx
        lda     sw_t2                   ; k = byte*8 + bit
        asl     a
        asl     a
        asl     a
        ora     sw_t4
        sta     e_k
        lda     sw_t2
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        sta     e_k+1
        jsr     cell_restore
@nx:    inc     sw_t4
        lda     sw_t3
        bne     @bit
@nb:    inc     sw_t2
        lda     sw_t2
        and     #15
        bne     :+
        jsr     ryield
:       lda     sw_t2
        cmp     #125
        bcc     @byte
@done:  rts

; Restore block for cell k (e_k, 16-bit): BG cell -> hidden buffer cell.
cell_restore:
        lda     e_k
        clc
        adc     #<kpos
        sta     zscr
        lda     e_k+1
        adc     #>kpos
        sta     zscr+1
        ldy     #0
        lda     (zscr),y                ; row
        tax
        lda     e_k
        clc
        adc     #<kcol
        sta     zscr
        lda     e_k+1
        adc     #>kcol
        sta     zscr+1
        lda     #0
        sta     e_bit                   ; column*8 (16 bit) in sw_t4+1 / e_bit
        lda     (zscr),y
        asl     a
        asl     a
        asl     a
        rol     e_bit
        sta     sw_t4+1
        lda     rb_lo,x                 ; src = BG row base + col*8
        clc
        adc     sw_t4+1
        sta     e_src
        lda     rb_mid,x
        adc     e_bit
        sta     e_src+1
        lda     rb_hi,x
        adc     #0
        sta     e_src+2
        ldy     r_hidden
        lda     rdd_lo,x                ; dst = D + (DT+8+8*row)*416 + 48 + col*8
        clc
        adc     sw_t4+1
        sta     e_dst
        lda     rdd_mid,x
        adc     e_bit
        sta     sw_t4+1
        lda     rdd_hi,x
        adc     #0
        sta     e_bit
        lda     sw_t4+1
        clc
        adc     dbase_mid,y
        sta     e_dst+1
        lda     e_bit
        adc     dbase_hi,y
        sta     e_dst+2
        lda     #7
        sta     e_w
        sta     e_h
        lda     #0
        sta     e_w+1
        jmp     emit_restore

rowoff_lo: .repeat 25, r
        .byte   <(r*40)
        .endrepeat
rowoff_hi: .repeat 25, r
        .byte   >(r*40)
        .endrepeat
rb_lo:  .repeat 25, r
        .byte   ((BG+(8+8*r)*320) & $FF)
        .endrepeat
rb_mid: .repeat 25, r
        .byte   (((BG+(8+8*r)*320) >> 8) & $FF)
        .endrepeat
rb_hi:  .repeat 25, r
        .byte   ((BG+(8+8*r)*320) >> 16)
        .endrepeat
scr_lo: .repeat 8, yy
        .byte   ((BG+(11-yy)*320) & $FF)
        .endrepeat
scr_mid: .repeat 8, yy
        .byte   (((BG+(11-yy)*320) >> 8) & $FF)
        .endrepeat
scr_hi: .repeat 8, yy
        .byte   ((BG+(11-yy)*320) >> 16)
        .endrepeat
        .ifdef DCHK
dlog:   stx     $F6FE                   ; debug event ring (A = event)
        ldx     $F6FF
        sta     $F6A0,x
        lda     frame_ctr
        sta     $F6C0,x
        inx
        txa
        and     #31
        sta     $F6FF
        ldx     $F6FE
        rts
        .endif
        .ifdef RTL
rtl:    php                             ; debug timeline ring (A = event): event, frame, VCOUNT at $F6C0/$F6D5/$F6EA
        stx     $F6FE
        ldx     $F69D
        sta     $F6C0,x
        lda     frame_ctr
        sta     $F6D5,x
        lda     $D40B
        sta     $F6EA,x
        inx
        cpx     #21
        bcc     :+
        ldx     #0
:       stx     $F69D
        ldx     $F6FE
        plp
        rts
        .endif
dbase_mid: .byte ((D0 >> 8) & $FF), ((D1 >> 8) & $FF)
dbase_hi: .byte (D0 >> 16), (D1 >> 16)
cb_lo:  .repeat 36, k
        .byte   ((CBLK + 21*k) & $FF)
        .endrepeat
cb_hi:  .repeat 36, k
        .byte   (>WIN + ((CBLK + 21*k) >> 8))
        .endrepeat
blk_lo: .repeat 28, k
        .byte   ((BLK + 21*k) & $FF)
        .endrepeat
blk_hi: .repeat 28, k
        .byte   (>WIN + ((BLK + 21*k) >> 8))
        .endrepeat
dr_lo:  .repeat 300, k
        .byte   ((k*DPITCH) & $FF)
        .endrepeat
dr_mid: .repeat 300, k
        .byte   (((k*DPITCH) >> 8) & $FF)
        .endrepeat
dr_hi:  .repeat 300, k
        .byte   ((k*DPITCH) >> 16)
        .endrepeat
bgr_lo: .repeat 300, k                  ; BG address of the display-buffer line k (BG line k-DT)
        .byte   ((BG+(k-DT)*320) & $FF)
        .endrepeat
bgr_mid: .repeat 300, k
        .byte   (((BG+(k-DT)*320) >> 8) & $FF)
        .endrepeat
bgr_hi: .repeat 300, k
        .byte   (((BG+(k-DT)*320) >> 16) & $FF)
        .endrepeat
rdd_lo: .repeat 25, r                   ; display-buffer offset of text row r (cell column 0)
        .byte   (((DT+8+8*r)*DPITCH+48) & $FF)
        .endrepeat
rdd_mid: .repeat 25, r
        .byte   ((((DT+8+8*r)*DPITCH+48) >> 8) & $FF)
        .endrepeat
rdd_hi: .repeat 25, r
        .byte   (((DT+8+8*r)*DPITCH+48) >> 16)
        .endrepeat
cl_lo:  .repeat CL_N, k                  ; window address of compose block k (VRAM bank 1)
        .byte   ((WIN + 21*k) & $FF)
        .endrepeat
cl_hi:  .repeat CL_N, k
        .byte   ((WIN + 21*k) >> 8)
        .endrepeat
cla_lo: .repeat CL_N, k                  ; VRAM address of compose block k
        .byte   ((CL + 21*k) & $FF)
        .endrepeat
cla_mid: .repeat CL_N, k
        .byte   (((CL + 21*k) >> 8) & $FF)
        .endrepeat
kpos:   .repeat 1000, k                 ; cell index -> row, column*8
        .byte   (k / 40)
        .endrepeat
kcol:   .repeat 1000, k
        .byte   (k .mod 40)
        .endrepeat
bitm:   .byte   1,2,4,8,16,32,64,128

; blitter templates (21 bytes): src(3) srcstepy(2) srcstepx dst(3) dststepy(2) dststepx width-1(2) height-1 AND XOR coll zoom pattern ctl
tpl_cell:
        .byte   0,0,1, 8,0, 1, 0,0,0, <320,>320, 1, 7,0, 7, $FF,0,0,0,0, 0
tpl_compose:
        .byte   0,0,0, <320,>320, 1, 0,0,0, <DPITCH,>DPITCH, 1, <319,>319, 199, $FF,1,0,0,0, 1
tpl_fill:
        .byte   0,0,0, 0,0, 1, 0,0,0, <DPITCH,>DPITCH, 1, <319,>319, 199, 0,1,0,0,0, 0
tpl_restore:                            ; BG -> display buffer (value xor 1), opaque, NEXT
        .byte   0,0,0, <320,>320, 1, 0,0,0, <DPITCH,>DPITCH, 1, 0,0, 0, $FF,1,0,0,0, 8
; BG over a behind-characters sprite, where the C64 shows the characters in front: hires 1 / multicolour 10, 11
; (BG values odd: 3, 4k+3); bg0 / multicolour 01 (BG 0, 2: even) leave the sprite visible. The blitter tests a
; pixel for transparency after AND/XOR, so it takes three blocks through the scratch rectangle OVT:
;   A: OVT = BG xor 1 (the displayed values)   B: OVT = 1 where BG is even   C: display = OVT and $FE, 0 transparent
tpl_ova:
        .byte   0,0,0, <320,>320, 1, <OVT,>OVT,^OVT, OVTP,0, 1, 0,0, 0, $FF,1,0,0,0, 8
tpl_ovb:
        .byte   0,0,0, <320,>320, 1, <OVT,>OVT,^OVT, OVTP,0, 1, 0,0, 0, $01,1,0,0,0, 9
tpl_ovc:
        .byte   <OVT,>OVT,^OVT, OVTP,0, 1, 0,0,0, <DPITCH,>DPITCH, 1, 0,0, 0, $FE,0,0,0,0, 9
ov_tpl: .byte   0, 21, 42
tpl_sprite:
        .byte   0,0,0, 24,0, 1, 0,0,0, <DPITCH,>DPITCH, 1, 23,0, 20, $FF,0,0,0,0, 1
tpl_clear_bg:
        .byte   0,0,0, 0,0, 1, (BG & $FF), ((BG >> 8) & $FF), (BG >> 16), <320,>320, 1, <319,>319, 215, 0,0,0,0,0, 0
tpl_clear_d0:
        .byte   0,0,0, 0,0, 1, ((D0+0) & $FF), (((D0+0) >> 8) & $FF), ((D0+0) >> 16), <DPITCH,>DPITCH, 1, <(DPITCH-1),>(DPITCH-1), (DROWS/2-1), 0,1,0,0,0, 0
tpl_clear_d0b:
        .byte   0,0,0, 0,0, 1, ((D0+(DROWS/2)*DPITCH) & $FF), (((D0+(DROWS/2)*DPITCH) >> 8) & $FF), ((D0+(DROWS/2)*DPITCH) >> 16), <DPITCH,>DPITCH, 1, <(DPITCH-1),>(DPITCH-1), (DROWS/2-1), 0,1,0,0,0, 0
tpl_clear_d1:
        .byte   0,0,0, 0,0, 1, ((D1+0) & $FF), (((D1+0) >> 8) & $FF), ((D1+0) >> 16), <DPITCH,>DPITCH, 1, <(DPITCH-1),>(DPITCH-1), (DROWS/2-1), 0,1,0,0,0, 0
tpl_clear_d1b:
        .byte   0,0,0, 0,0, 1, ((D1+(DROWS/2)*DPITCH) & $FF), (((D1+(DROWS/2)*DPITCH) >> 8) & $FF), ((D1+(DROWS/2)*DPITCH) >> 16), <DPITCH,>DPITCH, 1, <(DPITCH-1),>(DPITCH-1), (DROWS/2-1), 0,1,0,0,0, 0
SKIP    = 20
xdl:    .byte   $20, $00, SKIP-1
        .byte   $62, $88, 199
        .byte   ((D0+(DT+8)*DPITCH+48) & $FF), (((D0+(DT+8)*DPITCH+48) >> 8) & $FF), ((D0+(DT+8)*DPITCH+48) >> 16)
        .word   DPITCH
        .byte   1, $FF
xdl_end:

; palidx, rgb_r/g/b: resident (colour.s)

; =================================================================================================================
; Sprites: for each enabled VIC sprite (7..0) one blitter block "copy if non-zero" from a pre-coloured image in the shape cache.
; Cache: 128 slots of 24x21 bytes (VRAM SPR), slot = shape pointer & 127, keyed by (pointer, colour, multicolour); the shape
; bytes are re-checksummed every 4th frame.

; zscr = C64 address of the shape for sv_ptr
shape_ptr:
        lda     $DD00
        eor     #3
        and     #3
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        asl     a
        sta     zscr+1                  ; VIC bank high byte
        lda     sv_ptr
        lsr     a
        lsr     a
        clc
        adc     zscr+1
        sta     zscr+1
        lda     sv_ptr
        and     #3
        lsr     a
        ror     a
        ror     a
        sta     zscr                    ; (ptr&3)*64
        rts

; key2 = colour | (multicolour ? $10 : 0)
sp_key2:
        lda     sv_col
        ldx     sv_mc
        beq     :+
        ora     #$10
:       rts

; Z=1 if cache slot X holds (sv_ptr, key sw_t4, shared colours sv_skey)
sp_match:
        lda     WIN+SPK_PTR,x
        cmp     sv_ptr
        bne     :+
        lda     WIN+SPK_COL,x
        cmp     sw_t4
        bne     :+
        lda     WIN+SPK_S,x
        cmp     sv_skey
        bne     :+
        lda     WIN+SPK_SUM,x
        cmp     sv_sum
        bne     :+
        lda     WIN+SPK_SUM2,x
        cmp     sv_sum2
:       rts

; Ensure the cache slot sv_slot holds the shape (sv_ptr, sv_col, sv_mc); bank 0 mapped on entry and exit.
sp_ensure:
        lda     #$80+(PSUM >> 12)       ; the content key of this pointer's shape (vu_check, this render)
        sta     VB_MEMS
        ldx     sv_ptr
        lda     WIN+(PSUM & $FFF),x
        sta     sv_sum
        lda     WIN+(PSUM & $FFF)+$100,x
        sta     sv_sum2
        lda     #WINB
        sta     VB_MEMS
        jsr     sp_key2
        sta     sw_t4                   ; key: colour | multicolour
        lda     sv_ptr
        eor     sw_t4                   ; colour variants of one shape land in different sets
        eor     sv_skey
        sta     sw_t3
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        eor     sw_t3
        and     #$0F
        sta     sw_t3                   ; set (16 sets x 4 ways)
        asl     a
        asl     a
        tax
        ldy     #4
@w:     jsr     sp_match
        beq     @hit
        inx
        dey
        bne     @w
        ldx     sw_t3                   ; miss: round-robin victim in the set
        lda     WIN+SPK_RR,x
        tay
        clc
        adc     #1
        and     #3
        sta     WIN+SPK_RR,x
        lda     sw_t3
        asl     a
        asl     a
        sty     sw_t3
        clc
        adc     sw_t3
        sta     sv_slot
        jmp     @conv
@hit:   stx     sv_slot
        rts                             ; (verify_used has checked this shape's RAM data in this render)
@conv:  inc     r_gen                   ; band caches referring to slots are stale now
        .ifdef LOOPCOUNT
        inc     $F6F6                   ; debug: shape conversions
        .endif
        ldx     sv_slot
        lda     sv_ptr
        sta     WIN+SPK_PTR,x
        lda     sw_t4
        ldx     sv_slot
        sta     WIN+SPK_COL,x
        lda     sv_skey
        sta     WIN+SPK_S,x
        lda     sv_sum
        sta     WIN+SPK_SUM,x
        lda     sv_sum2
        sta     WIN+SPK_SUM2,x
        .ifndef NO_CONVERT
        jsr     convert_shape
        .endif
        lda     #WINB
        sta     VB_MEMS
@ok:    rts

; Expand the 63 shape bytes into 24 (hires) or 12 (multicolour) bytes per row, 21 rows at a 24-byte stride.
convert_shape:
        lda     sv_col
        clc
        adc     #1
        asl     a
        asl     a
        ora     #2
        sta     zk                      ; displayed palette index of the sprite's own colour
        sta     sv_mct+2
        lda     #0
        sta     sv_mct
        lda     sv_s0                   ; shared colours of the band, as displayed palette indices
        clc
        adc     #1
        asl     a
        asl     a
        ora     #2
        sta     sv_mct+1
        lda     sv_s1
        clc
        adc     #1
        asl     a
        asl     a
        ora     #2
        sta     sv_mct+3
        lda     sv_slot
        lsr     a
        lsr     a
        lsr     a
        clc
        adc     #$80+(SPR >> 12)
        sta     VB_MEMS
        lda     sv_slot
        and     #7
        asl     a
        clc
        adc     #>WIN
        sta     zshs+1
        lda     #0
        sta     zshs
        jsr     shape_ptr
        lda     sv_mc
        sta     zmc
        beq     :++
        ldx     #15                     ; multicolour: per nibble the two displayed bytes (cv_m0: its high pair,
:       txa                             ; cv_m1: its low pair)
        lsr     a
        lsr     a
        tay
        lda     sv_mct,y
        sta     cv_m0,x
        txa
        and     #3
        tay
        lda     sv_mct,y
        sta     cv_m1,x
        dex
        bpl     :-
:       lda     #21
        sta     zcnt
@row:   jsr     ryield                  ; (a conversion is ~5000 cycles: the main loop may need the CPU)
        ldy     #0
        lda     #3
        sta     ztmp
@by:    ldx     #0
        lda     (zscr,x)
        sta     zb
        inc     zscr
        bne     :+
        inc     zscr+1
:       lda     zmc
        bne     @mc
        lda     zb
        bne     @hb
        ldx     #8                      ; (empty byte: 8 transparent pixels)
:       sta     (zshs),y
        iny
        dex
        bne     :-
        beq     @bd
@hb:    ldx     #8
@hp:    asl     zb
        lda     #0
        bcc     :+
        lda     zk
:       sta     (zshs),y
        iny
        dex
        bne     @hp
        beq     @bd
@mc:    lda     zb                      ; 4 pixel pairs: two per nibble from the tables
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        tax
        lda     cv_m0,x
        sta     (zshs),y
        iny
        lda     cv_m1,x
        sta     (zshs),y
        iny
        lda     zb
        and     #15
        tax
        lda     cv_m0,x
        sta     (zshs),y
        iny
        lda     cv_m1,x
        sta     (zshs),y
        iny
@bd:    dec     ztmp
        bne     @by
        lda     zshs
        clc
        adc     #24
        sta     zshs
        bcc     :+
        inc     zshs+1
:       dec     zcnt
        bne     @row
        rts

; Pieces of band sw_b -> its band cache (bank 2): one entry per visible sprite, clipped to the raster lines the band covers.
derive_band:
        .ifdef LOOPCOUNT
        inc     $F6FA                   ; debug: band derivations
        .endif
        jsr     bc_ptr
        ldy     #44
        lda     #0
        sta     (zshc),y
        ldy     #47
        sta     (zshc),y                ; any piece behind the characters
        ldx     sw_b
        lda     rband_off,x
        sta     sw_bb
        tax
        lda     RBANDS+B_START,x
        sta     sw_s
        lda     RBANDS+B_END,x
        cmp     sw_s
        beq     @e251
        bcc     @e251
        cmp     #251
        bcc     @eok
@e251:  lda     #251
@eok:   sta     sw_e
        lda     sw_s
        cmp     #251
        bcc     :+
        rts                             ; bands that start below the picture are invisible
:       ldx     #7
@s:     stx     sv_n
        lda     bitm,x
        sta     sv_bit
        ldx     sw_bb
        and     RBANDS+B_EN,x
        bne     @pri
        jmp     @next
@pri:   lda     sv_n
        asl     a
        clc
        adc     sw_bb
        tax
        lda     RBANDS+1,x               ; y
        sta     sv_y
        cmp     #8
        bcs     :+
        jmp     @next
:       cmp     #251
        bcc     :+
        jmp     @next
:       lda     RBANDS,x                ; x + 24 (9 bits)
        clc
        adc     #24
        sta     sv_xlo
        lda     #0
        adc     #0
        sta     sv_xhi
        ldx     sw_bb
        lda     RBANDS+B_MSB,x
        and     sv_bit
        beq     :+
        inc     sv_xhi
:       lda     sv_xhi
        cmp     #1
        bcc     @xok
        beq     :+
        jmp     @next
:       lda     sv_xlo
        cmp     #$71
        bcc     @xok
        jmp     @next
@xok:   lda     sv_n
        clc
        adc     sw_bb
        tax
        lda     RBANDS+B_COL,x
        and     #15
        sta     sv_col
        lda     RBANDS+B_PTR,x
        sta     sv_ptr
        ldx     sw_bb
        lda     RBANDS+B_S0,x
        and     #15
        sta     sv_s0
        lda     RBANDS+B_S1,x
        and     #15
        sta     sv_s1
        lda     RBANDS+B_MC,x
        and     sv_bit
        beq     :+
        lda     #1
:       sta     sv_mc
        beq     :+
        lda     sv_s1
        asl     a
        asl     a
        asl     a
        asl     a
        ora     sv_s0
        bne     :++
:       lda     #0
:       sta     sv_skey
        lda     RBANDS+B_YE,x
        and     sv_bit
        beq     :+
        lda     #1
:       sta     sw_ye
        ; vertical clip: raster lines [top, sw_e) of the band, sprite covers [y, y + 21*(1+ye))
        lda     sv_y
        cmp     sw_s
        bcs     :+
        lda     sw_s
:       sta     sw_top
        cmp     sw_e
        bcc     :+
        jmp     @next                   ; starts at or below the band's end
:       lda     sw_top
        sec
        sbc     sv_y
        sta     sw_skip                 ; lines of the sprite above the clip
        lda     #21
        ldx     sw_ye
        beq     :+
        lda     #42
:       sec
        sbc     sw_skip                 ; remaining sprite lines
        bcs     :+
        jmp     @next
:       beq     @gone
        sta     sw_lines
        lda     sw_e
        sec
        sbc     sw_top                  ; lines available in the band
        cmp     sw_lines
        bcs     :+
        sta     sw_lines
:       lda     sw_lines
        bne     :+
@gone:  jmp     @next
:       lda     #WINB
        sta     VB_MEMS
        jsr     sp_ensure
        jsr     bc_ptr
        ldy     #44
        lda     (zshc),y
        cmp     #8
        bcc     :+
        jmp     @next
:       asl     a
        asl     a
        asl     a
        asl     a
        adc     #48
        sta     sw_t2                   ; entry offset
        lda     sw_lines                ; rows to copy = ceil(lines / (1+ye))
        ldx     sw_ye
        beq     :+
        clc
        adc     #1
        lsr     a
:       sta     e_h
        lda     sw_skip                 ; first source row = skip >> ye
        ldx     sw_ye
        beq     :+
        lsr     a
:       tax
        lda     mul24_lo,x              ; src = SPR + slot*512 + row*24
        sta     e_src
        lda     sv_slot
        asl     a
        clc
        adc     #((SPR >> 8) & $FF)
        adc     mul24_hi,x
        sta     e_src+1
        ldx     sw_bb
        lda     RBANDS+B_XE,x
        and     sv_bit
        sta     e_k                     ; x-expanded
        lda     sv_mc
        beq     @hw
        lda     #11
        sta     e_w
        lda     e_k
        beq     :+
        lda     #3
        bne     @xz
:       lda     #1
        bne     @xz
@hw:    lda     #23
        sta     e_w
        lda     e_k
        beq     :+
        lda     #1
        bne     @xz
:       lda     #0
@xz:    ldx     sw_ye
        beq     :+
        ora     #$10
:       sta     sv_base                 ; zoom
        ldy     sw_t2
        lda     sw_b
        asl     a
        asl     a
        asl     a
        sta     e_bit
        lda     #7
        sec
        sbc     sv_n
        ora     e_bit
        sta     (zshc),y                ; 0 key
        iny
        lda     sw_top
        clc
        adc     #3
        sec
        sbc     r_cys
        sta     (zshc),y                ; 1 display-buffer line = top + 3 - Y-scroll
        iny
        lda     sv_xlo
        sta     (zshc),y                ; 2/3 column = x + 24
        iny
        lda     sv_xhi
        sta     (zshc),y
        iny
        lda     e_k
        beq     :+
        lda     #47
        bne     :++
:       lda     #23
:       sta     (zshc),y                ; 4 width-1
        iny
        lda     e_h
        ldx     sw_ye
        beq     :+
        asl     a
:       sec
        sbc     #1
        sta     (zshc),y                ; 5 height-1
        iny
        lda     e_src
        sta     (zshc),y                ; 6-8 source
        iny
        lda     e_src+1
        sta     (zshc),y
        iny
        lda     #(SPR >> 16)
        sta     (zshc),y
        iny
        lda     e_w
        sta     (zshc),y                ; 9 block width-1
        iny
        lda     e_h
        sec
        sbc     #1
        sta     (zshc),y                ; 10 rows-1
        iny
        lda     sv_base
        sta     (zshc),y                ; 11 zoom
        iny
        ldx     sw_bb
        lda     RBANDS+B_PRI,x
        and     sv_bit
        .ifdef NO_BEHIND
        lda     #0                      ; debug: every sprite in front of the characters
        .endif
        beq     :+
        ldy     #47
        lda     #1
        sta     (zshc),y
        ldy     sw_t2
        tya
        clc
        adc     #12
        tay
        lda     #1
:       sta     (zshc),y                ; 12 behind the characters
        ldy     #44
        lda     (zshc),y
        clc
        adc     #1
        sta     (zshc),y
@next:  ldx     sv_n
        dex
        bmi     :+
        jmp     @s
:       rts

rband_off: .byte 0, 48, 96, 144, 192
bco_lo: .repeat 5, k
        .byte   <(WIN + BC_OFF + k*176)
        .endrepeat
bco_hi: .repeat 5, k
        .byte   >(WIN + BC_OFF + k*176)
        .endrepeat
obo_lo: .repeat 10, k                   ; old-piece lists per (buffer, band) in VRAM bank 1
        .byte   <(WIN + OB_OFF + k*OB_SZ)
        .endrepeat
obo_hi: .repeat 10, k
        .byte   >(WIN + OB_OFF + k*OB_SZ)
        .endrepeat
mul24_lo: .repeat 22, k
        .byte   ((k*24) & $FF)
        .endrepeat
mul24_hi: .repeat 22, k
        .byte   ((k*24) >> 8)
        .endrepeat

; =================================================================================================================
; Overworld screen scrolls (scroll.s): the rows below the HUD come from the playfield's own screen base, which the game
; flips between $0800 and $2000 every scroll step; each step moves the playfield one text row or column (horizontal
; scrolls add a 4-pixel fine X-scroll in between, not shown here). Instead of redrawing ~880 cells per step, the step is
; recognised from samples and BG and both shadows are moved with the blitter; the scan then draws the new edge.

; This render's playfield base: psn = its $D018, psr = first text row using it (25: no split).
pf_snap:
        php
        sei                             ; (base and step count of the same moment)
        lda     pf_life
        beq     @no
        lda     pf_d018
        sta     psn
        lda     pf_top
        sta     ptop
        lda     pf_steps
        tax
        sec
        sbc     pf_done
        clc
        adc     pf_new                  ; (a render that ended early leaves its steps for the next)
        sta     pf_new
        stx     pf_done
        plp
        lda     pf_line                 ; first row whose bad line follows the write: (line - 51 + 7) / 8
        sec
        sbc     #44
        lsr     a
        lsr     a
        lsr     a
        cmp     #1
        bcs     :+
        lda     #1
:       cmp     #24
        bcc     :+
        lda     #24
:       sta     psr
        rts
@no:    lda     pf_steps
        sta     pf_done
        lda     #0
        sta     pf_new
        plp
        lda     VSN+$08
        sta     psn
        sta     ptop
        lda     #25
        sta     psr
        rts

; After a yield: if the game flipped the playfield meanwhile, its main loop may already be rewriting the buffer this
; render reads (the old one) with the step after: take the new base and step now. (Between yields the main loop does
; not run, so the buffer cannot change under the scan; a flip alone, from the line-72 IRQ, changes nothing in RAM.)
pf_check:
        lda     psr
        cmp     #25
        beq     :+
        lda     pf_steps
        cmp     pf_done
        bne     @new
        lda     frame_ctr               ; no new step: refresh the edge once per frame (colours follow a frame later)
        cmp     ef_last
        beq     :+
        lda     #WINB
        sta     VB_MEMS
        lda     zrow
        pha
        jsr     edge_refresh
        pla
        sta     zrow
        rts
@new:
        lda     zrow
        pha
        jsr     pf_snap
        jsr     pf_shift
        pla
        sta     zrow
:       rts

; Z = 0: a scroll step is under 2 frames old, so colour RAM (which the game moves after the flip, in two halves) may
; still hold the step before: colour-only differences are not drawn yet. (keeps X, Y)
pf_cwait:
        lda     psr
        cmp     #25
        beq     :++
        lda     frame_ctr
        sec
        sbc     pf_ff
        cmp     #2
        bcs     :+
        lda     #1
        rts
:       lda     #0
:       rts

; X = text row -> A = high byte of its screen RAM base (keeps X, Y)
rbase:  cpx     psr
        bcs     :+
        lda     ptop
        jmp     @c
:       lda     psn
@c:     lsr     a
        lsr     a
        and     #$3C
        rts

; Apply the scroll steps since the last render: the picture moves the opposite way to Link ($0DF7: the game's scroll
; direction, 0 down, 1 up, 2 left, 3 right).
pf_shift:
        lda     #0
        sta     r_hold                  ; (shift_check's hold does not apply here)
        sta     r_holdn
        lda     pf_new
        beq     @none
        ldx     #0
        stx     pf_new
        cmp     #20
        bcs     @none                   ; (that far: everything is redrawn anyway)
        sta     pd_k
        lda     $0DF7
        and     #3
        tax
        lda     pc_dir4,x
        sta     pd_dir
        lda     #WINB
        sta     VB_MEMS
        jsr     pf_do
        lda     r_hidden                ; the shown picture has no variants yet (composed before the split): now
        eor     #1
        tax
        lda     xv_ok,x
        bne     :+
        jsr     xdl_shown
:       jmp     edge_fill               ; the shown picture's edge: the incoming rows/columns (xdl_vars)               ; the shown picture's edge: the incoming rows/columns (xdl_vars)
@none:  rts
pc_dir4: .byte  0, 1, 3, 2              ; -> 0 up, 1 down, 2 left, 3 right (the way the picture moves)

; Move rows psr..24 of BG, the screen shadow and the colour shadow pd_k rows/columns the way pd_dir. Rows/columns that
; come in keep their old contents with matching shadows (the scan redraws them where screen RAM differs).
pf_do:  jsr     vx_wait                 ; (the last compose chain reads BG)
        jsr     set_bl
        lda     #1                      ; planes 1, 2 (the shadows: the scan below compares them), then 0 (BG, the
        sta     pd_pl                   ; big one: not waited for, the scan runs meanwhile; flush_cells waits)
@pl:    lda     #<tpl_pfs
        ldx     #>tpl_pfs
        jsr     load_tpl
        ldy     pd_pl
        lda     pl_p_lo,y
        sta     WIN+BLK+3
        sta     WIN+BLK+9
        lda     pl_p_hi,y
        sta     WIN+BLK+4
        sta     WIN+BLK+10
        lda     pd_dir
        cmp     #2
        bcs     @h
        lda     pl_w_lo,y               ; vertical: whole rows, (n - k) of them
        sta     WIN+BLK+12
        lda     pl_w_hi,y
        sta     WIN+BLK+13
        lda     #25
        sec
        sbc     psr
        sec
        sbc     pd_k
        jsr     pd_hgt
        lda     pd_dir
        bne     @dn
        lda     psr                     ; up: rows a+k.. -> a..
        clc
        adc     pd_k
        tax
        jsr     pd_row
        jsr     pd_src
        ldx     psr
        jsr     pd_row
        jsr     pd_dst
        jmp     @go
@dn:    lda     #24                     ; down: bottom up, last line of row 24-k -> last line of row 24
        sec
        sbc     pd_k
        tax
        jsr     pd_row
        jsr     pd_last
        jsr     pd_src
        ldx     #24
        jsr     pd_row
        jsr     pd_last
        jsr     pd_dst
        ldy     pd_pl
        lda     pl_n_lo,y
        sta     WIN+BLK+3
        sta     WIN+BLK+9
        lda     pl_n_hi,y
        sta     WIN+BLK+4
        sta     WIN+BLK+10
        jmp     @go
@h:     lda     #25                     ; horizontal: all n rows, the 32 playfield columns (4-35) less k
        sec
        sbc     psr
        jsr     pd_hgt
        ldy     pd_pl
        lda     pd_k                    ; kc = k columns in bytes (BG: 8 per column)
        sta     pd_kc
        lda     #0
        sta     pd_kc+1
        cpy     #0
        bne     :+
        asl     pd_kc
        asl     pd_kc
        asl     pd_kc
:       lda     pl_hw,y                 ; width-1 = W-1-kc
        sec
        sbc     pd_kc
        sta     WIN+BLK+12
        lda     #0
        sbc     pd_kc+1
        sta     WIN+BLK+13
        ldx     psr
        jsr     pd_row
        ldy     pd_pl
        lda     pl_c0,y                 ; column 4
        ldx     #0
        jsr     pd_add
        lda     pd_dir
        cmp     #2
        bne     @rt
        jsr     pd_dst                  ; left: column k.. -> 0..
        lda     pd_kc
        ldx     pd_kc+1
        jsr     pd_add
        jsr     pd_src
        jmp     @go
@rt:    lda     pd_t                    ; right: right to left, column 39-k -> 39
        sta     pd_s
        lda     pd_t+1
        sta     pd_s+1
        lda     pd_t+2
        sta     pd_s+2
        lda     WIN+BLK+12              ; src = row + (W-1-kc)
        ldx     WIN+BLK+13
        jsr     pd_add
        jsr     pd_src
        lda     pd_s                    ; dst = row + (W-1)
        sta     pd_t
        lda     pd_s+1
        sta     pd_t+1
        lda     pd_s+2
        sta     pd_t+2
        ldy     pd_pl
        lda     pl_hw,y
        ldx     #0
        jsr     pd_add
        jsr     pd_dst
        lda     #$FF
        sta     WIN+BLK+5
        sta     WIN+BLK+11
@go:    lda     pd_pl
        beq     @bg
        jsr     blit
        inc     pd_pl
        lda     pd_pl
        cmp     #3
        bne     :+
        lda     #0
        sta     pd_pl
:       jmp     @pl
@bg:    jsr     vx_wait
        lda     #1
        sta     VB_BLGO                 ; (runs while the incoming cells are scanned)
        .ifdef LOOPCOUNT
        inc     $F6F8                   ; debug: BG shifts
        .endif
        lda     #0
        sta     r_dv                    ; both display buffers need the whole shifted BG
        sta     r_dv+1
        ldx     psr                     ; the colours follow a frame later (the game rewrites colour RAM in two halves):
        lda     #1                      ; look at every playfield row once more (the incoming cells: edge_refresh)
:       sta     r_hot,x
        inx
        cpx     #25
        bne     :-
        ; the incoming rows / columns now
        lda     pd_dir
        cmp     #2
        bcs     @eh
        ldx     psr                     ; down: rows psr .. psr+k-1
        cmp     #1
        beq     :+
        lda     #25                     ; up: rows 25-k .. 24
        sec
        sbc     pd_k
        tax
:       stx     zrow
        jsr     scan_row
        ldx     zrow
        inx
        dec     pd_k
        bne     :-
        jmp     flush_cells
@eh:    ldx     #4                      ; right: columns 4 .. 3+k
        cmp     #3
        beq     :+
        lda     #36                     ; left: columns 36-k .. 35
        sec
        sbc     pd_k
        tax
:       stx     pd_s                    ; first column
        txa
        clc
        adc     pd_k
        sta     pd_s+1                  ; end column
        lda     psr
        sta     zrow
:       jsr     row_ptrs
        lda     pd_s+1
        sta     sr_end
        ldy     pd_s
        jsr     scan_rng
        inc     zrow
        lda     zrow
        cmp     #25
        bne     :-
        jmp     flush_cells

; pd_t = address of text row X (column 0, first line) in plane pd_pl (0 BG, 1 screen shadow, 2 colour shadow)
pd_row: ldy     pd_pl
        bne     :+
        lda     rb_lo,x
        sta     pd_t
        lda     rb_mid,x
        sta     pd_t+1
        lda     rb_hi,x
        sta     pd_t+2
        rts
:       lda     rowoff_lo,x
        sta     pd_t
        lda     rowoff_hi,x
        clc
        adc     pl_sh,y
        sta     pd_t+1
        lda     #0
        sta     pd_t+2
        rts
; pd_t += X:A (unsigned)
pd_add: clc
        adc     pd_t
        sta     pd_t
        txa
        adc     pd_t+1
        sta     pd_t+1
        lda     pd_t+2
        adc     #0
        sta     pd_t+2
        rts
; BG: pd_t += 7 lines (the last line of the row)
pd_last:
        lda     pd_pl
        bne     :+
        lda     #<(7*320)
        ldx     #>(7*320)
        jmp     pd_add
:       rts
; A = rows -> height-1 in lines
pd_hgt: ldy     pd_pl
        bne     :+
        asl     a
        asl     a
        asl     a
:       sec
        sbc     #1
        sta     WIN+BLK+14
        rts
pd_src: lda     pd_t
        sta     WIN+BLK
        lda     pd_t+1
        sta     WIN+BLK+1
        lda     pd_t+2
        sta     WIN+BLK+2
        rts
pd_dst: lda     pd_t
        sta     WIN+BLK+6
        lda     pd_t+1
        sta     WIN+BLK+7
        lda     pd_t+2
        sta     WIN+BLK+8
        rts

pl_p_lo: .byte  <320, 40, 40            ; line pitch, and its negative in 13 bits (bottom-up copies)
pl_p_hi: .byte  >320, 0, 0
pl_n_lo: .byte  <($2000-320), <($2000-40), <($2000-40)
pl_n_hi: .byte  >($2000-320), >($2000-40), >($2000-40)
pl_w_lo: .byte  <319, 39, 39            ; row width - 1
pl_w_hi: .byte  >319, 0, 0
pl_sh:  .byte   0, >SHS, >SHC           ; shadow planes: VRAM bank 0 ($0800 / $0C00)
pl_hw:  .byte   255, 31, 31             ; horizontal scrolls: playfield width - 1 (columns 4-35; 0-3, 36-39 stay)
pl_c0:  .byte   32, 4, 4                ; and its column 4
tpl_pfs:
        .byte   0,0,0, 0,0, 1, 0,0,0, 0,0, 1, 0,0, 0, $FF,0,0,0,0, 0

; =================================================================================================================
; One-row scroll shift. At YSCROLL 7 the game may have moved the whole screen up one text row. Sample 88 cells: if they match
; the shadow shifted by one row (and mostly differ from the unshifted shadow) move BG and both shadows up with three blits,
; instead of redrawing ~900 cells. The scan then fixes the bottom row and any stragglers.
shift_check:
        .ifdef NO_SHIFT
        rts
        .endif
        lda     $14                     ; normal play (mode 5): the screen does not shift rows (the overworld scrolls
        cmp     #5                      ; through the playfield split): every 4th render only (its quick test alone
        bne     :+                      ; was ~6% of the CPU)
        lda     r_rcnt
        and     #3
        beq     :+
        rts
:
        lda     #WINB                   ; (at any Y-scroll: renders need not catch the frames right after the step)
        sta     VB_MEMS
        lda     #0
        sta     sh_qc
        ldx     #11                     ; quick test: 12 cells over the screen unchanged -> nothing scrolled
@pc:    stx     zrow                    ; (sh_qc: how many changed, their characters or colours)
        lda     pc_row,x
        tax
        jsr     sh_ptrs
        ldx     zrow
        ldy     pc_col,x
        lda     (zscr),y
        cmp     (zshs),y
        bne     @qc
        jsr     shc_on
        lda     (zcol),y                ; and its colour (the game moves colours in separate passes)
        and     #15
        cmp     (zshs),y
        php
        jsr     shc_off
        plp
        beq     @qn
@qc:    inc     sh_qc
@qn:    ldx     zrow
        dex
        bpl     @pc
        lda     sh_qc
        bne     @chg
        sta     r_hold                  ; nothing moved: no half-done shift either
        sta     r_holdn
        rts
@chg:   lda     #0
        sta     sh_mv
        ldx     #0                      ; per row: do 4 samples of RAM row r match the shadow of row r+1?
@row:   stx     zrow
        jsr     sh_ptrs
        lda     #0
        sta     sv_cnt
        sta     sv_cnt2
        ldy     #4
        jsr     samp
        ldy     #14
        jsr     samp
        ldy     #27
        jsr     samp
        ldy     #36
        jsr     samp
        lda     #0
        sta     sh_c3
        sta     sh_c4
        jsr     shc_on
        ldy     #4
        jsr     samp_c
        ldy     #14
        jsr     samp_c
        ldy     #27
        jsr     samp_c
        ldy     #36
        jsr     samp_c
        jsr     shc_off
        lda     sh_c3                   ; colours moved here (matching the next row's, not their own)
        cmp     #3
        bcc     :+
        lda     sh_c4
        beq     :+
        inc     sh_mv
:       ldx     zrow
        lda     #0
        ldy     sv_cnt
        cpy     #4
        bne     :+
        lda     #1
        ldy     sv_cnt2
        beq     :+
        inc     sh_mv
        lda     #3                      ; matches the next row and differs from its own: a moved row
:       sta     SCAND,x
        inx
        cpx     #24
        bne     @row
        ; the longest run of matching rows with at least two moved rows (the game may shift the screen in parts)
        lda     #0
        sta     sh_len
        ldx     #0
@run:   cpx     #24
        bcs     @rd
        lda     SCAND,x
        bne     :+
        inx
        bne     @run
:       stx     sw_t2                   ; run start
        lda     #0
        sta     sw_t3                   ; moved rows in it
:       lda     SCAND,x
        beq     :+
        and     #2
        beq     @nm
        inc     sw_t3
@nm:    inx
        cpx     #24
        bcc     :-
:       stx     sw_t4                   ; run end (exclusive)
        lda     sw_t3
        cmp     #2
        bcc     @run
        txa
        sec
        sbc     sw_t2
        cmp     sh_len
        bcc     @run
        sta     sh_len
        lda     sw_t2
        sta     sh_a
        jmp     @run
@rd:    lda     sh_len
        cmp     #3
        bcs     :+
        jmp     sh_half                 ; no shift (yet): moved rows mean the game is half way through one
:       lda     sh_a                    ; exact check of the run
        sta     zrow
@vr:    ldx     zrow
        jsr     sh_ptrs
        ldy     #39
:       lda     (zscr),y
        cmp     (zshc),y
        bne     @bad
        dey
        bpl     :-
        inc     zrow
        lda     sh_a
        clc
        adc     sh_len
        cmp     zrow
        bne     @vr
        jmp     @cv
@bad:   jmp     sh_half
@cv:    lda     sh_a                    ; the colours of the run must have moved too, or the picture is half done
        sta     zrow
@cr:    ldx     zrow
        jsr     sh_ptrs
        jsr     shc_on
        ldy     #39
:       lda     (zshc),y
        cmp     #$FF
        beq     @cok                    ; (unknown colour: redrawn by the scan anyway)
        lda     (zcol),y
        and     #15
        cmp     (zshc),y
        beq     @cok
        jsr     shc_off
        jmp     sh_half
@cok:   dey
        bpl     :-
        jsr     shc_off
        inc     zrow
        lda     sh_a
        clc
        adc     sh_len
        cmp     zrow
        bne     @cr
@do:    jsr     vx_wait
        jsr     set_bl
        lda     #<tpl_shift_bg          ; BG text rows a+1..a+len -> a..a+len-1
        ldx     #>tpl_shift_bg
        jsr     load_tpl
        ldx     sh_a
        lda     rb_lo+1,x
        sta     WIN+BLK
        lda     rb_mid+1,x
        sta     WIN+BLK+1
        lda     rb_hi+1,x
        sta     WIN+BLK+2
        lda     rb_lo,x
        sta     WIN+BLK+6
        lda     rb_mid,x
        sta     WIN+BLK+7
        lda     rb_hi,x
        sta     WIN+BLK+8
        lda     sh_len
        asl     a
        asl     a
        asl     a
        sec
        sbc     #1
        sta     WIN+BLK+14
        jsr     blit
        lda     #<tpl_shift_sh1
        ldx     #>tpl_shift_sh1
        jsr     sh_shadow
        lda     #<tpl_shift_sh2
        ldx     #>tpl_shift_sh2
        jsr     sh_shadow
        .ifdef DCHK
        lda     #0
        sta     $F675
        lda     #$30
        jsr     dlog
        .endif
        .ifdef LOOPCOUNT
        inc     $F6F8                   ; debug: BG row shifts
        .endif
        lda     #0
        sta     r_dv                    ; both display buffers need the whole shifted BG
        sta     r_dv+1
        lda     #1
        sta     r_fsc
        lda     r_blank                 ; black after the title: the scroller has started
        cmp     #5
        bne     :+
        jsr     bl_end
:
        ldx     sh_a                    ; watch the rows of the run and the one below it
        ldy     sh_len
        iny
        lda     #8
:       cpx     #25
        bcs     :+
        sta     r_hot,x
        inx
        dey
        bne     :-
:       lda     sh_a                    ; the shift reached the bottom row: the picture is whole again
        clc
        adc     sh_len
        cmp     #24
        bcc     sh_half
        lda     #0
        sta     r_hold
        sta     r_holdn
        rts

; The C64 shifts the screen in parts (the top rows right after the raster has shown them, the rest in the vertical blank),
; so it never shows the half-shifted screen: neither do we. Hold the picture (at most 3 renders) until the rest has moved.
sh_half:
        lda     sh_mv
        beq     @ns
        lda     r_holdn
        cmp     #3
        bcs     :+
        inc     r_holdn
        lda     #1
        sta     r_hold
        rts
:       lda     #0
        sta     r_hold
        sta     r_holdn
        rts
@ns:    sta     r_hold                  ; (A = 0) sampled cells changed, no rows moved: the screen was rewritten (a
        sta     r_holdn                 ; new screen: the story after the title, a menu): a full compare now, not at
        lda     $14                     ; the next periodic one (every 16th render while still: seconds on the
        cmp     #5                      ; CPU-bound title)
        beq     :+                      ; (not in normal play: enemies and the HUD change sampled cells)
        lda     sh_qc                   ; half the samples or more: a whole new screen (fewer: the story's text;
        cmp     #6                      ; a full compare at each was too slow for the game). Hidden (black) until
        bcc     :+                      ; the picture has caught up with it (r_blank 6, scan_chunk): the old screen
        lda     #1                      ; showed in the new one's colours for up to 40 frames (they apply at once)
        sta     r_fsc
        lda     r_blank
        bne     :+
        lda     #6
        sta     r_blank
        lda     #0
        sta     VB_CORE
        lda     frame_ctr
        sta     ex_t
:       rts

pc_row: .byte   2, 5, 8, 11, 14, 17, 20, 18, 0, 1, 0, 1     ; (not the bottom rows: new text appears there)
pc_col: .byte   9, 30, 17, 5, 34, 21, 12, 26, 13, 15, 27, 25

; Shadow (screen or colour, template A/X) rows a+1..a+len -> a..a+len-1.
sh_shadow:
        jsr     load_tpl
        ldx     sh_a
        lda     WIN+BLK+6               ; template dst = shadow base: + a*40, src = + 40
        clc
        adc     rowoff_lo,x
        sta     WIN+BLK+6
        lda     WIN+BLK+7
        adc     rowoff_hi,x
        sta     WIN+BLK+7
        lda     WIN+BLK+6
        clc
        adc     #40
        sta     WIN+BLK
        lda     WIN+BLK+7
        adc     #0
        sta     WIN+BLK+1
        lda     sh_len
        sec
        sbc     #1
        sta     WIN+BLK+14
        jmp     blit

; Row X: zscr = screen RAM row, zshs = its shadow, zshc = the shadow of the next row.
sh_ptrs:
        lda     rowoff_lo,x
        sta     zscr
        sta     zshs
        lda     rowoff_hi,x
        sta     ztmp
        jsr     rbase
        clc
        adc     ztmp
        sta     zscr+1
        lda     ztmp
        clc
        adc     #>(WIN+SHS)
        sta     zshs+1
        lda     zshs
        clc
        adc     #40
        sta     zshc
        lda     zshs+1
        adc     #0
        sta     zshc+1
        lda     zscr                    ; zcol = colour RAM row
        sta     zcol
        lda     ztmp
        clc
        adc     #$D8
        sta     zcol+1
        rts

; zshs/zshc -> the colour shadow rows (SHC = SHS + $400) and back.
shc_on: lda     zshs+1
        clc
        adc     #4
        sta     zshs+1
        lda     zshc+1
        clc
        adc     #4
        sta     zshc+1
        rts
shc_off:
        lda     zshs+1
        sec
        sbc     #4
        sta     zshs+1
        lda     zshc+1
        sec
        sbc     #4
        sta     zshc+1
        rts

samp_c: lda     (zcol),y                ; colour sample (shadow pointers on the colour shadow)
        and     #15
        sta     ztmp
        cmp     (zshc),y
        bne     :+
        inc     sh_c3
:       lda     ztmp
        cmp     (zshs),y
        beq     :+
        inc     sh_c4
:       rts

samp:   lda     (zscr),y
        cmp     (zshc),y
        bne     :+
        inc     sv_cnt
:       lda     (zscr),y
        cmp     (zshs),y
        beq     :+
        inc     sv_cnt2
:       rts

tpl_shift_bg:                           ; BG rows 1..24 -> rows 0..23 (192 lines)
        .byte   ((BG+16*320) & $FF), (((BG+16*320) >> 8) & $FF), ((BG+16*320) >> 16), <320,>320, 1
        .byte   ((BG+8*320) & $FF), (((BG+8*320) >> 8) & $FF), ((BG+8*320) >> 16), <320,>320, 1, <319,>319, 191, $FF,0,0,0,0, 0
tpl_shift_sh1:                          ; screen shadow up one row: 24 rows of 40 (blitter width is max 512 bytes)
        .byte   <(SHS+40),>(SHS+40),0, 40,0, 1, <SHS,>SHS,0, 40,0, 1, 39,0, 23, $FF,0,0,0,0, 0
tpl_shift_sh2:                          ; colour shadow up one row
        .byte   <(SHC+40),>(SHC+40),0, 40,0, 1, <SHC,>SHC,0, 40,0, 1, 39,0, 23, $FF,0,0,0,0, 0
