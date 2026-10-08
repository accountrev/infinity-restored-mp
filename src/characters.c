/* Player 2's character: chosen when they join, changed from the Virtual Base, and reported to its script. */

/* ---------------------------------------------------------------- hook: new player's avatar */
/* The PC override returns the Virtual Reader's avatar (P1's character) for every player index.
   For anyone but the primary player use player 2's character (choose_p2_figure), the one whose
   figure try_join already put on Base pad 1. */
EXPORT GameString *THISCALL coop_avatar_hook(void *pm, GameString *out, int idx)
{
    int primary = get_primary_local(pm);
    if (primary >= 0 && idx != primary) {
        int id = choose_p2_figure(pm, out, idx);
        if (id) {
            if (g_p2_pad && id != g_p2_figure)
                place_p2_figure(id);
            coop_log("new player slot %d avatar: %s (figure %d)", idx, out->s, id);
            return out;
        }
        coop_log("new player slot %d: no usable figure found, using player 1's character", idx);
    }
    return avatar_orig(pm, out, idx);
}

/* ---------------------------------------------------------------- hook: Lua Players_ChangeAvatar */
/* The PC Virtual Reader ignores playerNum and always swaps the figure on Base pad 0 (player 1).
   While two local players are in, a pick by player 2 swaps *their* figure on pad 1 instead, and
   neither player may take the character the other one has (one figure per character). */
EXPORT int STDCALL coop_change_avatar_hook(void *L)
{
    u8 *pm = G_GAME_PLAYERS;
    if (pm && GP_NUM_LOCAL(pm) > 1) {
        int pn = lua_checkint(L, 1);
        const char *name = lua_checkstr(L, 2, 0);
        int sku = parse_int(lua_checkstr(L, 5, 0));
        if (pn != get_primary_local(pm)) {
            if (!sku) {
                coop_log("player 2 Virtual Reader pick %s has no figure id; ignored", name);
            } else if (sku == p1_figure()) {
                coop_log("player 2 picked %s, which player 1 is using; ignored", name);
            } else if (sku != g_p2_figure) {
                place_p2_figure(sku);
                coop_log("player 2 Virtual Reader pick: %s -> figure %d on Base pad 1", name, sku);
            }
            return 0;
        }
        if (sku && sku == g_p2_figure) {
            coop_log("player 1 picked %s, which player 2 is using; ignored", name);
            return 0;
        }
    }
    return change_avatar_orig(L);
}

/* ---------------------------------------------------------------- hook: Lua GetPlayerAvatarData */
/* GetPlayerAvatarData(player) gives the player's avatar name, sparks and Play Set. The name is the actor's
   (AV_Perry, AV_Mike), while the Virtual Base keys its characters by figure (PNF_Perry, MU_Mike; sku_id), so
   player 2's half didn't find their character and started on Mr. Incredible. A fourth value is added: the
   figure the player's character was built from (their Base slot's applied figure; slot 0 = the primary
   player), 0 if none. */
#define orig_player_avatar_data ((int (STDCALL *)(void *))0x00C3E2B0)
#define lua_pushinteger         ((void (CDECL *)(void *, int))0x004645A0)

EXPORT int STDCALL coop_player_avatar_data_hook(void *L)
{
    int n = orig_player_avatar_data(L);
    u8 *pm = G_GAME_PLAYERS;
    int p = lua_checkint(L, 1), figure = 0;
    if (pm && G_IGP && p >= 0)
        figure = IGP_SLOT_APPLIED(G_IGP, p == get_primary_local(pm) ? 0 : 1);
    lua_pushinteger(L, figure);
    return n + 1;
}
