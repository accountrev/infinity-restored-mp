/* Player 2: their pad, unlinked from player 1 while they play, the virtual figure their character is built
   from, the join request and the drop-out when their pad is unplugged. The hooks that use these are in
   dropin.c and characters.c. */

/* ---------------------------------------------------------------- device helpers */
/* A gamepad that could become player 2: connected, not the keyboard. */
static u8 *joinable_pad(u8 *in, int i)
{
    u8 *dev = (u8 *)((void *(THISCALL *)(void *, int))VFN(in, IN_GET_DEVICE))(in, i);
    if (!dev || !((u8 (THISCALL *)(void *))VFN(dev, DEV_CONNECTED))(dev))
        return 0;
    const char *type = ((const char *(THISCALL *)(void *))VFN(dev, DEV_TYPE_NAME))(dev);
    if (!type || game_stricmp(type, "Keyboard") == 0)
        return 0;
    return dev;
}

static int device_index(u8 *in, u8 *dev)
{
    for (int i = 0; i < DRV_MAX_DEVICES; i++)
        if (DRV_DEVICE(in, i) == dev) return i;
    return -1;
}

static int is_known_device(u8 *in, u8 *dev)
{
    return dev && (device_index(in, dev) >= 0 || DRV_EXTRA(in) == dev);
}

/* ---------------------------------------------------------------- player-2 pad link state */
/* While a pad belongs to player 2 it is removed from every other device's sub-device list (so it
   stops driving player 1) and its own list is emptied (so player 1's devices don't drive it).
   What was removed is recorded so it can be put back when player 2 leaves. */
static u8 *g_p2_pad;              /* device object of the joining / joined pad, 0 = none */
static int g_p2_joined;           /* numLocal reached 2 */
static int g_p2_lost;             /* the pad was unplugged (its device is freed): 1, then 2 once the drop-out is asked */
static u32 g_p2_tick;             /* when the join was requested */
static u8 *g_removed_from[16];    /* devices whose list contained the pad (one entry per occurrence) */
static int g_removed_n;
static u8 *g_own_list[16];        /* the pad's own sub-device list */
static int g_own_n;

static int list_remove(u8 *owner, u8 *victim)
{
    u8 **data = SUB_DATA(owner);
    u32 n = SUB_COUNT(owner), w = 0;
    int removed = 0;
    if (!data) return 0;
    for (u32 r = 0; r < n; r++) {
        if (data[r] == victim) { removed++; continue; }
        data[w++] = data[r];
    }
    SUB_COUNT(owner) = w;
    return removed;
}

static void unlink_pad(u8 *in, u8 *pad, int record)
{
    u8 *devs[DRV_MAX_DEVICES + 1];
    int nd = 0;
    for (int i = 0; i < DRV_MAX_DEVICES; i++)
        if (DRV_DEVICE(in, i)) devs[nd++] = DRV_DEVICE(in, i);
    if (DRV_EXTRA(in) && device_index(in, DRV_EXTRA(in)) < 0) devs[nd++] = DRV_EXTRA(in);

    /* a fresh record per join: a pad that was unplugged while joined is never relinked */
    if (record)
        g_removed_n = g_own_n = 0;
    for (int i = 0; i < nd; i++) {
        if (devs[i] == pad) continue;
        int n = list_remove(devs[i], pad);
        while (record && n-- > 0 && g_removed_n < 16)
            g_removed_from[g_removed_n++] = devs[i];
    }
    if (record) {
        for (u32 i = 0; i < SUB_COUNT(pad) && g_own_n < 16; i++)
            g_own_list[g_own_n++] = SUB_DATA(pad)[i];
    }
    SUB_COUNT(pad) = 0;
}

