"""Gamepad bindings for the PC menu control scheme (Controls_UI_Win32).

The PC scheme binds the building/customising/Toy Box editor actions to keys only (categories V/B,
colours F/R, items Z/X, ...), so the console editor screens can't be used with a pad. The 360 pad
scheme (Controls_UI_x360_ps3, shipped on PC as controls_ui_xp.xldb) has those bindings. For every
action the 360 binds to a pad but the PC doesn't:
  - the 360 rows that define it are copied in under XP_-prefixed names (action column cleared, so no
    action is defined twice; contexts and timings as on the 360),
  - the PC row keeps its keyboard definition under <ACTION>_KB,
  - the PC row becomes "Combo Any" of <ACTION>_KB and the XP_ copy.
Actions the PC lacks entirely (UI_RBN_TB_PLACE, ...) are added as on the 360.
Analog axes (ANALOG_AXES): the editor screens' stick axes (UsesSticks: RBN_TB_MOVE_OBJ_X/Y, the left stick moving
the spark / held object, and RSTICK_X/Y_VALUE, the right stick turning the camera) are analog on the 360 but stepped
on PC. How the engine evaluates control rows:
  - Combo Any (ComboWatcher_Evaluate) is active when a child is, and its value is the last active child's;
  - an Analog node (AnalogWatcher_Evaluate) is always active;
  - a row with "Willful Actions Only" stays inactive after its context switches on until it has been released
    once (Watcher_UpdateContext / Watcher_Update), which an always-active Analog node never is;
  - a Key row is active while its key is held and gives its Control Factor every frame; a Repeat row gives
    one-frame pulses.
The PC rows are willful, so their analog parts only work through 0.4 thresholds and Repeat rows (a 1.1 pulse every
0.33 s, the keyboard's stepping), and a plain Analog child is suppressed for good. Each of these actions becomes
Combo Any of its own Analog row (<ACTION>_PAD, not willful, as on the 360) first and the PC's Key rows of its inputs
after, so a pressed key still wins; the action row's own Willful is cleared too. The Key rows give +-1.1 (a full
stick; the editor camera only uses the sign) while held, as the raise / lower keys always did.
Spark menu keys (SPARK_MOVE_KEYS): edit / delete / customise were S / D / W, which also move the spark; their keys
are dropped and EXTRA_KEYS gives them Enter, Backspace and C. The sheet gains the 360's Min/Max Hold Time columns
(the game reads columns by name; empty for the PC's own rows).
Names are resolved in file order when the scheme loads, so every row is placed after what it uses.
"""
import struct
import xldb

EMPTY = xldb.EMPTY
PAD_TYPES = ('Button', 'Analog')
KEY_TYPES = ('Key',)
# column indexes
TAG, ROWNUM, NAME, TYPE, CONTROL, INPUT, CONTEXTS, ACTION = range(8)
# action: (control, context of its analog row, as the 360's UI_LSTICK/RSTICK_X/Y_VALUE rows)
ANALOG_AXES = {'UI_RBN_TB_MOVE_OBJ_X': ('STICK1X', '_UITD_GEN_LSTICK'), 'UI_RBN_TB_MOVE_OBJ_Y': ('STICK1Y', '_UITD_GEN_LSTICK'),
               'UI_RSTICK_X_VALUE': ('STICK2X', '_UITD_GEN_RSTICK'), 'UI_RSTICK_Y_VALUE': ('STICK2Y', '_UITD_GEN_RSTICK')}
WILLFUL = 8                                       # column: Willful Actions Only
# spark menu (ModeSelect) actions whose keyboard key also moves the spark: Filter of UI_SOUTH / UI_EAST / UI_NORTH, keys
# S / D / W, so moving off an object edited, deleted or customised it. Their keys are dropped (the pad buttons stay)
# and EXTRA_KEYS gives them Enter, Backspace and C (the PC editor's delete and customise keys). Logic (UI_X, E) stays:
# E is also rotate right, which spark mode doesn't read (RumpusEditorModeSpark_Update reads only the move and
# raise / lower trackers).
SPARK_MOVE_KEYS = ('UI_SPARK_EDIT', 'UI_SPARK_DELETE', 'UI_SPARK_CUSTOMIZE')
# keyboard keys for console editor actions the PC binds to a pad only: an existing row name, or a key to add
# (UI_RBN_TB_PLACE: Enter places in grid mode too; Toy View / Build View had no key; G for spark mode, as P has no
# key image for its label; P keeps working), and the spark menu's
EXTRA_KEYS = {'UI_RBN_TB_PLACE': 'UI_OK_KEY', 'UI_RBN_TB_EASY_ADV_TOGGLE': 'F', 'UI_RBN_TB_SPARK_MODE': 'G',
              'UI_SPARK_EDIT': 'UI_OK_KEY', 'UI_SPARK_DELETE': 'BACKSPACE', 'UI_SPARK_CUSTOMIZE': 'C'}


