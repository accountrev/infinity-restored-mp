"""Virtual Base (screen VirtualReader) for two players: the real Infinity Base, the figures and Discs on it, and
the co-op class that splits the selector in two halves (as/CoopVirtualBase.as, compiled by build_as.py).

assets/flash/virtualreader/virtualreader.zip, built at patch time from the zip itself and the game's own
assets/flash/readersplash/readersplash.zip:
  - The Base art (image `virtualreader_ib5`: a half Base with one figure circle, drawn squashed 0.75 x 0.6)
    is replaced by `readersplash_i8` (512x256: the real Base, two figure circles and the hexagon). Same DDS
    format (32-bit ARGB, no mips), so the texture body is swapped as is; the movie's external image gets the
    new size and the Base shape becomes a 512x256 rectangle centred on its sprite, drawn 1:1 (1 texel = 1
    movie unit = 2.25 px at 1080p).
  - The Base sprite is placed with its centre at the old Base's centre x and BASE_RAISE px higher, so it
    clears the character ribbon. The fade-out drift keeps its offsets.
  - P1's figure (characterInfoBar.characterContainer: the 512x512 render and its shadow), the glow ring
    (baseGlow) and the swap flash move so the figure's anchor (FIGURE_ANCHOR, render px) lands on Base
    texel P1_TEXEL, scaled by FIGURE_SCALE about that anchor (so the figure stays on its texel).
  - The Discs (hexCoinScreen: the three Disc images Skew0-2 stacked 10 units apart, and the hexagon glow)
    move so Skew0 lands on Base texel DISC_TEXEL, scaled by FIGURE_SCALE about it. The Disc info tabs stay.
  - The co-op class (as/CoopVirtualBase.as, compiled into its own DoABC tag by build_as.py; the game's
    ActionScript is left as it is) is linked to a new empty sprite placed on the root clip, so the movie
    creates one. It splits the character ribbon in two halves (P1 left, P2 right, three characters each) on
    the Figures tab, and adds P2's figure (a copy of the info bar moved by P2_TEXEL - P1_TEXEL) and both name
    banners behind the Base, P2's P2_BANNER_DY below P1's. These offsets reach it through the Lua side
    (lua_stub(), presentation.zip), as the compiled code is fixed.
Movie units = the reader's root clip `xxx`, whose origin is the screen centre while the reader is attached
to the HUD Container (in single player, and in split screen through container_layout.py).
"""
import hashlib, os, struct

REPO_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
LUA_STUB = os.path.join(REPO_DIR, "lua", "virtualreader.lua")
CLASS = "CoopVirtualBase"                            # as/CoopVirtualBase.as
ABC_PATH = os.path.join(REPO_DIR, "build", CLASS + ".abc")   # its DoABC tag body, from build_as.py

GFX = "virtualreader.gfx"
GFX_SHA256 = "1c7a9ef4280e24e667dc8373c277ff4f92a25ec55a736f58d1a28e2b5c2f2c2d"
BASE_TEXTURE = "textures/239b55f28d3b1c25.tbody"     # virtualreader_ib5 (734x240)
I8_ZIP_ENTRY = "textures/70737ddd10a811a5.tbody"     # readersplash_i8 in readersplash.zip (512x256)
I8_SHA256 = "4d73b58727fe7e7460500f824102aab3de14e3e86f27d38449d30d362cb63b52"

