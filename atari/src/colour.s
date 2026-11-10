; Live background colours. The game splits the screen colours with raster IRQs (overworld: $D022/$D023 = HUD colours at
; line 14, playfield colours at line 74). Each write to $D021-$D023 (tools/patches.py -> hook_c2Nr) stores the shadow
; and sets the VBXE palette entry at once, so the split happens on the screen line where the C64 makes it; the BG and
; display buffers hold palette indices, not colours, so the composed pictures need no change. The renderer's
; palette_update leaves these entries alone and skips its own palette writes while hc_busy is set.
; Our handlers run some lines after their DLI (NMI, KERNAL entry, the $D012 hook's sprite snapshot) and are sometimes
; deferred further, so a split made by a handler lands ~10 lines low. Each write is therefore also recorded as
; (event line, register, value) with the Atari line where the C64 makes it (event line - 22 + 2, the DLI one line before). Every live entry
; has its own DLI bit on that display list line, set at each VBI (hc_vbi); the DLI sets the colour (hc_rep) and only
; then does the NMI look for a raster event. Entries the game did not write again during a frame are dropped at the
; VBI after HF_LIFE frames. Writes outside raster handlers count for the last event (harmless: replaying a value the register holds).
; Resident (RAM $DD10-$DDFF: unused CIA2 mirror range; the game only touches $DD00/$DD02/$DD0D).
        .include "atari.inc"
        .export hook_c21a, hook_c22a, hook_c23a, hook_c22x, hook_c23y, rgb_r, rgb_g, rgb_b, palidx, hc_busy
        .export hc_rep, hc_vbi, hc_ev, hl, hla, hr, hv
        .import pf_vbi
HF_LIFE = 8                             ; frames a split entry lives without the game writing it again
        .segment "RES6"

hook_c21a:
        sta     VSH+$21
        php
        pha
        lda     #1
        bne     hc
hook_c22a:
        sta     VSH+$22
        php
        pha
        lda     #2
        bne     hc
hook_c23a:
        sta     VSH+$23
        php
        pha
        lda     #3
        bne     hc
hook_c22x:
        stx     VSH+$22
        php
        pha
        lda     #2
        bne     hc
hook_c23y:
        sty     VSH+$23
        php
        pha
        lda     #3
hc:     sei                             ; (the caller's P is on the stack; no emulated IRQ between the palette writes)
        stx     hc_x
        sty     hc_y
        tax
        inc     hc_busy
        lda     hc_ev                   ; record (event line, register, value) for the next frame
        cmp     #8
        bcc     @live                   ; (C64 lines 0-7: not replayed; line 8 = the VBI event, whose handler may be
                                        ; deferred into the picture, replays at Atari line 12)
        cmp     #250                    ; (250 and below: the lower border, not replayed either; a late line-250
        bcs     @live                   ; handler runs the line-8 code itself, and its splits filed under 250
                                        ; evicted the line-72 one from the full table: the playfield top was white)
        ldy     #3
@f:     lda     hl,y
        cmp     hc_ev
        bne     :+
        txa
        cmp     hr,y
        beq     @put
:       dey
        bpl     @f
        ldy     #3
:       lda     hl,y
        beq     @new
        dey
        bpl     :-
        ldy     #0                      ; (table full: replace the first)
@new:   lda     hc_ev
        sta     hl,y
        cmp     #32                     ; DLI line: the C64 write's Atari line (T-22, +2: the C64 handler's own
        bcs     :+                      ; latency) less one: the palette writes end ~130 cycles after the DLI, so
        lda     #32                     ; the colours change at the start of the C64's line (C64 9-31: Atari 11)
:       sec
        sbc     #21
        sta     hla,y
        txa
        sta     hr,y
        bpl     @val
@put:   lda     VSH+$20,x               ; a known split with the same value: its DLI sets it on the right line (a
        cmp     hv,y                    ; late handler writing it now would undo a later split)
        beq     @fr                     ; (C = 1: not written live)
@val:   lda     VSH+$20,x
        sta     hv,y
        clc
@fr:    lda     #HF_LIFE
        sta     hf,y
        bcs     @nr
@live:  lda     #0
        sta     VB_PSEL
        lda     palidx,x
        sta     VB_CSEL
        lda     VSH+$20,x
        and     #15
        tay
        lda     rgb_r,y
        sta     VB_CR
        lda     rgb_g,y
        sta     VB_CG
        lda     rgb_b,y
        sta     VB_CB
@nr:    lda     $D40B                   ; queued splits due by now: a DLI during this write skipped them (it
        sta     hc_v                    ; leaves the palette to the write), and a known value is not written live,
        jsr     hc_rq                   ; so the playfield top kept the HUD's colour until the next DLI
        dec     hc_busy
        ldx     hc_x
        ldy     hc_y
        pla
        plp
        rts

