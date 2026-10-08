/* Key labels per input device. patch_exe.py renames label ids in the editor movies to coopui_* (the movie
   edits are in recipes/movies/), and this hook turns each one into the keyboard's or the pad's label, the way
   the game picks its string table (the pad one while the last input came from a pad):
   - customise, split movies (Customize_H/_V, from the 360): the item / category arrows used gameplay strings
     (button_target_mode, ...): LT / RT / LB / RB for a pad, but Left Shift / right mouse / Z / X on the
     keyboard, whose editor keys are Z / X (items) and V / B (categories);
   - customise, full-screen PC movie (Customize_win32, a pad player in single player): its labels exist only
     in the keyboard table (Z / X pages, F1 / F2 categories, 1-9 under the items), so a pad saw keys;
   - Play Set placement: the split movies (BuildingRibbon_H/_V) reuse the split customise ids; the full-screen
     PC movie (BuildingRibbon_win32) gets coopui_bld_* for its item arrows and on-screen button prompts;
   - the console Toy Box ribbon and spark menu: see the table.
   Replaces the string lookup (0x7C4E70) in the Flash text translator and in Lua TranslateText (button
   legends); both callers push a fifth argument that it doesn't read, which is passed on. */
#define orig_text_lookup ((const char *(CDECL *)(void *, const char **, const char **, int, int))0x007C4E70)

/* text with the key image `from` (img://<from>") replaced by `to`; a few buffers in turn, as callers copy the text */
static const char *swap_key_image(const char *text, const char *from, const char *to)
{
    static char bufs[4][768];
    static int next;
    char *out = bufs[next], *end = out + sizeof(bufs[0]) - 1, *p = out;
    u32 n = str_len(from);
    next = (next + 1) % 4;
    if (!text)
        return text;
    for (const char *t = text; *t; ) {
        if (starts_with(t, from) && t[n] == '"' && t >= text + 6 && starts_with(t - 6, "img://")) {
            for (const char *c = to; *c && p < end; c++) *p++ = *c;
            t += n;
        } else if (p < end) {
            *p++ = *t++;
        } else {
            return text;                        /* too long: leave it as it is */
        }
    }
    *p = 0;
    return out;
}