def _f(v):
    return struct.unpack('>I', struct.pack('>f', float(v)))[0]


def _tokens(inp):
    return [t.strip() for t in (inp or '').split(',') if t.strip()]


def _strip(tok):
    return tok.lstrip('~!')


def _widen_pc(pc):
    """PC sheet (14 columns) -> the 360's 16-column layout: insert Min/Max Hold Time after Control Factor."""
    assert pc.types == 'sissssssifffis', pc.types
    rows = []
    for r, row in enumerate(pc.rows):
        if r == 0:
            mid = ['M', 'N']
        elif r == 1:
            mid = ['Min Hold Time', 'Max Hold Time']
        else:
            mid = [EMPTY, EMPTY]
        rows.append(row[:10] + mid + row[10:])
    return xldb.Sheet(pc.name, 'sissssssifffffis', rows)


def _xp_row_as_pc(row, tag):
    """360 row (factor is an int there, a float on PC) in the widened PC layout."""
    out = list(row)
    out[TAG] = tag
    factor = out[9]
    if factor != EMPTY:
        out[9] = _f(factor - (1 << 32) if factor >= 1 << 31 else factor)
    return out


def _leaves(name, rows_by_name, seen=None):
    """{('pad'|'key'|..., control)} reachable from a name."""
    seen = set() if seen is None else seen
    row = rows_by_name.get(name)
    if row is None or name in seen:
        return set()
    seen.add(name)
    t = row[TYPE]
    if t in PAD_TYPES:
        return {('pad', row[CONTROL])}
    if t in KEY_TYPES:
        return {('key', row[CONTROL])}
    out = set()
    for tok in _tokens(row[INPUT]):
        out |= _leaves(_strip(tok), rows_by_name, seen)
    return out


def _key_rows(name, rows_by_name, out=None):
    """Names of the Key rows reachable from a name, in input order."""
    out = [] if out is None else out
    row = rows_by_name[name]
    if row[TYPE] in KEY_TYPES:
        if name not in out:
            out.append(name)
    elif row[TYPE] not in PAD_TYPES:
        for tok in _tokens(row[INPUT]):
            assert tok == _strip(tok), (name, tok)
            _key_rows(tok, rows_by_name, out)
    return out


def _by_name(rows):
    m = {}
    for row in rows:
        if row[NAME]:
            m[row[NAME]] = row
    return m


def _action_rows(rows):
    m = {}
    for row in rows:
        if row[ACTION]:
            m.setdefault(row[ACTION], row)
    return m


