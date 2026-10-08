#!/usr/bin/env python3
"""Apply / remove the local co-op patch on Disney Infinity 1.0 Gold Edition (Steam).

    python3 patcher/patch_exe.py [path/to/DisneyInfinity1.exe]            apply (backs up to .orig first)
    python3 patcher/patch_exe.py --restore [path/to/DisneyInfinity1.exe]  put the originals back
    python3 patcher/patch_exe.py --zip FILE [path/to/DisneyInfinity1.exe] write the patched files to a zip instead
    --run (Steam install only): close the game if it is running, patch / restore, then start it through Steam

With --zip the game folder is only read: the zip holds the patched files laid out like the game folder
(DisneyInfinity1.exe, assets/...), to be extracted over it. No .orig backups are made; Steam's "Verify integrity
of game files" puts the originals back.

Without a path, the game is found through Steam's library list (steam.py). The exe gets a new section with the
co-op code (build/coop.bin, from ./build.sh) and the hooks listed below; the data files next to it are rebuilt by
game_files.py. Only the known Steam files are accepted (SHA-256 checked), every patched location is verified to
hold its original value, and nothing is written until all files are ready.
"""
import argparse, os, shutil, struct, sys, zipfile

from game_files import DATA_FILES, backup_once, original, sha256
from steam import close_game, find_game_exe, launch_game

DEFAULT_EXE = find_game_exe()
ORIGINAL_SHA256 = "22c596d4af825981ca9f5d845fb7068197b544b9c4f12a9954c2d39eff502ac0"
IMAGE_BASE = 0x400000
SECTION_NAME = b".coop"
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (virtual address, original 32-bit value, replacement symbol, description)
POINTER_PATCHES = [
    (0x01350828, 0x00A022B0, "coop_poll_hook", "GameStandAloneLoop vtable +0xB4 (drop-in poll)"),
    (0x0131B1D0, 0x00A15ED0, "coop_avatar_hook", "GamePlayers vtable +0x2C (avatar for new player)"),
    (0x00C4B51B, 0x00C46B10, "coop_change_avatar_hook", "Lua Players_ChangeAvatar registration"),
    (0x00C4A52A, 0x00C3E2B0, "coop_player_avatar_data_hook", "Lua GetPlayerAvatarData registration (+ the player's figure id, for the Virtual Base)"),
    (0x0133A81C, 0x00BC82A0, "coop_pause_action_hook", "ActionPauseMenu@AiAvatarCtrlBot vtable +0x8"),
    (0x01460A58, 0x00F23880, "coop_key_watcher_hook", "KeyWatcher vtable +0x4 (keyboard binding)"),
    (0x01460A68, 0x00F238D0, "coop_pointer_watcher_hook", "PointerWatcher vtable +0x4 (mouse binding)"),
    (0x00B3D174, 0x00B3D0D0, "coop_avatar_input_hook", "avatar input component update registration"),
    (0x0129BAFC, 0x004938F0, "coop_key_pressed_hook", "WindowsSystemInputDriver vtable +0x28 (key pressed)"),
    (0x0129BB04, 0x00493920, "coop_key_released_hook", "WindowsSystemInputDriver vtable +0x30 (key released)"),
    (0x0129BB08, 0x00495440, "coop_key_down_hook", "WindowsSystemInputDriver vtable +0x34 (key down)"),
    (0x0129BAD8, 0x00497150, "coop_input_update_hook", "WindowsSystemInputDriver vtable +0x4 (driver update: player 2's input slot after a pad is plugged in / unplugged)"),
    # console editor for gamepad players
    (0x0104A03F, 0x012AF534, "coop_win32_swf_key", "screen loader SWF.WIN32 key (per player: touch movie or console)"),
    (0x00C4C195, 0x00C31A00, "coop_lua_controller_connected", "Lua IsControllerConnected registration (skip KBM-only popup)"),
    (0x013300E4, 0x00B3D3B0, "coop_gcm_set_actions_hook", "GameControlMapperActiveActions vtable +0 (customise / split placement screens: add OK so A selects)"),
    # editor grid push thresholds (RumpusEditor_MoveSnap): the 360's 0.2 / -0.2 for the console editor instead of the shared 1.0 / -1.0
    (0x00A2C660, 0x01280244, "coop_snap_push_pos", "editor move: push to the next grid cell above this stick value (comiss operand)"),
    (0x00A2C687, 0x01280240, "coop_snap_push_neg", "editor move: push to the previous grid cell below this stick value (movss operand)"),
    (0x00B514E8, 0x00B46A40, "coop_return_to_spark_hook", "Lua Place_ReturnToSparkIfNeeded registration (console editor: ModeSelect takes input again after customising)"),
    # the mouse cursor is player 1's: player 2's pauses, screens and menus don't lock or free it
    (0x01473DBC, 0x01050CC0, "coop_layer_update_hook", "Flash::ScreenStackLayer vtable +0x8 (UI layer update: whose screens' input runs)"),
    (0x0129BB18, 0x00495750, "coop_mouse_look_hook", "WindowsSystemInputDriver vtable +0x44 (enter mouse look; not for player 2, nor while player 1 is paused)"),
    (0x0129BB1C, 0x00493670, "coop_leave_mouse_look_hook", "WindowsSystemInputDriver vtable +0x48 (leave mouse look; not for player 2)"),
    (0x0129BB20, 0x00496560, "coop_show_cursor_hook", "WindowsSystemInputDriver vtable +0x4C (show / hide the cursor; not for player 2)"),
    (0x00C4B3F8, 0x01038630, "coop_pause_player_hook", "Lua Pause_PauseGame registration (Pause_PausePlayer: whose pause)"),
    (0x00C4B426, 0x01038730, "coop_unpause_player_hook", "Lua Pause_UnPauseFromPausedScreen registration (whose unpause)"),
    (0x00C4A47B, 0x00C32140, "coop_lua_is_mouse_pointer_mode", "Lua UI_IsMousePointerMode registration (no for player 2's scripts)"),
    # player 1's vibration: device 0 (virtual controller) passes it on to the pads linked into it
    (0x0129BD90, 0x008C3970, "coop_vibrate_hook", "iOSControllerInputDriver vtable +0x6C (vibrate)"),
    (0x0129BD94, 0x008A4F30, "coop_vibrate_for_hook", "iOSControllerInputDriver vtable +0x70 (vibrate for a time)"),
    (0x0129BD98, 0x00517A50, "coop_stop_vibrate_hook", "iOSControllerInputDriver vtable +0x74 (stop vibrating)"),
]

