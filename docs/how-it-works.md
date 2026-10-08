# How the patch works

The patch adds one code section to the exe (`.coop`, built from `src/`), points game function pointers and
calls at the hooks in it, changes one load-flag constant and turns off ASLR for the exe (the code uses fixed
addresses). No game instructions are rewritten. It also rebuilds eight data files (zips) next to the exe.

Every patch site, with the value it must hold before patching, is in the tables at the top of
[`patcher/patch_exe.py`](../patcher/patch_exe.py); the data files and their recipes are listed in
[`patcher/game_files.py`](../patcher/game_files.py). The sections below follow the source files in `src/`.

Function names such as `InputDriver_HotPlugCheck` are the game's functions as named in the IDA database the
patch was researched with.

## Joining and leaving
`src/player2.c`, `src/dropin.c`

### Hold START to join
**Hook:** `GameStandAloneLoop` vtable +0xB4, the drop-in poll (gutted on PC) → `coop_poll_hook`

START held for 1 s on an unbound gamepad (its own buttons only; the keyboard can't join) detaches that pad
from player 1, places player 2's figure and calls `OnJoinRequestFromController(pad)`. The hook also follows
player 2 and hands the pad back when they leave.

What the patch does beyond the 360's logic:
- **Player 2's figure.** The Base/figure manager (IGP) only enables a player once it has built their
  character from the figure on their Base slot. On the 360 player 2's figure was on the right-hand circle
  (pad 1). On PC nothing ever uses pad 1, so the patch places a virtual figure there, the way the PC places
  player 1's on pad 0. It does this when the join is requested, before player 2 exists: the IGP opens the
  Virtual Reader (which pauses the player) in the first frame a new player's slot is empty. Until the figure
  is applied, the IGP's Virtual Reader cooldown for slot 1 is also kept 10 s in the future.
- **Device linking.** The PC input driver links every device (keyboard, extra device, all gamepads) into
  every other one as "sub-devices", so any device drives player 1. When a pad joins, the patch removes it from
  every other device's list and empties its own list. It records what it removed and puts it back when
  player 2 leaves. The unlink is repeated every frame while player 2 is in, in case a hot-plug rebuilds the
  links.
- **Releasing the pad on drop-out.** The PC's remove-player code no longer unbinds the pad (the 360's did),
  so the patch unbinds it.
- **Arming drop-in.** On the 360, a figure on the Base's P2 circle enables drop-in. The PC's virtual Base
  never uses that pad, so the hook enables it directly, with the same "not in Adventures" rule
  (`IGP_IsDropInAllowedForLevel`).
- **A bug in the PC join handler.** `GameStandAloneLoop_OnJoinRequestFromController` passes the stale field
  `this+0x368` to `RequestJoinFromController` instead of its pad argument. The hook writes the pad into that
  field first.

### No pause during the join hold
**Hook:** `ActionPauseMenu@AiAvatarCtrlBot` vtable +0x8, the "pause player" action → `coop_pause_action_hook`

The game pauses when a player's controls see START go up. On PC every device also drives player 1, so the
join hold would pause player 1 (detaching the held pad looks like START going up, and so does letting go
after a refused join) or player 2 (letting go after joining). There is no pause while a join hold lasts. A
short press on any pad but player 2's is player 1's pause.

### Gamepad unplugged
**Hook:** `WindowsSystemInputDriver` vtable +0x4, the driver's update → `coop_input_update_hook`

Once a second the driver frees unplugged pads' devices and moves the others down, but leaves the slot →
device table as it was. After a change, player 2's input slot follows their pad to its new index; if their
pad is gone, the slot is unbound (a slot naming an empty index crashed the game when both pads were
unplugged) and player 2 is dropped out as by Drop Out. With no pad left for player 1, the "last input was a
gamepad" flag is cleared, and player 2's pad no longer sets it.

## Player 2's character
`src/characters.c`

- **Choosing it.** `GamePlayers` vtable +0x2C, the PC's avatar picker → `coop_avatar_hook`. The PC gives
  every player player 1's Virtual Reader character. Player 2 gets the first usable of: the figure they left
  with (if they rejoin), the base rules (`AvatarTypeForPlayerId1` / zone `DefaultAvatar2`), the zone's
  `DefaultAvatar`, then a fixed list. "Usable" means the zone has that character's avatar template (Play Sets
  use `<name>_PS`, added the game's way by `ApplyZoneAvatarSuffix`), it has a figure id, isn't player 1's
  figure, and is valid for the level (the game's own check).
- **Picking in the Virtual Base.** Lua `Players_ChangeAvatar` → `coop_change_avatar_hook`. The PC Virtual
  Reader always swaps the figure on Base pad 0 (player 1). While two players are in, player 2's picks swap
  *their* figure on pad 1 instead, and a character the other player has is refused.
- **Telling the Virtual Base.** Lua `GetPlayerAvatarData` → `coop_player_avatar_data_hook`. It returned the
  player's avatar name (the actor's: `AV_Perry`), sparks and Play Set; it now adds a fourth value, the figure
  the player's character was built from. The Virtual Base's player-2 half uses it to find player 2's
  character, as its data is keyed by figure (`PNF_Perry`).

