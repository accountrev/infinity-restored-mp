/* The PC replaced the console building/customising UI with a touch/mouse one:
   - ScreenDefinition.SWF.WIN32 replaces the single-player movie (Customize_Touch, LogicSelect_Touch);
   - its UI control scheme (Controls_UI_Win32) binds the editor actions to keys only.
   For a player on a gamepad the console movie is used instead. The pad bindings for the editor actions are
   added to Controls_UI_Win32 itself (assets/excel/excel.zip) by recipes/control_tables/controls_ui.py.
   The Lua touch-editor path is left on: for the customise screens it matches the 360 scripts. */

/* the ScreenDefinition loader (0x1049DC0) looks this key up in ScreenDefinition.SWF; "WIN32" = stock */
__attribute__((used)) char coop_win32_swf_key[32] = "WIN32";
static int g_skip_ctrl_popup;      /* a console customise screen was just opened for a pad user */
static u32 g_skip_ctrl_popup_tick;

static void set_win32_key(const char *k)
{
    int i = 0;
    for (; k[i] && i < 31; i++) coop_win32_swf_key[i] = k[i];
    coop_win32_swf_key[i] = 0;
}

static int starts_with(const char *s, const char *prefix)
{
    while (*prefix)
        if (*s++ != *prefix++) return 0;
    return 1;
}

static int player_on_gamepad(int p)
{
    u8 *in = G_INPUT_DRIVER;
    if (p < 0) return 0;
    if (is_p2_player(p)) return 1;
    return in && DRV_GAMEPAD_MODE(in);
}

#define SCREEN_PLAYER(s)  (*(int *)((u8 *)(s) + 0x40))

/* unique screen names are the screen's name plus a number (VirtualReader9) */
static int is_screen(const char *unique_name, const char *name)
{
    if (!starts_with(unique_name, name))
        return 0;
    for (const char *p = unique_name + str_len(name); *p; p++)
        if (*p < '0' || *p > '9') return 0;
    return 1;
}

/* Play Set placement (PlaceBase): buildings on lots, decorations, pranks, train cars */
static int is_placement_screen(const char *unique_name)
{
    return is_screen(unique_name, "PlaceBldg") || is_screen(unique_name, "PlaceDeco") ||
           is_screen(unique_name, "PlacePrank") || is_screen(unique_name, "PlaceTrainCar");
}

/* replaces the call of the ScreenDefinition loader in UIScreen_Init (0x1051440) */
EXPORT int THISCALL coop_screen_def_hook(void *scr, void *def, const char *unique_name, int a4)
{
    int pad = player_on_gamepad(SCREEN_PLAYER(scr));
    set_win32_key(pad ? "WIN32_off_for_gamepad" : "WIN32");
    int r = orig_screen_def(scr, def, unique_name, a4);
    set_win32_key("WIN32");
    if (pad && (starts_with(unique_name, "Customize") || is_placement_screen(unique_name))) {
        g_skip_ctrl_popup = 1;
        g_skip_ctrl_popup_tick = k32_GetTickCount();
    }
    return r;
}

/* Lua IsControllerConnected() really returns "last input was a gamepad". CustomizeBase:onEnter and
   PlaceBase:onEnter (Play Sets) use it to show a "keyboard and mouse only" popup; skip that once for a
   pad user's customise or placement screen. */
EXPORT int STDCALL coop_lua_controller_connected(void *L)
{
    if (g_skip_ctrl_popup) {
        g_skip_ctrl_popup = 0;
        if (k32_GetTickCount() - g_skip_ctrl_popup_tick < 2000) {
            lua_pushboolean(L, 0);
            return 1;
        }
    }
    return orig_lua_controller_connected(L);
}

/* Customise screens select an item when its ribbon button sees the list's selectButtonKey. The
   movies' timelines set that to "CUST_APPLY", but the list (AvaList) only hands its key to buttons
   when it builds them, so buttons built earlier keep the default "OK" (61), which no customise
   screen requests: a pad's A (CUST_APPLY, 148) and the keyboard's Enter never select (a mouse click
   does). OK is added to every action list that has CUST_APPLY. A is UI_OK on PC, so either code
   selects; nothing else in these movies reacts to OK except the PC movie's focus controller, which
   selects too. GameControlMapperActiveActions vtable (0x13300E4) +0 = set actions (name list). */
static char g_action_list[1024];

static int list_has(const char *list, const char *word)
{
    for (const char *p = list; *p; ) {
        const char *w = word;
        while (*w && *p == *w) { p++; w++; }
        if (!*w && (*p == ',' || !*p))
            return 1;
        while (*p && *p != ',') p++;
        if (*p == ',') p++;
    }
    return 0;
}

/* Play Set placement in split screen (BuildingRibbon_V / _H, from the 360): same thing, the item list's
   selectButtonKey is "PLACE_BLDG_PLACE" but its buttons keep "OK", and the movie has no handler of its
   own for PLACE_BLDG_PLACE, so A did nothing. The full-screen PC movie (BuildingRibbon_win32, the only
   one that also asks for PLACE_BLDG_ROTATE_OBJ_LEFT) places on PLACE_BLDG_PLACE itself and blanks the
   list's key, so it is left alone: there OK would place twice. */
/* The console Toy Box ribbon (Infinitorium_V, from the 360) too: in its item ribbon mode A places only
   through the ribbon's buttons (iconRibbon.selectButtonKey = "RBN_TB_PLACE", set after they are built), so
   A did nothing there. Its ribbon action list is the one with RBN_TB_PREV_ITEM and RBN_TB_EASY_ADV_TOGGLE
   (the touch movie's has RBN_TB_DISMISS instead). In grid mode the ribbon is inactive and the movie places
   on RBN_TB_PLACE itself, ignoring OK, so OK can't place twice. */
static int wants_ok(const char *names)
{
    if (list_has(names, "OK"))
        return 0;
    return list_has(names, "CUST_APPLY") ||
           (list_has(names, "PLACE_BLDG_PLACE") && !list_has(names, "PLACE_BLDG_ROTATE_OBJ_LEFT")) ||
           (list_has(names, "RBN_TB_PLACE") && list_has(names, "RBN_TB_PREV_ITEM") &&
            list_has(names, "RBN_TB_EASY_ADV_TOGGLE") && !list_has(names, "RBN_TB_DISMISS"));
}

EXPORT int THISCALL coop_gcm_set_actions_hook(void *mapping, const char *names)
{
    if (names && wants_ok(names)) {
        u32 n = str_len(names);
        if (n + 4 < sizeof(g_action_list)) {
            for (u32 i = 0; i < n; i++) g_action_list[i] = names[i];
            g_action_list[n] = ','; g_action_list[n + 1] = 'O'; g_action_list[n + 2] = 'K'; g_action_list[n + 3] = 0;
            names = g_action_list;
        }
    }
    return orig_gcm_set_actions(mapping, names);
}
