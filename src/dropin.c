/* Hooks for joining and leaving: the drop-in poll (hold START to join; player 2 leaving), pads plugged in or
   unplugged, and no pause during the join hold. */

/* ---------------------------------------------------------------- hook: drop-in poll */
static int g_announced;
static int g_last_local = -1, g_last_views = -1;

EXPORT int THISCALL coop_poll_hook(void *loop)
{
    int ret = orig_poll_dropin(loop);
    u8 *in = G_INPUT_DRIVER;
    u8 *pm = G_GAME_PLAYERS;

    if (!g_announced) {
        g_announced = 1;
        coop_log("coop patch v6.35 active");
    }
    if (!in || !pm)
        return ret;
    if ((int)GP_NUM_LOCAL(pm) != g_last_local || G_NUM_VIEWS != g_last_views) {
        g_last_local = (int)GP_NUM_LOCAL(pm);
        g_last_views = G_NUM_VIEWS;
        coop_log("local players=%d views=%d", g_last_local, g_last_views);
    }

    /* track the player-2 pad */
    if (g_p2_pad) {
        if (G_IGP) {
            /* slot 1 is filled by us, not by a figure-first drop-in: no "press START to join" prompt */
            IGP_P2_FIGURE_NEW(G_IGP) = 0;
            /* until player 2's figure is applied, keep the IGP from opening the Virtual Reader for them */
            if (g_p2_figure && IGP_SLOT_APPLIED(G_IGP, BASE_PAD_P2) != g_p2_figure &&
                k32_GetTickCount() - g_p2_tick < VR_HOLD_MS)
                IGP_VR_COOLDOWN(G_IGP, BASE_PAD_P2) = G_GAME_TIME + 10.0f;
        }
        if (GP_NUM_LOCAL(pm) >= 2) {
            if (!g_p2_joined) {
                g_p2_joined = 1;
                coop_log("player 2 joined on pad %d", device_index(in, g_p2_pad));
            }
            if (g_p2_lost == 1 && G_FRONTEND_LAYER)
                drop_lost_p2(pm);
            else if (!g_p2_lost && is_known_device(in, g_p2_pad))
                unlink_pad(in, g_p2_pad, 0);   /* re-assert after a controller hot-plug relink */
            if (G_IGP) {
                static int s_fig = -1, s_applied = -1;
                if (IGP_SLOT_FIGURE(G_IGP, BASE_PAD_P2) != s_fig || IGP_SLOT_APPLIED(G_IGP, BASE_PAD_P2) != s_applied) {
                    s_fig = IGP_SLOT_FIGURE(G_IGP, BASE_PAD_P2);
                    s_applied = IGP_SLOT_APPLIED(G_IGP, BASE_PAD_P2);
                    coop_log("  Base slot 1: figure=%d applied=%d", s_fig, s_applied);
                }
            }
        } else if (g_p2_joined) {
            release_p2_pad(in, pm, "player 2 left");
        } else if (k32_GetTickCount() - g_p2_tick > JOIN_TIMEOUT_MS) {
            release_p2_pad(in, pm, "join did not complete");
        }
    }

    /* Join: START held for JOIN_HOLD_MS on a pad nobody is bound to. A tap is player 1's pause (the
       game pauses on the release), and so is any START on another pad while a pad is player 2's. */
    if (g_join_hold && !(is_known_device(in, g_join_hold) && dev_button(g_join_hold, DEV_DOWN, BUTTON_START)))
        g_join_hold = 0;
    int n = in_call0(in, IN_NUM_DEVICES);
    for (int i = 0; i < n && i < DRV_MAX_DEVICES; i++) {
        u8 *dev = g_p2_pad ? 0 : joinable_pad(in, i);
        if (!dev || !dev_button(dev, DEV_DOWN, BUTTON_START) || in_is_bound(in, i) ||
            (G_FRONTEND_GATE && is_frontend_zone())) {
            g_start_down[i] = 0;
            continue;
        }
        u32 now = k32_GetTickCount();
        if (!g_start_down[i]) {
            if (dev_button(dev, DEV_PRESSED, BUTTON_START))
                g_start_down[i] = now | 1;
        } else if (!g_join_hold && now - g_start_down[i] >= JOIN_HOLD_MS) {
            g_join_hold = dev;
            try_join(loop, in, pm, i, dev);
        }
    }
    return ret;
}