static void relink_pad(u8 *in, u8 *pad)
{
    for (int i = 0; i < g_removed_n; i++) {
        u8 *d = g_removed_from[i];
        if (is_known_device(in, d) && SUB_DATA(d) && SUB_COUNT(d) < SUB_CAP(d))
            SUB_DATA(d)[SUB_COUNT(d)++] = pad;
    }
    if (SUB_COUNT(pad) == 0 && SUB_DATA(pad)) {
        for (int i = 0; i < g_own_n && SUB_COUNT(pad) < SUB_CAP(pad); i++)
            if (is_known_device(in, g_own_list[i]))
                SUB_DATA(pad)[SUB_COUNT(pad)++] = g_own_list[i];
    }
    g_removed_n = g_own_n = 0;
}

/* ---------------------------------------------------------------- player-2 figure (Base pad 1) */
/* On the 360 player 2's character comes from the figure on the Base's right circle (pad 1). The
   IGP builds a player's avatar from their slot's figure and only then enables the player; with an
   empty slot 1 player 2 stays disabled ("infinitely loading"), and after 15 s the PC opens the
   Virtual Reader for them. So player 2 gets a virtual figure on pad 1, like player 1 has on pad 0. */
static int g_p2_figure;        /* tag id currently on pad 1 (0 = none) */
static int g_p2_last_figure;   /* player 2's figure when they last left (0 = none) */

static const char *const k_p2_fallback[] = {
    "AV_MrIncredible", "AV_ElastiGirl", "AV_Buzz", "AV_Woody", "AV_McQueen", "AV_Mater",
    "MU_Sully", "MU_Mike", "PIR_JackSparrow", "PIR_Barbossa", "LR_LoneRanger", "LR_Tonto",
};

static int p1_figure(void)
{
    u8 *igp = G_IGP;
    int f = igp ? IGP_SLOT_FIGURE(igp, 0) : 0;
    return f ? f : G_VR_FIGURE;
}

/* Avatar templates are per zone: Play Sets set avatarSuffix "_PS", so their characters are
   "AV_ElastiGirl_PS" etc. The game's avatar rules (GamePlayersBase_GetAvatarForPlayer) already return the
   suffixed name, and a bare figure name has no template there: the new player's entity can't be created and
   the game drops the join in the same frame ("A player has joined the game." and nothing else). */
static const char *zone_avatar_suffix(void)
{
    const char *s = G_ZONE_INFO ? zone_string(G_ZONE_INFO, "avatarSuffix", *(u32 *)(G_ZONE_INFO + 0x154), 0, 0) : 0;
    return s ? s : "";
}

static u32 str_len(const char *s)
{
    u32 n = 0;
    while (s[n]) n++;
    return n;
}

/* figure id for an avatar template name: the name itself, or the name without the zone's suffix */
static int figure_for_avatar(const char *avatar)
{
    int id = figure_id_for_name(G_GATEWAY, avatar);
    const char *suffix = zone_avatar_suffix();
    u32 n = str_len(avatar), m = str_len(suffix);
    if (id || !m || n <= m || n - m >= 64)
        return id;
    for (u32 i = 0; i < m; i++)
        if (avatar[n - m + i] != suffix[i])
            return 0;
    char base[64];
    for (u32 i = 0; i < n - m; i++)
        base[i] = avatar[i];
    base[n - m] = 0;
    return figure_id_for_name(G_GATEWAY, base);
}

/* figure id for an avatar (game string) if player 2 may use it here: the zone has its template, and
   its figure is known, not player 1's, and valid for the level */
static int usable_p2_avatar(GameString *avatar)
{
    const char *name = avatar->s;
    if (!name || !*name || !G_GATEWAY || !G_TEMPLATES || !template_exists(G_TEMPLATES, avatar))
        return 0;
    int id = figure_for_avatar(name);
    if (!id || id == p1_figure())
        return 0;
    if (G_IGP && !figure_valid_for_slot(G_IGP, BASE_PAD_P2, id))
        return 0;
    return id;
}

static void place_p2_figure(int id)
{
    if (!G_GATEWAY || id == g_p2_figure)
        return;
    if (g_p2_figure)
        gw_remove_tag(G_GATEWAY, g_p2_figure, 0);
    gw_add_tag(G_GATEWAY, id, 0, id, BASE_PAD_P2, 0, 0, 0, 0, 0);
    g_p2_figure = id;
}