## Keyboard and mouse stay with player 1
`src/keyboard_mouse.c`

- **Input bindings.** `KeyWatcher` / `PointerWatcher` vtable +0x4 → `coop_key_watcher_hook` /
  `coop_pointer_watcher_hook`. Gamepad bindings (`ButtonWatcher`) read the player's own device, but keyboard
  and mouse bindings read the global keyboard and mouse for every player's `ControlMapper`. For player 2's
  mapper they now report "not pressed" / "no movement".
- **Movement keys.** The avatar input component's update → `coop_avatar_input_hook`, and
  `WindowsSystemInputDriver` vtable +0x28/+0x30/+0x34 (key pressed / released / down) → `coop_key_*_hook`.
  The component's WASD/arrow movement reads the global keyboard for every player's avatar; while it runs for
  player 2's avatar, the key queries return nothing.
- **Menus.** Two calls of `FlashMovie_SendScreenInput` → `coop_screen_input_hook`,
  `coop_screen_input_one_thunk`. Screens take keyboard events when their "keyboard" flag is set; it is cleared
  for player 2's screens, and their gamepad input is unchanged. The Virtual Base takes its input per device,
  so its movie couldn't tell the players apart: while two players are in, it gets it per player instead (as
  per-player screens do), so each half of its selector answers only its own player.

## The mouse cursor is player 1's
`src/mouse_cursor.c`

**Hooks:** `WindowsSystemInputDriver` vtable +0x44/+0x48/+0x4C (lock, free, show / hide), `Flash::ScreenStackLayer`
vtable +0x8 (UI layer update), `Pause_PausePlayer` (two calls and Lua), `Pause_UnPauseFromPausedScreen`, the
screen `onEnter` call, Lua `UI_IsMousePointerMode`