BASE_IMAGE_ID, BASE_SHAPE_ID, BASE_SPRITE_ID = 181, 182, 183
ROOT_SPRITE_ID, BASE_DEPTH = 206, 3                  # VirtualReader_win32 (`xxx`), depth of the Base
INFOBAR_SPRITE_ID = 177                              # characterInfoBar
FIGURE_DEPTHS = (7, 9, 12)                           # swap flash, characterContainer, baseGlow
DISCS_SPRITE_ID, DISCS_DEPTH = 205, 109              # hexCoinScreen, its depth in the root clip
DISC_DEPTHS = (1, 3, 5, 7)                           # Skew0, Skew1, Skew2, hexBaseGlow
COOP_SPRITE_ID, COOP_DEPTH = 207, 240                # the co-op class's sprite (new id), its depth in the root
BASE_SIZE = (512, 256)
OLD_BASE_CENTRE = (13.70, 75.73)                     # ib5 as placed today (movie units)
BASE_RAISE = 215                                     # px at 1080p (2.25 px per movie unit)
P1_TEXEL = (125, 111)                                # user, Base texture pixel for P1's figure
P2_TEXEL = (237, 165)                                # user, for P2's figure
DISC_TEXEL = (240, 75)                               # user, Base texture pixel for the Discs (Skew0's centre)
FIGURE_ANCHOR = (272, 460)                           # render px: disc centre x of every render; y where
                                                     # today's layout puts the Base circle's centre
FIGURE_SCALE = 0.85                                   # user: the figure was too big for this Base (Discs too)
P2_BANNER_DY = 108.3                                 # movie units: P1's banner height (130 x 0.833), so
                                                     # P2's banner sits right below it


# ---- bit-level SWF helpers ------------------------------------------------------------------------
class _Bits:
    def __init__(self, data, pos=0):
        self.d, self.p = data, pos * 8

    def ub(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.p >> 3] >> (7 - (self.p & 7))) & 1)
            self.p += 1
        return v

    def sb(self, n):
        v = self.ub(n)
        return v - (1 << n) if n and v >> (n - 1) else v

    def byte_pos(self):
        return (self.p + 7) >> 3


class _Writer:
    def __init__(self):
        self.out, self.acc, self.n = bytearray(), 0, 0

    def ub(self, n, v):
        for i in range(n - 1, -1, -1):
            self.acc = (self.acc << 1) | ((v >> i) & 1)
            self.n += 1
            if self.n == 8:
                self.out.append(self.acc); self.acc = self.n = 0

    def sb(self, n, v):
        self.ub(n, v & ((1 << n) - 1))

    def align(self):
        if self.n:
            self.ub(8 - self.n, 0)
        return self

    def raw(self, b):
        self.align(); self.out += b


def _sbits(*vals):
    return max([1] + [(v.bit_length() if v >= 0 else (~v).bit_length()) + 1 for v in vals])


def read_matrix(b, pos):
    """MATRIX at byte pos -> ((sx, r0, r1, sy) as 16.16 ints, (tx, ty) twips, end byte pos)."""
    r = _Bits(b, pos)
    sx = sy = 1 << 16; r0 = r1 = 0
    if r.ub(1):
        k = r.ub(5); sx, sy = r.sb(k), r.sb(k)
    if r.ub(1):
        k = r.ub(5); r0, r1 = r.sb(k), r.sb(k)
    k = r.ub(5); tx, ty = r.sb(k), r.sb(k)
    return (sx, r0, r1, sy), (tx, ty), r.byte_pos()


def write_matrix(w, lin, tr):
    sx, r0, r1, sy = lin
    has_scale = (sx, sy) != (1 << 16, 1 << 16)
    w.ub(1, has_scale)
    if has_scale:
        k = _sbits(sx, sy); w.ub(5, k); w.sb(k, sx); w.sb(k, sy)
    has_rot = (r0, r1) != (0, 0)
    w.ub(1, has_rot)
    if has_rot:
        k = _sbits(r0, r1); w.ub(5, k); w.sb(k, r0); w.sb(k, r1)
    k = _sbits(*tr) if any(tr) else 0
    w.ub(5, k)
    if k:
        w.sb(k, tr[0]); w.sb(k, tr[1])
    w.align()


# ---- tags ---------------------------------------------------------------------------------------
def parse_tags(b, pos):
    """[(code, long_header, body)] until and including End."""
    tags = []
    while True:
        cl, = struct.unpack_from('<H', b, pos)
        code, ln, hdr = cl >> 6, cl & 63, 2
        long_hdr = ln == 63
        if long_hdr:
            ln, = struct.unpack_from('<I', b, pos + 2); hdr = 6
        tags.append([code, long_hdr, bytes(b[pos + hdr:pos + hdr + ln])])
        pos += hdr + ln
        if code == 0:
            return tags, pos