static void remove_p2_figure(void)
{
    if (g_p2_figure && G_GATEWAY) {
        gw_remove_tag(G_GATEWAY, g_p2_figure, 0);
        coop_log("  removed player 2's figure %d from Base pad 1", g_p2_figure);
    }
    g_p2_figure = 0;
    if (G_IGP)
        IGP_P2_FIGURE_NEW(G_IGP) = 0;
}

/* Player 2's character: the first usable of player 2's figure from before they left, the base rules
   (AvatarTypeForPlayerId<N> / zone DefaultAvatar<N+1>), the zone's DefaultAvatar, then a fixed list.
   On success the avatar (template name, with the zone's suffix) is left in the game string *out and the
   figure id is returned; on failure *out is not constructed.
   On the 360 a drop-out leaves player 2's figure on the Base (the IGP's drop-out handler only resets the
   slot's applied figure), so they come back as the same character; here the virtual figure is taken off
   pad 1 when they leave and put back when they rejoin. */
static int choose_p2_figure(void *pm, GameString *out, int idx)
{
    if (g_p2_last_figure && G_GATEWAY) {
        figure_name(G_GATEWAY, out, g_p2_last_figure);
        apply_avatar_suffix(out);
        int id = usable_p2_avatar(out);
        if (id)
            return id;
        string_release(out);
    }
    for (int k = 0; k < 2; k++) {
        avatar_base(pm, out, k == 0 ? idx : 0);   /* already suffixed for the zone */
        int id = usable_p2_avatar(out);
        if (id)
            return id;
        string_release(out);
    }
    for (u32 k = 0; k < sizeof(k_p2_fallback) / sizeof(k_p2_fallback[0]); k++) {
        string_from_cstr(out, k_p2_fallback[k]);
        apply_avatar_suffix(out);
        int id = usable_p2_avatar(out);
        if (id)
            return id;
        string_release(out);
    }
    return 0;
}

static int parse_int(const char *s)
{
    int v = 0;
    while (s && *s >= '0' && *s <= '9')
        v = v * 10 + (*s++ - '0');
    return v;
}

/* Player 2 left (or the join failed): give the pad back to player 1. */
static void release_p2_pad(u8 *in, u8 *pm, const char *why)
{
    u8 *pad = g_p2_pad;
    int idx = g_p2_lost ? -1 : device_index(in, pad);   /* an unplugged pad's slot was unbound when it went */
    coop_log("%s: returning pad %d to player 1", why, idx);
    if (idx >= 0 && in_is_bound(in, idx)) {
        int slot = in_call1(in, IN_SLOT_OF_DEVICE, idx);
        /* the PC's RemoveLocalPlayer no longer releases the pad (the 360's did) */
        if (slot >= 0 && slot != get_primary_local(pm)) {
            in_call1(in, IN_UNBIND_SLOT, slot);
            coop_log("  unbound input slot %d", slot);
        }
    }
    if (idx >= 0)
        relink_pad(in, pad);
    if (g_p2_joined && g_p2_figure)
        g_p2_last_figure = g_p2_figure;
    remove_p2_figure();
    g_p2_pad = 0;
    g_p2_joined = 0;
    g_p2_lost = 0;
}

/* Mirrors GamePlayers::CanDropIn's inputs so a refusal can be explained in the log. */
static void log_dropin_state(u8 *pm)
{
    int session_block = 0;
    u8 *sm = G_SESSION_MGR;
    if (sm) {
        u8 *s = *(u8 **)(sm + 0x14);
        if (s) {
            u8 *proxy = *(u8 **)(s + 0xF4);
            if (proxy && *(u32 *)(proxy + 0x94) == 0) session_block = 1;
        }
    }
    int ui_free = -1;
    if (G_FRONTEND_LAYER)
        ui_free = ((u8 (THISCALL *)(void *))VFN(G_FRONTEND_LAYER, FE_NO_BLOCKING_UI))(G_FRONTEND_LAYER);
    coop_log("  state: local=%u/%d players=%u enabled=%u lock=%d uiFree=%d session=%d blockA3=%u blockA4=%u views=%d",
             GP_NUM_LOCAL(pm), get_max_local(), GP_NUM_PLAYERS(pm), GP_DROPIN_ENABLED(pm),
             G_DROPIN_LOCK != 0, ui_free, session_block, GP_BLOCK_A3(pm), GP_BLOCK_A4(pm), G_NUM_VIEWS);
}