def build(pc_sheet, xp_sheet):
    """Returns (new PC sheet, report lines)."""
    pc = _widen_pc(pc_sheet)
    assert xp_sheet.types == pc.types.replace('sissssssif', 'sissssssii', 1), xp_sheet.types
    tag = pc.rows[1][TAG]
    head, pc_rows = pc.rows[:2], pc.rows[2:]
    xp_rows = [_xp_row_as_pc(r, tag) for r in xp_sheet.rows[2:]]
    xp_names = _by_name(xp_rows)
    xp_actions = _action_rows(xp_rows)
    pc_names_orig = _by_name(pc_rows)
    pc_actions = _action_rows(pc_rows)

    # actions with a pad binding on the 360 and none on PC
    need = []
    for act, xrow in xp_actions.items():
        if not any(k == 'pad' for k, _ in _leaves(xrow[NAME], xp_names)):
            continue
        prow = pc_actions.get(act)
        if prow and any(k == 'pad' for k, _ in _leaves(prow[NAME], pc_names_orig)):
            continue
        need.append(act)
    need_set = set(need)

    # 360 rows needed (the subtrees of those actions), copied under XP_ names, in 360 file order
    wanted = set()

    def collect(name):
        if name in wanted:
            return
        row = xp_names.get(name)
        assert row is not None, 'unresolved 360 name %s' % name
        wanted.add(name)
        for tok in _tokens(row[INPUT]):
            collect(_strip(tok))
    for act in need:
        collect(xp_actions[act][NAME])

    def prefixed(inp):
        return ','.join(t[:len(t) - len(_strip(t))] + 'XP_' + _strip(t) for t in _tokens(inp)) or None

    clones, rownum = [], 1000
    for row in xp_rows:
        if row[NAME] in wanted:
            c = list(row)
            c[NAME] = 'XP_' + row[NAME]
            c[INPUT] = prefixed(row[INPUT])
            c[ACTION] = None
            c[ROWNUM] = rownum
            rownum += 1
            clones.append(c)

    # PC rows: wrap the ones still without a pad binding (in file order, so a Filter of an already
    # fixed action is left alone)
    out_rows = list(clones)
    report = []
    for row in pc_rows:
        act = row[ACTION]
        if act in need_set:
            names_now = _by_name(out_rows)
            if any(k == 'pad' for k, _ in _leaves(row[NAME], {**names_now, row[NAME]: row})):
                report.append('%-34s pad via its input (unchanged)' % act)
                out_rows.append(row)
                continue
            kb = list(row)
            kb[NAME] = act + '_KB'
            kb[ACTION] = None
            kb[ROWNUM] = rownum
            rownum += 1
            assert kb[NAME] not in pc_names_orig
            combo = [EMPTY] * len(row)
            combo[TAG] = row[TAG]
            combo[ROWNUM] = row[ROWNUM]
            combo[NAME] = row[NAME]
            combo[TYPE] = 'Combo Any'
            combo[CONTROL] = None
            combo[INPUT] = kb[NAME] + ',XP_' + xp_actions[act][NAME]
            combo[CONTEXTS] = row[CONTEXTS]
            combo[ACTION] = act
            combo[8] = row[8]                 # Willful Actions Only
            combo[15] = row[15]               # FlashKeyCodes (informational)
            out_rows += [kb, combo]
            report.append('%-34s key %-28s + pad (360: %s %s)' % (act, row[TYPE] + ' ' + (row[CONTROL] or row[INPUT] or ''),
                                                            xp_actions[act][TYPE], xp_actions[act][INPUT] or xp_actions[act][CONTROL]))
        elif act in ANALOG_AXES:
            keys = _key_rows(row[NAME], {**_by_name(out_rows), row[NAME]: row})
            pad = [EMPTY] * len(row)
            pad[TAG] = row[TAG]
            pad[ROWNUM] = rownum
            rownum += 1
            pad[NAME] = act + '_PAD'
            pad[TYPE] = 'Analog'
            pad[CONTROL], pad[CONTEXTS] = ANALOG_AXES[act]
            pad[INPUT] = None
            pad[ACTION] = None
            for c, t in enumerate(pc.types):              # empty string cells are None
                if t == 's' and pad[c] == EMPTY:
                    pad[c] = None
            assert pad[NAME] not in pc_names_orig
            new = list(row)
            new[INPUT] = ','.join([pad[NAME]] + keys)
            new[WILLFUL] = EMPTY
            out_rows += [pad, new]
            report.append('%-34s Combo Any %s (pad, analog, not willful, as on the 360) + %s (keys, held)'
                          % (act, pad[NAME], ','.join(keys)))
        else:
            out_rows.append(row)
    for act in need:
        if act not in pc_actions:
            x = xp_actions[act]
            new = list(x)
            new[INPUT] = prefixed(x[INPUT])
            new[ROWNUM] = rownum
            rownum += 1
            out_rows.append(new)
            report.append('%-34s added as on the 360 (%s %s)' % (act, x[TYPE], x[INPUT]))

    out_rows = _drop_spark_move_keys(out_rows, report)
    out_rows, rownum = _add_extra_keys(out_rows, pc.types, rownum, report)
    sheet = xldb.Sheet(pc.name, pc.types, head + out_rows)
    _validate(pc_sheet, sheet, need)
    return sheet, report


def _drop_spark_move_keys(rows, report):
    """SPARK_MOVE_KEYS: Filter of a Combo Any of a key and a button -> Combo Any of the button rows only."""
    rows = list(rows)
    names = _by_name(rows)
    for act in SPARK_MOVE_KEYS:
        i = next(n for n, r in enumerate(rows) if r[ACTION] == act)
        row = rows[i]
        src = names[row[INPUT]]
        assert row[TYPE] == 'Filter' and src[TYPE] == 'Combo Any', act
        kids = {t: _leaves(t, names) for t in _tokens(src[INPUT])}
        pads = [t for t, leaves in kids.items() if leaves and all(k == 'pad' for k, _ in leaves)]
        dropped = sorted(c for leaves in kids.values() for k, c in leaves if k == 'key')
        assert pads and dropped, act
        new = list(row)
        new[TYPE], new[INPUT] = 'Combo Any', ','.join(pads)
        rows[i] = new
        report.append('%-34s keyboard %s dropped (also moves the spark)' % (act, ','.join(dropped)))
    return rows


