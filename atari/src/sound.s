; SID -> POKEY: once per frame (from the VBI) the SID shadow (SSH) becomes POKEY sound. SID voice 3 plays on channels 1+2
; joined (16 bit, 1.79 MHz: exact low notes), voices 1 and 2 on channels 3 and 4 (8 bit, 64 kHz; notes below that range
; an octave up). The SID envelopes are emulated per frame (linear attack/decay/release); pulse, triangle and saw become
; pure tones, noise the 17-bit noise. No zero page is used (it may belong to the game or to the renderer).
        .include "atari.inc"
        .export snd_update
        .import in_update
        .segment "SND"

snd_update:
        txa
        pha
        tya
        pha
        jsr     in_update               ; joystick / keys -> CIA1 images (input.s)
        lda     #2
        sta     squota                  ; at most two divisions per frame (a changed pitch waits a frame otherwise)
        ldx     #2
@v:     stx     snv
        lda     voff,x
        sta     sy
        tay
        lda     SSH+4,y                 ; control: gate edge starts attack / release
        sta     sctl
        and     #1
        cmp     s_gt,x
        beq     @eg
        sta     s_gt,x
        sta     s_ph,x                  ; 1 attack, 0 release (2 decay/sustain)
@eg:    lda     s_ph,x
        beq     @rel
        cmp     #2
        beq     @dec
        lda     SSH+5,y                 ; attack
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        tay
        lda     s_lvl,x
        clc
        adc     att_t,y
        bcs     @top
        cmp     #240
        bcc     @sl
@top:   lda     #2
        sta     s_ph,x
        lda     #240
        bne     @sl
@dec:   lda     SSH+6,y                 ; decay to the sustain level
        and     #$F0
        sta     dv0
        lda     SSH+5,y
        and     #15
        tay
        lda     s_lvl,x
        sec
        sbc     dec_t,y
        bcc     @sus
        cmp     dv0
        bcs     @sl
@sus:   lda     dv0
        jmp     @sl
@rel:   lda     SSH+6,y
        and     #15
        tay
        lda     s_lvl,x
        sec
        sbc     dec_t,y
        bcs     @sl
        lda     #0
@sl:    sta     s_lvl,x
        ldy     sy                      ; volume and distortion
        lda     sctl
        and     #$F0
        beq     @mute                   ; no waveform
        lda     sctl
        and     #$08
        bne     @mute                   ; test bit
        lda     SSH+24
        and     #15
        beq     @mute                   ; master volume 0
        lda     s_lvl,x
        lsr     a
        lsr     a
        lsr     a
        lsr     a
        cpx     #2
        bne     :+
        sta     dv1                     ; (the triangle bass at 3/4: a POKEY square is louder)
        lsr     a
        lsr     a
        eor     #$FF
        sec
        adc     dv1
:       sta     dv1
        lda     sctl
        bmi     :+
        lda     #$A0                    ; pure tone
        bne     :++
:       lda     #$80                    ; noise
:       ora     dv1
        bne     @c
@mute:  lda     #0
@c:     sta     sctl                    ; AUDC value
        lda     SSH,y                   ; pitch: divider again only if the SID frequency changed
        cmp     s_fl,x
        bne     @nf
        lda     SSH+1,y
        cmp     s_fh,x
        bne     :+
        jmp     @wr
:
@nf:    lda     squota
        bne     :+
        jmp     @wr
:
        dec     squota
        lda     SSH,y
        sta     s_fl,x
        sta     f0
        lda     SSH+1,y
        sta     s_fh,x
        sta     f1
        ora     f0
        bne     :+
        jmp     @wr
:
        cpx     #2
        beq     @b16
@oc:    lda     f1                      ; 8 bit: N = 2^19 / F - 1, F >= 2048 (octaves up below)
        cmp     #8
        bcs     :+
        asl     f0
        rol     f1
        jmp     @oc
:       lda     #0
        sta     dv0
        sta     dv1
        lda     #8
        sta     dv2
        jsr     div
        ldx     snv
        lda     dv1
        bne     :+
        lda     dv0
        sec
        sbc     #1
        .byte   $2C                     ; (skip the next 2 bytes)
:       lda     #$FF
        sta     s_nl,x
        jmp     @wr
@b16:   lda     #$FE                    ; 16 bit: N = 14680062 / F - 7
        sta     dv0
        lda     #$FF
        sta     dv1
        lda     #$DF
        sta     dv2
        jsr     div
        ldx     snv
        lda     dv2
        bne     @max
        lda     dv0
        sec
        sbc     #7
        sta     s_nl,x
        lda     dv1
        sbc     #0
        sta     s_nh,x
        jmp     @wr
@max:   lda     #$FF
        sta     s_nl,x
        sta     s_nh,x
@wr:    cpx     #2
        beq     @w16
        ldy     chf,x
        lda     s_nl,x
        sta     $D200,y
        lda     sctl
        sta     $D201,y
        jmp     @nx
@w16:   lda     s_nl,x
        sta     $D200
        lda     s_nh,x
        sta     $D202
        lda     sctl
        sta     $D203
@nx:    ldx     snv
        dex
        bmi     :+
        jmp     @v
:       pla
        tay
        pla
        tax
        rts

; dv0-2 = dv0-2 / f0-1 (24-bit restoring division; remainder in r0/r1). Clobbers X.
div:    lda     #0
        sta     r0
        sta     r1
        ldx     #24
@l:     asl     dv0
        rol     dv1
        rol     dv2
        rol     r0
        rol     r1
        bcs     @s
        lda     r0
        cmp     f0
        lda     r1
        sbc     f1
        bcc     @n
@s:     lda     r0
        sec
        sbc     f0
        sta     r0
        lda     r1
        sbc     f1
        sta     r1
        inc     dv0
@n:     dex
        bne     @l
        rts

voff:   .byte   0, 7, 14
chf:    .byte   4, 6                    ; voices 1, 2: AUDF3 / AUDF4 (offsets from $D200)
att_t:  .byte   240, 240, 240, 167, 105, 71, 59, 50, 40, 16, 8, 5, 4, 1, 1, 1      ; 4.4 levels per frame
dec_t:  .byte   240, 167, 83, 56, 35, 24, 20, 17, 13, 5, 3, 2, 1, 1, 1, 1