/* ---------------------------------------------------------------- join */
static u32 g_start_down[DRV_MAX_DEVICES];  /* when START went down on an unbound pad (0 = not held) */
static u8 *g_join_hold;                      /* pad whose START hold asked to join, until its START is up */

static void try_join(void *loop, u8 *in, u8 *pm, int pad, u8 *dev)
{
    coop_log("START held on unbound pad %d", pad);
    if ((int)GP_NUM_LOCAL(pm) >= get_max_local()) {
        coop_log("  refused: local session full");
        return;
    }
    /* On the 360 the Base arms drop-in when a figure is on the P2 circle; the PC's virtual
       reader never uses that pad, so arm it here (Adventures stay excluded, as on the 360). */
    if (dropin_allowed_level())
        GP_DROPIN_ENABLED(pm) = 1;
    else
        coop_log("  note: drop-in not allowed in this level (Adventure)");

    if (!can_drop_in(pm, 1)) {
        coop_log("  refused: CanDropIn=0");
        log_dropin_state(pm);
        return;
    }

    unlink_pad(in, dev, 1);
    g_p2_pad = dev;
    g_p2_joined = 0;
    g_p2_tick = k32_GetTickCount();
    coop_log("  pad %d detached from player 1", pad);

    /* Player 2's figure goes on Base pad 1 now, before player 2 exists: the IGP opens the Virtual
       Reader (which pauses that player) for a new player whose slot is empty, in the same frame. */
    GameString name;
    int id = choose_p2_figure(pm, &name, get_primary_local(pm) == 0 ? 1 : 0);
    if (id) {
        place_p2_figure(id);
        if (G_IGP)
            IGP_P2_FIGURE_NEW(G_IGP) = 0;
        coop_log("  placed player 2's figure %s (%d) on Base pad 1", name.s, id);
        string_release(&name);
    } else {
        coop_log("  no usable figure for player 2; the Virtual Reader should open for them");
    }
    coop_log("  requesting join");

    /* The PC join handler forwards this->pendingJoinPad (+0x368) instead of its argument. */
    LOOP_PENDING_JOIN_PAD(loop) = pad;
    ((int (THISCALL *)(void *, int))VFN(loop, LOOP_JOIN_REQUEST))(loop, pad);
}

/* ---------------------------------------------------------------- player 2's pad unplugged */
/* the local player who isn't the primary one: player 2 (input slot = player index) */
static int p2_player(u8 *pm)
{
    return get_primary_local(pm) == 0 ? 1 : 0;
}

/* Player 2's pad was unplugged (coop_input_update_hook): drop them out the way their pause menu's Drop Out
   does (PauseMenu:CleanupOnCancel unpauses, then Lua RemovePlayer -> GameFrontEndLayer +0xB8).
   - Unpause first: the per-player pause flag (0x17573F8 + player) is only cleared by an unpause, so a player
     dropped while paused would come back frozen on their next join.
   - Hold off the Virtual Base: the drop-out resets Base slot 1's applied figure while player 2 is still in,
     and the IGP then opens the Virtual Base for them once the slot's cooldown has passed, pausing player 1
     too. The cooldown is pushed back, as during a join. */
static void drop_lost_p2(u8 *pm)
{
    int p = p2_player(pm);
    coop_log("player 2's pad is gone: dropping player %d out", p);
    if (G_IGP)
        IGP_VR_COOLDOWN(G_IGP, BASE_PAD_P2) = G_GAME_TIME + 10.0f;
    unpause_if_paused(p);
    ((void (THISCALL *)(void *, int))VFN(G_FRONTEND_LAYER, FE_PLAYER_DROPOUT))(G_FRONTEND_LAYER, p);
    g_p2_lost = 2;
}
