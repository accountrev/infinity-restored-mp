"""Reader/writer for Disney Infinity .xldb workbooks (big-endian, same on PC and 360).

Layout (inferred from controls*.xldb, verified by byte-exact round trips):
  0x00 'XLDB', u32 version (2), u32 sheet count
  per sheet, at h: u32 rows, u32 cols, u32 0, u32 typestr (0x18), u32 strbase, u32 rowdata  (offsets from h)
    typestr  = one char per column: s (string offset from strbase), i (int), f (float); NUL-padded to 4
    strbase  = string pool: the sheet name first, then the two header rows' strings column by column,
               then the data rows' strings column by column (all rows of column 0, then column 1, ...),
               each string once, in order of first use; NUL-padded to 4. Header row 0 (".xlfl", ".xlrw",
               column letters) is all strings; header row 1 (book:sheet tag, the int 1, column titles) is
               strings except column 1
    rowdata  = rows * cols big-endian 4-byte cells, 0xffbaddef = empty
  the next sheet header follows the previous sheet's row data.

Usage: xldb.py file.xldb [sheet]   -> TSV dump
"""
import struct, sys

EMPTY = 0xFFBADDEF
HEADER_ROWS = 2


def _cstr(d, off):
    return d[off:d.index(b'\0', off)].decode('latin-1')


class Sheet:
    """name, types (str), rows: list of lists; string cells are str (None = empty), others raw u32."""

    def __init__(self, name, types, rows):
        self.name, self.types, self.rows = name, types, rows

    def is_str(self, r, c):
        return r == 0 or (r == 1 and c != 1) or self.types[c] == 's'


def read(path):
    return parse(open(path, 'rb').read())


def parse(d):
    magic, ver, n = struct.unpack_from('>4sII', d, 0)
    assert magic == b'XLDB' and ver == 2, 'not an xldb'
    h, sheets = 12, []
    for _ in range(n):
        nrows, cols, zero, tso, sbo, rdo = struct.unpack_from('>6I', d, h)
        assert zero == 0 and tso == 0x18
        types = d[h + tso:h + tso + cols].decode()
        sb = h + sbo
        name = _cstr(d, sb)
        sh = Sheet(name, types, [])
        for r in range(nrows):
            cells = list(struct.unpack_from('>%dI' % cols, d, h + rdo + 4 * cols * r))
            for c in range(cols):
                if sh.is_str(r, c):
                    cells[c] = None if cells[c] == EMPTY else _cstr(d, sb + cells[c])
            sh.rows.append(cells)
        sheets.append(sh)
        h += rdo + 4 * cols * nrows
    assert h == len(d), 'trailing data'
    return sheets


def _pad4(b):
    return b + b'\0' * (-len(b) % 4)


def write(path, sheets):
    open(path, 'wb').write(dumps(sheets))


def dumps(sheets):
    out = bytearray(struct.pack('>4sII', b'XLDB', 2, len(sheets)))
    for sh in sheets:
        cols = len(sh.types)
        pool, offs = bytearray(), {}

        def add(s):
            if s not in offs:
                offs[s] = len(pool)
                pool.extend(s.encode('latin-1') + b'\0')
            return offs[s]
        add(sh.name)
        for part in (range(min(HEADER_ROWS, len(sh.rows))), range(HEADER_ROWS, len(sh.rows))):
            for c in range(cols):
                for r in part:
                    if sh.is_str(r, c) and sh.rows[r][c] is not None:
                        add(sh.rows[r][c])
        cells = []
        for r, row in enumerate(sh.rows):
            assert len(row) == cols
            for c, v in enumerate(row):
                if sh.is_str(r, c):
                    cells.append(EMPTY if v is None else offs[v])
                else:
                    cells.append(v)
        typestr = _pad4(sh.types.encode())
        pool = _pad4(bytes(pool))
        tso = 0x18
        sbo = tso + len(typestr)
        rdo = sbo + len(pool)
        out += struct.pack('>6I', len(sh.rows), cols, 0, tso, sbo, rdo)
        out += typestr + pool
        out += struct.pack('>%dI' % len(cells), *cells)
    return bytes(out)


def text(sh, r, c):
    """Cell as display text."""
    v = sh.rows[r][c]
    if sh.is_str(r, c):
        return v or ''
    if v == EMPTY:
        return ''
    if sh.types[c] == 'f':
        return '%g' % struct.unpack('>f', struct.pack('>I', v))[0]
    return str(v - (1 << 32) if v >= 1 << 31 else v)


def sheets(path):
    """Compatibility: [(name, types, rows as display text)]."""
    return [(sh.name, sh.types, [[text(sh, r, c) for c in range(len(sh.types))] for r in range(len(sh.rows))])
            for sh in read(path)]


if __name__ == '__main__':
    for sh in read(sys.argv[1]):
        if len(sys.argv) > 2 and sys.argv[2] != sh.name:
            continue
        print('##', sh.name, sh.types, len(sh.rows), 'rows')
        for r in range(len(sh.rows)):
            print('\t'.join(text(sh, r, c) for c in range(len(sh.types))))
