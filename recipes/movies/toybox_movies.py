"""Edits to the console Toy Box editor movies: per-input-device key labels.

infinitorium_v.gfx (assets/flash/infinitorium/infinitorium.zip: Infinitorium_V, the 360's console build ribbon,
which the patch uses for every console ribbon on PC)
    Its labels come from the string tables, and the PC's keyboard table holds the PC keyboard ribbon's keys:
    item arrows Left Shift / right mouse (button_target_mode / button_throw; the keys are Z / X), category arrows
    and titles Z / X (button_left / button_right, Legend_ChangeCategoryLeft / Right; the keys are V / B), spark
    mode E (Legend_Place_Spark; the keys are P and G), Toy View / Build View E (Legend_Easy / Legend_Advanced;
    the key is F, added by controls_ui.py).
modeselect.gfx (assets/flash/modeselect/modeselect.zip: the spark menu)
    The four buttons use the generic menu glyphs (menu_button_main / back-cancel / extra1 / extra2: Enter / Esc /
    left mouse / E on the keyboard, while the keys are Enter / Backspace / C / E; the pad table even shows B for
    logic, which is X), and the exit legend says Tab (Legend_Spark_Exit; the key is Esc).
The ids are renamed in place (same length) to coopui_*; the exe resolves them per device (coop.c,
coop_text_lookup_hook): the keyboard gets the right key, a pad the original pad text. Static label texts (`@id`)
and ActionScript string constants (length-prefixed) alike, every occurrence listed.
"""
import hashlib

RENAMES = {
    "infinitorium_v.gfx": [
        (19697, "button_target_mode", "coopui_target_mode"),
        (19929, "button_throw", "coopui_throw"),
        (17672, "button_left", "coopui_left"),
        (17848, "button_right", "coopui_right"),
        (13481, "Legend_ChangeCategoryLeft", "coopui_ChangeCategoryLeft"),
        (45388, "Legend_ChangeCategoryLeft", "coopui_ChangeCategoryLeft"),
        (13728, "Legend_ChangeCategoryRight", "coopui_ChangeCategoryRight"),
        (45414, "Legend_ChangeCategoryRight", "coopui_ChangeCategoryRight"),
        (44485, "Legend_Place_Spark", "coopui_Place_Spark"),
        (45601, "Legend_Advanced", "coopui_Advanced"),
        (46497, "Legend_Easy", "coopui_Easy"),
    ],
    "modeselect.gfx": [
        (20779, "menu_button_main", "coopui_sparkedit"),
        (20754, "menu_button_back-cancel", "coopui_spark_delete_key"),
        (20797, "menu_button_extra1", "coopui_sparkcustom"),
        (20817, "menu_button_extra2", "coopui_sparklogic_"),
        (21720, "Legend_Spark_Exit", "coopui_Spark_Exit"),
    ],
}
# entry -> (sha256 before, sha256 after)
HASHES = {
    "infinitorium_v.gfx": ("574c1cbc9d041afe7582ef78cd0273a52dd4784f1a640de9b236e47dcc4869e8",
                           "a8b4c679ce82fa60039ac4192ceed24d9b8716b936ce0b5f64117cf044d087a3"),
    "modeselect.gfx": ("90d791a713287700912a55203fe09440b62de8c11dc42a440038bec99d072eec",
                       "f48c20faf78a642d2b6def258873c0cdc2bc280c6e297aac0c0f6da3484049e9"),
}


def build(name, data):
    """The edited movie; asserts the original and the result are exactly the known files."""
    before, after = HASHES[name]
    assert hashlib.sha256(data).hexdigest() == before, f"{name}: unexpected original"
    out = bytearray(data)
    for off, old, new in RENAMES[name]:
        old, new = old.encode(), new.encode()
        assert len(old) == len(new), (old, new)
        assert data[off:off + len(old)] == old, f"{name}: unexpected bytes at {off}"
        out[off:off + len(old)] = new
    for _, old, _ in RENAMES[name]:                      # every occurrence renamed
        assert old.encode() not in out, f"{name}: {old} left"
    assert hashlib.sha256(out).hexdigest() == after, f"{name}: unexpected result"
    return bytes(out)
