/* The game's types, data, functions and virtual-table offsets that the patch uses (the Steam exe; SHA-256 in
   coop.c). Names in comments like InputDriver_HotPlugCheck are the game's functions as named in the IDA
   database the patch was researched with; the address follows. */
#include <stdint.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

#define THISCALL __attribute__((thiscall))
#define STDCALL  __attribute__((stdcall))
#define CDECL    __attribute__((cdecl))
#define EXPORT   __attribute__((used, noinline))

#define VFN(obj, off) ((*(void ***)(obj))[(off) / 4])

/* the game's string: one pointer to ref-counted characters (string_from_cstr / string_release below) */
typedef struct { const char *s; } GameString;

/* ---------------------------------------------------------------- game data */
#define G_INPUT_DRIVER   (*(u8 **)0x0161D060)     /* WindowsSystemInputDriver* */
#define G_GAME_PLAYERS   (*(u8 **)0x0175766C)     /* GamePlayers* */
#define G_NUM_VIEWS      (*(int *)0x0175B3FC)
#define G_FRONTEND_GATE  (*(int *)0x01759820)     /* same gate as the original poller */
#define G_DROPIN_LOCK    (*(int *)0x017574E4)
#define G_SESSION_MGR    (*(u8 **)0x01758A94)
#define G_FRONTEND_LAYER (*(void **)0x0175984C)   /* GameFrontEndLayer* */
#define G_GATEWAY        (*(void **)0x0161B6C4)   /* Base/portal driver (virtual tags) */
#define G_IGP            (*(u8 **)0x016BCCF8)     /* in-game Base/figure manager */
#define G_VR_FIGURE      (*(int *)0x016BF8E8)     /* Virtual Reader's figure on pad 0 */
#define G_ZONE_INFO      (*(u8 **)0x01757674)     /* zone manager; +0x154: master zone handle (what zone property lookups take) */
#define G_TEMPLATES      (*(void **)0x016A7BE4)   /* entity template registry */

/* IGP fields: figure currently on a Base slot / figure the slot's avatar was built from */
#define IGP_SLOT_FIGURE(igp, s)  (*(int *)((igp) + 1588 + 4 * (s)))
#define IGP_SLOT_APPLIED(igp, s) (*(int *)((igp) + 1452 + 4 * (s)))
#define IGP_P2_FIGURE_NEW(igp)   (*(u8 *)((igp) + 1722))   /* "figure placed on P2 slot" -> join prompt */
#define IGP_VR_COOLDOWN(igp, s)  (*(float *)((igp) + 1892 + 4 * (s)))  /* no Virtual Reader auto-open before this game time */
#define G_GAME_TIME      (*(float *)0x0167DFA0)
#define BASE_PAD_P2 1   /* player 2's Base pad; pad 1 is also IGP slot 1 */

/* GamePlayers fields */
#define GP_NUM_PLAYERS(pm)    (*(u32 *)((pm) + 0x98))
#define GP_NUM_LOCAL(pm)      (*(u32 *)((pm) + 0x9C))
#define GP_DROPIN_ENABLED(pm) (*(u8 *)((pm) + 0xA0))
#define GP_BLOCK_A3(pm)       (*(u8 *)((pm) + 0xA3))
#define GP_BLOCK_A4(pm)       (*(u8 *)((pm) + 0xA4))

/* WindowsSystemInputDriver: 11 device slots, plus one extra device linked with all of them.
   Every device carries a "sub-device" list whose button state is OR'ed into its own queries
   (includeSub=1). InputDriver_CrossLinkDevices (0x496D60) links every device into every other one,
   which is why an unbound pad also drives player 1 on PC. */
#define DRV_MAX_DEVICES  11
#define DRV_DEVICE(d, i) (((u8 **)((d) + 0x438))[i])
#define DRV_EXTRA(d)     (*(u8 **)((d) + 0x42C))
#define DRV_GENERATION(d) (*(u32 *)((d) + 0x100))  /* +1 when a pad comes or goes (InputDriver_HotPlugCheck) */
#define DRV_GAMEPAD_MODE(d) (*(u8 *)((d) + 0x4A4))   /* last input came from an XInput pad (0 after a key/mouse) */
#define SUB_DATA(v)      (*(u8 ***)((v) + 0x274))   /* a device's sub-device list */
#define SUB_COUNT(v)     (*(u32 *)((v) + 0x278))
#define SUB_CAP(v)       (*(u32 *)((v) + 0x27C))

/* GameStandAloneLoop field read by the (buggy) join handler instead of its argument */
#define LOOP_PENDING_JOIN_PAD(loop) (*(int *)((u8 *)(loop) + 0x368))

#define BUTTON_START    13
#define JOIN_HOLD_MS    1000    /* START held this long on a pad nobody is bound to = join (a tap = player 1's pause) */
#define JOIN_TIMEOUT_MS 15000
#define VR_HOLD_MS      20000   /* longest the Virtual Reader auto-open is held off for player 2's figure */