EXPORT const char *CDECL coop_text_lookup_hook(void *key, const char **id, const char **id_sfx, int has_sfx,
                                                int a5)
{
    static const char *const labels[][5] = {        /* movie id, keyboard, pad[, keyboard image -> image] */
        /* split movies */
        {"coopui_target_mode", "_cbi_win32_keyz", "button_target_mode"},    /* previous item */
        {"coopui_throw", "_cbi_win32_keyx", "button_throw"},                /* next item */
        {"coopui_left", "_cbi_win32_keyv", "button_left"},                  /* previous category */
        {"coopui_right", "_cbi_win32_keyb", "button_right"},                /* next category */
        /* full-screen PC movie (keyboard: as shipped) */
        {"coopui_pageDown", "button_pageDown", "button_target_mode"},       /* previous item */
        {"coopui_pageUp", "button_pageUp", "button_throw"},                 /* next item */
        {"coopui_prev_category", "prev_ribbon_category", "button_left"},
        {"coopui_next_category", "next_ribbon_category", "button_right"},
        {"coopui_itemkey1", "_cbi_win32_key1", "SharedText_Empty"},        /* keys 1-9 under the items */
        {"coopui_itemkey2", "_cbi_win32_key2", "SharedText_Empty"},
        {"coopui_itemkey3", "_cbi_win32_key3", "SharedText_Empty"},
        {"coopui_itemkey4", "_cbi_win32_key4", "SharedText_Empty"},
        {"coopui_itemkey5", "_cbi_win32_key5", "SharedText_Empty"},
        {"coopui_itemkey6", "_cbi_win32_key6", "SharedText_Empty"},
        {"coopui_itemkey7", "_cbi_win32_key7", "SharedText_Empty"},
        {"coopui_itemkey8", "_cbi_win32_key8", "SharedText_Empty"},
        {"coopui_itemkey9", "_cbi_win32_key9", "SharedText_Empty"},
        /* full-screen placement movie (BuildingRibbon_win32): arrows and on-screen button prompts */
        {"coopui_bld_prev", "_cbi_win32_keyz", "_cbi_xbox360_ltrigger"},          /* previous item */
        {"coopui_bld_next", "_cbi_win32_keyx", "_cbi_xbox360_rtrigger"},          /* next item */
        {"coopui_bld_lotl", "_cbi_win32_keya", "_cbi_xbox360_lstick_l"},          /* previous lot */
        {"coopui_bld_lotr", "_cbi_win32_keyd", "_cbi_xbox360_lstick_r"},          /* next lot */
        {"coopui_bld_placeobj", "_cbi_win32_keyenter", "_cbi_xbox360_button_a"},  /* place */
        {"coopui_bld_rotl", "_cbi_win32_keyq", "_cbi_xbox360_dpad_l"},            /* rotate left */
        {"coopui_bld_rotr", "_cbi_win32_keye", "_cbi_xbox360_dpad_r"},            /* rotate right */
        {"coopui_bld_cancel", "_cbi_win32_keyesc", "_cbi_xbox360_button_b"},      /* close */
        /* console Toy Box ribbon (Infinitorium_V; also uses coopui_target_mode / throw / left / right above) and
           spark menu (ModeSelect): worded legends keep their (localised) text, with the key image swapped for
           the key the console editor really uses on the keyboard */
        {"coopui_ChangeCategoryLeft", "Legend_ChangeCategoryLeft", "Legend_ChangeCategoryLeft", "cbi_keyZ", "cbi_keyV"},
        {"coopui_ChangeCategoryRight", "Legend_ChangeCategoryRight", "Legend_ChangeCategoryRight", "cbi_keyX", "cbi_keyB"},
        {"coopui_Place_Spark", "Legend_Place_Spark", "Legend_Place_Spark", "cbi_keyE", "cbi_keyG"},
        {"coopui_Advanced", "Legend_Advanced", "Legend_Advanced", "cbi_keyE", "cbi_keyF"},
        {"coopui_Easy", "Legend_Easy", "Legend_Easy", "cbi_keyE", "cbi_keyF"},
        {"coopui_Place_Exit", "Legend_Place_Exit", "Legend_Place_Exit", "cbi_keyEsc", "cbi_keyTab"},
        /* spark menu keys off W/A/S/D, which move the spark (controls_ui.py SPARK_MOVE_KEYS) */
        {"coopui_sparkedit", "_cbi_win32_keyenter", "menu_button_main"},             /* A / Enter: edit */
        {"coopui_spark_delete_key", "_cbi_win32_keybackspace", "menu_button_back-cancel"}, /* B / Backspace: delete */
        {"coopui_sparkcustom", "_cbi_win32_keyc", "menu_button_extra1"},             /* Y / C: customise */
        {"coopui_sparklogic_", "_cbi_win32_keye", "_cbi_xbox360_button_x"},          /* X / E: logic (pad table: B) */
        {"coopui_Spark_Exit", "Legend_Spark_Exit", "Legend_Spark_Exit", "cbi_keyTab", "cbi_keyEsc"},
    };
    if (!*id || !starts_with(*id, "coopui_"))
        return orig_text_lookup(key, id, id_sfx, has_sfx, a5);
    for (u32 i = 0; i < sizeof(labels) / sizeof(labels[0]); i++) {
        if (game_stricmp(*id, labels[i][0]) == 0) {
            u8 *in = G_INPUT_DRIVER;
            int pad = in && DRV_GAMEPAD_MODE(in);
            const char *s = labels[i][pad ? 2 : 1];
            const char *text = orig_text_lookup(key, &s, &s, 0, a5);
            return pad || !labels[i][3] ? text : swap_key_image(text, labels[i][3], labels[i][4]);
        }
    }
    return orig_text_lookup(key, id, id_sfx, has_sfx, a5);
}
