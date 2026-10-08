/* The PC opens the touch/mouse ribbon (iOS_RibbonToyBox) for every player: one full-screen movie, objects
   picked with the mouse and keys by VirtualController_x360 (player 1 only), closed with Tab. The 360 opened
   the console ribbon (RibbonToyBox, Infinitorium / Infinitorium_V) per player, driven by that player's pad,
   with spark mode (X -> ModeSelect) to pick placed objects. Every way into build mode, and every native
   lookup of the open ribbon, asks UI_GetRibbonScreenName (0xC32CF0) for the screen name; its 17 calls come
   here. A player on a pad, and both players in split screen, get the console ribbon (its 360 scripts are
   put back in presentation.zip by patch_exe.py); keyboard and mouse in single player keep the touch one.
   A ribbon that is already open keeps its name, so lookups match it whatever the last input was. */
#define orig_ribbon_name ((const char *(STDCALL *)(int))0x00C32CF0)              /* "SelectMenu" in a Play Set */
/* UI_GetHandleFromName: thiscall on the GameFrontEndLayer (every game caller loads it into ecx), -1 if none */
#define ui_screen_handle ((int (THISCALL *)(void *, const char *, int))0x010447E0)
static const char k_touch_ribbon[] = "iOS_RibbonToyBox";
static const char k_console_ribbon[] = "RibbonToyBox";

/* does this player build with the console editor? The open ribbon decides; with none open, a pad (and
   split screen) means console. The ribbon name hook and the editor patches below all ask this. */
static int console_editor(int player)
{
    void *fe = G_FRONTEND_LAYER;
    if (fe && ui_screen_handle(fe, k_console_ribbon, player) != -1)
        return 1;
    if (fe && ui_screen_handle(fe, k_touch_ribbon, player) != -1)
        return 0;
    return player_on_gamepad(player) || g_p2_joined;
}

EXPORT const char *STDCALL coop_ribbon_name_hook(int player)
{
    const char *name = orig_ribbon_name(player);
    if (player < 0 || player > 1 || !G_FRONTEND_LAYER || !name || game_stricmp(name, k_touch_ribbon) != 0)
        return name;
    return console_editor(player) ? k_console_ribbon : k_touch_ribbon;
}

/* The PC's Toy Box editor is its touch/mouse one: six places in the editor ask
   ZoneGetString("PlaysetProperties") == "RumpusRoom" and then run touch code instead of the 360's (whose
   editor has no Toy Box case at all; the PC runs the 360 code in Play Sets):
     0xA8D81B in RumpusEditor_Update: camera and cursor from the touch deltas; the sticks are never read
     0xA88408 in RumpusEditor_Init: touch orbit camera around the avatar, touch pick state
     0xA84D34 in RumpusEditor_StateCameraRequests (spark mode), 0xA84FD0 in RumpusEditor_PlaceModeUpdate: the
              camera never follows the spark / held object (RumpusEditorCam_FocusOnObject skipped, or the touch
              camera's RumpusEditorCam_TouchFocusOnObject instead)
     0xA83ED1 in RumpusEditorCam_Target: the camera target isn't moved to the object
     0xA43AA3 in RumpusEditorCam_Rotate: camera rotation from the touch controls instead of the right stick
   For the console editor these calls answer "none", so the editor runs the 360 code. Not 0xA4381D: its Toy Box
   camera distance (20) is the 360's. All players' editors are the same kind (single player: player 1's;
   split screen: console for both), so no player is needed here. */
EXPORT int CDECL coop_editor_console(void)
{
    return g_p2_joined || console_editor(0);
}

__asm__(".text\n"
        ".globl coop_editor_zone_thunk\n"
        "coop_editor_zone_thunk:\n"          /* replaces call ZoneGetString at the six sites above */
        "    pushl %ecx\n"
        "    call coop_editor_console\n"
        "    popl %ecx\n"
        "    testl %eax, %eax\n"
        "    jnz 1f\n"
        "    movl $0x00EFE4B0, %eax\n"           /* ZoneGetString: 4 stack arguments, ecx kept */
        "    jmp *%eax\n"
        "1:  xorl %eax, %eax\n"
        "    ret $16\n");

/* Lua Place_CreateGhost (0xB42F50). The 360's only creates the ghost (the editor then holds it at its
   cursor). The PC's adds its touch "tap to place" steps: first it commits the ghost held so far (the console
   ribbon makes a new ghost after every scroll pause, so objects were placed unasked), then it moves the new
   ghost to a raycast from the touch point (none with a pad: an uninitialised screen point, objects far away)
   and starts touch dragging. For the console editor both are skipped:
   - 0xB42FC4: the call of the place mode's state (0xA44AA0, ecx = editor + 0x168) answers none: no commit;
   - 0xB4313D: the string_release right after the ghost is made (ebx = ghost) returns to 0xB432A7, where
     the function pushes the ghost and returns, as the 360's does. */
