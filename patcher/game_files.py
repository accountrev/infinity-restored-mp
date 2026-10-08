"""The game's files that the patch changes besides the exe, and the .orig backups of all of them.

Each data file is a zip next to the exe whose entries are rebuilt by a recipe (recipes/):
  assets/excel/excel.zip                          pad bindings for the editor menus (controls_ui.py) and for leaving
                                                  the Toy Box logic mode (controls_gameplay.py)
  assets/flash/customize/customize.zip            the customise movies (customize_movies.py)
  assets/flash/buildingribbon/buildingribbon.zip  the Play Set placement movies' key labels (buildingribbon_movies.py)
  assets/startup4.zip                             split-screen placement of the PC-only full-screen menus
                                                  (container_layout.py)
  assets/flash/virtualreader/virtualreader.zip    the Virtual Base: the real Infinity Base art (from the game's own
                                                  readersplash.zip), the figures and Discs on it, and the selector
                                                  split for two players (vr_movie.py)
  assets/presentation/presentation.zip            the Virtual Base's script for player 2 (lua/virtualreader.lua) and
                                                  the console Toy Box ribbon's scripts (build/lua/, build_lua.py)
  assets/flash/infinitorium/infinitorium.zip,     the console Toy Box editor's key labels (toybox_movies.py)
  assets/flash/modeselect/modeselect.zip
Only the known Steam files are accepted (SHA-256 checked), and every rebuilt zip is checked entry by entry.
"""
import hashlib, io, os, shutil, struct, sys, zipfile, zlib

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(REPO_DIR, "recipes", d) for d in ("control_tables", "movies")]
import buildingribbon_movies, container_layout, controls_gameplay, controls_ui, customize_movies, toybox_movies, vr_movie, xldb