# (address of a `call rel32` (E8) or `jmp rel32` (E9), original target, replacement symbol, description)
CALL_PATCHES = [
    (0x010439AC, 0x007C61A0, "coop_screen_input_hook", "Flash screen input call (per local player)"),
    (0x010439D9, 0x007C61A0, "coop_screen_input_one_thunk", "Flash screen input call (one screen; Virtual Base per player)"),
    (0x0047816D, 0x0042AD26, "coop_lua_error_hook", "printf of LUA ERROR in the script call wrapper (to the log)"),
    (0x01051BDE, 0x01049DC0, "coop_screen_def_hook", "ScreenDefinition loader call (movie per player)"),
    (0x00BC82D2, 0x01038630, "coop_pause_player_hook", "Pause_PausePlayer call in the pause action (whose pause)"),
    (0x00F035DF, 0x01038630, "coop_pause_player_hook", "Pause_PausePlayer call in the loop update (whose pause)"),
    (0x0103880C, 0x01038730, "coop_unpause_player_hook", "jmp to Pause_UnPauseFromPausedScreen in ...IfPaused (whose unpause)"),
    (0x01051D10, 0x01042DB0, "coop_screen_enter_hook", "screen onEnter call in UIScreen_Init (whose screen)"),
    (0x007CCF80, 0x007C4E70, "coop_text_lookup_hook", "string lookup in the Flash text translator (customise labels)"),
    (0x007CD122, 0x007C4E70, "coop_text_lookup_hook", "string lookup in Lua TranslateText (customise legends)"),
    # the Toy Box editor's touch-only branches: the console editor runs the 360 code
    (0x00A8D81B, 0x00EFE4B0, "coop_editor_zone_thunk", "ZoneGetString in the Toy Box editor update (sticks for the console editor)"),
    (0x00A88408, 0x00EFE4B0, "coop_editor_zone_thunk", "ZoneGetString in the Toy Box editor init (no touch orbit camera)"),
    (0x00A84D34, 0x00EFE4B0, "coop_editor_zone_thunk", "ZoneGetString in the editor spark mode (camera follows the spark)"),
    (0x00A84FD0, 0x00EFE4B0, "coop_editor_zone_thunk", "ZoneGetString in the editor place mode (camera follows the object)"),
    (0x00A83ED1, 0x00EFE4B0, "coop_editor_zone_thunk", "ZoneGetString in the editor camera target (on the object)"),
    (0x00A43AA3, 0x00EFE4B0, "coop_editor_zone_thunk", "ZoneGetString in the editor camera rotation (right stick)"),
    (0x00B42FC4, 0x00A44AA0, "coop_create_ghost_state_thunk", "Lua Place_CreateGhost: held ghost (no commit for the console editor)"),
    (0x00B4313D, 0x00416270, "coop_create_ghost_done_thunk", "Lua Place_CreateGhost: after creating (no touch raycast / drag for the console editor)"),
    (0x00A85D21, 0x00A2C250, "coop_move_ramp_hook", "spark movement speed ramp (console editor: 30 Hz steps, as on the 360)"),
    (0x00A85D66, 0x00A2C570, "coop_move_hook", "spark movement (console editor: 30 Hz steps, as on the 360)"),
    (0x00A897A2, 0x00A2C250, "coop_move_ramp_hook", "held object movement speed ramp (console editor: 30 Hz steps)"),
    (0x00A897DC, 0x00A2C570, "coop_move_hook", "held object movement (console editor: 30 Hz steps)"),
    (0x00A860EF, 0x00A7DED0, "coop_spark_highlight_hook", "spark update: target the object under the spark (360 pick, for ModeSelect A/B/X/Y)"),
]
# UI_GetRibbonScreenName: every call (build mode and the native lookups of the open ribbon)
RIBBON_NAME_CALLS = (0x00A1FA89, 0x00A1FE0A, 0x00A79B84, 0x00B860ED, 0x00B860FF, 0x00B86B01, 0x00B86B13, 0x00BA39D3,
                     0x00BA39DF, 0x00BA4C4D, 0x00C32D36, 0x00C3726D, 0x00C372A3, 0x00C3D266, 0x00CF2CEB, 0x00D15E62,
                     0x00D1B302)
