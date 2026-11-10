; EasyFlash EAPI stand-in. The game saves through EAPI: it copies the driver from EF bank 0 $B800-$BAFF to RAM $1000
; (RAM $5D59), calls its init at $1014 and then the jump table at $DF80 (RAM $5D83 SetBank, $5D8A EraseSector,
; $5CE8 WriteFlash). This driver replaces the original in cart bank 0 at $B800 (tools/build_atari.py) and runs at $1000.
; The "flash" is Atari RAM $8000-$BFFF with the cart off: EF banks 8-63 all map there (hook_bank_a), the game uses only
; bank 16 (ROML, $8000). Erased = $FF; boot2 erases it. Writes store the byte (the game always erases first).
; Persistent through a disk in D1: (save.s): every write marks sv_dirty; the main loop writes the save out.
; Only A/X/Y and absolute RAM inside this driver are used (zero page belongs to the game).
        .include "atari.inc"
        .import hook_bank_a, sv_dirty, sv_t
        .segment "EAPI"

EAPI_JT = $DF80

base:   .byte   $65, $61, $70, $69      ; "eapi" (PETSCII), as in the original header
        .byte   "ATARI RAM", 0
        .res    $14 - (* - base), 0

; $1014: EAPIInit. Installs the jump table; C = 0, A = device ($A4), X = manufacturer ($01), Y = banks (64): an AM29F040.
init:   ldx     #jt_end - jt - 1
:       lda     jt,x
        sta     EAPI_JT,x
        dex
        bpl     :-
        lda     #0
        sta     e_bank
        lda     #$A4
        ldx     #$01
        ldy     #64
        clc
        rts

jt:     jmp     w_flash                 ; $DF80 EAPIWriteFlash: A = byte, X/Y = address ($8000-$BFFF or $E000-$FFFF)
        jmp     erase                   ; $DF83 EAPIEraseSector: A = bank, Y = $80 (ROML) or $E0 (ROMH)
        jmp     setbank                 ; $DF86 EAPISetBank: A = bank (also switches to it)
        jmp     getbank                 ; $DF89 EAPIGetBank
        jmp     unused                  ; $DF8C EAPISetPtr          (the game never calls these: C = 1 so a use shows)
        jmp     unused                  ; $DF8F EAPISetLen
        jmp     unused                  ; $DF92 EAPIReadFlashInc
        jmp     unused                  ; $DF95 EAPIWriteFlashInc
        jmp     slot                    ; $DF98 EAPISetSlot
        jmp     slot                    ; $DF9B EAPIGetSlot
jt_end:

w_flash:
        sta     e_val
        stx     @w+1
        tya
        cmp     #$E0                    ; ROMH seen at $E000 (ultimax) -> $A000
        bcc     :+
        sbc     #$40
:       sta     @w+2
        cmp     #$B0
        bcs     @ok                     ; ($B000-$BFFF: the disk save code, save.s; the game uses ROML only)
        lda     e_bank
        cmp     #8
        bcc     err                     ; banks 0-7 are the game (ROM)
        jsr     save_on
        lda     e_val
@w:     sta     $8000
        jsr     save_off
        jsr     dirty
@ok:    lda     e_val
        clc
        rts

; the save changed: written to the disk once the game is done (save.s, from the main loop's idle wait)
dirty:  lda     #1
        sta     sv_dirty
        lda     frame_ctr
        sta     sv_t
        rts

erase:  cmp     #8
        bcc     err
        lda     #$80
        cpy     #$E0
        bcc     :+
        lda     #$A0
:       sta     @e+2
        jsr     save_on
        ldx     #$20                    ; 8 KB
        cpy     #$E0
        bcc     :+
        ldx     #$10                    ; (ROMH: 4 KB, $A000-$AFFF; $B000 up is the disk save code, save.s)
:       ldy     #0
        lda     #$FF
@e:     sta     $8000,y
        iny
        bne     @e
        inc     @e+2
        dex
        bne     @e
        jsr     save_off
        jsr     dirty
        clc
        rts

setbank:
        sta     e_bank
        jsr     hook_bank_a             ; (keeps A and the flags)
        clc
        rts

getbank:
        lda     e_bank
        clc
        rts

slot:   lda     #0
        clc
        rts

unused:
err:    sec
        rts

; cart off for the save RAM; `mapped` first, so an NMI in between restores the same mapping
save_on:
        lda     #$80
        sta     mapped
        sta     $D500
        rts
save_off:
        lda     cur_bank
        sta     mapped
        sta     $D500
        rts

e_bank: .byte   0
e_val:  .byte   0