def write_tags(tags):
    out = bytearray()
    for code, long_hdr, body in tags:
        if long_hdr or len(body) >= 63:
            out += struct.pack('<HI', (code << 6) | 63, len(body))
        else:
            out += struct.pack('<H', (code << 6) | len(body))
        out += body
    return bytes(out)


def _matrix_pos(code, b):
    """Byte offset of the MATRIX in a PlaceObject2 (26) / PlaceObject3 (70) body, or None."""
    flags = b[0]
    if not flags & 0x04:
        return None
    if code == 26:
        return 3 + (2 if flags & 0x02 else 0)
    p = 4                                                  # flags, flags2, depth
    if b[1] & 0x08 or (b[1] & 0x10):                       # image / class name
        if b[1] & 0x10 or flags & 0x02:
            p = b.index(0, p) + 1
    return p + (2 if flags & 0x02 else 0)


def _depth(code, b):
    return struct.unpack_from('<H', b, 1 if code == 26 else 2)[0]


def _place_matrix_edit(code, body, fn):
    """PlaceObject2/3 body with its matrix (if any) replaced by fn(lin, tr) -> (lin, tr)."""
    p = _matrix_pos(code, body)
    if p is None:
        return body
    lin, tr, end = read_matrix(body, p)
    w = _Writer(); write_matrix(w, *fn(lin, tr))
    return body[:p] + bytes(w.out) + body[end:]


def _first_matrix(sprite_body, depth):
    """The first placement matrix at depth in a DefineSprite body."""
    tags, _ = parse_tags(sprite_body, 4)
    for code, _, b in tags:
        if code in (26, 70) and _depth(code, b) == depth and _matrix_pos(code, b) is not None:
            return read_matrix(b, _matrix_pos(code, b))[:2]
    raise KeyError(depth)


def _edit_sprite(body, depths, fn):
    sid, frames = struct.unpack_from('<HH', body, 0)
    tags, _ = parse_tags(body, 4)
    for t in tags:
        assert t[0] not in (4, 5, 28), 'old-style place/remove tag'
        if t[0] in (26, 70) and _depth(t[0], t[2]) in depths:
            t[2] = _place_matrix_edit(t[0], t[2], fn)
    return body[:4] + write_tags(tags)


def _base_shape(sid):
    """DefineShape: the Base bitmap 1:1 on a BASE_SIZE rectangle centred on (0, 0), as the original (2 fills)."""
    w2, h2 = BASE_SIZE[0] * 10, BASE_SIZE[1] * 10            # half size in twips
    w = _Writer()
    w.raw(struct.pack('<H', sid))
    k = _sbits(-w2, w2, -h2, h2); w.ub(5, k)
    for v in (-w2, w2, -h2, h2):
        w.sb(k, v)
    w.align()
    w.raw(bytes([2]))
    w.raw(bytes([0x41]) + struct.pack('<H', 0xFFFF)); write_matrix(w, (20 << 16, 0, 0, 20 << 16), (0, 0))
    w.raw(bytes([0x41]) + struct.pack('<H', BASE_IMAGE_ID)); write_matrix(w, (20 << 16, 0, 0, 20 << 16), (-w2, -h2))
    w.raw(bytes([0]))                                     # no line styles
    w.ub(4, 2); w.ub(4, 0)                                # fill bits, line bits
    k = _sbits(w2, h2)                                    # style change: move to bottom-right, fill1 = 2
    w.ub(1, 0); w.ub(5, 0b00101); w.ub(5, k); w.sb(k, w2); w.sb(k, h2); w.ub(2, 2)
    for vert, d in ((0, -2 * w2), (1, -2 * h2), (0, 2 * w2), (1, 2 * h2)):
        k = _sbits(d)
        w.ub(1, 1); w.ub(1, 1); w.ub(4, k - 2); w.ub(1, 0); w.ub(1, vert); w.sb(k, d)
    w.ub(6, 0)                                            # end of shape
    return bytes(w.align().out)


