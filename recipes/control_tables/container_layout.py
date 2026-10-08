"""Split-screen rows for the PC-only full-screen menus in Excel/Container (startup4.zip:excel/container.xldb).

A new screen is loaded into the HUD Container movie, which moves its root clip to the row's x/y, only if
the sheet for the current split layout (OnePlayer, TwoPlayerVertical or TwoPlayerHorizontal) has a row
for it and the opener's viewport. The PC added its own full-screen menus to OnePlayer only (viewport 0),
so in split screen they got a movie of their own, and their root clip stayed where the movie authors it:
(512, 384), an iPad 1024x768 centre, which puts the menu at the bottom right. The OnePlayer row is copied
into both split sheets for viewports 0 and 1, so these menus open as in single player: centred, full
screen.
"""
import xldb

SCREENS = ('VirtualReader', 'iOS_RibbonToyBox')     # the Virtual Base, the Toy Box build ribbon
SPLIT_SHEETS = ('TwoPlayerVertical', 'TwoPlayerHorizontal')
VIEWPORTS = (0, 1)
TAG, ROWNUM = 0, 1                                  # column indexes; the rest are found by title


def _cols(sheet):
    return {title: c for c, title in enumerate(sheet.rows[1]) if c > ROWNUM}


def build(sheets):
    """sheets (from xldb.parse) -> (new sheets, report lines). The input is not modified."""
    sheets = [xldb.Sheet(s.name, s.types, [list(r) for r in s.rows]) for s in sheets]
    by_name = {s.name: s for s in sheets}
    one = by_name['OnePlayer']
    one_cols = _cols(one)
    src = {}
    for row in one.rows[2:]:
        name = row[one_cols['lua']]
        if name in SCREENS:
            assert name not in src and row[one_cols['viewport']] == 0, 'unexpected OnePlayer rows for %s' % name
            src[name] = row
    assert set(src) == set(SCREENS), 'OnePlayer rows missing'
    report = []
    for sheet_name in SPLIT_SHEETS:
        sh = by_name[sheet_name]
        cols = _cols(sh)
        assert all(sh.types[c] == one.types[one_cols[t]] for t, c in cols.items()), sheet_name
        assert not any(r[cols['lua']] in SCREENS for r in sh.rows[2:]), '%s already has these rows' % sheet_name
        before = len(sh.rows)
        for name in SCREENS:
            for vp in VIEWPORTS:
                row = [None] * len(sh.types)
                row[TAG] = sh.rows[2][TAG]
                row[ROWNUM] = len(sh.rows)
                for title, c in cols.items():
                    row[c] = src[name][one_cols[title]]
                row[cols['viewport']] = vp
                sh.rows.append(row)
        report.append('%s: %d -> %d rows (%s, viewports %s)' % (sheet_name, before, len(sh.rows),
                                                              ', '.join(SCREENS), ' and '.join(map(str, VIEWPORTS))))
    return sheets, report


def _validate(orig, new):
    """Every original row unchanged, and the only new rows are the SCREENS rows at the OnePlayer x/y."""
    assert [s.name for s in orig] == [s.name for s in new]
    for o, n in zip(orig, new):
        assert o.types == n.types and n.rows[:len(o.rows)] == o.rows, o.name
        added = n.rows[len(o.rows):]
        if o.name not in SPLIT_SHEETS:
            assert not added, o.name
            continue
        cols = _cols(n)
        assert sorted((r[cols['lua']], r[cols['viewport']]) for r in added) == \
            sorted((s, vp) for s in SCREENS for vp in VIEWPORTS), o.name
        for i, r in enumerate(added):
            assert r[ROWNUM] == len(o.rows) + i and r[TAG] == o.rows[2][TAG]


def build_checked(data):
    """container.xldb bytes -> (patched bytes, report lines), re-parsed and checked."""
    orig = xldb.parse(data)
    assert xldb.dumps(orig) == data, 'container.xldb does not round-trip'
    sheets, report = build(orig)
    new = xldb.dumps(sheets)
    _validate(xldb.parse(data), xldb.parse(new))
    return new, report