/* ---------------------------------------------------------------- hook: controller plugged in / unplugged */
/* Once a second the input driver checks for pads that came or went (InputDriver_HotPlugCheck). An unplugged
   pad's device is freed, the devices after it move down one index and the keyboard goes last
   (InputDriver_CompactDevices), and all are cross-linked again, but the slot -> device index table (driver
   +0x464) is not updated. Player 1 is always on device 0 (Virtual_Controller), which never moves. Player 2's
   slot was left naming another device (nothing happens) or an empty index, which crashes:
   ButtonWatcher_Evaluate (0xF237C0) uses the device unchecked. So right after each change, before any mapper
   reads its device again:
   - player 2's pad still here: their slot follows it, and it is unlinked from player 1 again;
   - player 2's pad gone: their slot is unbound (their mapper then gets the first free device,
     InputDriver_GetDeviceForSlot) and the poll drops them out (drop_lost_p2);
   - no pad left for player 1: keyboard and mouse prompts at once (otherwise only a key or mouse move does it).
   The game's own disconnect watcher (FrontEnd_ControllerDisconnectWatch) sends a pause that the game loop
   ignores, as on the 360. */
static int p1_has_pad(u8 *in)
{
    for (int i = 0; i < DRV_MAX_DEVICES; i++) {
        u8 *dev = DRV_DEVICE(in, i);
        if (dev && dev != g_p2_pad &&
            game_stricmp(((const char *(THISCALL *)(void *))VFN(dev, DEV_TYPE_NAME))(dev), "XInput") == 0)
            return 1;
    }
    return 0;
}

static void devices_changed(u8 *in)
{
    u8 *pm = G_GAME_PLAYERS;
    coop_log("controllers changed: %d devices", in_call0(in, IN_NUM_DEVICES));
    if (g_p2_pad && !g_p2_lost && pm) {
        int idx = device_index(in, g_p2_pad), slot = p2_player(pm);
        int in_game = GP_NUM_LOCAL(pm) >= 2;
        if (idx < 0) {
            g_p2_lost = 1;
            coop_log("  player 2's pad was unplugged");
            if (in_game && in_slot_bound(in, slot)) {
                in_call1(in, IN_UNBIND_SLOT, slot);
                coop_log("  unbound input slot %d", slot);
            }
        } else {
            unlink_pad(in, g_p2_pad, 0);
            if (in_game && in_call1(in, IN_DEVICE_OF_SLOT, slot) != idx) {
                in_call1(in, IN_UNBIND_SLOT, slot);
                ((int (THISCALL *)(void *, int, int))VFN(in, IN_BIND_SLOT))(in, slot, idx);
                coop_log("  player 2's pad is now device %d; input slot %d follows it", idx, slot);
            }
        }
    }
    if (DRV_GAMEPAD_MODE(in) && !p1_has_pad(in)) {
        DRV_GAMEPAD_MODE(in) = 0;
        coop_log("  no pad left for player 1: keyboard and mouse");
    }
}

/* WindowsSystemInputDriver vtable +0x4: the driver's update (hot-plug check, device and key states) */
EXPORT int THISCALL coop_input_update_hook(u8 *in)
{
    u32 gen = DRV_GENERATION(in);
    u8 pad_mode = DRV_GAMEPAD_MODE(in);
    int r = orig_input_update(in);
    if (DRV_GENERATION(in) != gen)
        devices_changed(in);
    /* "last input was a pad" (player 1's prompts and menus) is taken from device 1 only, which is player 2's
       pad when player 1 is on the keyboard or their pad was unplugged */
    if (!pad_mode && DRV_GAMEPAD_MODE(in) && g_p2_joined && !g_p2_lost && DRV_DEVICE(in, 1) == g_p2_pad)
        DRV_GAMEPAD_MODE(in) = 0;
    return r;
}

/* ---------------------------------------------------------------- hook: pause action */
/* ActionPauseMenu@AiAvatarCtrlBot fires when a mapper sees START go up (PauseMenuUI, a Filter on MENU):
   for player 1 from *any* linked device, since player 1 is bound to device 0 (Virtual_Controller)
   whatever they started with and every pad drives them through the links; for player 2 from their pad.
   So a tap on any pad but player 2's is player 1's pause. No pause while a join hold lasts: detaching
   the held pad looks like START going up to player 1's mapper, the release reaches player 2's (joined)
   or player 1's (join refused, the pad is still linked). */
EXPORT u8 THISCALL coop_pause_action_hook(void *action, int a2, int a3, int a4)
{
    if (g_join_hold) {
        coop_log("pause during the join hold on pad %d ignored", device_index(G_INPUT_DRIVER, g_join_hold));
        return 1;
    }
    return orig_pause_action(action, a2, a3, a4);
}