def layout():
    """Movie-unit numbers derived from the constants (for the build and for the docs): the Base centre and
    where P1's figure, P2's figure and the Discs stand."""
    bc = (OLD_BASE_CENTRE[0], OLD_BASE_CENTRE[1] - BASE_RAISE / 2.25)
    on_base = lambda t: (bc[0] - BASE_SIZE[0] / 2 + t[0], bc[1] - BASE_SIZE[1] / 2 + t[1])
    return bc, on_base(P1_TEXEL), on_base(P2_TEXEL), on_base(DISC_TEXEL)


def coop_layout():
    """What the movie's code needs at run time (Lua CoopLayout): P2's figure offset from P1's (x, y) and P2's
    banner offset from P1's (y), movie units. The Base is drawn 1:1, so a texel is a movie unit."""
    return "%g,%g,%g" % (P2_TEXEL[0] - P1_TEXEL[0], P2_TEXEL[1] - P1_TEXEL[1], P2_BANNER_DY)


def lua_stub():
    """presentation/virtualreader.lua (Lua source): loads the game's script and adds P2's half."""
    text = open(LUA_STUB).read()
    assert text.count("@COOP_LAYOUT@") == 1
    return text.replace("@COOP_LAYOUT@", coop_layout()).encode()


def _place_on_frame1(sprite_body, depth, cid):
    """DefineSprite body with `cid` placed (PlaceObject2, no name or matrix) at `depth` at the end of frame 1."""
    tags, _ = parse_tags(sprite_body, 4)
    assert all(_depth(c, b) != depth for c, _, b in tags if c in (26, 70)), 'depth in use'
    i = next(k for k, t in enumerate(tags) if t[0] == 1)
    tags.insert(i, [26, False, struct.pack('<BHH', 0x02, depth, cid)])
    return sprite_body[:4] + write_tags(tags)