def _add_extra_keys(rows, types, rownum, report):
    """EXTRA_KEYS: the action row gets the key as one more Combo Any input (a non-Combo row is kept as
    <ACTION>_PAD and the action becomes Combo Any of it and the key)."""
    rows = list(rows)
    for act, key in EXTRA_KEYS.items():
        names = _by_name(rows)
        i = next(n for n, r in enumerate(rows) if r[ACTION] == act)
        row = rows[i]
        new_rows = []
        if key not in names:                            # a key to add
            k = [EMPTY] * len(row)
            for c, t in enumerate(types):
                if t == 's':
                    k[c] = None
            k[TAG], k[ROWNUM], k[NAME], k[TYPE], k[CONTROL], k[CONTEXTS] = row[TAG], rownum, act + '_KEY2', 'Key', key, row[CONTEXTS]
            rownum += 1
            assert k[NAME] not in names
            new_rows.append(k)
            key_name = k[NAME]
        else:
            key_name = key
        if row[TYPE] == 'Combo Any':
            combo = list(row)
            combo[INPUT] = row[INPUT] + ',' + key_name
        else:
            padrow = list(row)
            padrow[NAME], padrow[ACTION], padrow[ROWNUM], padrow[15] = act + '_PAD', None, rownum, None
            rownum += 1
            assert padrow[NAME] not in names
            new_rows.append(padrow)
            combo = [EMPTY] * len(row)
            for c, t in enumerate(types):
                if t == 's':
                    combo[c] = None
            combo[TAG], combo[ROWNUM], combo[NAME], combo[TYPE] = row[TAG], row[ROWNUM], row[NAME], 'Combo Any'
            combo[INPUT], combo[CONTEXTS], combo[ACTION] = padrow[NAME] + ',' + key_name, row[CONTEXTS], act
            combo[WILLFUL], combo[15] = row[WILLFUL], row[15]
        rows[i:i + 1] = new_rows + [combo]
        report.append('%-34s + keyboard %s' % (act, key))
    return rows, rownum


def _validate(orig, new, need):
    rows = new.rows[2:]
    seen, actions = {}, set()
    for row in rows:
        for tok in _tokens(row[INPUT]):
            assert _strip(tok) in seen, 'row %s uses %s before it is defined' % (row[NAME], tok)
        if row[ACTION]:
            assert row[ACTION] not in actions, 'action %s defined twice' % row[ACTION]
            actions.add(row[ACTION])
        if row[NAME]:
            seen[row[NAME]] = row
    names_new = _by_name(rows)
    o_rows = orig.rows[2:]
    o_names, o_actions = _by_name(o_rows), _action_rows(o_rows)
    n_actions = _action_rows(rows)
    move_keys = {c for a in ('UI_RBN_TB_MOVE_OBJ_X', 'UI_RBN_TB_MOVE_OBJ_Y')
                 for k, c in _leaves(n_actions[a][NAME], names_new) if k == 'key'}
    for act, orow in o_actions.items():         # keyboard and every other binding kept
        before = _leaves(orow[NAME], o_names)
        after = _leaves(n_actions[act][NAME], names_new)
        if act in SPARK_MOVE_KEYS:              # but the spark menu's movement keys: gone, and no other one
            old = {leaf for leaf in before if leaf[0] == 'key'}
            assert old and {c for _, c in old} <= move_keys and not old & after, (act, old, after)
            assert not move_keys & {c for k, c in after if k == 'key'}, (act, after)
            before -= old
        assert before <= after, 'action %s lost %s' % (act, before - after)
    for act in need:                            # and now reachable from a pad
        assert any(k == 'pad' for k, _ in _leaves(n_actions[act][NAME], names_new)), act
    for act, key in EXTRA_KEYS.items():         # the added keyboard keys reach their actions
        keys = {c for k, c in _leaves(n_actions[act][NAME], names_new) if k == 'key'}
        want = {c for k, c in _leaves(key, names_new) if k == 'key'} if key in names_new else {key}
        assert want and want <= keys, (act, want, keys)
    for act, (ctl, _) in ANALOG_AXES.items():   # pad: only the not-willful analog row; keys: the held Key rows
        row = n_actions[act]
        assert row[WILLFUL] == EMPTY, act
        kids = [names_new[_strip(t)] for t in _tokens(row[INPUT])]
        assert kids[0][TYPE] == 'Analog' and kids[0][CONTROL] == ctl and kids[0][WILLFUL] == EMPTY, act
        assert len(kids) > 1 and all(k[TYPE] in KEY_TYPES for k in kids[1:]), act
