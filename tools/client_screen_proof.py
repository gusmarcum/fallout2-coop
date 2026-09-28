"""Proofs that need the REAL game client on the far end (bugs/033, bugs/034).

Both defects lived in the client's own screen and keyboard handling, where a wire bot sees
nothing. So the second player here is fallout2-ce.exe itself, started the way join.cmd
starts it but with no window (SDL dummy drivers), and watched two ways: screenshots it dumps
of what it draws (F2_VIEWER_SHOT_EVERY) and what the server receives from it.

  hp     bugs/033. The host is hurt, the second player is put at 1 hit point, leaves, and
         joins again. Their counter must show their own hit points. It is read off the
         screenshots by colour: the counter turns red at low health, and only the second
         player is low.
  chat   bugs/034. The second player's keyboard is a recording (F2_INPUT_REPLAY) that
         presses T, types "hey" and presses Enter every few seconds. A hostile attacks the
         host part way through, so the fight cannot be called off. During the fight the
         server must receive chat lines from the second player and no request to end combat.

--expect-defect inverts the verdict, to show the defect on a build older than the fix.

Nothing here reads or writes a live world: point it at a sandbox copy. It empties that
folder's save slots and working maps before it starts. Needs Pillow for `hp`.

usage: python -u client_screen_proof.py <hp|chat> <f2_server.exe> <fallout2-ce.exe> <game dir>
                                        <net port> <cmd port> [--expect-defect] [--keep <dir>]
"""
import glob, os, re, shutil, socket, subprocess, sys, threading, time

args = [a for a in sys.argv[1:] if not a.startswith("--")]
expect_defect = "--expect-defect" in sys.argv
keep = None
if "--keep" in sys.argv:
    keep = sys.argv[sys.argv.index("--keep") + 1]
    args.remove(keep)
what, server_exe, client_exe, gamedir = args[0], args[1], args[2], args[3]
port, cmdport = int(args[4]), int(args[5])

NL = chr(10)
RAIDER = "0x010000EE"
KEY_T, KEY_H, KEY_E, KEY_Y, KEY_ENTER = 23, 11, 8, 28, 40  # SDL scancodes
logpath = os.path.join(gamedir, "client-screen-proof-server.log")
tracepath = os.path.join(gamedir, "client-screen-proof-keys.txt")
results = []
log = None
srv = None
game = None


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ("  [" + detail + "]" if detail else ""))


def fixed(name, ok, detail=""):
    """A check of the fix: inverted when the defect is being shown."""
    if expect_defect:
        check("(defect shown) NOT: " + name, not ok, detail)
    else:
        check(name, ok, detail)


class Host:
    """The host's seat: a wire client that logs in and can end its combat turns."""

    def __init__(self):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
        threading.Thread(target=self.drain, daemon=True).start()

    def drain(self):
        while True:
            try:
                if not self.s.recv(65536):
                    return
            except Exception:
                return

    def send(self, line, wait):
        self.s.sendall((line + NL).encode())
        time.sleep(wait)


def admin(line, wait=1.0):
    s = socket.create_connection(("127.0.0.1", cmdport), timeout=5)
    s.sendall((line + NL).encode())
    time.sleep(0.4)
    s.settimeout(0.6)
    out = b""
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            out += chunk
    except socket.timeout:
        pass
    s.close()
    time.sleep(wait)
    return out.decode(errors="replace").strip()


def logtext():
    if log is not None and not log.closed:
        log.flush()
    return open(logpath, encoding="utf-8", errors="replace").read()


def clean_env():
    env = dict(os.environ)
    for name in list(env):
        if name.startswith("F2_"):
            env.pop(name)
    return env