__asm__(".text\n"
        ".globl coop_create_ghost_state_thunk\n"
        "coop_create_ghost_state_thunk:\n"
        "    pushl %ecx\n"
        "    call coop_editor_console\n"
        "    popl %ecx\n"
        "    testl %eax, %eax\n"
        "    jnz 1f\n"
        "    movl $0x00A44AA0, %eax\n"           /* thiscall, no stack arguments */
        "    jmp *%eax\n"
        "1:  xorl %eax, %eax\n"
        "    ret\n"
        ".globl coop_create_ghost_done_thunk\n"
        "coop_create_ghost_done_thunk:\n"
        "    movl $0x00416270, %eax\n"           /* the replaced call: string release, thiscall */
        "    call *%eax\n"
        "    testl %ebx, %ebx\n"                 /* no ghost: the game returns 0 itself */
        "    jz 1f\n"
        "    call coop_editor_console\n"
        "    testl %eax, %eax\n"
        "    jz 1f\n"
        "    movl $0x00B432A7, (%esp)\n"         /* skip the touch steps: push the ghost, return 1 */
        "1:  ret\n");

/* Editor movement at the 360's frame rate. Every frame, the spark / held-object movement
   (RumpusEditor_MoveSpeedRamp, RumpusEditor_MoveSnap) scales the stick by the frame time (G_FRAME_MS), drops a
   move under 0.03 units and snaps the position to the grid (RoundToStep) from the last snapped position. The
   360 ran it at 30 fps; at 165 fps a frame's move is 5.5 times smaller, so most of it is dropped or rounded
   away: slow, steppy movement. For the console editor these calls (from RumpusEditorModeSpark_Update and
   RumpusEditorModeObject_Update) see 360 frames instead: 33 ms on every 30th of a second (the remainder
   carried), 0 in between; at 30 fps or less, every frame as it is. The ramp (called first, arg 1 = editor +
   0x2410) decides the step; the move (arg 4 = editor + 0x240C) reuses it. */
#define G_FRAME_MS     (*(u32 *)0x0167DF84)
#define orig_move_ramp ((void (CDECL *)(void *, u32, void *))0x00A2C250)
#define orig_move      ((int (CDECL *)(void *, void *, void *, void *, void *, void *))0x00A2C570)
#define EDITOR_STEP_MS 33
static struct { u8 *editor; u32 acc, step, used; } g_move_clock[4];
static u32 g_move_uses;

/* an editor is made per build-mode visit: a new one takes the least recently used slot */
static int move_clock(u8 *editor)
{
    int lru = 0;
    for (int i = 0; i < 4; i++) {
        if (g_move_clock[i].editor == editor) {
            g_move_clock[i].used = ++g_move_uses;
            return i;
        }
        if (g_move_clock[i].used < g_move_clock[lru].used) lru = i;
    }
    g_move_clock[lru].editor = editor;
    g_move_clock[lru].acc = 0;
    g_move_clock[lru].step = 0;
    g_move_clock[lru].used = ++g_move_uses;
    return lru;
}

EXPORT void CDECL coop_move_ramp_hook(u8 *moves, u32 flags, void *state)
{
    if (!coop_editor_console()) {
        orig_move_ramp(moves, flags, state);
        return;
    }
    int i = move_clock(moves - 0x2410);
    u32 real = G_FRAME_MS;
    g_move_clock[i].step = 0;
    if (real >= EDITOR_STEP_MS) {               /* 30 fps or slower: every frame is a step, as unpatched */
        g_move_clock[i].step = real;
        g_move_clock[i].acc = 0;
    } else {                                    /* faster: one 360 frame (33.3 ms) per step, remainder kept */
        g_move_clock[i].acc += real * 3;        /* thirds of a millisecond */
        if (g_move_clock[i].acc >= 100) {
            g_move_clock[i].acc -= 100;
            if (g_move_clock[i].acc >= 100)
                g_move_clock[i].acc = 0;
            g_move_clock[i].step = EDITOR_STEP_MS;
        }
    }
    G_FRAME_MS = g_move_clock[i].step;
    orig_move_ramp(moves, flags, state);
    G_FRAME_MS = real;
}

/* Grid push. After snapping, RumpusEditor_MoveSnap moves the snapped position on by one grid cell when the
   stick is held that way (stick > T, and the unsnapped position has caught up), so a held stick walks cell by
   cell although one step's move (~0.7) is under half a cell (the Toy Box grid is 2 x 4 x 2). The 360 uses
   T = 0.2 / -0.2; the PC uses 1.0 / -1.0, which a stick hardly ever exceeds. The two compares (0xA2C65D,
   0xA2C683) read these variables instead of the shared 1.0 / -1.0 constants: the 360's values for the console
   editor, the PC's otherwise. Between 30 Hz steps the move sees a still stick, or the push would fire every
   frame. */
__attribute__((used)) float coop_snap_push_pos = 1.0f, coop_snap_push_neg = -1.0f;

