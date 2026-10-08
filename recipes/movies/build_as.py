#!/usr/bin/env python3
"""Builds build/CoopVirtualBase.abc: the co-op class for the Virtual Base (as/CoopVirtualBase.as) compiled into its
own ActionScript block (DoABC tag), which patch_exe.py adds to virtualreader.gfx next to the game's.

    python3 recipes/movies/build_as.py path/to/ffdec [path/to/game folder]

Needs Java and JPEXS FFDec (the folder of its release zip, with ffdec-cli.jar; tested: FFDec 26.2.1, OpenJDK 25),
and the game: the class is compiled against the game's own movie (assets/flash/virtualreader/virtualreader.zip,
only read; its .orig backup if the game is already patched). The game folder defaults to the one Steam lists.

The game's own class (VirtualReader_win32) stays byte-identical. FFDec only replaces classes that exist, so the
donor is the game's movie plus a second DoABC holding an empty stub of the class (built here); FFDec compiles the
source over the stub and the second DoABC is taken from its output. Checks: the game's DoABC is unchanged, the new
one defines the class, and it uses no opcode that the game's own compiler doesn't use somewhere in this movie
(FFDec's `inclocal`, which the game's code never uses, crashed Scaleform).
"""
import glob, hashlib, io, os, re, struct, subprocess, sys, tempfile, zipfile

import vr_movie

sys.path.insert(0, os.path.join(vr_movie.REPO_DIR, "patcher"))
import game_files, steam  # noqa: E402

CLASS = vr_movie.CLASS
TESTED_SHA256 = "4f4e45236b3de41d8b1148006b3b5f1bf8af2efe7913f90eba7674ad89123ac2"   # FFDec 26.2.1, v6.35
BASES = [("", "Object"), ("flash.events", "EventDispatcher"), ("flash.display", "DisplayObject"),
         ("flash.display", "InteractiveObject"), ("flash.display", "DisplayObjectContainer"),
         ("flash.display", "Sprite"), ("flash.display", "MovieClip")]


def u30(v):
    out = bytearray()
    while True:
        b = v & 0x7F
        v >>= 7
        out.append(b | (0x80 if v else 0))
        if not v:
            return bytes(out)


def stub_abc():
    """ABC with `public class CoopVirtualBase extends flash.display.MovieClip {}` (constructor only)."""
    strings = ["", CLASS] + sorted({p for p, _ in BASES} - {""}) + [n for _, n in BASES]
    s = {v: i + 1 for i, v in enumerate(strings)}
    pkgs = [""] + sorted({p for p, _ in BASES} - {""})
    ns = {p: i + 1 for i, p in enumerate(pkgs)}                        # PackageNamespace (0x16) each
    names = [("", CLASS)] + BASES
    mn = {v: i + 1 for i, v in enumerate(names)}                        # QName (0x07) each
    out = bytearray(struct.pack("<HH", 16, 46))
    out += u30(0) + u30(0) + u30(0)                                     # int, uint, double
    out += u30(len(strings) + 1) + b"".join(u30(len(v.encode())) + v.encode() for v in strings)
    out += u30(len(pkgs) + 2) + b"".join(b"\x16" + u30(s[p]) for p in pkgs) + b"\x18" + u30(s[CLASS])
    out += u30(0)                                                       # ns sets
    out += u30(len(names) + 1) + b"".join(b"\x07" + u30(ns[p]) + u30(s[n]) for p, n in names)
    out += u30(3) + b"".join(u30(0) + u30(0) + u30(0) + b"\x00" for _ in range(3))   # iinit, cinit, script init
    out += u30(0)                                                       # metadata
    out += u30(1)                                                       # instance + class
    out += u30(mn[("", CLASS)]) + u30(mn[BASES[-1]]) + b"\x09" + u30(len(pkgs) + 1) + u30(0) + u30(0) + u30(0)
    out += u30(1) + u30(0)
    out += u30(1) + u30(2) + u30(1) + u30(mn[("", CLASS)]) + b"\x04" + u30(1) + u30(0)   # script: Class trait
    depth = len(BASES) + 1
    sinit = b"\xd0\x30\x65\x00" + b"".join(b"\x60" + u30(mn[b]) + b"\x30" for b in BASES)
    sinit += b"\x60" + u30(mn[BASES[-1]]) + b"\x58\x00" + b"\x1d" * len(BASES) + b"\x68" + u30(mn[("", CLASS)]) + b"\x47"
    bodies = [(0, 1, depth + 1, depth + 2, b"\xd0\x30\xd0\x49\x00\x47"),   # iinit: super()
              (1, 1, depth, depth + 1, b"\xd0\x30\x47"),                   # cinit
              (2, 2, 1, depth, sinit)]                                     # script init
    out += u30(len(bodies))
    for m, stack, d0, d1, code in bodies:
        out += u30(m) + u30(stack) + u30(1) + u30(d0) + u30(d1) + u30(len(code)) + code + u30(0) + u30(0)
    return bytes(out)


