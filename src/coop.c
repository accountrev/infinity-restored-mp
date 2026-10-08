/*
 * Disney Infinity 1.0 Gold Edition (PC): local split-screen drop-in for a second player.
 *
 * Target: DisneyInfinity1.exe, SHA-256 22c596d4af825981ca9f5d845fb7068197b544b9c4f12a9954c2d39eff502ac0
 * This code is linked at a fixed address into a new PE section (see link.ld / patcher/patch_exe.py), so every
 * game address is absolute (image base 0x400000; the patcher turns ASLR off). patcher/patch_exe.py lists where each
 * coop_* hook is installed, and docs/how-it-works.md explains them.
 *
 * One translation unit: the parts share static state and are included in this order.
 */
#include "game.h"           /* types, calling conventions, the game's data, functions and virtual-table offsets */
#include "log.c"            /* DisneyInfinityCoop.log */
#include "player2.c"        /* player 2's pad (unlinked from player 1) and virtual figure, the join request */
#include "dropin.c"         /* hooks: hold START to join, leaving, pads unplugged, no pause during the join hold */
#include "vibration.c"      /* hooks: player 1's pads vibrate */
#include "characters.c"     /* hooks: player 2's character, Virtual Base picks */
#include "keyboard_mouse.c" /* hooks: keyboard and mouse stay with player 1; Virtual Base input per player */
#include "console_editor.c" /* hooks: console customise / placement screens for pad players */
#include "toybox_editor.c"  /* hooks: the 360's console Toy Box editor for pad players and split screen */
#include "key_labels.c"     /* hook: on-screen key labels per input device */
#include "script_errors.c"  /* hook: UI script errors to the log */
#include "mouse_cursor.c"   /* hooks: the mouse cursor is player 1's */
