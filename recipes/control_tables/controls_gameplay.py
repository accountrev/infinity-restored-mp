"""Gamepad binding for leaving the Toy Box logic mode (Controls_win32, the PC gameplay control scheme).

The gameplay action LogicSelectCancel (context InLogicMode: pointing the wand at objects to link them) is
bound to Escape only on PC (LOGIC_SELECT_CANCEL = Combo All of Escape and not Alt); the 360 binds it to B.
With a pad there was no way out of logic mode. The PC definition is kept as LOGIC_SELECT_CANCEL_KB, a pad
B button row is added as LOGIC_SELECT_CANCEL_PAD, and LOGIC_SELECT_CANCEL becomes Combo Any of the two (the
same shape as the PC's own JUMP = JUMP_KEY or JUMP_BUTTON). Names are resolved in file order, so the new rows
follow the one they replace.
"""
import controls_ui as c
import xldb

EMPTY = xldb.EMPTY
NAME_ROW = 'LOGIC_SELECT_CANCEL'


def build(sheet):
    """Returns (new sheet, report lines)."""
    assert sheet.types == 'sissssssssifffffis', sheet.types
    head, rows = sheet.rows[:2], sheet.rows[2:]
    idx = [i for i, r in enumerate(rows) if r[c.NAME] == NAME_ROW]
    assert len(idx) == 1, idx
    i = idx[0]
    orig = rows[i]
    assert orig[c.TYPE] == 'Combo All' and orig[c.INPUT] == 'LOGIC_SELECT_CANCEL_PRIMARY,~LEFT_ALT,~RIGHT_ALT', orig
    names = {r[c.NAME] for r in rows if r[c.NAME]}
    assert NAME_ROW + '_KB' not in names and NAME_ROW + '_PAD' not in names

    kb = list(orig)
    kb[c.NAME] = NAME_ROW + '_KB'
    kb[c.ROWNUM] = 1000
    pad = [orig[c.TAG], 1001, NAME_ROW + '_PAD', 'Button', 'B', None, None, None, None, None] + [EMPTY] * 7 + [None]
    combo = list(orig)
    combo[c.TYPE] = 'Combo Any'
    combo[c.INPUT] = NAME_ROW + '_KB,' + NAME_ROW + '_PAD'
    new_rows = rows[:i] + [kb, pad, combo] + rows[i + 1:]
    new = xldb.Sheet(sheet.name, sheet.types, head + new_rows)
    _validate(sheet, new)
    return new, ['LogicSelectCancel                  key Escape (not Alt) + pad B (as on the 360)']


def _validate(orig, new):
    o_rows, n_rows = orig.rows[2:], new.rows[2:]
    assert len(n_rows) == len(o_rows) + 2
    seen = set()
    for row in n_rows:                              # every name is defined before it is used
        for tok in c._tokens(row[c.INPUT]):
            assert c._strip(tok) in seen, 'row %s uses %s before it is defined' % (row[c.NAME], tok)
        if row[c.NAME]:
            seen.add(row[c.NAME])
    o_names, n_names = c._by_name(o_rows), c._by_name(n_rows)
    for row in o_rows:                              # every other row unchanged, in order
        if row[c.NAME] != NAME_ROW:
            assert row in n_rows, row
    before = c._leaves(NAME_ROW, o_names)
    after = c._leaves(NAME_ROW, n_names)
    assert before < after and ('pad', 'B') in after, (before, after)