CALL_PATCHES += [(va, 0x00C32CF0, "coop_ribbon_name_hook",
                  "Toy Box ribbon name lookup (console ribbon for pads / split)") for va in RIBBON_NAME_CALLS]


# (virtual address, original 32-bit value, new 32-bit value, description)
CONST_PATCHES = [
    # Menus/HUD were created with LoadOrdered only, so the SWF is parsed on Scaleform's task thread
    # while the game immediately advances the movie and runs its "loaded" callback. If frame 1 isn't
    # parsed yet, _root.GetMovieRoot fails, the screen is never initialised and the menu hangs
    # invisible (its player stays paused). LoadWaitCompletion (as the game uses for "Container").
    (0x007CA719, 0x00000010, 0x00000011, "Flash movie load flags: LoadOrdered -> LoadOrdered|LoadWaitCompletion"),
]


def align(v, a):
    return (v + a - 1) & ~(a - 1)


class PE:
    def __init__(self, data):
        self.d = bytearray(data)
        self.pe = struct.unpack_from("<I", self.d, 0x3C)[0]
        self.opt = self.pe + 24
        self.nsec = struct.unpack_from("<H", self.d, self.pe + 6)[0]
        self.sec_tab = self.opt + struct.unpack_from("<H", self.d, self.pe + 20)[0]
        self.file_align = struct.unpack_from("<I", self.d, self.opt + 36)[0]
        self.sect_align = struct.unpack_from("<I", self.d, self.opt + 32)[0]
        self.size_of_image = struct.unpack_from("<I", self.d, self.opt + 56)[0]
        self.size_of_headers = struct.unpack_from("<I", self.d, self.opt + 60)[0]

    def sections(self):
        for i in range(self.nsec):
            o = self.sec_tab + i * 40
            name, vsize, va, rsize, roff = struct.unpack_from("<8sIIII", self.d, o)
            yield name.rstrip(b"\0"), vsize, va, rsize, roff

    def va_to_off(self, va):
        rva = va - IMAGE_BASE
        for _, vsize, sva, rsize, roff in self.sections():
            if sva <= rva < sva + max(vsize, rsize):
                return roff + rva - sva
        raise ValueError(f"VA {va:#x} not in any section")