The game keeps one cursor state (locked for the camera, or free) and lets every pause, unpause, menu script
and the Toy Box editor switch it, for either player. The patch tracks the acting player (a pause or unpause
by its player, a screen's `onEnter` and a UI layer's update by the screen's). Player 2's don't lock, free or
show the cursor, their pause keeps the saved state, and scripts asking "is it free?" for player 2 get "no".
While player 1 is paused nothing locks it.

## Player 1's pads vibrate
`src/vibration.c`

**Hooks:** `iOSControllerInputDriver` vtable +0x6C/+0x70/+0x74 (vibrate, vibrate for a time, stop) →
`coop_vibrate_hook`, `coop_vibrate_for_hook`, `coop_stop_vibrate_hook`

The game vibrates a player's bound device, and player 1's is device 0, the virtual controller, whose
vibration methods do nothing: player 1's pad never vibrated. Device 0 now passes the call on to the devices
linked into it (player 1's pads; player 2's is unlinked while they're in), unless vibration is off in its
settings.

## Console editor screens for pad players
`src/console_editor.c`, `recipes/control_tables/`

The PC replaced the console building and customising screens with touch/mouse ones and bound their actions
to keys only.

- **Console movies.** The screen loader's `"WIN32"` key and the call of the ScreenDefinition loader →
  `coop_win32_swf_key`, `coop_screen_def_hook`. A screen opened by a player on a gamepad (player 2, or
  player 1 when their last input was a pad) uses the console movie instead of the PC touch movie
  (`Customize_Touch`, `LogicSelect_Touch`). Keyboard and mouse keep the touch movie.
- **No "keyboard and mouse only" popup.** Lua `IsControllerConnected` → `coop_lua_controller_connected`.
  The popup is skipped once for a pad user's customise screen or Play Set placement screen (`PlaceBldg`,
  `PlaceDeco`, `PlacePrank`, `PlaceTrainCar`).
- **A selects.** `GameControlMapperActiveActions` vtable +0 → `coop_gcm_set_actions_hook`. Customise movies
  select on their ribbon buttons' select key, but the list only hands it to buttons it builds, so buttons
  could keep the default `OK`, which no customise screen asked for: A and Enter didn't select. `OK` is added
  to every action list that has `CUST_APPLY`. The split-screen placement movies (`BuildingRibbon_V` / `_H`)
  and the console Toy Box ribbon have the same problem, so their lists get `OK` too.
- **Pad bindings** (`assets/excel/excel.zip`, built at patch time):
  - `controls_ui_win32.xldb` (`controls_ui.py`): the PC menu control scheme binds the editor actions to keys
    only. 33 actions also get the 360's pad binding, from the zip's own `controls_ui_xp.xldb` (the 360
    scheme, also shipped on PC): each becomes "any of" its PC keys and the 360's pad definition, copied in
    under `XP_` names. Keyboard bindings are unchanged (checked).
  - The same file, console Toy Box keys: `UI_RBN_TB_PLACE` and `UI_RBN_TB_EASY_ADV_TOGGLE` (added from the 360)
    get Enter and F, spark mode gets G (P has no key image for its label), and the spark menu's edit /
    delete / customise move from S / D / W (which also move the spark) to Enter / Backspace / C
    (`EXTRA_KEYS`, `SPARK_MOVE_KEYS`).
  - The same file, editor stick axes (`ANALOG_AXES`): the left stick (spark / held object) and right stick
    (editor camera) were stepped, with a pad and with the keyboard. Each becomes "any of" its own analog
    row, as on the 360, and the PC's key rows, held instead of repeated.
  - `controls_win32.xldb` (`controls_gameplay.py`): leaving the Toy Box logic mode (`LogicSelectCancel`) was
    Escape only; it gets pad B, as on the 360. Every other row is checked unchanged.

## The console Toy Box editor
`src/toybox_editor.c`

The PC opens its touch/mouse build ribbon for every player. For a player on a pad, and for both players in
split screen, the patch opens the 360's console ribbon and editor instead; keyboard and mouse in single
player keep the PC's.

- **The console ribbon.** The 17 calls of `UI_GetRibbonScreenName` (build mode and every lookup of the open
  ribbon) → `coop_ribbon_name_hook`: `RibbonToyBox` instead of `iOS_RibbonToyBox`. A ribbon that is already
  open keeps its name. Play Sets (`SelectMenu`) are unchanged.
- **Its scripts.** `assets/presentation/presentation.zip`: the PC reworked `ribbontoybox.lua` and
  `ribbonbase.lua` for its keyboard grid (and never opens them). They are replaced by the 360's, which
  `recipes/scripts/build_lua.py` builds into `build/lua/` from the game's own scripts. The PC has no console
  full-screen movie, so every layout uses `Infinitorium_V`.
- **The 360 editor code.** Six calls of `ZoneGetString` in the editor → `coop_editor_zone_thunk`, and two
  calls in Lua `Place_CreateGhost` → `coop_create_ghost_state_thunk`, `coop_create_ghost_done_thunk`. The PC
  runs touch code in the Toy Box: an orbit camera, the held object never followed, new ghosts moved to a
  raycast from the touch point and the held one placed first. For the console editor the zone checks answer
  "not the Toy Box" and `Place_CreateGhost` only creates the ghost, so the editor runs the 360's code (which
  has no Toy Box case; the PC uses it in Play Sets): the sticks move the object and the spark, and the camera
  follows them.
- **Movement at 30 Hz.** Four calls of the editor movement → `coop_move_ramp_hook`, `coop_move_hook`. The
  movement scales the stick by the frame time and snaps to the grid every frame, which at high frame rates
  rounds most of it away. For the console editor it runs in 360 frames (33 ms steps).
- **Grid push.** Two float operands in the editor movement → `coop_snap_push_pos` / `_neg`. A held stick
  pushes the spark or object to the next grid cell past 0.2, as on the 360, instead of the PC's 1.0, which a
  stick hardly ever reaches.
- **Spark target.** The spark update's highlight call → `coop_spark_highlight_hook`. The PC dropped the 360's
  "object under the spark" step (its target comes from the mouse), so in console spark mode nothing was
  targeted and the spark menu's buttons stayed off. It is back for the console editor.
- **Back to spark mode after customising.** Lua `Place_ReturnToSparkIfNeeded` → `coop_return_to_spark_hook`.
  The PC's version only sets the mode; the 360's also gives the spark menu its input back.

## Key labels per input device
`src/key_labels.c`, `recipes/movies/`

**Hook:** the string lookup in the Flash text translator and in Lua `TranslateText` → `coop_text_lookup_hook`

