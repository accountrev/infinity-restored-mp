#!/usr/bin/env python3
"""Builds build/lua/ribbonbase.lua and build/lua/ribbontoybox.lua: the Xbox 360's console Toy Box ribbon scripts,
which patch_exe.py puts in presentation.zip in place of the PC's keyboard rework.

    python3 recipes/scripts/build_lua.py path/to/unluac.jar [path/to/game folder]

Needs Java and unluac 1.2.3 (unluac_2025_12_23.jar from SourceForge; `--version` prints 1.2.3.569), and the game:
the PC's own scripts (compiled Lua in assets/presentation/presentation.zip, only read; its .orig backup if the game
is already patched) are decompiled to build/lua/pc/, then an ed script from lua/ (`diff -e` output) turns each into
the 360's: the 360's script is the PC's with the keyboard rework taken out, plus the co-op patch's changes. The
decompiled text is checked by SHA-256, so another unluac version is caught before the ed script is applied. The
game folder defaults to the one Steam lists (steam.py).

To change a script: edit build/lua/<name>, then
    diff -e build/lua/pc/<name> build/lua/<name> > lua/<name>.ed
"""
import hashlib, io, os, re, subprocess, sys, tempfile, zipfile

REPO_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
sys.path.insert(0, os.path.join(REPO_DIR, "patcher"))
import game_files, steam  # noqa: E402

OUT_DIR = os.path.join(REPO_DIR, "build", "lua")
# script -> sha256 of the PC's script as unluac 1.2.3 decompiles it
DECOMPILED_SHA256 = {
    "ribbonbase.lua": "8e3179de11764ddab51dd5846b754484ba8843ba6be50074fa5afd8d041a5315",
    "ribbontoybox.lua": "832c0cb4448b3adbac1a80ece609c3dda5dc88469f3cb8b377d2f286620da19b",
}


def apply_ed(text, script):
    """text with an ed script from `diff -e` applied (a / c / d commands, last line first, so the line numbers
    are the original's)."""
    lines, cmds, i = text.splitlines(keepends=True), script.splitlines(keepends=True), 0
    while i < len(cmds):
        m = re.fullmatch(r"(\d+)(?:,(\d+))?([acd])\n", cmds[i])
        assert m, f"unexpected ed command {cmds[i]!r}"
        first, last, op = int(m[1]), int(m[2] or m[1]), m[3]
        i += 1
        new = []
        if op != "d":
            while cmds[i] != ".\n":
                new.append(cmds[i])
                i += 1
            i += 1
        if op == "a":
            lines[first:first] = new
        else:
            lines[first - 1:last] = new
    return "".join(lines)


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    jar = sys.argv[1]
    if not os.path.exists(jar):
        sys.exit(f"{jar} not found (unluac.jar is the first argument)")
    game_dir = sys.argv[2] if len(sys.argv) == 3 else os.path.dirname(steam.find_game_exe())
    path = os.path.join(game_dir, game_files.PRESENTATION_REL)
    if not os.path.exists(path):
        sys.exit(f"{path} not found")
    z = zipfile.ZipFile(io.BytesIO(game_files.original(path, game_files.PRESENTATION_SHA256, os.path.basename(path))))

    os.makedirs(os.path.join(OUT_DIR, "pc"), exist_ok=True)
    for name, digest in DECOMPILED_SHA256.items():
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, name), "wb").write(z.read(name))
            pc = subprocess.run(["java", "-jar", jar, os.path.join(tmp, name)], check=True,
                                stdout=subprocess.PIPE).stdout.replace(b"\r\n", b"\n")    # Java on Windows: \r\n
        if hashlib.sha256(pc).hexdigest() != digest:
            sys.exit(f"{name}: unluac's output differs from unluac 1.2.3's; the ed script needs that version")
        open(os.path.join(OUT_DIR, "pc", name), "wb").write(pc)
        out = apply_ed(pc.decode("ascii"), open(os.path.join(REPO_DIR, "lua", name + ".ed")).read())
        open(os.path.join(OUT_DIR, name), "w", newline="").write(out)
        print(f"built build/lua/{name} ({out.count(chr(10))} lines) from the game's {name}; "
              f"sha256 {hashlib.sha256(out.encode()).hexdigest()}")


if __name__ == "__main__":
    main()
