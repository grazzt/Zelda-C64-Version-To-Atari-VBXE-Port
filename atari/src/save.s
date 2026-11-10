; Persistent saves on a disk in D1: (a 90 KB ATR; the game itself never sees it).
; The game saves through EasyFlash EAPI into "flash" that is Atari RAM $8000-$85FF with the cart off (eapi.s). This
; code runs from RAM $B000 with the cart off as well (boot2 copies it there from cart bank 12; RAM $8600-$BFFF under
; the cart window is never used by the game), so it reads and writes the save data in place:
;   SV_LOAD  (boot, NMIs off): sector 4 = signature; sectors 5-16 = $8000-$85FF. Nothing valid: the RAM stays erased.
;   SV_FLUSH (resident sv_go, from the main loop's idle wait, cart off): once the game has not written for half a
;            second (eapi.s marks sv_dirty / sv_t), the signature and the data go to the disk with NMIs off (~1 s:
;            the picture holds, the sound stops), then POKEY is set up for sound again.
; No disk (or a write-protected one): the transfers fail fast and the save stays in RAM only, as before.
; The SIO driver is the port kit's native polled one (templates/loader64/src/sio_native.s, verified with the OS ROM
; off in Atari800 and AltirraSDL), here in RAM so its self-modifying loads/stores and variables work.
        .include "atari.inc"
        .export sv_entry
        .import sv_dirty, sv_t, sv_ws, sv_rs
        .segment "SAVE"

SV_SIG   = 4                            ; signature sector, then the data
SV_N     = 12                           ; 12 x 128 = $8000-$85FF
SV_QUIET = 30                           ; frames without a write before the flush

sv_entry:
        jmp     sv_load                 ; $B000
        jmp     sv_flush                ; $B003

; ---- boot: read the save back ---------------------------------------------------------------------------------
sv_load:
        lda     #'R'
        sta     sio_cmd
        lda     #<sv_rbuf               ; (not into the "flash": the game looks at all of it)
        sta     sio_buf
        lda     #>sv_rbuf
        sta     sio_buf+1
        lda     #SV_SIG
        jsr     sv_sector
        lda     sio_y
        sta     sv_rs
        cmp     #1
        bne     @no
        ldx     #15
:       lda     sv_rbuf,x
        cmp     sv_sigb,x
        bne     @no
        dex
        bpl     :-
        jsr     sv_data
        bne     @bad
        lda     #$11                    ; (sv_rs: $11 = a save was loaded)
        sta     sv_rs
@no:    rts
@bad:   ldx     #SV_N * 128 / 256       ; (a sector missing: back to an erased "flash": the game finds no save)
        ldy     #0
        lda     #$FF
@e:     sta     $8000,y
        iny
        bne     @e
        inc     @e+2
        dex
        bne     @e
        lda     #>$8000
        sta     @e+2
        rts

; ---- after the game saved: write it out -------------------------------------------------------------------------
sv_flush:
        lda     frame_ctr
        sec
        sbc     sv_t
        cmp     #SV_QUIET
        bcs     :+
        rts                             ; (the game may still be writing)
:       lda     #0
        sta     sv_dirty
        sta     $D40E                   ; NMIEN off: no VBI (it updates POKEY) and no DLIs during the transfer
        lda     #'W'
        sta     sio_cmd
        lda     #<sv_sigb
        sta     sio_buf
        lda     #>sv_sigb
        sta     sio_buf+1
        lda     #SV_SIG
        jsr     sv_sector
        bne     :+
        jsr     sv_data
:       lda     sio_y
        sta     sv_ws
        lda     #$50                    ; POKEY for sound again (as boot2): AUDCTL, volumes off, SKCTL, no IRQs
        sta     $D208
        lda     #0
        ldx     #7
:       sta     $D200,x
        dex
        bpl     :-
        lda     #3
        sta     $D20F
        lda     #0
        sta     $D20E
        lda     #$FF                    ; the sound driver writes its dividers again (it only writes changes)
        ldx     #2
:       sta     s_fl,x
        sta     s_fh,x
        dex
        bpl     :-
        lda     #$3C
        sta     $D303                   ; PBCTL: COMMAND high
        lda     #$C0
        sta     $D40E                   ; NMIEN: DLI + VBI
        rts

; The 12 data sectors (sio_cmd set): sector 5 + k <-> $8000 + k * 128. Z = 1: all done.
sv_data:
        lda     #<$8000
        sta     sio_buf
        lda     #>$8000
        sta     sio_buf+1
        lda     #SV_SIG+1
        sta     sv_k
@d:     lda     sv_k
        jsr     sv_sector
        bne     @r
        lda     sio_buf
        eor     #$80
        sta     sio_buf
        bne     :+
        inc     sio_buf+1
:       inc     sv_k
        lda     sv_k
        cmp     #SV_SIG+1+SV_N
        bne     @d
        lda     #0                      ; (Z = 1)
@r:     rts

; A = sector (D1:, sio_cmd, sio_buf set) -> Z = 1 ok (one retry)
sv_sector:
        sta     sio_aux1
        lda     #0
        sta     sio_aux2
        lda     #$31
        sta     sio_dev
        lda     #4
        sta     sv_try
@t:     jsr     sio_do
        cmp     #1
        beq     @r
        dec     sv_try
        bne     @t