EXCEL_REL = os.path.join("assets", "excel", "excel.zip")
EXCEL_SHA256 = "07d76b3537d07ded6ce12390310f58a41d4b9883547df65fe66c01d63060275d"
CONTROLS_UI_PC = "controls_ui_win32.xldb"
CONTROLS_UI_360 = "controls_ui_xp.xldb"
CONTROLS_PC = "controls_win32.xldb"
CUSTOMIZE_REL = os.path.join("assets", "flash", "customize", "customize.zip")
CUSTOMIZE_SHA256 = "09696c907bbd21842b8e26d9f9db5f316c533a18acf8346fb4f1ca285a28df41"
BUILDINGRIBBON_REL = os.path.join("assets", "flash", "buildingribbon", "buildingribbon.zip")
BUILDINGRIBBON_SHA256 = "07f6d0326e38bc38d76902293f8fadd7a082bc6d0b6fbfd13c2c7472aced2049"
STARTUP4_REL = os.path.join("assets", "startup4.zip")
STARTUP4_SHA256 = "ff0d4cf09f917dc77b53961bbb570fdadab51329211d63a9e3f679076a7110bc"
CONTAINER_XLDB = "excel/container.xldb"
VIRTUALREADER_REL = os.path.join("assets", "flash", "virtualreader", "virtualreader.zip")
VIRTUALREADER_SHA256 = "f90c76aadcb1659241c8c89f80ed9bcc0bb1538f977012f546ca6cc4be7ae66a"
READERSPLASH_REL = os.path.join("assets", "flash", "readersplash", "readersplash.zip")
PRESENTATION_REL = os.path.join("assets", "presentation", "presentation.zip")
INFINITORIUM_REL = os.path.join("assets", "flash", "infinitorium", "infinitorium.zip")
INFINITORIUM_SHA256 = "dc15bd184130ed31f04b7b50d19aeedbfc2e072c58421ae0b21441bafd0b8348"
MODESELECT_REL = os.path.join("assets", "flash", "modeselect", "modeselect.zip")
MODESELECT_SHA256 = "b932aed34e3e8dec41029cdffae52d55828722a6358dcd66c625d686e6741d0c"
PRESENTATION_SHA256 = "0e8a2b2ad129aa87d508b589d8330e3c5815a3a3fb1007e9ec55a188b28a929b"
VR_LUA, VR_LUA_ORIG = "virtualreader.lua", "virtualreader_orig.lua"
# the console Toy Box ribbon: the 360's scripts (Lua source, build/lua/) in place of the PC's rework; sha256 of the PC ones
CONSOLE_RIBBON_LUA = {
    "ribbontoybox.lua": "d64dd3f9346a3c636baac3d557da3ad5923107a5bf44316c517728f0a57af145",
    "ribbonbase.lua": "1559a9d2047ee045f2a52b262f59a6ad0c7676f24facaa1d5ef5f91e9ef518d7",
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def original(path, digest_ok, what):
    """The original bytes of a file we patch: the file itself, or its .orig backup if it's patched."""
    data = open(path, "rb").read()
    backup = path + ".orig"
    if sha256(data) == digest_ok:
        return data
    if os.path.exists(backup) and sha256(open(backup, "rb").read()) == digest_ok:
        print(f"{what} is not the original (already patched?) - re-patching from the .orig backup")
        return open(backup, "rb").read()
    sys.exit(f"unexpected {what} (sha256 {sha256(data)}); refusing to patch")


def backup_once(path, digest_ok):
    backup = path + ".orig"
    if not os.path.exists(backup) and sha256(open(path, "rb").read()) == digest_ok:
        shutil.copy2(path, backup)
        print(f"backup written: {backup}")


def zip_replace(zdata, name, new_data):
    """zdata with one stored entry's contents replaced (deflate); every other byte copied as is."""
    eocd = len(zdata) - 22
    sig, _, _, n_this, n_total, cd_size, cd_off, clen = struct.unpack_from("<IHHHHIIH", zdata, eocd)
    assert sig == 0x06054B50 and clen == 0 and n_this == n_total, "unexpected zip layout"
    entries, p = [], cd_off
    for _ in range(n_total):
        f = list(struct.unpack_from("<IHHHHHHIIIHHHHHII", zdata, p))
        assert f[0] == 0x02014B50
        nlen, xlen, cmlen = f[10], f[11], f[12]
        ename = zdata[p + 46:p + 46 + nlen].decode()
        entries.append((f, zdata[p + 46:p + 46 + nlen + xlen + cmlen], ename))
        p += 46 + nlen + xlen + cmlen
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    new_comp = comp.compress(new_data) + comp.flush()
    new_crc = zlib.crc32(new_data) & 0xFFFFFFFF
    out, new_offsets, found = bytearray(), {}, False
    for f, _, ename in sorted(entries, key=lambda e: e[0][16]):
        lho = f[16]
        lf = list(struct.unpack_from("<IHHHHHIIIHH", zdata, lho))
        assert lf[0] == 0x04034B50 and not (lf[2] & 8), "unexpected local header"
        hdr_len = 30 + lf[9] + lf[10]
        body = zdata[lho + 30:lho + hdr_len]
        payload = zdata[lho + hdr_len:lho + hdr_len + lf[7]]
        if ename == name:
            assert lf[3] == 8, "entry not deflated"
            lf[6], lf[7], lf[8] = new_crc, len(new_comp), len(new_data)
            payload, found = new_comp, True
        new_offsets[ename] = len(out)
        out += struct.pack("<IHHHHHIIIHH", *lf) + body + payload
    assert found, f"{name} not in zip"
    cd_start = len(out)
    for f, tail, ename in entries:
        f = list(f)
        if ename == name:
            f[7], f[8], f[9] = new_crc, len(new_comp), len(new_data)
        f[16] = new_offsets[ename]
        out += struct.pack("<IHHHHHHIIIHHHHHII", *f) + tail
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, n_this, n_total, len(out) - cd_start, cd_start, 0)
    return bytes(out)


def zip_add(zdata, name, new_data, like):
    """zdata with a new deflated entry appended after the others, its headers copied from entry `like`
    (without extra fields); every other byte copied as is."""
    eocd = len(zdata) - 22
    sig, _, _, n_this, n_total, cd_size, cd_off, clen = struct.unpack_from("<IHHHHIIH", zdata, eocd)
    assert sig == 0x06054B50 and clen == 0 and n_this == n_total, "unexpected zip layout"
    p, cd_like = cd_off, None
    for _ in range(n_total):
        f = list(struct.unpack_from("<IHHHHHHIIIHHHHHII", zdata, p))
        ename = zdata[p + 46:p + 46 + f[10]].decode()
        assert f[0] == 0x02014B50 and ename != name
        if ename == like:
            cd_like = f
        p += 46 + f[10] + f[11] + f[12]
    assert cd_like and p == cd_off + cd_size
    lf = list(struct.unpack_from("<IHHHHHIIIHH", zdata, cd_like[16]))
    assert lf[0] == 0x04034B50 and lf[3] == 8 and not (lf[2] & 8)
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    new_comp = comp.compress(new_data) + comp.flush()
    crc, bname = zlib.crc32(new_data) & 0xFFFFFFFF, name.encode()
    lf[6:11] = [crc, len(new_comp), len(new_data), len(bname), 0]
    cd = cd_like[:7] + [crc, len(new_comp), len(new_data), len(bname), 0, 0] + cd_like[13:16] + [cd_off]
    out = bytearray(zdata[:cd_off]) + struct.pack("<IHHHHHIIIHH", *lf) + bname + new_comp
    cd_start = len(out)
    out += zdata[cd_off:cd_off + cd_size] + struct.pack("<IHHHHHHIIIHHHHHII", *cd) + bname
    out += struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, n_this + 1, n_total + 1, len(out) - cd_start, cd_start, 0)
    return bytes(out)


