/* The PC reads the keyboard and mouse globally, not through a device, in code that runs once per
   player: the KeyWatcher/PointerWatcher input bindings (every ControlMapper's actions: jump,
   attack, pause, menu navigation...), the avatar input component (WASD/arrow movement) and the
   Flash screen input (key events to each player's screens). While player 2 is in, those see no
   keyboard/mouse for player 2. The keyboard can't be player 2's device. */
#define MAPPER_DEVICE(m) (*(u8 **)((m) + 12))

static int g_block_keys;   /* set while player 2's avatar input component runs */

static int is_p2_player(int p)
{
    u8 *pm = G_GAME_PLAYERS;
    return g_p2_joined && pm && p >= 0 && p != get_primary_local(pm);
}

static int is_p2_mapper(u8 *mapper)
{
    return g_p2_joined && mapper && MAPPER_DEVICE(mapper) == g_p2_pad;
}

/* Watcher::Evaluate(out {u8 value; float amount}, dt, mapper) */
EXPORT void *THISCALL coop_key_watcher_hook(void *w, u8 *out, u32 dt, u8 *mapper)
{
    if (is_p2_mapper(mapper)) {
        out[0] = 0;
        *(u32 *)(out + 4) = 0;
        return out;
    }
    return orig_key_watcher(w, out, dt, mapper);
}

EXPORT void *THISCALL coop_pointer_watcher_hook(void *w, u8 *out, u32 dt, u8 *mapper)
{
    if (is_p2_mapper(mapper)) {
        out[0] = 1;             /* same as "no pointer": valid, no movement */
        *(u32 *)(out + 4) = 0;
        return out;
    }
    return orig_pointer_watcher(w, out, dt, mapper);
}

/* per-avatar input component update: comp -> avatar entity at +0. Runs for every avatar every frame,
   so the avatar's player is only looked up while player 2 is in. */
EXPORT int CDECL coop_avatar_input_hook(u8 *comp, u32 dt)
{
    u8 *pm = G_GAME_PLAYERS;
    g_block_keys = g_p2_joined && pm && is_p2_player(player_of_avatar(pm, *(u32 *)comp));
    int r = orig_avatar_input(comp, dt);
    g_block_keys = 0;
    return r;
}

/* WindowsSystemInputDriver key state queries: nothing pressed while player 2's avatar input runs */
#define KEY_HOOK(name, orig)                                        \
    EXPORT u8 THISCALL name(void *drv, int key)                     \
    {                                                               \
        return g_block_keys ? 0 : orig(drv, key);                   \
    }
KEY_HOOK(coop_key_pressed_hook, orig_key_pressed)
KEY_HOOK(coop_key_released_hook, orig_key_released)
KEY_HOOK(coop_key_down_hook, orig_key_down)

/* Flash screen input (movie, mapping, ?, perPlayer, player, keyboard): no keyboard events for
   player 2's screens (their pad still works through the mapping). */
EXPORT u8 THISCALL coop_screen_input_hook(void *movie, void *map, int a3, int per_player, int player, int kbd)
{
    if ((u8)kbd && (u8)per_player && is_p2_player(player))
        kbd = 0;
    return orig_screen_input(movie, map, a3, per_player, player, kbd);
}

/* The Virtual Base for two players: the screen takes device-indexed input (playerBasedInput
   off), so its movie can't tell the players apart. While two local players are in, it gets its input per local
   player instead, as per-player screens do: key events carry the player number (controllerIdx), the movie gives
   the left half to the first local player and the right half to the other, and the keyboard stays player 1's.
   On the dispatcher's one-screen path (Flash_DispatchScreenInput, the call at 0x10439D9) edi still holds
   the screen from ScreenStackLayer_Update; the thunk passes it on. Screen +12: its name. */
#define SCREEN_NAME(s) (*(const char **)((u8 *)(s) + 12))

static int str_eq(const char *a, const char *b)
{
    while (*a && *a == *b)
        a++, b++;
    return *a == *b;
}

EXPORT u8 THISCALL coop_screen_input_one(void *movie, void *scr, void *map, int a3, int per_player, int player, int kbd)
{
    u8 *pm = G_GAME_PLAYERS;
    if (!(u8)per_player && g_p2_joined && pm && GP_NUM_LOCAL(pm) > 1 && SCREEN_NAME(scr) &&
        str_eq(SCREEN_NAME(scr), "VirtualReader")) {
        u8 r = 0;
        for (int p = 0; p < (int)GP_NUM_LOCAL(pm); p++)
            r |= coop_screen_input_hook(movie, map, a3, 1, p, kbd);
        return r;
    }
    return coop_screen_input_hook(movie, map, a3, per_player, player, kbd);
}

__asm__(".text\n"
        ".globl coop_screen_input_one_thunk\n"
        "coop_screen_input_one_thunk:\n"
        "    popl %eax\n"                  /* return address */
        "    pushl %edi\n"                 /* the screen: one more stack argument */
        "    pushl %eax\n"
        "    jmp coop_screen_input_one\n");