EXPORT int CDECL coop_move_hook(float *a1, float *a2, float *a3, u8 *block, void *a5, float *a6)
{
    if (!coop_editor_console()) {
        coop_snap_push_pos = 1.0f;
        coop_snap_push_neg = -1.0f;
        return orig_move(a1, a2, a3, block, a5, a6);
    }
    coop_snap_push_pos = 0.2f;
    coop_snap_push_neg = -0.2f;
    int i = move_clock(block - 0x240C);
    u32 real = G_FRAME_MS, step = g_move_clock[i].step;
    float still[3] = {0.0f, 0.0f, 0.0f};
    G_FRAME_MS = step;
    int r = orig_move(a1, step ? a2 : still, a3, block, a5, a6);
    G_FRAME_MS = real;
    return r;
}

/* Spark target. Every frame, the 360's spark update finds the placed object under the spark, stores it as the
   spark's target (spark + 8912) and hands it to the spark's EditorSparkComponent (EditorSparkComponent_SetTarget:
   the highlight, Place_DoSparkSelection's target and the A / B / X / Y buttons ModeSelect shows). The PC
   dropped that step (its target comes from the mouse, RumpusEditor_TouchSetSparkTarget), so in console spark
   mode nothing was ever targeted and ModeSelect's buttons stayed off. It runs again here, at the spark
   update's call of SparkEditorObject_HighlightTarget (0xA860EF; it ignores ecx), for the console editor only:
   - query a +-1 box around the spark's position (its matrix translation, spark + 136) with the editor's box
     query (RumpusEditor_BoxQuery, mode 7 as the touch cursor's preview uses) and the spark's options (+284);
   - the first result that is a placed object (has a rumpus object component) becomes the target. Results are
     56-byte entries from +4: type at +4 (128 = ignored), entity at +52. */
#define orig_spark_highlight ((void (STDCALL *)(u8 *))0x00A7DED0)
#define editor_box_query     ((u16 *(CDECL *)(float *, void *, u16 **, u32))0x00A84440)
#define rumpus_object_of     ((void *(CDECL *)(u32))0x00CDF220)
#define game_free            ((void (CDECL *)(void *))0x0040A370)
#define spark_set_target     ((void (THISCALL *)(void *, u32))0x00C0ED00)
#define SPARK_TARGET(s)      (*(u32 *)((s) + 8912))
#define SPARK_COMPONENT(s)   (*(void **)((s) + 8924))

EXPORT void STDCALL coop_spark_highlight_hook(u8 *spark)
{
    if (spark && SPARK_COMPONENT(spark) && coop_editor_console()) {
        float *pos = (float *)(spark + 136);
        float box[6] = {pos[0] - 1.0f, pos[1] - 1.0f, pos[2] - 1.0f, pos[0] + 1.0f, pos[1] + 1.0f, pos[2] + 1.0f};
        u16 *list = 0;
        u32 target = 0;
        editor_box_query(box, spark + 284, &list, 0);
        if (list) {
            for (u32 i = 0; i < list[1] && !target; i++) {
                u8 *entry = (u8 *)list + 4 + 56 * i;
                u32 entity = *(u32 *)(entry + 52);
                if (*(u32 *)(entry + 4) != 128 && entity && rumpus_object_of(entity))
                    target = entity;
            }
            game_free(list);
        }
        SPARK_TARGET(spark) = target;
        spark_set_target(SPARK_COMPONENT(spark), target);
    }
    orig_spark_highlight(spark);
}

/* Back to spark mode after customising. ModeSelect:Customize (Y on a spark target) closes the spark menu and
   opens the customise screen, whose onExit calls Place_ReturnToSparkIfNeeded. The 360's version gets or
   creates the player's ModeSelect screen, calls its DoInput (so it takes input again, as
   RibbonToyBox:StartSparkMode does) and sets RumpusEditorModeSpark. The PC's only sets the mode (the touch
   editor has no ModeSelect), so the spark menu came back ignoring input until the ribbon was reopened. For the
   console editor the 360's two steps run first. */
#define orig_return_to_spark ((int (STDCALL *)(void *))0x00B46A40)
#define RETURN_TO_SPARK(p)   (*((u8 *)0x016BC498 + (p)))       /* per player: "go back to spark mode" */
#define fe_create_screen(fe, name, p) \
    ((int (THISCALL *)(void *, const char *, int, int, int, const char *, int, int, int))VFN(fe, 0x6C)) \
        (fe, name, p, 0, 0, "MAIN", 0, 1, -1)
#define fe_call_screen       ((void *(THISCALL *)(void *, u32 *, int, const char *, const char *))0x0104FD60)
#define lua_release_result   ((void (CDECL *)(u32, u32))0x00465330)

EXPORT int STDCALL coop_return_to_spark_hook(void *L)
{
    int player = lua_checkint(L, 1);
    void *fe = G_FRONTEND_LAYER;
    if (fe && player >= 0 && player < 2 && RETURN_TO_SPARK(player) && coop_editor_console()) {
        int handle = ui_screen_handle(fe, "ModeSelect", player);
        if (handle == -1)
            handle = fe_create_screen(fe, "ModeSelect", player);
        if (handle != -1) {
            u32 result[2] = {0, 0};
            fe_call_screen(fe, result, handle, "DoInput", "");
            if (result[0])
                lua_release_result(result[0], result[1]);
        }
    }
    return orig_return_to_spark(L);
}
