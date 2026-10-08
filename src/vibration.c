/* The game vibrates a player's bound device. Player 1's is device 0, the virtual controller
   (iOSControllerInputDriver), whose vibration methods do nothing, so player 1's pads never vibrated.
   Its vtable's vibration methods pass the call on to the devices linked into it: player 1's pads
   (player 2's is unlinked while they're in; the keyboard's methods do nothing). Not while vibration
   is off for device 0 (its settings flag, as on a pad). */
#define DEV_VIBRATION_ON(d) (*(u8 *)((d) + 0x261))
#define DEV_VIBRATE      0x6C   /* (XINPUT_VIBRATION packed in a u32, ?) */
#define DEV_VIBRATE_FOR  0x70   /* (duration, vibration, ?) */
#define DEV_STOP_VIBRATE 0x74   /* (?) */

static int g_vibration_logged;

static void note_vibration(u8 passed)
{
    if (passed && !g_vibration_logged) {
        g_vibration_logged = 1;
        coop_log("player 1 vibration passed to their pads");
    }
}

EXPORT u8 THISCALL coop_vibrate_hook(u8 *dev, u32 vib, int a3)
{
    u8 r = 0;
    if (!DEV_VIBRATION_ON(dev) && vib)
        return 0;
    for (u32 i = 0; i < SUB_COUNT(dev); i++) {
        u8 *sub = SUB_DATA(dev)[i];
        r |= ((u8 (THISCALL *)(void *, u32, int))VFN(sub, DEV_VIBRATE))(sub, vib, a3);
    }
    note_vibration(r);
    return r;
}

EXPORT u8 THISCALL coop_vibrate_for_hook(u8 *dev, int duration, u32 vib, int a3)
{
    u8 r = 0;
    if (!DEV_VIBRATION_ON(dev) && vib)
        return 0;
    for (u32 i = 0; i < SUB_COUNT(dev); i++) {
        u8 *sub = SUB_DATA(dev)[i];
        r |= ((u8 (THISCALL *)(void *, int, u32, int))VFN(sub, DEV_VIBRATE_FOR))(sub, duration, vib, a3);
    }
    note_vibration(r);
    return r;
}

EXPORT u8 THISCALL coop_stop_vibrate_hook(u8 *dev, int a2)
{
    u8 r = 0;
    for (u32 i = 0; i < SUB_COUNT(dev); i++) {
        u8 *sub = SUB_DATA(dev)[i];
        r |= ((u8 (THISCALL *)(void *, int))VFN(sub, DEV_STOP_VIBRATE))(sub, a2);
    }
    return r;
}
