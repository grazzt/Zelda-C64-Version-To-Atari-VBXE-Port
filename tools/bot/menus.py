"""Power-on to the first overworld screen: title, START, register GZ (joystick + fire), SELECT x3 to END, START,
START (the game). Waits on the game's own mode ($14: 0 title, 1 select screen, $0E registration, 5 play) and on the
port's picture (r_blank 0: the title is shown), so it does not depend on start-up timing."""
R_BLANK = 0xFD2D                                         # (atari.inc r_blank: 0 = the picture is shown)


def wait_until(m, cond, limit, d='center'):
    for i in range(limit):
        if cond(): return True
        m.hold(d, 1)
    return cond()


def to_game(m, name_moves=('right',) * 6 + ('F',) + ('down', 'down') + ('left',) * 3 + ('F',), title_frames=120):
    mode = lambda: m.peek(0x14)
    def tap(d, n=6, w=10): m.hold(d, n); m.hold('center', w)
    def fire(): m.hold('center', 6, fire=True); m.hold('center', 20)
    def con(k): m.hold('center', 4, consol=k); m.hold('center', 1)
    assert wait_until(m, lambda: m.frames > 200 and m.peek(R_BLANK) == 0, 2000), 'title'
    m.hold('center', title_frames)
    con('start')
    assert wait_until(m, lambda: mode() == 1, 600), 'select %02X' % mode()
    m.hold('center', 60)
    con('start')
    assert wait_until(m, lambda: mode() == 0x0E, 600), 'register %02X' % mode()
    m.hold('center', 60)
    for s in name_moves:
        fire() if s == 'F' else tap(s)
    m.hold('center', 30)
    for i in range(3): con('select'); m.hold('center', 25)
    con('start')
    assert wait_until(m, lambda: mode() == 1, 600), 'select again %02X' % mode()
    m.hold('center', 90)
    con('start')
    assert wait_until(m, lambda: mode() == 5, 900), 'game %02X' % mode()
    m.hold('center', 30)