def zip_replace_checked(zdata, new_files):
    """zdata with entries replaced ({name: contents}), verified: CRCs, new entries, every other entry unchanged."""
    new_zip = zdata
    for name, data in new_files.items():
        new_zip = zip_replace(new_zip, name, data)
    z, nz = zipfile.ZipFile(io.BytesIO(zdata)), zipfile.ZipFile(io.BytesIO(new_zip))
    assert nz.testzip() is None
    for info in z.infolist():
        assert nz.read(info.filename) == new_files.get(info.filename, z.read(info.filename))
    return new_zip


def patched_excel(zdata, game_dir):
    """excel.zip with the gamepad bindings added to the PC menu control scheme and to the gameplay scheme's
    logic-mode cancel."""
    z = zipfile.ZipFile(io.BytesIO(zdata))
    pc = xldb.parse(z.read(CONTROLS_UI_PC))
    xp = xldb.parse(z.read(CONTROLS_UI_360))
    sheet, report = controls_ui.build(pc[0], xp[0])
    assert len(pc) == 1 and len(xp) == 1
    game = xldb.parse(z.read(CONTROLS_PC))
    assert len(game) == 1 and xldb.dumps(game) == z.read(CONTROLS_PC)
    game_sheet, game_report = controls_gameplay.build(game[0])
    new_zip = zip_replace_checked(zdata, {CONTROLS_UI_PC: xldb.dumps([sheet]), CONTROLS_PC: xldb.dumps([game_sheet])})
    return new_zip, [f"{CONTROLS_UI_PC}: {len(pc[0].rows)} -> {len(sheet.rows)} rows; pad bindings for:"] + \
        ["  " + line for line in report] + \
        [f"{CONTROLS_PC}: {len(game[0].rows)} -> {len(game_sheet.rows)} rows; pad binding for:"] + \
        ["  " + line for line in game_report]


def patched_customize(zdata, game_dir):
    """customize.zip with the edited customise movies."""
    z = zipfile.ZipFile(io.BytesIO(zdata))
    new_zip = zip_replace_checked(zdata, {n: customize_movies.build(n, z.read(n)) for n in customize_movies.EDITS})
    return new_zip, ["customize.gfx: LT/RT move the highlight one item (with a sound), LB/RB to a section's first item; key labels per input device (single player)",
                     "customize_h.gfx, customize_v.gfx: item/category labels per input device (split screen)"]


def patched_buildingribbon(zdata, game_dir):
    """buildingribbon.zip with the placement movies' key labels per input device."""
    z = zipfile.ZipFile(io.BytesIO(zdata))
    new_zip = zip_replace_checked(zdata, {n: buildingribbon_movies.build(n, z.read(n))
                                          for n in buildingribbon_movies.EDITS})
    return new_zip, ["buildingribbon.gfx: item arrows and on-screen button prompts per input device (single player)",
                     "buildingribbon_h.gfx, buildingribbon_v.gfx: item labels per input device (split screen)"]


def patched_startup4(zdata, game_dir):
    """startup4.zip with the PC-only full-screen menus placed by the Container in split screen too."""
    z = zipfile.ZipFile(io.BytesIO(zdata))
    xl, report = container_layout.build_checked(z.read(CONTAINER_XLDB))
    new_zip = zip_replace_checked(zdata, {CONTAINER_XLDB: xl})
    return new_zip, [f"{CONTAINER_XLDB}: split-screen rows for the Virtual Base and the Toy Box build ribbon"] + \
        ["  " + line for line in report]