The editor movies label their keys from the string tables, and the PC's keyboard table often holds the wrong
key: the split-screen customise movies show Left Shift / right mouse / Z / X where the editor keys are Z / X
and V / B, and the full-screen PC movie shows keys (Z / X, F1 / F2, 1–9) even to a pad player. The patch
renames the label ids in the movies to `coopui_*` (same length, in place, each file checked by SHA-256 before
and after), and the hook resolves each one to the keyboard's or the pad's label, the way the game picks its
string table. Worded legends keep their (localised) text, with only the key image swapped.

| File | Movies | Recipe |
|---|---|---|
| `assets/flash/customize/customize.zip` | `customize.gfx` (full screen), `customize_h.gfx`, `customize_v.gfx` (split screen) | `customize_movies.py` |
| `assets/flash/buildingribbon/buildingribbon.zip` | `buildingribbon.gfx`, `buildingribbon_h.gfx`, `buildingribbon_v.gfx` | `buildingribbon_movies.py` |
| `assets/flash/infinitorium/infinitorium.zip` | `infinitorium_v.gfx` (the console Toy Box ribbon) | `toybox_movies.py` |
| `assets/flash/modeselect/modeselect.zip` | `modeselect.gfx` (the spark menu) | `toybox_movies.py` |

`customize.gfx` also gets new item and category handlers: LT/RT flipped a page of nine items, a leftover of
the PC layout (items on keys 1–9). Its `prevItem` / `nextItem` now move the movie's own highlight one slot,
turn the page at the first / last slot and preview the item; `prevCategory` / `nextCategory` (LB/RB) move the
highlight to the section's first item. LT/RT play `menu_prev` / `menu_next`, as their own sound,
`ribbon_scroll`, is an empty event in the PC's `ui.fev`.

## The Virtual Base for two players
`recipes/movies/vr_movie.py`, `as/CoopVirtualBase.as`, `lua/virtualreader.lua`

- **The movie** (`assets/flash/virtualreader/virtualreader.zip`). The PC's Virtual Base shows a half Base (one
  figure circle), squashed 0.75 × 0.6, and one character ribbon. The patch uses the real Base art
  (`readersplash_i8` from the game's own `readersplash.zip`: two circles and the hexagon) at 512×256, moves
  player 1's figure and the Discs onto it, and adds a co-op class (`as/CoopVirtualBase.as`, compiled by
  `recipes/movies/build_as.py` into its own ActionScript block; the game's own ActionScript is untouched).
  On the Figures tab the class splits the character ribbon in two halves of three characters, player 1 on
  the left and player 2 on the right, and shows player 2's figure and both name banners. The layout numbers
  are at the top of `vr_movie.py`. Every other part of the movie is checked unchanged.
- **The script** (`assets/presentation/presentation.zip`). The game's `virtualreader.lua` is kept as
  `virtualreader_orig.lua`, and a new `virtualreader.lua` (`lua/virtualreader.lua`) loads it and adds player
  2's half: their starting character, their picks, both players paused while it is open, and on close each
  half's pick going to its own player (the Discs stay player 1's).

## Full-screen menus in split screen
`recipes/control_tables/container_layout.py`

**File:** `assets/startup4.zip`: `excel/container.xldb`

A new screen is loaded into the HUD Container, which centres it, only if the sheet for the current split
layout has a row for it and its player's viewport. The Virtual Base (`VirtualReader`) and the Toy Box build
ribbon (`iOS_RibbonToyBox`) had rows only in the `OnePlayer` sheet, so in split screen they got a movie of
their own and sat at the bottom right. Their rows are copied into `TwoPlayerVertical` and
`TwoPlayerHorizontal` for both viewports, so they open as in single player: centred, full screen, over both
views. Every original row is checked unchanged.

## The menu softlock
**Patch:** the constant at `0x7CA719`, Scaleform's load flags for every menu and HUD movie:
`LoadOrdered` → `LoadOrdered | LoadWaitCompletion`

Without "wait", the movie is parsed on Scaleform's task thread while the game immediately advances it and
runs its "loaded" callback. If frame 1 isn't parsed yet, `_root.GetMovieRoot` fails, the screen is never set
up, and the menu hangs invisible with its player paused. The game already loads "Container" and "SubTitles"
this way. Menus take about 10 ms longer to open.

## Script errors
`src/script_errors.c`

**Hook:** `printf("LUA ERROR: %s\n")` in the script call wrapper → `coop_lua_error_hook`

UI script errors go to stdout, which is lost under Proton; they now go to `DisneyInfinityCoop.log`.
