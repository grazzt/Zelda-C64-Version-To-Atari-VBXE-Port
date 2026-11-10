"""Path finding on the play area, from the game's own tile buffer ($6530).

Link's position on the 8-pixel grid: column c = X / 8 (0..30), row k = (Y - 61) / 8 (0..20). Only his lower half
collides (measured: tools/bot walk tests), so grid cell (c, k) is open when the tiles in row k + 1, columns c and c + 1
are walkable. Walkable tile codes: measured per code by putting it in the buffer in front of Link (walk_ow.json:
Y reached after 40 frames walking up; 87 = walked through). Cells the executor finds blocked anyway (an enemy, a
tile the table gets wrong) are remembered for the screen (`Nav.learned`)."""
import json, os, heapq
import zram as Z

HERE = os.path.dirname(os.path.abspath(__file__))
_W = json.load(open(os.path.join(HERE, 'walk_ow.json')))
WALK_OW = {int(t) for t, y in _W.items() if y < 100} | {0x74, 0x75}
# ($74/$75: the 2-tile passages up Death Mountain, $1A -> $0A, $1B -> $0B: they stop Link off the 8-px grid, but a cell
# needs both its tiles walkable, so only the aligned cell in such a passage is open)
COLS, ROWS = 31, 21                                       # grid cells (Link's X 0..240, Y 61..221)
STEP = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}


def cell_of(x, y):
    return (x + 4) // 8, (y - Z.PLAY_TOP + 4) // 8


def pos_of(c, k):
    return 8 * c, Z.PLAY_TOP + 8 * k


class Grid:
    def __init__(self, tiles, walk=WALK_OW, blocked=(), ladder=()):
        self.t = tiles
        self.walk = walk
        self.blocked = set(blocked)
        self.bridge = self.ladder_tiles(ladder) if ladder else set()

    def ladder_tiles(self, water):
        """Water tiles the ladder spans: in a run of at most 2 tiles (16 px, one ladder) across, by row or column."""
        out = set()
        for r in range(22):
            for c in range(32):
                if self.t[r][c] not in water: continue
                for dc, dr in ((1, 0), (0, 1)):
                    n = 1; k = 1
                    while 0 <= c + dc * k < 32 and 0 <= r + dr * k < 22 and self.t[r + dr * k][c + dc * k] in water: n += 1; k += 1
                    k = 1
                    while 0 <= c - dc * k < 32 and 0 <= r - dr * k < 22 and self.t[r - dr * k][c - dc * k] in water: n += 1; k += 1
                    first = (c - dc * (k - 1), r - dr * (k - 1))          # (the run's first tile)
                    # one 16-px block of water (2 tiles, starting on an even tile: the room's 16-px grid)
                    if n == 2: out.add((c, r)); break      # (dry paths come first in goto: no parity rule needed;
                                                            # Level 7 room $49's moat starts on an odd tile row)
        return out

    def tile_ok(self, c, r):
        return 0 <= c < 32 and 0 <= r < 22 and (self.t[r][c] in self.walk or (c, r) in self.bridge)

    def open(self, c, k):
        if not (0 <= c < COLS and 0 <= k < ROWS) or (c, k) in self.blocked: return False
        return self.tile_ok(c, k + 1) and self.tile_ok(c + 1, k + 1)

    def exits(self, c, k):
        """Screen exits from an open cell: the direction that walks off the play area."""
        out = []
        if c == 0: out.append('left')
        if c == COLS - 1: out.append('right')
        if k == 0: out.append('up')
        if k == ROWS - 1: out.append('down')
        return out

    def path(self, start, goal_fn, avoid=()):
        """Shortest path (list of cells) from start to the first cell where goal_fn(cell) is true. avoid: cells with
        an extra cost (near enemies)."""
        avoid = set(avoid)
        best = {start: 0}
        prev = {}
        q = [(0, start)]
        while q:
            d, cur = heapq.heappop(q)
            if d > best.get(cur, 1e9): continue
            if goal_fn(cur):
                out = [cur]
                while cur in prev: cur = prev[cur]; out.append(cur)
                return out[::-1]
            for dc, dk in STEP.values():
                n = (cur[0] + dc, cur[1] + dk)
                if not self.open(*n): continue
                nd = d + 1 + (6 if n in avoid else 0)
                if nd < best.get(n, 1e9):
                    best[n] = nd; prev[n] = cur; heapq.heappush(q, (nd, n))
        return None

    def reachable(self, start):
        seen = {start}; todo = [start]
        while todo:
            c = todo.pop()
            for dc, dk in STEP.values():
                n = (c[0] + dc, c[1] + dk)
                if n not in seen and self.open(*n): seen.add(n); todo.append(n)
        return seen

    def show(self, marks=None):
        marks = marks or {}
        rows = []
        for k in range(ROWS):
            rows.append(''.join(marks.get((c, k), '.' if self.open(c, k) else '#') for c in range(COLS)))
        return '\n'.join(rows)


def segments(path):
    """A path of cells as straight runs: [(direction, end cell)]."""
    out = []
    for a, b in zip(path, path[1:]):
        d = next(n for n, v in STEP.items() if v == (b[0] - a[0], b[1] - a[1]))
        if out and out[-1][0] == d: out[-1] = (d, b)
        else: out.append((d, b))
    return out