def patched_virtualreader(zdata, game_dir):
    """virtualreader.zip with the real Base (readersplash_i8 from the game's readersplash.zip) and P1's figure on it."""
    if not os.path.exists(vr_movie.ABC_PATH):
        sys.exit("build/CoopVirtualBase.abc missing - run recipes/movies/build_as.py first")
    z = zipfile.ZipFile(io.BytesIO(zdata))
    rs = os.path.join(game_dir, READERSPLASH_REL)
    if not os.path.exists(rs):
        sys.exit(f"{rs} not found")
    base = zipfile.ZipFile(rs).read(vr_movie.I8_ZIP_ENTRY)
    if sha256(base) != vr_movie.I8_SHA256:
        sys.exit(f"unexpected {vr_movie.I8_ZIP_ENTRY} in {rs}")
    gfx, (bc, p1, _, _, disc) = vr_movie.build(z.read(vr_movie.GFX))
    new_zip = zip_replace_checked(zdata, {vr_movie.GFX: gfx, vr_movie.BASE_TEXTURE: base})
    return new_zip, [f"Base art: readersplash_i8 (512x256), centre ({bc[0]:.2f}, {bc[1]:.2f}) movie units, "
                     f"{vr_movie.BASE_RAISE} px above the old Base",
                     f"P1's figure on Base texel {vr_movie.P1_TEXEL} = ({p1[0]:.2f}, {p1[1]:.2f}), "
                     f"scaled {vr_movie.FIGURE_SCALE} about that point",
                     f"Discs on Base texel {vr_movie.DISC_TEXEL} = ({disc[0]:.2f}, {disc[1]:.2f}), "
                     f"scaled {vr_movie.FIGURE_SCALE} about that point",
                     f"co-op class {vr_movie.CLASS} added in its own ActionScript block (the game's is unchanged): "
                     "character selector in two halves (P1 left, P2 right, 3 characters each), P2's figure and banner"]


def patched_presentation(zdata, game_dir):
    """presentation.zip: the Virtual Base's script kept as virtualreader_orig.lua (same bytes), and a new
    virtualreader.lua (Lua source, lua/virtualreader.lua) that loads it and adds player 2's half; the console
    Toy Box ribbon's scripts (ribbontoybox.lua, ribbonbase.lua) replaced by the 360's (build/lua/)."""
    for name in CONSOLE_RIBBON_LUA:
        if not os.path.exists(os.path.join(REPO_DIR, "build", "lua", name)):
            sys.exit(f"build/lua/{name} missing - run recipes/scripts/build_lua.py first")
    z = zipfile.ZipFile(io.BytesIO(zdata))
    script = z.read(VR_LUA)
    added = zip_add(zdata, VR_LUA_ORIG, script, like=VR_LUA)
    replace = {VR_LUA: vr_movie.lua_stub()}
    for name, digest in CONSOLE_RIBBON_LUA.items():
        assert sha256(z.read(name)) == digest, f"{name}: unexpected original"
        replace[name] = open(os.path.join(REPO_DIR, "build", "lua", name), "rb").read()
    new_zip = zip_replace_checked(added, replace)
    nz = zipfile.ZipFile(io.BytesIO(new_zip))
    assert nz.read(VR_LUA_ORIG) == script and len(nz.infolist()) == len(z.infolist()) + 1
    return new_zip, [f"{VR_LUA} -> {VR_LUA_ORIG} (unchanged); new {VR_LUA}: P2's half of the Virtual Base, "
                     f"layout {vr_movie.coop_layout()} (P2's figure offset x,y, banner offset y)",
                     "ribbontoybox.lua, ribbonbase.lua: the Xbox 360's console Toy Box ribbon (Lua source, build/lua/)"]


def patched_toybox_movie(zip_entry, report):
    def build(zdata, game_dir):
        z = zipfile.ZipFile(io.BytesIO(zdata))
        return zip_replace_checked(zdata, {zip_entry: toybox_movies.build(zip_entry, z.read(zip_entry))}), [report]
    return build


# (path relative to the game folder, original sha256, builder: (original bytes, game folder) -> (new bytes, report lines))
DATA_FILES = [
    (EXCEL_REL, EXCEL_SHA256, patched_excel),
    (CUSTOMIZE_REL, CUSTOMIZE_SHA256, patched_customize),
    (BUILDINGRIBBON_REL, BUILDINGRIBBON_SHA256, patched_buildingribbon),
    (STARTUP4_REL, STARTUP4_SHA256, patched_startup4),
    (VIRTUALREADER_REL, VIRTUALREADER_SHA256, patched_virtualreader),
    (PRESENTATION_REL, PRESENTATION_SHA256, patched_presentation),
    (INFINITORIUM_REL, INFINITORIUM_SHA256, patched_toybox_movie(
        "infinitorium_v.gfx", "infinitorium_v.gfx: console Toy Box ribbon key labels per input device (toybox_movies.py)")),
    (MODESELECT_REL, MODESELECT_SHA256, patched_toybox_movie(
        "modeselect.gfx", "modeselect.gfx: spark menu key labels per input device (toybox_movies.py)")),
]