@f:     lda     #1                      ; (Z = 0)
@r:     rts

sv_k:   .byte   0
sv_try: .byte   0
sv_sigb: .byte  "ZELDA-VBXE-SAVE1"      ; the signature sector: these 16 bytes, then anything
        .res    128 - 16, 0
sv_rbuf: .res   128, 0                  ; (the signature sector read at boot)

; ---------------------------------------------------------------------------------------------------
; The port kit's native polled standard-speed SIO driver (unchanged but for its labels' scope).
; It reprograms POKEY (AUDF/AUDCTL/SKCTL/IRQEN): it stops any sound. It needs I set (it does sei and restores the
; flags), no NMI handler touching POKEY/PIA (NMIEN = 0 here), and no OS.
;   sio_dev $31 = D1:, sio_cmd 'R'/'W', sio_aux1/2 sector, sio_buf 128-byte buffer; jsr sio_do; A = 1 ok, $8A no ACK in
;   time (no drive), $8B NAK, $8C no COMPLETE, $8D device error, $8E data timeout, $8F bad checksum.
POKEY_SEROUT = $D20D
POKEY_SERIN = $D20D
POKEY_IRQEN = $D20E
POKEY_IRQST = $D20E
POKEY_SKCTL = $D20F
PIA_PBCTL = $D303
BYTE_DELAY = 200
IRQ_MASK = $60

.macro fail_if_timeout code
        bcc :+
        lda #code
        rts
:
.endmacro

.macro fail_unless_equal code
        beq :+
        lda #code
        rts
:
.endmacro

sio_do:
        php
        sei
        jsr sio_run
        sta sio_y
        plp
        lda sio_y
        rts

sio_run:
        cld
        ldx #8
init_pokey:
        lda pokey_table,x
        sta $D200,x
        dex
        bpl init_pokey
        lda #IRQ_MASK
        sta POKEY_IRQEN
        lda #$23
        sta POKEY_SKCTL
        sta $D20A
        lda #0
        sta sio_sum
        ldx #3
sum_frame:
        lda sio_dev,x
        jsr add_sum
        dex
        bpl sum_frame
        lda sio_sum
        sta sio_frame_sum
        lda #$3C
        sta PIA_PBCTL
        lda #$34
        sta PIA_PBCTL
        ldy #2
        jsr delay
        ldx #0
frame_loop:
        lda sio_dev,x
        jsr put
        inx
        cpx #5
        bne frame_loop
        ldy #2
        jsr delay
        lda #$3C
        sta PIA_PBCTL
        lda #$13
        sta POKEY_SKCTL
        ldy #14
        jsr get
        fail_if_timeout $8A
        cmp #'A'
        fail_unless_equal $8B
        lda sio_cmd
        cmp #'W'
        beq write_sector
        ldy #0
        jsr get
        fail_if_timeout $8C
        cmp #'C'
        fail_unless_equal $8D
        lda sio_buf
        sta store+1
        lda sio_buf+1
        sta store+2
        lda #0
        sta sio_sum
        tay
read_loop:
        sty sio_y
        ldy #4
        jsr get
        fail_if_timeout $8E
        ldy sio_y
store:  sta $FFFF,y
        jsr add_sum
        iny
        bpl read_loop
        ldy #4
        jsr get
        fail_if_timeout $8E
        cmp sio_sum
        fail_unless_equal $8F
        lda #1
        rts
write_sector:
        lda sio_buf
        sta load+1
        lda sio_buf+1
        sta load+2
        lda #$23
        sta POKEY_SKCTL
        lda #0
        sta sio_sum
        tay
write_loop:
load:   lda $FFFF,y
        jsr add_sum
        jsr put
        iny
        bpl write_loop
        lda sio_sum
        jsr put
        lda #$13
        sta POKEY_SKCTL
        ldy #14
        jsr get
        fail_if_timeout $8A
        cmp #'A'
        fail_unless_equal $8B
        ldy #0
        jsr get
        fail_if_timeout $8C
        cmp #'C'
        fail_unless_equal $8D
        lda #1
        rts

add_sum:
        pha
        clc
        adc sio_sum
        adc #0
        sta sio_sum
        pla
        rts

put:    sta POKEY_SEROUT
        txa
        pha
        ldx #BYTE_DELAY
byte_time:
        dex
        bne byte_time
        pla
        tax
        rts

get:    ldx #0
wait_in:
        lda POKEY_IRQST
        and #$20
        beq have
        dex
        bne wait_in
        dey
        bne wait_in
        sec
        rts
have:   lda POKEY_SERIN
        pha
        lda #IRQ_MASK & ~$20
        sta POKEY_IRQEN
        lda #IRQ_MASK
        sta POKEY_IRQEN
        pla
        clc
        rts

delay:  ldx #0
d1:     dex
        bne d1
        dey
        bne delay
        rts

pokey_table:    .byte 0,$A0,0,$A0,$28,$A0,0,$A0,$28
sio_dev:        .byte $31
sio_cmd:        .byte 'R'
sio_aux1:       .byte 0
sio_aux2:       .byte 0
sio_frame_sum:  .byte 0
sio_buf:        .word 0
sio_sum:        .byte 0
sio_y:          .byte 0