rgb_r:  .byte   $00,$FF,$68,$70,$6F,$58,$35,$B8,$6F,$43,$9A,$44,$6C,$9A,$6C,$95
rgb_g:  .byte   $00,$FF,$37,$A4,$3D,$8D,$28,$C7,$4F,$39,$67,$44,$6C,$D2,$5E,$95
        .segment "RES3"                 ; (RES6 is full)
rgb_b:  .byte   $00,$FF,$2B,$B2,$86,$43,$79,$6F,$25,$00,$59,$44,$6C,$84,$B5,$95
        .segment "RES7"                 ; (RAM $DF00-$DF7F: EF I/O-2 RAM the game never uses; its EAPI table is at $DF80)
; VBI (A saved by the caller; X, Y kept): the frame's line-8 event; drop the entries not written for HF_LIFE frames
; (and their DLI bits, unless a raster event waits there), set the DLI bits of the others
hc_vbi: lda     #8
        sta     hc_ev
        txa
        pha
        tya
        pha
        ldy     #3
@a:     lda     hl,y
        beq     @x
        lda     hla,y
        sec
        sbc     #9
        tax                             ; display list entry
        lda     hf,y
        bne     @k
        sta     hl,y                    ; (A = 0) dropped
        cpx     dl_idx
        beq     @x
        lda     DLB,x
        and     #$7F
        sta     DLB,x
        jmp     @x
@k:     lda     DLB,x
        ora     #$80
        sta     DLB,x
        lda     hf,y                    ; (frames left without a write: a raster event that slips a frame must not
        sec                             ; drop the split)
        sbc     #1
        sta     hf,y
@x:     dey
        bpl     @a
        pla
        tay
        pla
        tax
        jmp     pf_vbi                  ; (scroll.s: playfield split ageing)

palidx: .byte   8, 1, 3, 2                ; displayed index = BG value xor 1: border -> 8 (COLBK), bg0 -> 1, bg1 -> 3, bg2 -> 2
hc_x:   .byte   0
hc_y:   .byte   0
hc_busy: .byte  0
hc_ev:  .byte   8
hl:     .byte   0, 0, 0, 0              ; split table: C64 event line (0 = free), register (1-3), value, written this frame
hr:     .byte   0, 0, 0, 0
hv:     .byte   0, 0, 0, 0
hf:     .byte   0, 0, 0, 0
hla:    .byte   0, 0, 0, 0              ; Atari line of the entry's DLI

        .segment "RES8"                 ; (RAM $FF88-$FFF9: under the C64 KERNAL, which the game never banks out)
; DLI (NMI; A and X saved by the caller, Y kept): set the colours of the split entries on this line; C = 0 if the DLI
; is also the pending raster event's (the caller goes on with it), C = 1 if it only carried colours (the caller returns).
; The splits come from this frame's queue (vicirq.s hq_build, at the VBI: live entries sorted by line, palette index
; and colour ready), so a DLI only looks at the next ones.
hc_rep: lda     $D40B
        sta     hc_v                    ; VCOUNT: line / 2
        lda     hc_busy
        bne     hr_cls                  ; (a palette write is half way: it applies the due entries when done)
; hc_busy is set while the entries are written: a DLI one line later interrupts this one (NMIs nest), and its hc_rep
; wrote the same entry again (hq_i not moved on yet), so our remaining colour writes went to the next palette entry
; (HANDOFF bug 3: palette entry 3, the HUD's brown and the playfield's blue, became teal for up to ~70 frames). The
; loop reads VCOUNT itself, so the entries a skipped nested DLI was due to set are set here.
hc_rq:  tya                             ; (from hc: hc_v set, the palette free; returns C as hc_rep)
        pha
        inc     hc_busy
        ldy     hq_i
@l:     cpy     hq_n
        bcs     @e
        lda     $D40B
        cmp     hq_line,y
        bcc     @e                      ; (a later line: its own DLI)
@ap:    lda     #0                      ; (this line, or passed: a DLI that read VCOUNT a line late, or whose bit an
                                        ; event cleared; it was skipped, and a late handler that finds the value
                                        ; known does not write it live: the playfield kept the HUD's colour a frame)
        sta     VB_PSEL
        lda     hq_pal,y
        sta     VB_CSEL
        ldx     hq_col,y
        lda     rgb_r,x
        sta     VB_CR
        lda     rgb_g,x
        sta     VB_CG
        lda     rgb_b,x
        sta     VB_CB
        iny
        bne     @l
@e:     sty     hq_i
        dec     hc_busy
        pla
        tay
hr_cls: lda     dl_idx                  ; a raster event pending on this line (entry 0: lines 8-9)?
        bne     :+
        lda     DLB
        bpl     @col
        lda     #0
:       clc
        adc     #9
        lsr     a
        cmp     hc_v
        beq     @ev
        clc
        adc     #1
        cmp     hc_v
        bne     @col
@ev:    clc                             ; (hc_ev: set by the dispatch itself, resident irq; here it also caught an
        rts                             ; event then deferred, and the running handler's writes were filed under it)
@col:   sec
        rts
hc_v:   .byte   0