def call_target(pe, va):
    return (va + 5 + struct.unpack_from("<i", pe.d, pe.va_to_off(va) + 1)[0]) & 0xFFFFFFFF


def load_blob():
    blob_path = os.path.join(REPO_DIR, "build", "coop.bin")
    sym_path = os.path.join(REPO_DIR, "build", "coop.sym")
    if not os.path.exists(blob_path):
        sys.exit("build/coop.bin missing - run ./build.sh first")
    syms = {}
    for line in open(sym_path):
        name, val = line.split()
        syms[name] = int(val, 16)
    return open(blob_path, "rb").read(), syms


def apply(exe, zip_path=None):
    data = original(exe, ORIGINAL_SHA256, "exe")
    game_dir = os.path.dirname(os.path.abspath(exe))
    new_data = []           # (path, original sha256, new bytes, report lines)
    for rel, digest_ok, builder in DATA_FILES:
        path = os.path.join(game_dir, rel)
        if not os.path.exists(path):
            sys.exit(f"{path} not found")
        new_data.append((path, digest_ok, *builder(original(path, digest_ok, os.path.basename(path)), game_dir)))

    blob, syms = load_blob()
    pe = PE(data)
    if any(n == SECTION_NAME for n, *_ in pe.sections()):
        sys.exit("exe already has a .coop section")

    new_rva = align(pe.size_of_image, pe.sect_align)
    if IMAGE_BASE + new_rva != syms["COOP_BASE"]:
        sys.exit(f"blob was linked for {syms['COOP_BASE']:#x} but the section would land at "
                 f"{IMAGE_BASE + new_rva:#x}; fix COOP_BASE in build.sh")

    hdr_off = pe.sec_tab + pe.nsec * 40
    if hdr_off + 40 > pe.size_of_headers or any(pe.d[hdr_off:hdr_off + 40]):
        sys.exit("no free space for another section header")

    # verify patch sites before touching anything
    for va, orig, sym, desc in POINTER_PATCHES:
        cur = struct.unpack_from("<I", pe.d, pe.va_to_off(va))[0]
        if cur != orig:
            sys.exit(f"{desc}: expected {orig:#x} at {va:#x}, found {cur:#x}")
    for va, orig, sym, desc in CALL_PATCHES:
        off = pe.va_to_off(va)
        if pe.d[off] not in (0xE8, 0xE9) or call_target(pe, va) != orig:
            sys.exit(f"{desc}: expected call/jmp {orig:#x} at {va:#x}")
    for va, orig, new, desc in CONST_PATCHES:
        cur = struct.unpack_from("<I", pe.d, pe.va_to_off(va))[0]
        if cur != orig:
            sys.exit(f"{desc}: expected {orig:#x} at {va:#x}, found {cur:#x}")

    # append the section
    raw_off = align(len(pe.d), pe.file_align)
    raw_size = align(len(blob), pe.file_align)
    pe.d += b"\0" * (raw_off - len(pe.d))
    pe.d += blob + b"\0" * (raw_size - len(blob))
    struct.pack_into("<8sIIIIIIHHI", pe.d, hdr_off, SECTION_NAME, len(blob), new_rva, raw_size, raw_off,
                     0, 0, 0, 0, 0xE0000020)  # code | execute | read | write
    struct.pack_into("<H", pe.d, pe.pe + 6, pe.nsec + 1)
    struct.pack_into("<I", pe.d, pe.opt + 56, align(new_rva + len(blob), pe.sect_align))

    # fixed addresses everywhere -> load at the preferred base (clear IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE)
    dllch = struct.unpack_from("<H", pe.d, pe.opt + 70)[0]
    struct.pack_into("<H", pe.d, pe.opt + 70, dllch & ~0x0040)

    pe = PE(pe.d)
    for va, orig, sym, desc in POINTER_PATCHES:
        struct.pack_into("<I", pe.d, pe.va_to_off(va), syms[sym])
        print(f"  {desc}: {orig:#010x} -> {syms[sym]:#010x} ({sym})")
    for va, orig, sym, desc in CALL_PATCHES:
        struct.pack_into("<i", pe.d, pe.va_to_off(va) + 1, syms[sym] - (va + 5))
        print(f"  {desc}: call {orig:#010x} -> {call_target(pe, va):#010x} ({sym})")
    for va, orig, new, desc in CONST_PATCHES:
        struct.pack_into("<I", pe.d, pe.va_to_off(va), new)
        print(f"  {desc}: {orig:#x} -> {new:#x}")

    # (path in the game folder, new bytes, report lines)
    outputs = [(exe, bytes(pe.d), [f".coop section at {IMAGE_BASE + new_rva:#x}, {len(blob)} bytes"])]
    outputs += [(path, new_bytes, report) for path, _, new_bytes, report in new_data]
    if zip_path:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for path, data, _ in outputs:
                z.writestr(os.path.relpath(path, game_dir).replace(os.sep, "/"), data)
    else:
        check_writable([path for path, _, _ in outputs])
        backup_once(exe, ORIGINAL_SHA256)
        for path, digest_ok, _, _ in new_data:
            backup_once(path, digest_ok)
        for path, data, _ in outputs:
            open(path, "wb").write(data)
    for path, data, report in outputs:
        print(f"patched {os.path.relpath(path, game_dir) if zip_path else path}")
        for line in report:
            print("  " + line)
        print(f"  sha256 {sha256(data)}")
    if zip_path:
        print(f"wrote {zip_path} (the game folder is unchanged): extract it into {game_dir}")