def build(gfx):
    """virtualreader.gfx (original) -> edited movie."""
    assert hashlib.sha256(gfx).hexdigest() == GFX_SHA256, "unexpected virtualreader.gfx"
    nbits = gfx[8] >> 3
    start = 8 + (5 + 4 * nbits + 7) // 8 + 4
    tags, end = parse_tags(gfx, start)
    assert end == len(gfx)
    bc, p1, _, disc = layout()
    by_id = {}
    for t in tags:
        if t[0] in (2, 39, 1009):
            by_id.setdefault((t[0], struct.unpack_from('<H', t[2], 0)[0]), t)

    # the external image: new target size (u16 width, u16 height after id/format)
    img = by_id[(1009, BASE_IMAGE_ID)]
    assert struct.unpack_from('<HH', img[2], 6) == (734, 240)
    img[2] = img[2][:6] + struct.pack('<HH', *BASE_SIZE) + img[2][10:]
    # the Base shape
    by_id[(2, BASE_SHAPE_ID)][2] = _base_shape(BASE_SHAPE_ID)

    # the Base sprite in the root clip: scale 1, centre bc; frame-to-frame drift (fade-out) kept
    root = by_id[(39, ROOT_SPRITE_ID)]
    first = {}

    def place_base(lin, tr):
        first.setdefault('tr', tr)
        dx, dy = tr[0] - first['tr'][0], tr[1] - first['tr'][1]
        return (1 << 16, 0, 0, 1 << 16), (round(bc[0] * 20) + dx, round(bc[1] * 20) + dy)
    root[2] = _edit_sprite(root[2], (BASE_DEPTH,), place_base)
    assert first['tr'] == (-3626, 722), first                  # (-181.3, 36.1)

    # P1's figure: the anchor moves from where today's layout puts it to Base texel P1_TEXEL, then the whole
    # group (every frame of depths FIGURE_DEPTHS) is scaled by FIGURE_SCALE about that point. The info bar
    # is scaled (0.833, 0.8328) in the root clip, so the move is divided by its scale.
    (bsx, _, _, bsy), (btx, bty) = _first_matrix(root[2], 5)              # characterInfoBar in the root clip
    infobar = by_id[(39, INFOBAR_SPRITE_ID)]
    (csx, _, _, csy), (ctx, cty) = _first_matrix(infobar[2], 9)           # characterContainer in the bar
    sx, sy = bsx / 65536, bsy / 65536
    ax = btx / 20 + sx * (ctx / 20 + csx / 65536 * (-332 + FIGURE_ANCHOR[0]))
    ay = bty / 20 + sy * (cty / 20 + csy / 65536 * (-260 + FIGURE_ANCHOR[1]))
    mx, my = round((p1[0] - ax) / sx * 20), round((p1[1] - ay) / sy * 20)
    kx, ky = (p1[0] * 20 - btx) / sx, (p1[1] * 20 - bty) / sy              # the anchor in bar twips
    f = FIGURE_SCALE

    def place_figure(lin, tr):
        x, y = tr[0] + mx, tr[1] + my
        return tuple(round(v * f) for v in lin), (round(kx + f * (x - kx)), round(ky + f * (y - ky)))
    infobar[2] = _edit_sprite(infobar[2], FIGURE_DEPTHS, place_figure)

    # The Discs the same way: Skew0's centre (frame 1) moves to Base texel DISC_TEXEL, then the Disc images and
    # the hexagon glow (every frame) are scaled by FIGURE_SCALE about that point.
    (hsx, _, _, hsy), (htx, hty) = _first_matrix(root[2], DISCS_DEPTH)      # hexCoinScreen in the root clip
    discs = by_id[(39, DISCS_SPRITE_ID)]
    _, (stx, sty) = _first_matrix(discs[2], DISC_DEPTHS[0])                # Skew0
    dkx, dky = (disc[0] * 20 - htx) / (hsx / 65536), (disc[1] * 20 - hty) / (hsy / 65536)   # in its twips
    dmx, dmy = dkx - stx, dky - sty

    def place_disc(lin, tr):
        x, y = tr[0] + dmx, tr[1] + dmy
        return tuple(round(v * f) for v in lin), (round(dkx + f * (x - dkx)), round(dky + f * (y - dky)))
    discs[2] = _edit_sprite(discs[2], DISC_DEPTHS, place_disc)

    # the co-op class: an empty sprite linked to it (SymbolClass), placed on the root clip at frame 1 (unnamed,
    # above every depth the root's timeline uses), and its own DoABC tag after the game's
    root[2] = _place_on_frame1(root[2], COOP_DEPTH, COOP_SPRITE_ID)
    symbols = next(t for t in tags if t[0] == 76)
    n, = struct.unpack_from('<H', symbols[2], 0)
    symbols[2] = struct.pack('<H', n + 1) + symbols[2][2:] + struct.pack('<H', COOP_SPRITE_ID) + CLASS.encode() + b'\0'

    # every other tag unchanged
    orig, _ = parse_tags(gfx, start)
    changed = [(o[0], struct.unpack_from('<H', o[2], 0)[0] if o[0] != 76 else 0) for o, n in zip(orig, tags)
               if o[2] != n[2]]
    assert len(orig) == len(tags) and sorted(changed) == sorted([(2, BASE_SHAPE_ID), (39, INFOBAR_SPRITE_ID),
                                                                   (39, DISCS_SPRITE_ID), (39, ROOT_SPRITE_ID),
                                                                   (76, 0), (1009, BASE_IMAGE_ID)]), changed
    abc = open(ABC_PATH, "rb").read()
    i = next(k for k, t in enumerate(tags) if t[0] == 39 and struct.unpack_from('<H', t[2], 0)[0] == ROOT_SPRITE_ID)
    tags.insert(i, [39, False, struct.pack('<HH', COOP_SPRITE_ID, 1) + write_tags([[1, False, b''], [0, False, b'']])])
    i = next(k for k, t in enumerate(tags) if t[0] == 82)
    tags.insert(i + 1, [82, True, abc])
    body = write_tags(tags)
    out = bytearray(gfx[:start]) + body
    struct.pack_into('<I', out, 4, len(out))
    return bytes(out), (bc, p1, (ax, ay), (mx / 20, my / 20), disc)
