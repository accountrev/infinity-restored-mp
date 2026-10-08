"""Steam: where the game is installed (find_game_exe), and closing / starting it for patch_exe.py --run.
Linux (native or Flatpak Steam, the game under Proton) and Windows."""
import csv, os, re, signal, subprocess, sys, time

WINDOWS = os.name == "nt"
STEAM_APPID = "541640"   # Disney Infinity 1.0: Gold Edition
STEAM_DIRS = ("~/.local/share/Steam", "~/.steam/steam", "~/.var/app/com.valvesoftware.Steam/.local/share/Steam")
GAME_EXE = "DisneyInfinity1.exe"
GAME_EXE_REL = os.path.join("steamapps", "common", "Disney Infinity Gold Edition", GAME_EXE)


def _steam_dirs():
    """Steam's own folder: on Windows the registry's SteamPath, then the default; on Linux the usual places."""
    if not WINDOWS:
        return [os.path.expanduser(d) for d in STEAM_DIRS]
    import winreg
    dirs = []
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            dirs.append(os.path.normpath(winreg.QueryValueEx(key, "SteamPath")[0]))
    except OSError:
        pass
    return dirs + [os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Steam")]


def find_game_exe():
    """The exe in the Steam library that has the game (Steam's libraryfolders.vdf), else in Steam's own folder."""
    for steam in _steam_dirs():
        vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
        if os.path.exists(vdf):
            # one block per library: its "path" (backslashes doubled on Windows), then its "apps" (app id -> size)
            for block in re.split(r'(?="path")', open(vdf, encoding="utf-8").read())[1:]:
                if f'"{STEAM_APPID}"' in block:
                    library = re.match(r'"path"\s+"([^"]*)"', block)[1].replace("\\\\", "\\")
                    return os.path.join(library, GAME_EXE_REL)
    return os.path.join(_steam_dirs()[0], GAME_EXE_REL)


def _game_pids():
    """Processes whose program is DisneyInfinity1.exe (on Linux the Wine process; not this script or IDA's .i64)."""
    if WINDOWS:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
        return [int(row[1]) for row in csv.reader(out.splitlines())
                if len(row) > 1 and row[0].lower() == GAME_EXE.lower()]
    pids = []
    for d in os.listdir("/proc"):
        if not d.isdigit() or int(d) == os.getpid():
            continue
        try:
            argv0 = open(f"/proc/{d}/cmdline", "rb").read().split(b"\0")[0].decode(errors="replace")
        except OSError:
            continue
        if argv0.replace("\\", "/").rsplit("/", 1)[-1].lower() == GAME_EXE.lower():
            pids.append(int(d))
    return pids


def _steam_session_running():
    """Whether Steam still counts the game as running (it won't start it again until it doesn't): on Linux while its
    launch wrapper (reaper) lives, on Windows while the game's Running value in the registry is set."""
    if WINDOWS:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Valve\Steam\Apps\{STEAM_APPID}") as key:
                return winreg.QueryValueEx(key, "Running")[0] == 1
        except OSError:
            return False
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if f"AppId={STEAM_APPID}".encode() in open(f"/proc/{d}/cmdline", "rb").read():
                    return True
            except OSError:
                pass
    return False


def _wait(cond, seconds):
    for _ in range(int(seconds * 4)):
        if not cond():
            return True
        time.sleep(0.25)
    return not cond()


def close_game():
    pids = _game_pids()
    if not pids:
        return
    print(f"closing the running game (pid {', '.join(map(str, pids))})")
    for sig in (signal.SIGTERM, getattr(signal, "SIGKILL", signal.SIGTERM)):    # Windows: both end the process
        for pid in _game_pids():
            try:
                os.kill(pid, sig)
            except OSError:     # already gone
                pass
        if _wait(_game_pids, 15):
            break
    else:
        sys.exit("the game did not close; not patching")
    if not _wait(_steam_session_running, 30):
        print("warning: Steam still shows the game as running; the launch may be ignored")


def launch_game():
    url = f"steam://rungameid/{STEAM_APPID}"
    print(f"starting the game through Steam ({url})")
    try:
        if WINDOWS:
            os.startfile(url)
        else:
            subprocess.Popen(["steam", url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:             # no steam program (Linux) or no steam:// handler (Windows)
        sys.exit("steam not found; start the game yourself")