def check_writable(paths):
    """Windows locks a running game's files: make sure every file can be written before writing any."""
    for path in paths:
        try:
            if os.path.exists(path):
                open(path, "r+b").close()
        except PermissionError:
            sys.exit(f"{path} can't be written (is the game running?); nothing was changed")


def restore(exe):
    game_dir = os.path.dirname(os.path.abspath(exe))
    files = [(exe, ORIGINAL_SHA256)] + [(os.path.join(game_dir, rel), d) for rel, d, _ in DATA_FILES]
    check_writable([path for path, _ in files])
    for path, digest_ok in files:
        backup = path + ".orig"
        if not os.path.exists(backup):
            print(f"no backup at {backup}; leaving {path} as it is")
            continue
        if sha256(open(backup, "rb").read()) != digest_ok:
            sys.exit(f"{backup} does not match the original; not restoring")
        shutil.copy2(backup, path)
        print(f"restored original {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Apply / remove the local co-op patch on Disney Infinity 1.0 Gold Edition.")
    ap.add_argument("exe", nargs="?", default=DEFAULT_EXE,
                    help="the game's DisneyInfinity1.exe (default: found through Steam's library list)")
    ap.add_argument("--restore", action="store_true", help="put the original files back")
    ap.add_argument("--run", action="store_true",
                    help="Steam install only: close the game first if it is running, start it through Steam after")
    ap.add_argument("--zip", metavar="FILE",
                    help="write the patched files to FILE instead of patching the game (the game folder is only read)")
    args = ap.parse_args()
    if args.zip and (args.restore or args.run):
        ap.error("--zip can't be combined with --restore or --run")
    if args.run and os.path.realpath(args.exe) != os.path.realpath(DEFAULT_EXE):
        sys.exit("--run only works on the Steam install (no exe path argument)")
    if args.run:
        close_game()
    if args.restore:
        restore(args.exe)
    else:
        apply(args.exe, args.zip)
    if args.run:
        launch_game()