/* ---------------------------------------------------------------- game functions */
#define orig_poll_dropin     ((int (THISCALL *)(void *))0x00A022B0)
#define orig_pause_action    ((u8 (THISCALL *)(void *, int, int, int))0x00BC82A0)
#define is_frontend_zone     ((u8 (*)(void))0x01036730)
#define game_stricmp         ((int (CDECL *)(const char *, const char *))0x0042A9C2)
#define get_max_local        ((int (*)(void))0x00ED85F0)
#define get_primary_local    ((int (THISCALL *)(void *))0x00EE1350)
#define dropin_allowed_level ((u8 (*)(void))0x00B76710)
#define can_drop_in          ((u8 (THISCALL *)(void *, int))0x00F01C30)
#define avatar_base          ((GameString *(THISCALL *)(void *, GameString *, int))0x00F084D0)
#define avatar_orig          ((GameString *(THISCALL *)(void *, GameString *, int))0x00A15ED0)
#define string_release       ((void (THISCALL *)(GameString *))0x00416270)
#define lua_checkint         ((int (CDECL *)(void *, int))0x00465FC0)
#define change_avatar_orig   ((int (STDCALL *)(void *))0x00C46B10)
#define lua_checkstr         ((const char *(CDECL *)(void *, int, u32 *))0x00465E70)
#define string_from_cstr     ((GameString *(THISCALL *)(GameString *, const char *))0x00416350)
#define figure_id_for_name   ((int (THISCALL *)(void *, const char *))0x0048A360)  /* 0 = unknown */
#define figure_name          ((GameString *(THISCALL *)(void *, GameString *, int))0x0048AF50)  /* (gateway, out, id): "" if unknown */
#define figure_valid_for_slot ((u8 (THISCALL *)(void *, int, int))0x00B7DFD0)
#define zone_string          ((const char *(THISCALL *)(void *, const char *, u32, int, const char *))0x00EFE4B0)  /* (zone manager, property, zone handle, 0, default) */
#define apply_avatar_suffix  ((void (STDCALL *)(GameString *))0x00F01FC0)      /* += zone avatarSuffix (or FallbackAvatar) */
#define template_exists      ((u8 (THISCALL *)(void *, GameString *))0x0072C4C0) /* (registry, name) */
#define gw_add_tag           ((int (THISCALL *)(void *, int, int, int, int, int, int, int, int, int))0x004877B0)
#define gw_remove_tag        ((int (THISCALL *)(void *, int, int))0x004827E0)
#define player_of_avatar     ((int (THISCALL *)(void *, u32))0x00EE8070)   /* avatar entity -> player index or -1 */
#define orig_key_watcher     ((void *(THISCALL *)(void *, u8 *, u32, u8 *))0x00F23880)
#define orig_pointer_watcher ((void *(THISCALL *)(void *, u8 *, u32, u8 *))0x00F238D0)
#define orig_avatar_input    ((int (CDECL *)(u8 *, u32))0x00B3D0D0)
#define orig_key_pressed     ((u8 (THISCALL *)(void *, int))0x004938F0)
#define orig_key_released    ((u8 (THISCALL *)(void *, int))0x00493920)
#define orig_key_down        ((u8 (THISCALL *)(void *, int))0x00495440)
#define orig_screen_input    ((u8 (THISCALL *)(void *, void *, int, int, int, int))0x007C61A0)
#define lua_pushboolean      ((void (CDECL *)(void *, int))0x00464720)
#define orig_screen_def      ((int (THISCALL *)(void *, void *, const char *, int))0x01049DC0)
#define orig_lua_controller_connected ((int (STDCALL *)(void *))0x00C31A00)
#define orig_gcm_set_actions ((int (THISCALL *)(void *, const char *))0x00B3D3B0)
#define orig_input_update    ((int (THISCALL *)(void *))0x00497150)
#define unpause_if_paused    ((u8 (CDECL *)(int))0x010387F0)   /* Pause_UnPauseFromPausedScreenIfPaused(player) */

/* input driver / device / loop virtuals. Input slot = player index (TryAddSecondLocalPlayer binds slot N's pad). */
#define IN_NUM_DEVICES   0x60
#define IN_BIND_SLOT     0x6C   /* (slot, device index); refused if the slot or the device is already bound */
#define IN_UNBIND_SLOT   0x70
#define IN_SLOT_BOUND    0x74   /* (slot) -> bool */
#define IN_IS_BOUND      0x78   /* (device index) -> bool */
#define IN_DEVICE_OF_SLOT 0x80  /* (slot) -> device index or -1 */
#define IN_GET_DEVICE    0x88
#define IN_SLOT_OF_DEVICE 0x9C  /* (device index) -> slot or -1 */
#define DEV_TYPE_NAME    0x08
#define DEV_CONNECTED    0x10
#define DEV_PRESSED      0x18   /* (button, includeSub): up last frame, down now */
#define DEV_DOWN         0x20   /* (button, includeSub): down now */
#define LOOP_JOIN_REQUEST 0xAC  /* GameStandAloneLoop::OnJoinRequestFromController(pad) */
#define FE_NO_BLOCKING_UI 0x90  /* GameFrontEndLayer: primary player has no menu open */
#define FE_PLAYER_DROPOUT 0xB8  /* GameFrontEndLayer_PlayerDropout (0xC33D40, Lua RemovePlayer) */

#define in_call0(in, off)       ((int (THISCALL *)(void *))VFN(in, off))(in)
#define in_call1(in, off, a)    ((int (THISCALL *)(void *, int))VFN(in, off))(in, a)
#define in_is_bound(in, i)      ((u8 (THISCALL *)(void *, int))VFN(in, IN_IS_BOUND))(in, i)   /* bool in AL only */
#define in_slot_bound(in, s)    ((u8 (THISCALL *)(void *, int))VFN(in, IN_SLOT_BOUND))(in, s) /* bool in AL only */
#define dev_button(dev, off, b) ((u8 (THISCALL *)(void *, int, int))VFN(dev, off))(dev, b, 0)

/* ---------------------------------------------------------------- kernel32 (exe IAT) */
#define IAT(addr) (*(void **)(addr))
#define k32_CreateFileA ((void *(STDCALL *)(const char *, u32, u32, void *, u32, u32, void *))IAT(0x0125416C))
#define k32_WriteFile   ((int (STDCALL *)(void *, const void *, u32, u32 *, void *))IAT(0x01254164))
#define k32_GetTickCount ((u32 (STDCALL *)(void))IAT(0x01254268))
