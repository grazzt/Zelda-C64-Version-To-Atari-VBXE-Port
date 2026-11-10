; Atari input -> C64 CIA1 images, once per frame from the VBI (cart bank 12, mapped by the caller).
; The game reads CIA1 in two places only: the per-frame scan (RAM $44C3/$44DA/$44E7, from bank 7) and the F7/F8 check
; (bank 0 $9A8B/$9A95). Each read follows a constant column select, so the patches (tools/patches.py input_patches)
; turn every `LDA $DC00` / `LDA $DC01` into `LDA` of one of the bytes below; the game's writes to $DC00/$DC02 stay plain
; RAM. Active low, as on the C64.
;   J_JOY  = $DC00 read: joystick 2 (up 1, down 2, left 4, right 8, fire 16) = Atari stick 0 / trigger 0
;   KC_FE  = column 0 ($DC00=$FE): F7 bit 3, F1 bit 4, F3 bit 5, F5 bit 6
;   KC_7F  = column 7: SPACE bit 4 (B button)
;   KC_FD  = column 1: left SHIFT bit 7 (F8 = SHIFT+F7)
;   KC_BF  = column 6: right SHIFT bit 4 (never pressed: only the left one is used)
; Atari keys: START = F7, SELECT = F5, OPTION = F8 (SHIFT+START too), SPACE = B, keys 1/3/5/7/8 = F1/F3/F5/F7/F8.
        .include "atari.inc"
        .export in_update
        .segment "SND"

PORTA   = $D300
TRIG0   = $D010
CONSOL  = $D01F
KBCODE  = $D209
SKSTAT  = $D20F

in_update:
        lda     TRIG0                   ; bit 0: 0 = pressed -> C64 bit 4
        and     #1
        asl     a
        asl     a
        asl     a
        asl     a
        sta     KC_BF                   ; (temp)
        lda     PORTA                   ; stick 0: bits 0-3 up/down/left/right, 0 = pushed (same order as the C64)
        and     #$0F
        ora     KC_BF
        ora     #$E0
        sta     J_JOY
        lda     #$FF
        sta     KC_FE
        sta     KC_7F
        sta     KC_FD
        sta     KC_BF
        lda     CONSOL                  ; bit 0 START, 1 SELECT, 2 OPTION (0 = held)
        lsr     a
        bcs     :+
        pha
        lda     #$08                    ; START -> F7
        jsr     @fe
        pla
:       lsr     a
        bcs     :+
        pha
        lda     #$40                    ; SELECT -> F5
        jsr     @fe
        pla
:       lsr     a
        bcs     :+
        jsr     @f8                     ; OPTION -> F8
:       lda     SKSTAT
        and     #$08                    ; 0: a SHIFT key is held
        bne     :+
        jsr     @sh
:       lda     SKSTAT
        and     #$04                    ; 0: a key is held (KBCODE = that key)
        bne     @done
        lda     KBCODE
        and     #$3F
        cmp     #$21                    ; SPACE -> B button
        bne     :+
        lda     KC_7F
        and     #$EF
        sta     KC_7F
        rts
:       cmp     #$35                    ; 8 -> F8
        beq     @f8
        ldx     #3
:       cmp     kb_code,x               ; 1 3 5 7 -> F1 F3 F5 F7
        beq     :+
        dex
        bpl     :-
@done:  rts
:       lda     kb_bit,x
@fe:    eor     #$FF
        and     KC_FE
        sta     KC_FE
        rts
@f8:    lda     #$08
        jsr     @fe
@sh:    lda     KC_FD
        and     #$7F
        sta     KC_FD
        rts

kb_code: .byte  $1F, $1A, $1D, $33      ; Atari key codes of 1, 3, 5, 7
kb_bit:  .byte  $10, $20, $40, $08      ; F1, F3, F5, F7 in column 0
