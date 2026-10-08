/* The mouse cursor is player 1's. It has one state: mouse look (locked and re-centred every frame, driver
   +0x21E) or pointer (free). Everything sets it through the input driver (+0x44 lock, +0x48 free, +0x4C show /
   hide), whoever it is for: a pause (Pause_PausePlayer saves the state in G_SAVED_CURSOR and frees the cursor;
   the next Pause_UnPauseFromPausedScreen restores it), the screen scripts (UI_MousePointerMode on enter,
   UI_MouseCamMode on exit if they switched it) and the Toy Box editor (frees it on entering, locks it on
   leaving). With two players in, player 2's menus freed player 1's cursor in play, two pauses restored each
   other's saved state, and player 2 leaving a menu locked the cursor under player 1's pause menu.
   So the acting player is tracked, innermost first: a pause or unpause by its player, a screen's onEnter by
   the screen's, a UI layer's update (its screens' input, scripts and onExit) by its top screen's. While that
   is player 2, the driver's lock / free / show calls do nothing, their pause leaves G_SAVED_CURSOR alone, and
   UI_IsMousePointerMode answers "no" (so a script's remembered switch can't stop player 1's from locking
   again). While player 1 is paused nothing may lock the cursor (this covers locks with no known player). */
#define G_SAVED_CURSOR   (*(u8 *)0x017597D6)   /* cursor shown before the last pause; the next unpause restores it */
#define PLAYER_PAUSED(p) (*(u8 *)(0x017573F8 + (p)))
#define orig_pause_player     ((u8 (CDECL *)(int, int, int))0x01038630)
#define orig_unpause_player   ((u8 (CDECL *)(int))0x01038730)
#define orig_screen_on_enter  ((u8 (THISCALL *)(void *))0x01042DB0)
#define orig_leave_mouse_look ((int (THISCALL *)(void *))0x00493670)
#define orig_show_cursor      ((int (THISCALL *)(void *, int))0x00496560)
#define orig_lua_is_mouse_pointer_mode ((int (STDCALL *)(void *))0x00C32140)
#define orig_layer_update     ((int (THISCALL *)(void *))0x01050CC0)
#define orig_enter_mouse_look ((int (THISCALL *)(void *))0x00495750)

static int g_mouse_actor = -1;

/* the player of a ScreenStackLayer's top screen (layer +0x18: screen list, +0x1C: top node, node +8: screen) */
static int layer_player(void *layer)
{
    u8 *list = *(u8 **)((u8 *)layer + 0x18);
    u8 *node = list ? *(u8 **)(list + 0x1C) : 0;
    u8 *scr = node ? *(u8 **)(node + 8) : 0;
    return scr ? SCREEN_PLAYER(scr) : -1;
}

/* lock: the call would lock / hide the cursor (else free / show it) */
static int cursor_change_refused(int lock)
{
    u8 *pm = G_GAME_PLAYERS;
    if (!g_p2_joined || !pm)
        return 0;
    if (is_p2_player(g_mouse_actor))
        return 1;
    int p1 = get_primary_local(pm);
    return lock && p1 >= 0 && PLAYER_PAUSED(p1);
}

/* Flash::ScreenStackLayer vtable +0x8: a UI layer's update */
EXPORT int THISCALL coop_layer_update_hook(void *layer)
{
    int prev = g_mouse_actor;
    g_mouse_actor = layer_player(layer);   /* its screens' input, scripts and onExit run in here */
    int r = orig_layer_update(layer);
    g_mouse_actor = prev;
    return r;
}

/* WindowsSystemInputDriver vtable +0x44: enter mouse look (cursor re-centred every frame) */
EXPORT int THISCALL coop_mouse_look_hook(void *drv)
{
    return cursor_change_refused(1) ? 0 : orig_enter_mouse_look(drv);
}

/* WindowsSystemInputDriver vtable +0x48: leave mouse look; +0x4C: show (1) / hide (0) the cursor */
EXPORT int THISCALL coop_leave_mouse_look_hook(void *drv)
{
    return cursor_change_refused(0) ? 0 : orig_leave_mouse_look(drv);
}

EXPORT int THISCALL coop_show_cursor_hook(void *drv, int show)
{
    return cursor_change_refused(!(u8)show) ? 0 : orig_show_cursor(drv, show);
}

/* Pause_PausePlayer(player, ...) (two calls and Lua Pause_PauseGame) */
EXPORT u8 CDECL coop_pause_player_hook(int p, int a2, int a3)
{
    int prev = g_mouse_actor;
    u8 saved = G_SAVED_CURSOR;
    g_mouse_actor = p;
    u8 r = orig_pause_player(p, a2, a3);
    if (is_p2_player(p))
        G_SAVED_CURSOR = saved;
    g_mouse_actor = prev;
    return r;
}

/* Pause_UnPauseFromPausedScreen(player) (the tail jump of ...IfPaused and Lua) */
EXPORT u8 CDECL coop_unpause_player_hook(int p)
{
    int prev = g_mouse_actor;
    g_mouse_actor = p;
    u8 r = orig_unpause_player(p);
    g_mouse_actor = prev;
    return r;
}

/* a new screen's onEnter (UIScreen_Init) */
EXPORT u8 THISCALL coop_screen_enter_hook(void *scr)
{
    int prev = g_mouse_actor;
    g_mouse_actor = SCREEN_PLAYER(scr);
    u8 r = orig_screen_on_enter(scr);
    g_mouse_actor = prev;
    return r;
}

/* Lua UI_IsMousePointerMode */
EXPORT int STDCALL coop_lua_is_mouse_pointer_mode(void *L)
{
    if (is_p2_player(g_mouse_actor)) {
        lua_pushboolean(L, 0);
        return 1;
    }
    return orig_lua_is_mouse_pointer_mode(L);
}
