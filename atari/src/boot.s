; Bank 8 start. The first 7 bytes must equal the trampoline patched into EF bank 0 at $8000.
        .include "atari.inc"
        .import __RESIDENT_LOAD__, __RESIDENT_RUN__, __RESIDENT_SIZE__
        .import __KENT_LOAD__, __KENT_RUN__, __KENT_SIZE__
        .import __RES2_LOAD__, __RES2_RUN__, __RES2_SIZE__
        .import __VECT_LOAD__, __VECT_RUN__, __VECT_SIZE__
        .import __BOOT2_LOAD__, __BOOT2_RUN__, __BOOT2_SIZE__
        .import __RES3_LOAD__, __RES3_RUN__, __RES3_SIZE__
        .import __RES5_LOAD__, __RES5_RUN__, __RES5_SIZE__
        .import __RES6_LOAD__, __RES6_RUN__, __RES6_SIZE__
        .import __RES7_LOAD__, __RES7_RUN__, __RES7_SIZE__
        .import __RES8_LOAD__, __RES8_RUN__, __RES8_SIZE__
        .import __RES9_LOAD__, __RES9_RUN__, __RES9_SIZE__
        .import boot2
        .segment "B8CODE"
        sei
        cld
        lda     #8
        sta     $D500                   ; the fetch after this store comes from bank 8
start:  ldx     #$FF
        txs
        lda     #0
        sta     $D40E                   ; NMIEN off
        sta     $D20E                   ; IRQEN off
        sta     $D400                   ; DMACTL off
        lda     #$FE
        sta     $D301                   ; PORTB: OS and BASIC off
        ; clear Atari-side shadow area $F000-$F0FF
        ldx     #0
        txa
:       sta     VSH,x
        inx
        bne     :-
        .macro  COPY src, dst, len
        lda     #<(src)
        sta     $F8
        lda     #>(src)
        sta     $F9
        lda     #<(dst)
        sta     $FA
        lda     #>(dst)
        sta     $FB
        lda     #<(len)
        sta     $FC
        lda     #>(len)
        sta     $FD
        jsr     copy
        .endmacro
        COPY __RESIDENT_LOAD__, __RESIDENT_RUN__, __RESIDENT_SIZE__
        COPY __RES2_LOAD__, __RES2_RUN__, __RES2_SIZE__
        COPY __KENT_LOAD__, __KENT_RUN__, __KENT_SIZE__
        COPY __VECT_LOAD__, __VECT_RUN__, __VECT_SIZE__
        COPY __BOOT2_LOAD__, __BOOT2_RUN__, __BOOT2_SIZE__
        COPY __RES3_LOAD__, __RES3_RUN__, __RES3_SIZE__
        COPY __RES5_LOAD__, __RES5_RUN__, __RES5_SIZE__
        COPY __RES6_LOAD__, __RES6_RUN__, __RES6_SIZE__
        COPY __RES7_LOAD__, __RES7_RUN__, __RES7_SIZE__
        COPY __RES8_LOAD__, __RES8_RUN__, __RES8_SIZE__
        COPY __RES9_LOAD__, __RES9_RUN__, __RES9_SIZE__
        jmp     boot2

copy:   ldy     #0
@l:     lda     $FC
        ora     $FD
        beq     @d
        lda     ($F8),y
        sta     ($FA),y
        inc     $F8
        bne     :+
        inc     $F9
:       inc     $FA
        bne     :+
        inc     $FB
:       lda     $FC
        bne     :+
        dec     $FD
:       dec     $FC
        jmp     @l
@d:     rts
