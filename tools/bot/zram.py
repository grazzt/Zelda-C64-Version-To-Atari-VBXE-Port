"""The game's RAM, as the bot reads it. The C64 game is a conversion of the NES game's code: its RAM layout follows the NES
one (Data Crystal "The Legend of Zelda/RAM map"), zero page shifted by +2 (NES $12 game mode = C64 $14), pages 3-7 and
the play-area tile buffer at $6530 unchanged. Every address here was checked in the port (tools/bot notes in HANDOFF)."""

MODE = 0x14          # 0 title, 1 select, 5 play, 6 prepare scroll, 7 scroll, $0B cave/underground entry, $0E register,
                     # $11 death, (NES $12)
LEVEL = 0x12         # 0 overworld, 1-9 dungeon (NES $10)
SCREEN = 0xED        # map location: x + 16*y (overworld 16x8; start $77, level 1 entrance $37) (NES $EB)
LINK_X, LINK_Y = 0x72, 0x86     # object 0 (NES $70/$84): X 0..240, Y 61..221 (top of the play area = 61)
OBJ_X, OBJ_Y = 0x72, 0x86       # objects 0-11: Link, enemies 1-6, projectiles... (NES $70+i / $84+i)
LINK_DIR = 0x9A      # $08 up, $04 down, $01 right, $02 left (NES $98)
OBJ_DIR = 0x9A
ENEMY_TYPE = 0x034F  # + slot, slots 1..11 (0 = none; NES $034F+i: Data Crystal lists $0350 = slot 1)
ENEMY_HP = 0x0485    # + slot: high nibble = hits left ($10 = one wooden-sword hit) (NES $0485+i)
TILES = 0x6530       # the play area's tiles: column-major, 32 columns x 22 rows of 8x8 (NES PRG RAM $6530)

SWORD = 0x0657       # 0 none, 1 wooden, 2 white, 3 magical
BOMBS = 0x0658
ARROWS = 0x0659
BOW = 0x065A
CANDLE = 0x065B
RECORDER = 0x065C
RAFT = 0x0660
LADDER = 0x0663
COMPASS = 0x0667
MAP = 0x0668
RUPEES = 0x066D
KEYS = 0x066E
HEARTS = 0x066F      # low nibble: full hearts (minus the partial one), high nibble: containers - 1
HEART_PART = 0x0670  # $00 empty, $01-$7F half, $80-$FF full
TRIFORCE = 0x0671
BOOMERANG = 0x0674

DIR_BITS = {'right': 1, 'left': 2, 'down': 4, 'up': 8}

PLAY_TOP = 61        # Link's Y on the top row of the play area: row k of the grid = Y 61 + 8k


def hearts(m):
    """Link's health in half hearts, and the maximum."""
    h, p = m.peek(HEARTS), m.peek(HEART_PART)
    full = h & 15
    return full * 2 + (2 if p >= 0x80 else 1 if p else 0), ((h >> 4) + 1) * 2


def tiles(m):
    """22 rows x 32 columns of tile codes (rows top to bottom)."""
    b = m.peek(TILES, 32 * 22)
    return [[b[c * 22 + r] for c in range(32)] for r in range(22)]


def objects(m):
    """Objects in slots 1-11 with a type: [(slot, type, x, y, hp)] (slots 1-6 enemies, 7+ projectiles and others;
    an enemy slot with hp 0 is not spawned yet or dead)."""
    t = m.peek(ENEMY_TYPE, 12)
    xs, ys, hp = m.peek(OBJ_X, 12), m.peek(OBJ_Y, 12), m.peek(ENEMY_HP, 12)
    return [(i, t[i], xs[i], ys[i], hp[i]) for i in range(1, 12) if t[i]]


def enemies(m):
    """Live enemies: [(slot, type, x, y, hp)]."""
    return [o for o in objects(m) if o[0] <= 6 and o[4] and 0 < o[2] < 248 and o[3] >= 56]


def state(m):
    hp, mx = hearts(m)
    return {'mode': m.peek(MODE), 'level': m.peek(LEVEL), 'screen': m.peek(SCREEN), 'x': m.peek(LINK_X),
            'y': m.peek(LINK_Y), 'dir': m.peek(LINK_DIR), 'hp': hp, 'hp_max': mx, 'sword': m.peek(SWORD),
            'rupees': m.peek(RUPEES), 'keys': m.peek(KEYS), 'bombs': m.peek(BOMBS)}