def boot():
    global srv, log
    env = clean_env()
    env.update({"F2_SERVER_MAP": "arvillag.map", "F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
                "F2_SERVER_PACE_MS": "100", "F2_AUTOSAVE_SECS": "0", "F2_SERVER_KEEPALIVE": "1",
                "F2_TRACE_EVENTS": "1"})
    log = open(logpath, "w")
    srv = subprocess.Popen([server_exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT)
    time.sleep(7)


def join(extra):
    """Start the real client as the second player. Returns the process."""
    env = clean_env()
    env.update({"F2_CLIENT_CONNECT": "127.0.0.1:%d" % port, "F2_PLAYER_NAME": "Brother",
                "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"})
    env.update(extra)
    return subprocess.Popen([client_exe], cwd=gamedir, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def leave(proc):
    alive = proc.poll() is None
    proc.kill()
    try:
        proc.wait(timeout=10)
    except Exception:
        pass
    time.sleep(2.0)
    return alive


def screenshots():
    return sorted(glob.glob(os.path.join(gamedir, "scr*.bmp")))


def drop_screenshots():
    for path in screenshots():
        if keep is not None:
            os.makedirs(keep, exist_ok=True)
            shutil.move(path, os.path.join(keep, os.path.basename(path)))
        else:
            os.remove(path)


def counter_is_red(path):
    """The hit point counter sits on the right of the interface bar, which is 640 wide,
    100 high, centred at the bottom of the screen. Red digits = low health."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    left = (w - 640) // 2
    box = im.crop((left + 500, h - 100 + 30, left + 600, h - 100 + 62))
    red = sum(1 for r, g, b in box.getdata() if r > 150 and g < 80 and b < 80)
    white = sum(1 for r, g, b in box.getdata() if r > 170 and g > 170 and b > 170)
    return red > white and red > 20, red, white


def prove_hp():
    global game
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    mark = len(logtext())
    game = join({})
    time.sleep(9)
    check("the second player joined", leave(game)
          and "control claimed by session" in logtext()[mark:])
    game = None

    admin("hurt 10")
    admin("kill 1", 2.0)
    out = admin("revive 1", 2.0)
    check("the second player has 1 hit point and the host has many", "back at 1 HP" in out, out[:80])

    drop_screenshots()
    mark = len(logtext())
    game = join({"F2_VIEWER_SHOT_EVERY": "40"})
    time.sleep(14)
    alive = leave(game)
    game = None
    check("the second player joined again as the same character",
          alive and "body reattached" in logtext()[mark:])
    shots = screenshots()
    check("the client drew the game", len(shots) >= 4, "%d screenshots" % len(shots))
    if len(shots) >= 4:
        verdicts = [counter_is_red(path) for path in shots[len(shots) // 2:]]
        red = sum(1 for is_red, _r, _w in verdicts if is_red)
        fixed("the counter shows the second player's own hit points (red: 1 of 44)",
              red == len(verdicts), "%d of %d late screenshots show a red counter" % (red, len(verdicts)))
    drop_screenshots()


def prove_chat():
    global game
    with open(tracepath, "w") as trace:
        trace.write("# T, h, e, y, Enter, again and again" + NL)
        start = 300
        while start < 60000:
            at = start
            for key in (KEY_T, KEY_H, KEY_E, KEY_Y, KEY_ENTER):
                trace.write("K %d %d 1%s" % (at, key, NL))
                trace.write("K %d %d 0%s" % (at + 3, key, NL))
                at += 12
            start += 240

    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    drop_screenshots()
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_VIEWER_SHOT_EVERY": "45"})
    time.sleep(14)
    peace = logtext()
    check("out of combat the second player's chat arrives (the keyboard recording works)",
          peace.count("control say slot=1 'hey'") >= 1, "%d lines" % peace.count("control say slot=1 'hey'"))

    rows = re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=(-?\d+) pid=\S+ tile=(-?\d+)", peace)
    out = admin("spawn %s 1 %d" % (RAIDER, int(rows[-1][1]) + 3), 2.0)
    admin("aggro 1", 3.0)
    mark = len(logtext())
    for _ in range(9):
        time.sleep(2.5)
        host.send("cendturn", 0.2)
    fight = logtext()[mark:]
    alive = leave(game)
    game = None
    os.remove(tracepath)

    check("a fight was on for the whole window", alive and "placed 1/1" in out
          and "not in combat" not in fight, out[:70])
    said = fight.count("control say slot=1 'hey'")
    ended = sum(1 for line in fight.splitlines() if "cendcombat" in line and "slot=1" in line)
    fixed("chat lines typed during the fight reach the server", said >= 3, "%d lines" % said)
    fixed("the Enter that sends a line does not ask to end combat", ended == 0, "%d requests" % ended)
    drop_screenshots()


for path in glob.glob(os.path.join(gamedir, "data", "SAVEGAME", "SLOT*")):
    shutil.rmtree(path, ignore_errors=True)
for path in glob.glob(os.path.join(gamedir, "data", "MAPS", "*.SAV")):
    os.remove(path)

try:
    boot()
    if what == "hp":
        prove_hp()
    elif what == "chat":
        prove_chat()
    else:
        raise SystemExit("unknown proof '%s' (hp or chat)" % what)
finally:
    if game is not None and game.poll() is None:
        game.kill()
    try:
        admin("quit", 1)
    except Exception:
        pass
    time.sleep(1.5)
    if srv is not None and srv.poll() is None:
        srv.kill()
    if log is not None:
        log.close()

failed = [name for name, ok, _detail in results if not ok]
print("")
print("%d/%d checks passed%s" % (len(results) - len(failed), len(results),
                                  " (the defect was reproduced as expected)" if expect_defect and not failed else ""))
for name in failed:
    print("   FAILED: " + name)
sys.exit(1 if failed else 0)
