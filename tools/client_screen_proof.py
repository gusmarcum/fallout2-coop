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
  sheet  bugs/035 (GitHub issues 3 and 11). The recorded keyboard opens the character
         sheet with C and closes it with C three seconds later, then Options with O and
         Enter, then the skilldex with S and S, over and over, before and during a fight.
         Each sheet must stay up until its own C (timed from the server's sheetopen/
         sheetclose lines), and the Enter must close Options, not reach the fight as "end
         combat". The fixed client also logs who closed each screen, and when.
  invhp  GitHub issue 9. The second player opens the inventory and keeps it open; the
         operator puts them at 1 hit point. The counter must turn red while the screen is
         still up (read off the screenshots as in `hp`).
  clock  GitHub issue 10. The second player, at 1 hit point, opens the pipboy on its alarm
         clock and keeps it open; the operator rests the party six hours. The date and
         clock at the top of the pipboy, and the alarm clock's own "Hit Points" line, must
         be redrawn while it is still up (the screenshots' areas must change).
  hands  GitHub issue 7 (bugs/037). Both hands are empty. The keyboard presses B three
         times a quarter second apart, every three seconds, in peace and then in a fight.
         Every press must reach the server: the old client waited 1.2 s after each swap
         for an animation that never plays, so the second and third press were eaten.
  fidget GitHub issue 15 (bugs/036). The keyboard opens and closes the inventory once (that
         is what turns the client's idle fidget on) and then presses G five times a second
         for a hundred seconds. Every press must reach the server: on the old client a
         fidget of the player's own character blocked input until it finished.
  cancelui  GitHub issue 12 (bugs/044), the screen's half. With points to spend, the
         keyboard opens the sheet, selects Small Guns (Tab), buys three points (Right) and
         leaves with C (vanilla's Cancel); then buys two and leaves with Enter (Done); then
         buys one and a fight starts under the open sheet. The server's row must be back
         after the Cancel, keep the Done's two, and (since the v1.4.0 follow-up) be back
         again after the fight closed the screen: only Done keeps.
  npcloot  GitHub issue 13, follow-up. A spear lies on the ground and a fight pulls the
         unarmed Arroyo villagers in; one of their weapon hunts takes the spear. The second
         player's real client (event trace on) must mirror the spear in that critter's
         hand, so it is drawn armed and its corpse lists the spear for looting. The server
         log must show no crouch shipped for an attempt a critter had no AP for.
  createui  GitHub issue 14 (bugs/043), the screen's half. A new player rolls a character
         on the real creation screen, keyboard only: female (S, Right, Enter), 30 (A, Up
         x5, Enter), five points into Strength, three tagged skills, Done. The line the
         client sends and the character the server builds must both say female and 30.

--expect-defect inverts the verdict, to show the defect on a build older than the fix.

Nothing here reads or writes a live world: point it at a sandbox copy. It empties that
folder's save slots and working maps before it starts. Needs Pillow for hp, invhp, clock.

usage: python -u client_screen_proof.py <hp|chat|sheet|invhp|clock|hands|fidget|cancelui|createui|npcloot>
                                        <f2_server.exe> <fallout2-ce.exe> <game dir> <net port>
                                        <cmd port> [--expect-defect] [--keep <dir>]
"""
import glob, os, re, shutil, socket, struct, subprocess, sys, threading, time

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
KEY_C, KEY_O, KEY_I, KEY_P = 6, 18, 12, 19
KEY_A, KEY_B, KEY_G, KEY_S, KEY_TAB, KEY_Z = 4, 5, 10, 22, 43, 29
KEY_RIGHT, KEY_LEFT, KEY_DOWN, KEY_UP = 79, 80, 81, 82
EVENT_COMBAT_ENTER, EVENT_COMBAT_EXIT = 12, 13
logpath = os.path.join(gamedir, "client-screen-proof-server.log")
clientlogpath = os.path.join(gamedir, "client-screen-proof-client.log")
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
    """The host's seat: a wire client that logs in and can end its combat turns. It also
    timestamps the fight's start and end events as they arrive, so a check can ask whether
    a fight was really on at a given moment (the server log does not say)."""

    def __init__(self):
        self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.buf = bytearray()
        self.pos = 10  # past the "F2NS" stream header
        self.combat = []  # (wall time, True = COMBAT_ENTER / False = COMBAT_EXIT)
        threading.Thread(target=self.drain, daemon=True).start()

    def drain(self):
        while True:
            try:
                data = self.s.recv(65536)
                if not data:
                    return
            except Exception:
                return
            self.buf += data
            self.scan()

    def scan(self):
        """Frame: 18-byte header (u32 seq, u32 sim, u32 payload length, u16 count, u32
        entry base). Event: u8 type, u8 flags, u16 length, body."""
        if len(self.buf) < 10 or self.buf[:4] != b"F2NS":
            return
        now = time.time()
        while self.pos + 18 <= len(self.buf):
            length = struct.unpack_from("<I", self.buf, self.pos + 8)[0]
            if self.pos + 18 + length > len(self.buf):
                return
            payload = bytes(self.buf[self.pos + 18:self.pos + 18 + length])
            self.pos += 18 + length
            ep = 0
            while ep + 4 <= len(payload):
                etype, _flags, elen = struct.unpack_from("<BBH", payload, ep)
                if etype in (EVENT_COMBAT_ENTER, EVENT_COMBAT_EXIT):
                    self.combat.append((now, etype == EVENT_COMBAT_ENTER))
                ep += 4 + elen

    def fighting(self, t0, t1):
        """True when a fight was on for the whole of [t0, t1]."""
        state = False
        for when, entered in self.combat:
            if when <= t0:
                state = entered
        return state and not any(t0 < when <= t1 and not entered for when, entered in self.combat)

    def fight_started_after(self, t0):
        return next((when for when, entered in self.combat if entered and when > t0), None)

    def send(self, line, wait):
        self.s.sendall((line + NL).encode())
        time.sleep(wait)

    def objects(self):
        """(netId, pid, tile, elevation) of every object the join snapshot carried."""
        data = bytes(self.buf)
        rows = []
        pos = 10
        while pos + 18 <= len(data):
            length = struct.unpack_from("<I", data, pos + 8)[0]
            if pos + 18 + length > len(data):
                break
            payload = data[pos + 18:pos + 18 + length]
            pos += 18 + length
            ep = 0
            while ep + 4 <= len(payload):
                etype, _flags, elen = struct.unpack_from("<BBH", payload, ep)
                if etype in (1, 8) and elen >= 16:
                    rows.append(struct.unpack_from("<iiii", payload, ep + 4))
                ep += 4 + elen
        return rows


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
    # The client's stderr goes to a file: with F2_TRACE_EVENTS it carries the mirror's
    # inventory lines ([inv-apply]), which the npcloot proof reads.
    return subprocess.Popen([client_exe], cwd=gamedir, env=env,
                            stdout=subprocess.DEVNULL, stderr=open(clientlogpath, "w"))


def client_stderr():
    try:
        return open(clientlogpath, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


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


def write_keys(presses):
    """The recorded keyboard: each (frame, scancode) is a press and a release 3 frames on."""
    events = []
    for at, key in presses:
        events.append((at, key, 1))
        events.append((at + 3, key, 0))
    with open(tracepath, "w") as trace:
        for at, key, down in sorted(events):
            trace.write("K %d %d %d%s" % (at, key, down, NL))


class LogFollower:
    """Timestamps the server log's lines as they are written: the log has no clock, and
    how long a screen stayed open is the whole question for `sheet`."""

    def __init__(self):
        self.lines = []
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        with open(logpath, encoding="utf-8", errors="replace") as stream:
            pending = ""
            while not self.stop:
                chunk = stream.read()
                if not chunk:
                    time.sleep(0.05)
                    continue
                pending += chunk
                *complete, pending = pending.split(NL)
                now = time.time()
                self.lines.extend((now, line) for line in complete)


def sheet_spans(lines, slot):
    """(opened, closed) wall times of each of the slot's character sheets, server side."""
    spans = []
    opened = None
    for when, line in lines:
        if "control sheetopen slot=%d" % slot in line:
            opened = when
        elif "control sheetclose slot=%d" % slot in line and opened is not None:
            spans.append((opened, when))
            opened = None
    return spans


def client_debug_log():
    path = os.path.join(gamedir, "debug.log")
    return open(path, encoding="utf-8", errors="replace").read() if os.path.exists(path) else ""


def host_tile(text):
    rows = re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=(-?\d+) pid=\S+ tile=(-?\d+)", text)
    return int(rows[-1][1])


def prove_sheet():
    global game
    # One cycle: C opens the sheet, C closes it 3 s later, O opens Options, Enter closes it
    # 3 s later (60 frames a second). Two cycles in peace, then a quiet gap in which the
    # fight is started, so it never starts under an open screen (that close is the game's,
    # and the Enter meant for Options would then land in the fight), then cycles again.
    # The skilldex (S, closed by S) rides along in every cycle, 700 frames long.
    presses = []
    for start in [300, 1000] + list(range(2400, 60000, 700)):
        presses += [(start, KEY_C), (start + 180, KEY_C), (start + 220, KEY_O), (start + 400, KEY_ENTER),
                    (start + 440, KEY_S), (start + 620, KEY_S)]
    write_keys(presses)

    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    follower = LogFollower()
    started = time.time()
    game = join({"F2_INPUT_REPLAY": tracepath})
    time.sleep(28.5)  # both peace cycles are over by frame 1623, about 27 s in; the spawn below
    # refreshes every client's world, which closes whatever screen is open, so it waits for that
    peace_end = time.time()
    aggro_at = time.time()
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(logtext()) + 3), 1.0)
    admin("aggro 1", 1.0)
    mark = len(logtext())
    while time.time() < started + 66:
        time.sleep(2.5)
        host.send("cendturn", 0.2)
    fight_end = time.time()
    fight = logtext()[mark:]
    alive = leave(game)
    game = None
    follower.stop = True
    os.remove(tracepath)

    fight_start = host.fight_started_after(aggro_at)
    spans = sheet_spans(follower.lines, 1)
    peace = [closed - opened for opened, closed in spans if closed <= peace_end]
    during = [closed - opened for opened, closed in spans
              if fight_start is not None and opened > fight_start and host.fighting(opened, closed)]
    check("out of combat the sheet stays up until its own C (the keyboard recording works)",
          len(peace) >= 2 and all(held >= 2.0 for held in peace), " ".join("%.1fs" % held for held in peace))
    check("a fight started (the server said so on the wire)", alive and "placed 1/1" in out
          and fight_start is not None, out[:70])
    if not expect_defect:
        check("and it lasted the whole window", fight_start is not None and host.fighting(fight_start, fight_end),
              "fight %.1fs .. %.1fs after the client started" % ((fight_start or started) - started, fight_end - started))
    fixed("during the fight each character sheet stays up until the player's C",
          len(during) >= 2 and all(held >= 2.0 for held in during),
          "held " + " ".join("%.1fs" % held for held in during))
    ended = sum(1 for line in fight.splitlines() if "cendcombat" in line and "slot=1" in line)
    fixed("the Enter that closes Options never reaches the fight as 'end combat'", ended == 0,
          "%d requests" % ended)
    if not expect_defect:
        debug = client_debug_log()
        by_game = re.findall(r"(?:options|character sheet|skilldex): closed after (\d+) ms by the game", debug)
        for screen in ("options", "skilldex"):
            by_player = re.findall(r"%s: closed after (\d+) ms by the player" % screen, debug)
            check("the client says each %s screen was closed by the player, after seconds" % screen,
                  len(by_player) >= 4 and all(int(ms) >= 2000 for ms in by_player) and not by_game,
                  "%d closes: %s ms; %d screens closed by the game" % (len(by_player), " ".join(by_player[:8]),
                                                                        len(by_game)))


def prove_invhp():
    global game
    write_keys([(420, KEY_I)])  # open the inventory once and never close it
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    drop_screenshots()
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_VIEWER_SHOT_EVERY": "40"})
    time.sleep(14)
    before = screenshots()  # the inventory has been open since frame 420 (7 s)
    admin("kill 1", 2.0)
    out = admin("revive 1", 2.0)
    check("the second player is put at 1 hit point", "back at 1 HP" in out, out[:80])
    time.sleep(6)
    alive = leave(game)
    game = None
    os.remove(tracepath)
    debug = client_debug_log()
    check("the inventory opened and was still open when the client stopped",
          alive and "inventory: screen up" in debug and "inventory: closed" not in debug)
    shots = screenshots()
    late = shots[-4:]
    verdicts = [counter_is_red(path) for path in late]
    red = sum(1 for is_red, _r, _w in verdicts if is_red)
    fixed("with the inventory still open, the counter shows the new hit points (red: 1)",
          len(late) == 4 and red == len(late), "%d of %d late screenshots show a red counter" % (red, len(late)))
    if not expect_defect and len(before) >= 2 and late:
        # The inventory's own stats panel prints the hit points too: steady before, and
        # different once the hit points changed, with the screen still open.
        steady = summary_area(before[-1]) == summary_area(before[-2])
        moved = summary_area(late[-1]) != summary_area(before[-1])
        check("the inventory's own stats panel shows the change too (steady before, redrawn after)",
              steady and moved, "steady before: %s, changed after: %s" % (steady, moved))
    drop_screenshots()


def summary_area(path):
    """The inventory's stats panel: the window is 499x377, centred on the screen, and the
    panel is at x 297..440, y 44..232 inside it."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    left, top = (w - 499) // 2, (h - 377) // 2
    return im.crop((left + 297, top + 44, left + 440, top + 232)).tobytes()


def clock_area(path):
    """The pipboy's date and clock strip: the window is 640x480, centred on the screen,
    and the day/month/year/time digits sit at y 17 from x 20 to about x 200."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    left, top = (w - 640) // 2, (h - 480) // 2
    return im.crop((left + 15, top + 12, left + 205, top + 32)).tobytes()


def prove_clock():
    global game
    # The second player joins once so the operator can put them at 1 hit point (kill +
    # revive, the hp proof's recipe), then joins again with Z pressed at frame 420: the
    # pipboy opens straight on its alarm clock, whose "Hit Points 1/N" line sits above the
    # rest options, and never closes. The operator then rests six hours (one heal step).
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({})
    time.sleep(9)
    leave(game)
    game = None
    admin("kill 1", 2.0)
    out = admin("revive 1", 2.0)
    check("the second player is put at 1 hit point", "back at 1 HP" in out, out[:80])

    # P at frame 900 opens the pipboy (a second join of the same character takes the
    # client longer to reach its main loop than the first, so later than the other
    # proofs' presses), and a mouse click on its alarm clock button brings up the rest
    # options with the "Hit Points" line, the way the reporter gets there. The mouse
    # trace is relative: pin the cursor in the corner first, then move onto the button
    # (window-relative (124, 13), the window centred on the 1280x720 screen).
    write_keys([(900, KEY_P)])
    with open(tracepath, "a") as trace:
        trace.write("M 1020 -5000 -5000 0%sM 1030 %d %d 0%sM 1040 0 0 1%sM 1046 0 0 0%s"
                    % (NL, (1280 - 640) // 2 + 124 + 8, (720 - 480) // 2 + 13 + 6, NL, NL, NL))
    drop_screenshots()
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_VIEWER_SHOT_EVERY": "30"})
    time.sleep(26)
    before = screenshots()
    debug = client_debug_log()
    # The fixed client says which tab is up; an older one has no such line, so the
    # screenshots decide: the Hit Points line's strip is no longer the world drawn there
    # before the press (the pipboy opens at frame 900, the early screenshots predate it).
    logged = "pipboy: screen up" in debug and "pipboy: alarm clock up" in debug and "pipboy: closed" not in debug
    drawn = len(before) >= 6 and hp_line_area(before[-1]) != hp_line_area(before[2])
    check("the pipboy is up on its alarm clock",
          drawn and (logged or expect_defect),
          (re.findall(r"pipboy: [^\n]*", debug) or ["no pipboy line in the client's log (older client)"])[-1])
    out = admin("rest 360 1", 3.0)  # slot 1: the reply reports the second player's hit points
    time.sleep(6)
    alive = leave(game)
    game = None
    os.remove(tracepath)
    after = screenshots()
    check("the second player's client ran throughout", alive and len(before) >= 3 and len(after) > len(before) + 2,
          "%d then %d screenshots" % (len(before), len(after)))
    healed = re.findall(r"hp (\d+) -> (\d+)", out)
    check("the operator's rest passed six hours and healed the second player",
          "rest" in out.lower() and healed and int(healed[0][1]) > int(healed[0][0]), out[-60:])
    steady = clock_area(before[-1]) == clock_area(before[-2])
    check("the pipboy was up and still before the rest (its clock strip did not move)", steady)
    changed = clock_area(after[-1]) != clock_area(before[-1])
    # The clock redraw shipped in v1.4.0 (bugs/038): a plain check on both builds.
    check("the pipboy redrew its date and clock after the rest, while still open", changed)
    # The alarm clock's own "Hit Points" line (GitHub issue 10, follow-up): steady before
    # the rest, and showing the new number after it, with the pipboy still up. v1.4.0
    # redrew it only when a rest option was clicked, so it showed the heal one rest late.
    hp_steady = hp_line_area(before[-1]) == hp_line_area(before[-2])
    check("the alarm clock's Hit Points line was up and still before the rest", hp_steady)
    hp_changed = hp_line_area(after[-1]) != hp_line_area(before[-1])
    redrawn = re.findall(r"pipboy: alarm clock hit points line redrawn: \d+/\d+", client_debug_log())
    fixed("the alarm clock's Hit Points line shows the heal while the pipboy is still open",
          hp_changed and (expect_defect or bool(redrawn)), (redrawn or ["no redraw line in the client's log"])[-1])
    drop_screenshots()


def hp_line_area(path):
    """The pipboy alarm clock's "Hit Points cur/max" line: the window is 640x480, centred
    on the screen, and the line is drawn at y 66 from x 254 to x 604 inside it."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    left, top = (w - 640) // 2, (h - 480) // 2
    return im.crop((left + 254, top + 63, left + 604, top + 79)).tobytes()


def bursts(times, gap=1.0):
    """Group sorted times into bursts: a new burst after a silence longer than `gap`."""
    groups = []
    for when in sorted(times):
        if groups and when - groups[-1][-1] <= gap:
            groups[-1].append(when)
        else:
            groups.append([when])
    return groups


def prove_hands():
    global game
    # B, B, B a quarter second apart, every 3 s: frames 420..1500 in peace, 2400..4800 in a fight.
    presses = []
    for start in list(range(420, 1500, 180)) + list(range(2400, 4800, 180)):
        presses += [(start, KEY_B), (start + 15, KEY_B), (start + 30, KEY_B)]
    write_keys(presses)

    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    follower = LogFollower()
    started = time.time()
    game = join({"F2_INPUT_REPLAY": tracepath})
    time.sleep(28.0)  # the peace bursts end at frame 1530, about 26 s in
    peace_end = time.time()
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(logtext()) + 3), 1.0)
    admin("aggro 1", 1.0)
    while time.time() < started + 84:
        time.sleep(2.5)
        host.send("cendturn", 0.2)
    alive = leave(game)
    game = None
    follower.stop = True
    os.remove(tracepath)

    # Out of combat the server applies a swap at once and logs oldCode/newCode; in combat it
    # queues it for the player's turn and logs that. Anything in the first 6 s is the join's
    # own `hand` line, not a press.
    peace = [when for when, line in follower.lines
             if re.search(r"control hand=\d slot=1 oldCode=0 newCode=0", line) and started + 6 < when <= peace_end]
    fight = [when for when, line in follower.lines if "queued (combat, slot=1)" in line]
    peace_bursts = [len(group) for group in bursts(peace)]
    fight_bursts = [len(group) for group in bursts(fight)]
    check("both hands are empty and the swaps reached the server", alive and len(peace_bursts) >= 4,
          "peace bursts %s" % peace_bursts)
    check("a fight started", "placed 1/1" in out and host.fight_started_after(peace_end) is not None, out[:60])
    fixed("out of combat every press of a burst goes through (3 of 3)",
          len(peace_bursts) >= 4 and all(size == 3 for size in peace_bursts), "bursts %s" % peace_bursts)
    fixed("in the fight, on the player's turn, every press of a burst goes through (3 of 3)",
          len(fight_bursts) >= 1 and max(fight_bursts) == 3, "bursts %s" % fight_bursts)


def prove_fidget():
    global game
    # Open and close the inventory once: closing a screen turns the client's idle fidget on.
    # Then G five times a second for 100 s.
    presses = [(300, KEY_I), (330, KEY_I)] + [(at, KEY_G) for at in range(600, 6600, 12)]
    write_keys(presses)
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    follower = LogFollower()
    game = join({"F2_INPUT_REPLAY": tracepath})
    time.sleep(115)
    alive = leave(game)
    game = None
    follower.stop = True
    os.remove(tracepath)

    times = sorted(when for when, line in follower.lines if "control gethere" in line)
    gaps = [later - earlier for earlier, later in zip(times, times[1:])]
    long_gaps = [gap for gap in gaps if gap > 0.7]
    check("the G presses reached the server for the whole run", alive and len(times) >= 300,
          "%d presses received" % len(times))
    fixed("no press was held up: no silence over 0.7 s between two presses (G is sent every 0.2 s)",
          len(times) >= 300 and not long_gaps,
          "longest %.2f s; %d silences over 0.7 s: %s" % (max(gaps) if gaps else 0, len(long_gaps),
                                                          " ".join("%.1f" % gap for gap in long_gaps[:8])))


def unspent(slot):
    found = re.findall(r"unspent (-?\d+)", admin("sheet %d" % slot, 0.3))
    return int(found[0]) if found else None


def prove_cancelui():
    global game
    # Phase A: C, Tab x7 (Small Guns), Right x3, C (Cancel).
    # Phase B: C, Right x2, Enter (Done). Phase C: C, Right x1, and a fight starts under it.
    presses = [(900, KEY_C)] + [(930 + 10 * i, KEY_TAB) for i in range(7)]
    presses += [(1010, KEY_RIGHT), (1020, KEY_RIGHT), (1030, KEY_RIGHT), (1080, KEY_C)]
    presses += [(1320, KEY_C), (1350, KEY_RIGHT), (1360, KEY_RIGHT), (1410, KEY_ENTER)]
    presses += [(1680, KEY_C), (1710, KEY_RIGHT)]
    write_keys(presses)

    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({"F2_INPUT_REPLAY": tracepath})
    time.sleep(9.0)
    admin("sp 1 20", 1.0)  # well before frame 900: points to spend
    before = unspent(1)

    # Each reading waits for the server to see that visit end. The client counts frames
    # more slowly while it starts up, so wall-clock readings would race the keyboard.
    def wait_for(pattern, count, timeout=40.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if len(re.findall(pattern, logtext())) >= count:
                return True
            time.sleep(0.3)
        return False

    wait_for(r"control sheetclose slot=1", 1)  # phase A over (C = Cancel)
    after_cancel = unspent(1)
    wait_for(r"control sheetclose slot=1", 2)  # phase B over (Enter = Done)
    after_done = unspent(1)
    wait_for(r"control skillup slot=1 skill=0 rc=0", 6)  # phase C's point is in, sheet still open
    time.sleep(0.5)
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(logtext()) + 3), 1.0)
    admin("aggro 1", 1.0)
    wait_for(r"control sheetclose slot=1", 3)  # the game closed it
    after_fight = unspent(1)
    alive = leave(game)
    game = None
    os.remove(tracepath)

    text = logtext()
    ups = len(re.findall(r"control skillup slot=1 skill=0 rc=0", text))
    cancels = len(re.findall(r"control sheetcancel slot=1 rc=0", text))
    debug = client_debug_log()
    check("the keyboard bought six points in Small Guns across the three visits", alive and ups == 6,
          "%d points bought; unspent before %s" % (ups, before))
    # Cancel itself shipped in v1.4.0 (bugs/044): a plain check on both builds. The cancel
    # count is read at the end, after the forced close below has sent its own.
    check("Cancel (C) put the three points back",
          before is not None and after_cancel == before and cancels >= 1,
          "unspent %s -> %s after Cancel; %d cancels sent in all" % (before, after_cancel, cancels))
    check("Done (Enter) kept its two points",
          after_cancel is not None and after_done == after_cancel - 2, "unspent %s -> %s" % (after_cancel, after_done))
    # Since the v1.4.0 follow-up a close the game forces is a Cancel too: the fight that
    # closed the open sheet puts its one point back (v1.4.0 kept it: "closed by the game,
    # no Cancel sent").
    closed_by_game = re.findall(r"character sheet: closed after \d+ ms by the game[^\n]*", debug)
    check("the game closed the sheet when the fight started",
          bool(closed_by_game), (closed_by_game or ["no close by the game logged"])[0])
    fixed("the fight that closed the open sheet put its one point back (a forced close is a Cancel)",
          after_done is not None and after_fight == after_done and cancels == 2,
          "unspent %s -> %s; %d cancels sent" % (after_done, after_fight, cancels))


def prove_createui():
    global game
    # On the creation screen (the frame count starts when it opens): S, Right, Enter = female;
    # A, Up x5, Enter = 30; Right x5 = Strength 10 (all five points); Tab x4 to the skills,
    # then Right, Down, Right, Down, Right = three tags; Enter = Done, Enter = yes to the
    # "you have not named your character" box.
    # Everything 300 frames later than the screen's first frame, in case the client pumps
    # input while it starts up (the frame count starts with the process, not the screen).
    base = 420
    presses = [(base, KEY_S), (base + 30, KEY_RIGHT), (base + 60, KEY_ENTER)]
    presses += [(base + 100, KEY_A)] + [(base + 130 + 10 * i, KEY_UP) for i in range(5)] + [(base + 200, KEY_ENTER)]
    presses += [(base + 240 + 10 * i, KEY_RIGHT) for i in range(5)]
    presses += [(base + 320 + 10 * i, KEY_TAB) for i in range(4)]
    presses += [(base + 380, KEY_RIGHT), (base + 400, KEY_DOWN), (base + 420, KEY_RIGHT), (base + 440, KEY_DOWN),
                (base + 460, KEY_RIGHT)]
    presses += [(base + 500, KEY_ENTER), (base + 560, KEY_ENTER)]
    write_keys(presses)

    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_PLAYER_NAME": "Sister", "F2_PLAYER_CREATE": "ask"})
    time.sleep(30)
    alive = leave(game)
    game = None
    os.remove(tracepath)

    debug = client_debug_log()
    sent = re.findall(r"client-viewer: created character -> create ([-\d ]+)", debug)
    made = re.findall(r"\[create\] slot=(\d+) SPECIAL:([ \d]+) maxhp=\d+ hp=\d+(.*)", logtext())
    check("the creation screen was finished and the character created", alive and len(sent) == 1 and len(made) == 1,
          "sent %r; server %r" % (sent[:1], made[:1]))
    numbers = sent[0].split() if sent else []
    fixed("the line the creation screen sends ends with female (1) and 30",
          len(numbers) == 14 and numbers[-2:] == ["1", "30"], repr(sent[:1]))
    fixed("the server built her female, 30, in the female body",
          len(made) == 1 and "gender=1 age=30" in made[0][2] and "fid=0x1000004" in made[0][2], repr(made[:1]))


def prove_npcloot():
    global game
    # A spear on the ground, a raider set on the host past it, and the fight that pulls the
    # unarmed Arroyo villagers in: their weapon hunts walk them to the spear and one of
    # them takes it (bugs/042). The second player's REAL client watches with its event
    # trace on: its mirror of that critter must list the spear in hand once the server
    # says so, so the critter is drawn armed and its corpse, the same object, lists the
    # spear for looting. v1.4.0's mirror ignored a stack it never had (an invisible spear,
    # a corpse without it). The server log also says whether any critter shipped a crouch
    # at a spear it had no AP to walk to (the follow-up's "animation loop").
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({"F2_TRACE_EVENTS": "1"})
    time.sleep(12)
    start = host_tile(logtext())
    admin("give 7", 0.5)
    admin("drop 7", 1.0)
    dropped = re.findall(r"CONNECT net=(\d+) pid=7 tile=%d " % start, logtext())
    spear = int(dropped[-1]) if dropped else -1
    admin("warp 6", 1.0)
    mark = len(logtext())
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(logtext()) + 3), 1.5)
    spawned = re.findall(r"\[evt\] SPAWN\s+net=(\d+) pid=16777454", logtext()[mark:])
    raider = int(spawned[-1]) if spawned else -1
    admin("aggro 1", 1.0)
    # The raider pulls the unarmed Arroyo villagers into the fight, and every one of them
    # hunts the spear: whoever walks up to it takes it. The host ends its turns.
    taker = None
    deadline = time.time() + 75
    while time.time() < deadline:
        time.sleep(2.5)
        host.send("cendturn", 0.2)
        found = re.findall(r"\[cpickup\] critter=(\d+) item_net=%d taken" % spear, logtext())
        if found:
            taker = int(found[0])
            break
    time.sleep(5)  # the delta with the spear in hand reaches the client
    fight = logtext()[mark:]
    alive = leave(game)
    game = None
    mirror = client_stderr()

    check("a spear lay where the host stood and a raider was set on the host",
          alive and spear > 0 and raider > 0 and "placed 1/1" in out,
          "spear net %d, raider net %d; %s" % (spear, raider, out[:50]))
    check("a critter's weapon hunt took the spear (server)", taker is not None,
          "taken by net %s; attempts: %s" % (taker, "; ".join(re.findall(r"\[cpickup\] [^\n]*", fight)[-3:])))
    skipped = len(re.findall(r"reach check already failed", fight))
    refused = len(re.findall(r"\[cpickup\] critter=\d+ item_net=%d NOT attempted" % spear, fight))
    crouches = len(re.findall(r"reach check already failed\n\[presseq\] SEND ops=\d+ bytes=\d+ actor=\d+", fight))
    if refused + skipped >= 1:
        fixed("no crouch was shipped for an attempt a critter had no AP for (v1.4.0 shipped one per attempt)",
              skipped == 0 and crouches == 0,
              "%d attempts refused for lack of AP; %d old-style skips, %d of them followed by a shipped sequence"
              % (refused, skipped, crouches))
    rows = re.findall(r"\[inv-apply\] net=%d items=(\d+) rhandPid=(-?\d+)" % (taker if taker is not None else -1), mirror)
    fixed("the second player's mirror lists the spear in the taker's hand once it was taken",
          taker is not None and any(hand == "7" for _n, hand in rows),
          "mirror rows for net %s (items, right hand): %s" % (taker, rows[-6:]))


def prove_lvlup():
    global game
    # Issue 21, the client's half: the second player's real client plays the level-up
    # sound itself when its own sheet row says its level rose, and logs it.
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({})
    time.sleep(12)
    out = admin("xp 1 80000", 4.0)
    alive = leave(game)
    game = None
    debug = client_debug_log()
    lines = re.findall(r"client_net: level-up sound \(level \d+ -> \d+\)", debug)
    check("the second player was given experience while in the game", alive and "xp" in out.lower(), out[:60])
    fixed("the client played the level-up sound for its own level", len(lines) >= 1,
          lines[-1] if lines else "no level-up sound line in the client's log")


def prove_dialogdots():
    global game
    # Issue 23: an observer's dialog options opened with two bullets, the server's own
    # prefix plus one the viewer added. The host talks to Mynoc (script 10) through the
    # debug port; the second player's real client watches the node and logs each option
    # text it displays.
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({})
    time.sleep(12)
    out = admin("dtalk 10", 4.0)
    time.sleep(3)
    admin("dend", 1.0)
    alive = leave(game)
    game = None
    raw = open(os.path.join(gamedir, "debug.log"), "rb").read() if os.path.exists(os.path.join(gamedir, "debug.log")) else b""
    options = re.findall(rb'client_dialog: option \d+ "([^"\n]*)"', raw)
    check("the observer's client displayed a dialog node with options", alive and len(options) >= 1,
          "%d options; dtalk said %r" % (len(options), out[:50]))
    single = [o for o in options if len(o) >= 3 and o[0] == 0x95 and o[1] == 0x20 and o[2] != 0x95]
    double = [o for o in options if len(o) >= 2 and o[0] == 0x95 and o[1] == 0x95]
    fixed("every option on the observer's screen opens with one bullet, not two",
          len(options) >= 1 and len(single) == len(options) and not double,
          "%d of %d single, %d double; first %r" % (len(single), len(options), len(double), options[:1]))


def prove_stealgear():
    global game
    # Issue 27: on an observer's screen, the thief's worn armor and held weapon were plain
    # items in the steal screen's left list. A viewer rebuilds its mirror of the thief's
    # whole pack from each inventory delta of the session, and that rebuild dropped the
    # in-hand and worn flags the screens hide equipped gear by. Here the host holds a
    # spear, has its Steal skill raised, walks up to Mynoc and takes his spear; the second
    # player's real client (event trace on) logs its rebuilt mirror of the thief's pack.
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({"F2_TRACE_EVENTS": "1"})
    time.sleep(12)
    admin("give 7", 0.5)  # a spear...
    admin("wield 1", 1.0)  # ...held in the right hand (the debug verb wields the first weapon carried)
    admin("sp 0 99", 0.5)  # points for the Steal skill, so the take succeeds
    host.send("sheetopen", 0.3)
    for _ in range(99):
        host.send("skillup 10", 0.02)
    host.send("sheetclose", 1.0)
    admin("give 51", 0.5)  # a stick of dynamite to plant: the thief's pack changes mid-session
    text = logtext()
    host_net = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=(\d+) ", text)[-1])
    mark = len(text)
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(text) + 2), 1.5)
    spawned = re.findall(r"\[evt\] SPAWN\s+net=(\d+) pid=16777454", logtext()[mark:])
    raider = int(spawned[-1]) if spawned else -1
    steal = re.findall(r"control skillup slot=0 skill=10 rc=0 value=(\d+)", logtext())
    host.send("skill %d 10" % raider, 6.0)  # Steal, walk-then-act
    opened = "steal session OPEN thief=net%d" % host_net in logtext()
    host.send("splant 51 1", 3.0)  # the thief's pack changes: the observer rebuilds its mirror of it
    host.send("sdone", 2.0)
    alive = leave(game)
    game = None
    server = logtext()
    planted = "control splant pid=51" in server
    caught = re.findall(r"steal session CLOSE thief=net%d caught=(\d)" % host_net, server)
    rows = re.findall(r"\[inv-full\] net=%d items=(\d+) worn=(\d+) held=(\d+)" % host_net, client_stderr())
    check("the host held a spear, a raider stood beside it, and a steal session opened for everyone",
          alive and raider > 0 and opened, "raider net %d; Steal skill %s; session opened %s" % (raider, steal[-1:], opened))
    check("the thief planted the dynamite without being caught, so the session stayed open for it",
          planted and caught and caught[0] == "0", "plant sent %s; caught %s" % (planted, caught[:1]))
    fixed("the observer's rebuilt mirror of the thief's pack keeps the in-hand flag of the held spear",
          len(rows) >= 1 and int(rows[-1][2]) >= 1,
          "mirror rows (items, worn, held): %s" % rows[-4:])


def prove_musicline():
    # Issue 18. The music watchdog's "Music 'X' could not be restarted (see debug.log)"
    # line in the message window is gone: the string is no longer in the client, and
    # the quiet log line that replaced it is.
    raw = open(client_exe, "rb").read()
    old = b"could not be restarted (see debug.log)"
    new = b"could not be restarted (rc=%d); will keep trying"
    fixed("the client no longer carries the message-window line", old not in raw and new in raw,
          "old line present %s, log line present %s" % (old in raw, new in raw))
    if expect_defect:
        check("the old client carried it", old in raw)


KEY_DOWN_ARROW = 81


class Bot:
    """A second wire seat that can answer a yes/no prompt (the trade proposal)."""

    def __init__(self, name):
        self.name = name
        self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.buf = bytearray()
        threading.Thread(target=self.drain, daemon=True).start()

    def drain(self):
        while True:
            try:
                data = self.s.recv(65536)
                if not data:
                    return
            except Exception:
                return
            self.buf += data

    def send(self, line, wait):
        self.s.sendall((line + NL).encode())
        time.sleep(wait)

    def events(self, wanted):
        data = bytes(self.buf)
        bodies = []
        pos = 10
        while pos + 18 <= len(data):
            length = struct.unpack_from("<I", data, pos + 8)[0]
            if pos + 18 + length > len(data):
                break
            payload = data[pos + 18:pos + 18 + length]
            pos += 18 + length
            ep = 0
            while ep + 4 <= len(payload):
                etype, _flags, elen = struct.unpack_from("<BBH", payload, ep)
                if etype == wanted:
                    bodies.append(payload[ep + 4:ep + 4 + elen])
                ep += 4 + elen
        return bodies


def trade_list_area(path):
    """The left list of the trade window (the trading player's pack): the window is
    480x180 at (80, 290) inside the 640x480 dialog frame centred on the screen; the list
    is at x 29..93, three rows of 48 from y 30."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    left = (w - 640) // 2 + 80
    top = (h - 480) // 2 + 290
    return im.crop((left + 29, top + 30, left + 93, top + 30 + 144)).tobytes()


def prove_tradescroll():
    global game
    # Issue 26. The host barters with Tubby, the Den store owner (the debug port opens the
    # conversation, `dbarter` opens the trade), and the real client watches as a second
    # player: every viewer gets the barter screen, only the driver's keys were honoured.
    # The observer presses the down arrow (the list's scroll button sends the same key)
    # while the trade is up; the host carries twelve things, so its list scrolls, and the
    # observer's copy of that list must change with the presses.
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    for pid in (7, 51, 1, 8, 9, 10, 11, 12, 13, 14, 15, 16):
        admin("give %d" % pid, 0.2)
    write_keys([(at, KEY_DOWN_ARROW) for at in range(2400, 5400, 60)])
    drop_screenshots()
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_VIEWER_SHOT_EVERY": "30"})
    time.sleep(10)
    admin("entermap 6", 12.0)  # the Den, business district: Tubby's store
    admin("movdone", 1.0)
    admin("dtalk 47", 4.0)  # Tubby (scripts.lst line 48)
    talking = "[dialog] SEND node" in logtext()
    host.send("dbarter", 6.0)
    opened = "[barter] SEND begin" in logtext()
    before = screenshots()
    time.sleep(45)  # the presses run from frame 2400 to 5400
    after = screenshots()
    host.send("bdone", 1.0)
    host.send("dend", 1.0)
    alive = leave(game)
    game = None
    os.remove(tracepath)
    shots = after[len(before):]
    areas = [trade_list_area(p) for p in shots]
    changes = sum(1 for a, b in zip(areas, areas[1:]) if a != b)
    check("the party reached the Den, the host opened a trade with Tubby, and the observer watched",
          alive and talking and opened, "dialog %s, barter %s, %d screenshots during the trade" % (talking, opened, len(shots)))
    fixed("the observer's copy of the trading player's list scrolled with the presses",
          changes >= 2, "%d changes between consecutive screenshots of the list" % changes)
    drop_screenshots()


for path in glob.glob(os.path.join(gamedir, "data", "SAVEGAME", "SLOT*")):
    shutil.rmtree(path, ignore_errors=True)
for path in glob.glob(os.path.join(gamedir, "data", "MAPS", "*.SAV")):
    os.remove(path)
if os.path.exists(os.path.join(gamedir, "debug.log")):
    os.remove(os.path.join(gamedir, "debug.log"))

try:
    boot()
    if what == "hp":
        prove_hp()
    elif what == "chat":
        prove_chat()
    elif what == "sheet":
        prove_sheet()
    elif what == "invhp":
        prove_invhp()
    elif what == "clock":
        prove_clock()
    elif what == "hands":
        prove_hands()
    elif what == "fidget":
        prove_fidget()
    elif what == "cancelui":
        prove_cancelui()
    elif what == "createui":
        prove_createui()
    elif what == "npcloot":
        prove_npcloot()
    elif what == "lvlup":
        prove_lvlup()
    elif what == "dialogdots":
        prove_dialogdots()
    elif what == "stealgear":
        prove_stealgear()
    elif what == "musicline":
        prove_musicline()
    elif what == "tradescroll":
        prove_tradescroll()
    else:
        raise SystemExit("unknown proof '%s' (hp, chat, sheet, invhp, clock, hands, fidget,"
                         " cancelui, createui or npcloot)" % what)
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
