# Restored Multiplayer for Disney Infinity 1.0 GE
An attempt to bringing back split-screen from the console versions to Disney Infinity 1.0 Gold Edition, using unused code that is still in the game (and some code/assets from the console versions).

This is my first project that involves heavy usage of Claude Code (Opus 5.5) as I try to learn how to use LLMs as tools.

<img width="500" alt="image" src="https://github.com/user-attachments/assets/bb7ae6f8-5837-4056-8d0a-36b004f7acea" />
<img width="500" alt="image" src="https://github.com/user-attachments/assets/b44ba224-9e73-41b6-ac03-01283d2efde2" />
<img width="500" alt="image" src="https://github.com/user-attachments/assets/f565a88a-2b1d-4c03-ae4f-b5a8940701ec" />
<img width="500" alt="image" src="https://github.com/user-attachments/assets/52675c32-a064-47bd-b367-9dd35fa95c87" />

## Features
* Restores the ability to play with a second player through split-screen, which was intentionally kept removed from the PC remaster
* Custom Virtual Base + UI, which now allows two players to choose a character.
* Various fixes and patches to improve the split-screen experience, inherited from the Xbox 360 version of 1.0

## How it works
The split-screen patch adds one block of new code to the game's executable. It then points some of the game's own function pointers and calls at that code. Apart from that, it changes one constant internally (because of a Scaleform bug) and turns off address randomization since the code uses fixed addresses. No game instructions are rewritten. It also rebuilds various files in the assets folder: Lua scripts, Flash movies and control tables. Each is built from the game's own files, checked through hashing (SHA-256) before and after.

Various patches relied on the Xbox 360 version of 1.0 plus Title Update 3, which has split-screen code and many UI assets intact. I used some of those assets to be able to make the split-screen experience better since they are missing on PC.

Documentation written by Claude can be found [here](docs/how-it-works.md).

## Installation
[Download the latest mod files](https://github.com/accountrev/infinity-restored-mp/releases/latest) in the Releases tab, and extract the contents of the zip file to the root of your game folder.

OR

Build and patch the mod yourself.


## How to play
Player 1 can either play using keyboard and mouse or a controller. Player 2 can only play on controller.

During a session, Player 2 needs to **hold down the START button** on a controller for one second to join.

Once both players are in the world, Player 2 can now choose their figure by pausing -> Virtual Base. Player 1's character selector is on the left side, while Player 2 is on the right side.

To disconnect as Player 2, Player 2 should pause -> Drop Out, or just disconnect the controller. They are free to join back in after a disconnect.

Player 2 cannot be the same figure as Player 1, and vice versa.

## Building and Patching
**You must own a copy of Disney Infinity 1.0 Gold Edition to build this patch.**

Three parts are built before the patch is applied:
* the code (`src/coop.c`)
* the Virtual Base's ActionScript co-op class (`as/CoopVirtualBase.as`)
* the console Toy Box ribbon's scripts (PC Lua scripts that include Xbox 360 Lua code with the ed scripts in `lua/`). 

Building works on Linux and Windows, and needs:
* LLVM: `clang` (it targets 32-bit x86 itself, no 32-bit libraries are needed), `ld.lld`, `llvm-objcopy`, `llvm-nm`
* Python 3
* Java (8 or later) and [JPEXS FFDec](https://github.com/jindrapetrik/jpexs-decompiler/releases) (26.2.1)
* [unluac Lua decompiler](https://sourceforge.net/projects/unluac/files/Unstable/) (2025_12_23 / version 1.2.3.569)
* 1.0 Gold Edition game files

### Linux
* Fedora: `sudo dnf install clang lld llvm python3 java-25-openjdk-headless`
* Debian / Ubuntu: `sudo apt install clang lld llvm python3 default-jre`.

Then, in this folder:
```sh
./build.sh
python3 recipes/movies/build_as.py path/to/ffdec "path/to/your/game"
python3 recipes/scripts/build_lua.py path/to/unluac.jar "path/to/your/game"
```

### Windows (tested through Wine)
* Install [LLVM](https://github.com/llvm/llvm-project/releases). During installation, let it add LLVM to the PATH.
* Install Python 3 (tested on 3.14)
* Install a Java runtime of your choice

Then, in this folder:
```bat
build.bat
py recipes\movies\build_as.py C:\path\to\ffdec "C:\path\to\your\game"
py recipes\scripts\build_lua.py C:\path\to\unluac.jar "C:\path\to\your\game"
```

### Applying and removing the patch

**To apply the patch:**
```sh
python3 patcher/patch_exe.py			# patches the game directly
python3 patcher/patch_exe.py --run		# patches the game directly, then runs the game automatically through Steam
python3 patcher/patch_exe.py --zip		# saves the modified files to a zip file for manual replacement
```
**Note**: If `patch_exe.py` cannot find your Steam installation, add `"path/to/your/game"` as an argument.


**To remove the patch:**
```sh
python3 patcher/patch_exe.py --restore		# attempts to restore the files using existing .orig files
```
or you can just verify your files on Steam.

## Why
The original console version of the game came with the ability to play with another person through local split-screen (Xbox 360, Playstation 3, Wii and Wii U). The Nintendo 3DS version stripped split-screen entirely and introduced a single player Base which allowed only one playable character slot.
The iOS version would branch off the 3DS version, introducing the Virtual Base based off the 3DS base. Then, the Windows 8 version would branch off the iOS version with the same features.
When Gold Editon remaster came out, they did not bother to bring back split-screen, but there are still remnants of code left from the console versions that were passed down.
I wanted to play the Infinity games with a friend originally, but had issues with certain emulators in the past. I was already knowledgeable with the game's Lua scripts (since I wanted to mod this game years ago), but couldn't find a solution. I eventually learned how to do basic reverse engineering, but deemed this project too advanced for me. Therefore, I decided to use Claude as a gateway to how I wanted to create this mod (and to learn how to use it as a tool), and was a majority of the help.

## Known bugs
* Player 1's mouse clicks may still reach Player 2's open menus (we love Flash).
* There may be some controller weirdness. If so, run the game using Steam Input enabled.
* The wrong keybinds may show up on either Player's screen if Player 1 is playing KBM (may fix later).

## AI Disclosure
This project was created with the assistance of Claude Opus 5.5 LLM. Claude assisted with mainly reverse engineering and the majority of the programming. All code generated was analyzed by myself afterwards for accuracy.