def movie_tags(gfx):
    start = 8 + (5 + 4 * (gfx[8] >> 3) + 7) // 8 + 4
    tags, _ = vr_movie.parse_tags(gfx, start)
    return start, tags


def pcode_ops(path):
    ops = set()
    for f in glob.glob(os.path.join(path, "**", "*.pcode"), recursive=True):
        for line in open(f, encoding="utf-8", errors="replace"):
            m = re.match(r"\s+([a-z][a-z0-9_]*)(?:\s|$)", line)   # not labels ("ofs0123:")
            if m:
                ops.add(m.group(1))
    return ops


def game_movie(game_dir):
    """The game's virtualreader.gfx, from its virtualreader.zip (or the .orig backup of a patched one)."""
    path = os.path.join(game_dir, game_files.VIRTUALREADER_REL)
    if not os.path.exists(path):
        sys.exit(f"{path} not found")
    zdata = game_files.original(path, game_files.VIRTUALREADER_SHA256, os.path.basename(path))
    return zipfile.ZipFile(io.BytesIO(zdata)).read(vr_movie.GFX)


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    jar = os.path.join(sys.argv[1], "ffdec-cli.jar")
    if not os.path.exists(jar):
        sys.exit(f"{jar} not found (FFDec's folder is the first argument)")
    game_dir = sys.argv[2] if len(sys.argv) == 3 else os.path.dirname(steam.find_game_exe())

    def ffdec(*args):
        subprocess.run(["java", "-jar", jar] + list(args), check=True, stdout=subprocess.DEVNULL)

    orig = game_movie(game_dir)
    assert hashlib.sha256(orig).hexdigest() == vr_movie.GFX_SHA256, "not the game's virtualreader.gfx"
    with tempfile.TemporaryDirectory() as tmp:
        start, tags = movie_tags(orig)
        i = next(k for k, t in enumerate(tags) if t[0] == 82)
        donor = bytearray(orig[:start]) + vr_movie.write_tags(
            tags[:i + 1] + [[82, True, struct.pack("<I", 1) + b"coop\0" + stub_abc()]] + tags[i + 1:])
        struct.pack_into("<I", donor, 4, len(donor))
        open(os.path.join(tmp, "game.gfx"), "wb").write(orig)
        open(os.path.join(tmp, "donor.gfx"), "wb").write(donor)
        os.makedirs(os.path.join(tmp, "src", "scripts"))
        source = open(os.path.join(vr_movie.REPO_DIR, "as", CLASS + ".as"), "rb").read()
        open(os.path.join(tmp, "src", "scripts", CLASS + ".as"), "wb").write(source)
        ffdec("-importScript", os.path.join(tmp, "donor.gfx"), os.path.join(tmp, "out.gfx"), os.path.join(tmp, "src"))
        out = open(os.path.join(tmp, "out.gfx"), "rb").read()
        _, otags = movie_tags(out)
        abcs = [t[2] for t in otags if t[0] == 82]
        assert len(abcs) == 2 and abcs[0] == tags[i][2], "FFDec changed the game's DoABC"
        new = abcs[1]
        assert CLASS.encode() in new and len(new) > 2000, "class not compiled"

        # opcodes: only those the game's compiler uses in this movie
        ffdec("-format", "script:pcode", "-export", "script", os.path.join(tmp, "pc_game"), os.path.join(tmp, "game.gfx"))
        ffdec("-format", "script:pcode", "-selectclass", CLASS, "-export", "script", os.path.join(tmp, "pc_coop"),
              os.path.join(tmp, "out.gfx"))
        unknown = pcode_ops(os.path.join(tmp, "pc_coop")) - pcode_ops(os.path.join(tmp, "pc_game"))
        assert not unknown, "opcodes the game's code never uses: %s" % sorted(unknown)

    os.makedirs(os.path.dirname(vr_movie.ABC_PATH), exist_ok=True)
    open(vr_movie.ABC_PATH, "wb").write(new)
    digest = hashlib.sha256(new).hexdigest()
    print(f"built {os.path.relpath(vr_movie.ABC_PATH, vr_movie.REPO_DIR)} ({len(new)} bytes); game's DoABC unchanged; "
          "opcodes all used by the game")
    print(f"sha256 {digest}: " + ("the tested build" if digest == TESTED_SHA256 else
                                  "differs from the tested build (another FFDec version, or the .as was changed)"))


if __name__ == "__main__":
    main()
