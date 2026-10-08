"""Edits to the Play Set placement movies in assets/flash/buildingribbon/buildingribbon.zip.

buildingribbon.gfx (BuildingRibbon_win32: the full-screen PC movie, single player)
    Its labels exist only as keyboard keys: the item arrows (set to _cbi_win32_keyZ / X on win32 in
    ReloadRibbon) and the on-screen buttons' prompts (change lot A / D, place Enter, rotate Q / E, close Esc),
    so a pad player saw keys. The eight ids are renamed in place (same length) to coopui_bld_*; the exe
    resolves those to the same keys for the keyboard and to the pad buttons that do the same thing (LT / RT,
    left stick, A, D-pad left / right, B) for a pad.

buildingribbon_h.gfx / buildingribbon_v.gfx (BuildingRibbon_H / _V: the split-screen movies of PlaceBldg,
PlaceDeco, PlacePrank and PlaceTrainCar, from the 360)
    The item arrows are labelled with gameplay strings (button_target_mode, button_throw): LT / RT in the
    pad string table, but Left Shift / right mouse in the keyboard one, while the keyboard's item keys are
    Z / X. The two label ids are renamed in place (same length) to the coopui_* ids the split customise
    movies use; the exe resolves those to Z / X for the keyboard and to the original strings for a pad
    (coop.c, coop_text_lookup_hook). Same edit as customize_movies.py.
"""
import hashlib

# entry -> (sha256 before, sha256 after, [(offset in the original, original bytes, new bytes)])
EDITS = {
    "buildingribbon.gfx": (
        "8adfd8bfa3baec241537cceec4935b5977c51733fb12d8af178312e7e14b12f7",
        "5003e3ed45e38aa97b91ece19f87a04002855ba6bf760a4bbd3ad5694f919e86",
        [
            (4373, b"@_cbi_win32_keyD".hex(), b"@coopui_bld_lotr".hex()),
            (4554, b"@_cbi_win32_keyA".hex(), b"@coopui_bld_lotl".hex()),
            (4828, b"@_cbi_win32_keyEnter".hex(), b"@coopui_bld_placeobj".hex()),
            (5013, b"@_cbi_win32_keyE".hex(), b"@coopui_bld_rotr".hex()),
            (5195, b"@_cbi_win32_keyQ".hex(), b"@coopui_bld_rotl".hex()),
            (8423, b"@_cbi_win32_keyEsc".hex(), b"@coopui_bld_cancel".hex()),
            (33614, b"@_cbi_win32_keyZ".hex(), b"@coopui_bld_prev".hex()),
            (33631, b"@_cbi_win32_keyX".hex(), b"@coopui_bld_next".hex()),
        ],
    ),
    "buildingribbon_h.gfx": (
        "9691b98cba71a09178a2f808449acf3cd2c25aca0814c15f6fde2192a2eac424",
        "052a0b163de47a1dca01a5920215751fb9a0441fb663c3cfda9278078fb86cc7",
        [
            (25841, b"@button_target_mode".hex(), b"@coopui_target_mode".hex()),
            (25942, b"@button_throw".hex(), b"@coopui_throw".hex()),
        ],
    ),
    "buildingribbon_v.gfx": (
        "81038b320e216b2b69d958e173f22b7d68f6988e02be98446d22118b3f113f89",
        "a26b467a80f62030c866ad2e42b40c9ec5353df052988c50170cfa1d16bd197d",
        [
            (25627, b"@button_target_mode".hex(), b"@coopui_target_mode".hex()),
            (25725, b"@button_throw".hex(), b"@coopui_throw".hex()),
        ],
    ),
}


def build(name, data):
    """The edited movie; asserts the original and the result are exactly the known files."""
    before, after, edits = EDITS[name]
    assert hashlib.sha256(data).hexdigest() == before, f"{name}: unexpected original"
    out = bytearray(data)
    for off, old, new in edits:                              # same-length renames: offsets stay valid
        old, new = bytes.fromhex(old), bytes.fromhex(new)
        assert data[off:off + len(old)] == old, f"{name}: unexpected bytes at {off}"
        out[off:off + len(old)] = new
    assert hashlib.sha256(out).hexdigest() == after, f"{name}: unexpected result"
    return bytes(out)
