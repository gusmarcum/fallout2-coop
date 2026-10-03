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
  corpseloot  GitHub issue 13, second follow-up (bugs/060). A raider is given a stick of
         dynamite in a steal session, it is taken off the living raider again with no
         session open (the observer's copy of a living critter's pack never loses a
         stack), and the raider is killed. The second player's real client must rebuild its
         copy of the corpse's pack at the death, without the dynamite: the old corpse still
         listed it, and taking it answered "That item is gone."
  createui  GitHub issue 14 (bugs/043), the screen's half. A new player rolls a character
         on the real creation screen, keyboard only: female (S, Right, Enter), 30 (A, Up
         x5, Enter), five points into Strength, three tagged skills, Done. The line the
         client sends and the character the server builds must both say female and 30.

  firstjoin  GitHub issue 32 (bugs/058). The ONLY proof here in which no wire bot logs in
         first. The server is started the way start-server.cmd starts it (no admin port)
         and the client the way join.cmd starts it (F2_PLAYER_CREATE=ask, so an `account`
         probe connection first), three times: a new name on a new game through the
         creation screen, the same name again on the now empty and frozen server, and once
         more after the server was restarted from the F6 quicksave. Each time the client
         must be sent the world, log in and draw the game. v1.4.1 never sent it: the black
         screen every first player of a session got.
  heldturn  GitHub issue 16, the real client's half. Two players are in a fight that is
         waiting on the real client; the host leaves and the client is closed, so the
         world freezes with the turn still theirs. They come back alone and press Space.
         Nobody may take a turn before that end of turn is accepted, and their game must
         know the turn is its own (it is announced again after the login).

  lookclick  GitHub issue 31. The real client, alone, has a raider two tiles off, switches
         to the arrow cursor (right-click), starts a fight (A) and clicks on the raider.
         In a fight that click is LOOK, as vanilla's hover icon says; the old client sent
         `talk`, which the server refuses in combat.
  earlyspace  GitHub issue 30. The real client, alone, fights a raider and presses Space
         in pairs half a second apart: the first ends its turn, the second lands while the
         raider's answer is still being shown. No pair may end two turns (the server is
         already waiting on the player by then, and the old client sent the second one).

  reloads  GitHub issues 33 and 34. The real client, alone, holds an empty pistol. It
         cycles the hand slot to reload and clicks it twice: the first click reloads, and
         the second must be the shot's click (vanilla's reload puts the slot back on the
         primary attack), not a second reload. The pistol is emptied again, the inventory
         opened, and the ammo dragged from the list onto the pistol's hand slot, which
         must load it (the viewer's inventory used to skip that drop).

  hpcount  GitHub issue 44 (bugs/069). The real client, alone, has two raiders beside it
         in a fight and ends its turn. The screen is read off screenshots taken every 8
         frames: the hit point counter must not move before the message log shows the
         first line of the enemy phase (the old client counted it down to the END of the
         enemy phase while the first swing was still in the air).

  armorview  GitHub issue 28 (bugs/070). The real client, alone, opens the inventory, drags
         a leather armor onto the armor slot and later back onto the list. The body
         turning in the middle of the screen must show the armor while it is worn and the
         bare body after (the old client drew it one change behind: bare with the armor
         on, armored with it off).

  nightmap  GitHub issue 37 (bugs/071). The real client, alone, sees the Den's west and
         east sides by day, waits on the west side until midnight (it goes dark), crosses
         east and comes back. Both must be drawn dark: the old server never said the
         light level of a freshly loaded map, and the client drew it at full day.

  tradeunload  GitHub issue 38 (bugs/073). The real client, alone, carries a loaded pistol
         to Tubby, clicks the dialog's Barter button, switches to the arrow (right-click)
         and clicks the pistol in its own list (look), holds the button on it and draws
         the cursor down to the menu's Unload, then clicks the first thing in Tubby's
         list. The old client's trade screen ignored every click under the arrow.

  acturn  GitHub issue 24 (bugs/075). Two players in a fight. The real client, on its own
         turn, opens the inventory (4 action points), closes it and ends the turn; the
         other player then holds its turn. The armor class counter must stand still
         through the own turn and show the unspent action points only once it is ended
         (the old client showed them all along, a point less per action point spent).

  syncwalk  Not one fix: all of them, judged by the real client's own copy of the world.
         The real client, alone (the host's seat), goes through arrival, a map change, the
         Den's orphans, midnight and another map change, a fight with a kill, and Modoc.
         After each, the server's audit (every object's fields as the server holds them)
         must match what the client is showing, object for object.

  auditwatch  A probe: the real client beside the Den's orphans, audited every two seconds,
         to tell a lasting difference from one caught mid-change.

  syncwalk2  The same walk with the real client in the other seat: it joins a session a
         wire client hosts, as every player but the first does.

  doorsync  A used door in the client's copy of the map (bugs/077, found by syncwalk): the
         host's actor uses the nearest door in the Den, where people walk all the time,
         and three and six seconds later the client's copy of that door must be the
         server's. Before the fix the slide played and the door's flags stayed those of a
         closed door for as long as anybody on the map was walking. The real client is in
         the host's seat.

  doorsync2  The same with the real client in the other seat, watching another player's
         actor use the door.

  fightprobe  A probe: who fights whom when a raider is put beside the host and set on it
         (PROBE_SEAT, PROBE_WARP and PROBE_SPAWN in the environment).

  corpsesync  A critter killed while its own attacks are still being shown (bugs/078, found
         by syncwalk): a raider attacks the host and the operator kills it one second
         later. Ten seconds on, its corpse in the client's copy must be the server's.
         Before the fix the corpse state landed at the end of the first replay to finish,
         the queued attacks and the death then played over it, and the body was left in
         the animation's last frame, no blood under it, its flat flag toggled back off.
         The real client is in the host's seat.

  corpsesync2  The same with the real client in the other seat.

  oldsave  Saves made by the released servers load on the one under test: each of
         f2_server-v141/v140/v132/v131.exe found in the game folder makes a world (the
         host with experience and a pistol, the party in the Den, the clock run forward,
         somebody killed) and saves it; the server under test is started on that save and
         the real client joins as the saved host. The host must be where and what it was,
         the map must hold as many objects, and the client's copy must match the server's.

  hpcount2  Issue 44 from the second player's seat, where it was reported: the real client
         joins a session a wire client hosts, raiders are set on the host, and while the
         first one's attacks are still being shown the operator lands three blows on the
         real client's own character. The hit point counter must not move before the
         first of those blows is played (the client's log is timestamped: when the blow's
         sequence arrives, and when its turn comes).

  nightmap2  Issue 37 with the real client in the second seat. Both nightmap proofs end
         with the player leaving and joining again at midnight.

--expect-defect inverts the verdict, to show the defect on a build older than the fix.

Nothing here reads or writes a live world: point it at a sandbox copy. It empties that
folder's save slots and working maps before it starts. Needs Pillow for hp, invhp, clock.

usage: python -u client_screen_proof.py <firstjoin|heldturn|hp|chat|sheet|invhp|clock|hands|fidget|cancelui|
                                         createui|npcloot|corpseloot|lvlup|dialogdots|stealgear|musicline|lookclick|earlyspace|reloads|hpcount|armorview|nightmap|
                                         tradeunload|acturn|syncwalk|auditwatch|syncwalk2|doorsync|doorsync2|fightprobe|corpsesync|corpsesync2|oldsave|nightmap2|hpcount2|tradescroll>
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


def unthrottle(proc):
    """Ask Windows to leave a process started here at full speed. The client under test
    has no window, and while another program holds the foreground (somebody playing a
    game on this machine) Windows treats it as background work: its timers go coarse and
    it runs at 36 frames a second instead of 60. The recorded keyboard counts frames, so
    every press then lands late and the proofs that wait a fixed time for one fail,
    on any build. Measured 2026-10-02: 36 a second as started, 58 with this."""
    if os.name != "nt":
        return proc
    try:
        import ctypes

        class PowerThrottling(ctypes.Structure):
            _fields_ = [("Version", ctypes.c_ulong), ("ControlMask", ctypes.c_ulong), ("StateMask", ctypes.c_ulong)]

        # ProcessPowerThrottling (4): control execution speed (1) and timer resolution (4),
        # with neither throttled.
        state = PowerThrottling(1, 0x1 | 0x4, 0)
        ctypes.windll.kernel32.SetProcessInformation(int(proc._handle), 4, ctypes.byref(state), ctypes.sizeof(state))
    except Exception:
        pass
    return proc


def boot():
    global srv, log
    env = clean_env()
    env.update({"F2_SERVER_MAP": "arvillag.map", "F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
                "F2_SERVER_PACE_MS": "100", "F2_AUTOSAVE_SECS": "0", "F2_SERVER_KEEPALIVE": "1",
                "F2_TRACE_EVENTS": "1"})
    log = open(logpath, "w")
    srv = unthrottle(subprocess.Popen([server_exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT))
    time.sleep(7)


def join(extra):
    """Start the real client as the second player. Returns the process."""
    env = clean_env()
    env.update({"F2_CLIENT_CONNECT": "127.0.0.1:%d" % port, "F2_PLAYER_NAME": "Brother",
                "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"})
    env.update(extra)
    # The client's stderr goes to a file: with F2_TRACE_EVENTS it carries the mirror's
    # inventory lines ([inv-apply]), which the npcloot proof reads.
    return unthrottle(subprocess.Popen([client_exe], cwd=gamedir, env=env,
                                       stdout=subprocess.DEVNULL, stderr=open(clientlogpath, "w")))


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
    # The kill can land in the middle of a screenshot being written. Every screenshot of
    # a run is the same size, so one that is not is the one cut short: it would not open.
    shots = screenshots()
    if len(shots) >= 2:
        sizes = [os.path.getsize(path) for path in shots]
        usual = max(set(sizes), key=sizes.count)
        for path, size in zip(shots, sizes):
            if size != usual:
                os.remove(path)
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
    how long a screen stayed open is the whole question for `sheet`. Given another path
    (the client's own log) it does the same for that file."""

    def __init__(self, path=None):
        self.path = path or logpath
        self.lines = []
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        with open(self.path, encoding="utf-8", errors="replace") as stream:
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


EVENT_TURN_START = 14
KEY_SPACE, KEY_F6 = 44, 63


def boot_as_start_server(load_slot=None):
    """The server exactly as start-server.cmd starts it: keepalive, autosaves, a new game
    at the Temple or a slot to load, and NO admin port. The log is appended to, so one
    proof can restart the server and still read the whole story."""
    global srv, log
    env = clean_env()
    env.update({"F2_SERVER_NET": str(port), "F2_SERVER_PACE_MS": "100", "F2_AUTOSAVE_SECS": "300",
                "F2_SERVER_KEEPALIVE": "1", "F2_SERVER_NAME": "Fallout 2 Co-op"})
    if load_slot is None:
        env["F2_SERVER_MAP"] = "artemple.map"
    else:
        env["F2_SERVER_LOAD"] = str(load_slot)
    log = open(logpath, "a")
    srv = unthrottle(subprocess.Popen([server_exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT))
    time.sleep(8)


def stop_server():
    global srv, log
    if srv is not None and srv.poll() is None:
        srv.kill()
        try:
            srv.wait(timeout=10)
        except Exception:
            pass
    srv = None
    if log is not None:
        log.close()
    log = None
    time.sleep(1.5)


def world_lit(path):
    """Share of the world view (everything above the interface bar) that is not black."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    data = list(im.crop((0, 0, w, h - 100)).resize((160, 90)).getdata())
    return sum(1 for r, g, b in data if max(r, g, b) > 40) / float(len(data))


def join_as_join_cmd(name, presses, seconds):
    """Start the real client with join.cmd's settings (F2_PLAYER_CREATE=ask, so it makes
    its `account` probe connection first), let it run, close it. Returns whether it was
    still running, its debug log, the server's log of the visit and its screenshots' share
    of lit world."""
    global game
    drop_screenshots()
    if os.path.exists(os.path.join(gamedir, "debug.log")):
        os.remove(os.path.join(gamedir, "debug.log"))
    mark = len(logtext())
    extra = {"F2_PLAYER_NAME": name, "F2_PLAYER_CREATE": "ask", "F2_VIEWER_SHOT_EVERY": "40"}
    if presses:
        write_keys(presses)
        extra["F2_INPUT_REPLAY"] = tracepath
    game = join(extra)
    time.sleep(seconds)
    alive = leave(game)
    game = None
    if presses:
        os.remove(tracepath)
    shots = screenshots()
    lit = [world_lit(path) for path in shots[len(shots) // 2:]]
    drop_screenshots()
    return alive, client_debug_log(), logtext()[mark:], lit


def creation_keys(base):
    """The creation screen by keyboard, as in createui: female, 30, five points into
    Strength, three tagged skills, Done, and yes to the unnamed-character box."""
    presses = [(base, KEY_S), (base + 30, KEY_RIGHT), (base + 60, KEY_ENTER)]
    presses += [(base + 100, KEY_A)] + [(base + 130 + 10 * i, KEY_UP) for i in range(5)] + [(base + 200, KEY_ENTER)]
    presses += [(base + 240 + 10 * i, KEY_RIGHT) for i in range(5)]
    presses += [(base + 320 + 10 * i, KEY_TAB) for i in range(4)]
    presses += [(base + 380, KEY_RIGHT), (base + 400, KEY_DOWN), (base + 420, KEY_RIGHT), (base + 440, KEY_DOWN),
                (base + 460, KEY_RIGHT)]
    presses += [(base + 500, KEY_ENTER), (base + 560, KEY_ENTER)]
    return presses


def prove_corpseloot():
    global game
    # GitHub issue 13, second follow-up (bugs/060): "if he originally had a spear but he
    # threw it at me and I picked it up, his body will still have a visible loot on client
    # side. But when I try to take it, game says 'This item is gone'." A viewer's copy of a
    # LIVING critter's pack never loses a stack, and the copy was only put right in full by
    # a delta that carried the pack of a dead critter, which the death itself never sent.
    #
    # Here a raider is given a stick of dynamite in a steal session (which the observer's
    # game mirrors in full, the session being open), the session is closed, the dynamite
    # is taken off the living raider again by the operator (no session: the observer's
    # copy keeps it), and the raider is killed. The second player's real client (event
    # trace on) must then rebuild its copy of the corpse's pack from the server's, without
    # the dynamite.
    host = Host()
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({"F2_TRACE_EVENTS": "1"})
    time.sleep(12)
    admin("sp 0 99", 0.5)  # points for the Steal skill, so the plant succeeds
    host.send("sheetopen", 0.3)
    for _ in range(99):
        host.send("skillup 10", 0.02)
    host.send("sheetclose", 1.0)
    admin("give 51", 0.5)  # the stick of dynamite
    admin("warp 8", 1.5)  # away from the second player: the raider must be the nearest critter
    text = logtext()
    host_net = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=(\d+) ", text)[-1])
    mark = len(text)
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(text) + 2), 1.5)
    spawned = re.findall(r"\[evt\] SPAWN\s+net=(\d+) pid=16777454", logtext()[mark:])
    raider = int(spawned[-1]) if spawned else -1
    host.send("skill %d 10" % raider, 6.0)  # Steal, walk-then-act
    opened = "steal session OPEN thief=net%d" % host_net in logtext()
    host.send("splant 51 1", 3.0)
    host.send("sdone", 2.0)
    planted = "control splant pid=51" in logtext()
    during = re.findall(r"\[inv-full\] net=%d items=(\d+) " % raider, client_stderr())
    check("a raider stood by the host and was given a stick of dynamite, which the observer's game mirrored",
          raider > 0 and opened and planted and len(during) >= 1 and int(during[-1]) >= 1,
          "raider net %d; session opened %s; planted %s; observer's copy of its pack, items: %s"
          % (raider, opened, planted, during[-3:]))

    # Taken off the living raider with no session open, then the raider is killed.
    mark = len(logtext())
    admin("stealall", 2.0)
    emptied = "[inv] DELTA net=%d invBit=1" % raider in logtext()[mark:]
    seen_before_death = len(re.findall(r"\[inv-full\] net=%d items=" % raider, client_stderr()))
    admin("cdamage 999", 4.0)
    alive = leave(game)
    game = None
    rows = re.findall(r"\[inv-full\] net=%d items=(\d+) " % raider, client_stderr())
    check("the dynamite was taken off the living raider on the server with no session open",
          alive and emptied,
          "pack changed on the server %s; observer rebuilt its copy %d times before the death, %d after"
          % (emptied, seen_before_death, len(rows) - seen_before_death))
    fixed("the observer's copy of the corpse's pack was rebuilt at the death and no longer lists the dynamite",
          len(rows) > seen_before_death and int(rows[-1]) == 0,
          "observer's copy of the pack, items, at each rebuild: %s" % rows[-4:])


def mouse_lines(events):
    """Mouse lines for the recorded input: (frame, dx, dy, button mask), relative moves."""
    return "".join("M %d %d %d %d%s" % (at, dx, dy, mask, NL) for at, dx, dy, mask in events)


def prove_lookclick():
    global game
    # GitHub issue 31. In a fight, a plain click on a living critter with the arrow cursor
    # is LOOK in vanilla (the hover icon is the binoculars, since nobody talks mid-fight).
    # The client drew vanilla's icon and sent `talk` regardless, which the server answers
    # with "You can't talk to anyone in combat"; reading an enemy's condition took the
    # hold-and-pick menu.
    #
    # The real client is the only player here, so the view is centred on its character: a
    # hex is 32 by 16, its top-left corner drawn at ((1280 - 32) / 2, (620 - 16) / 2) for
    # the centre tile, and two tiles on in the tile index is 48 left and 12 down whatever
    # the row's parity. A raider is put there, and the cursor on its chest. Right-click
    # switches the cursor to the arrow, A starts a fight (the one who starts it moves
    # first, so it waits on the player), and the click follows.
    feet_x, feet_y = (1280 - 32) // 2 + 16 - 48, (620 - 16) // 2 + 8 + 12
    with open(tracepath, "w") as trace:
        # The cursor starts in the middle of the screen, and is moved from there: pinning
        # it in a corner first, as the screen proofs do, scrolls the map by a hex.
        trace.write(mouse_lines([(900, feet_x - 1280 // 2, feet_y - 28 - 720 // 2, 0),
                                 (930, 0, 0, 2), (936, 0, 0, 0)]))
        trace.write("K 1020 %d 1%sK 1023 %d 0%s" % (KEY_A, NL, KEY_A, NL))
        trace.write(mouse_lines([(1200, 0, 0, 1), (1206, 0, 0, 0)]))
    drop_screenshots()
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_VIEWER_SHOT_EVERY": "120", "F2_TRACE_EVENTS": "1"})
    time.sleep(14)
    text = logtext()
    joined = "control claimed by session" in text
    mark = len(text)
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(text) + 2), 1.5)
    spawned = re.findall(r"\[evt\] SPAWN\s+net=(\d+) pid=16777454", logtext()[mark:])
    raider = int(spawned[-1]) if spawned else -1
    time.sleep(26)
    alive = leave(game)
    game = None
    os.remove(tracepath)
    text = logtext()[mark:]
    primary = re.findall(r"\[primary\] net=(\d+) ", client_stderr())
    check("the player was alone with a raider two tiles off, started a fight and clicked on the raider",
          alive and joined and raider > 0 and "control cstart" in text and primary[-1:] == [str(raider)],
          "raider net %d; fight started %s; the client's primary clicks landed on net %s"
          % (raider, "control cstart" in text, primary[-3:]))
    fixed("the click in the fight asked to look at the raider, not to talk to it",
          "control look netId=%d" % raider in text and "control talk dropped (in combat)" not in text,
          "look sent %s; talk refused in combat %s"
          % ("control look netId=%d" % raider in text, "control talk dropped (in combat)" in text))
    drop_screenshots()


def prove_earlyspace():
    global game
    # GitHub issue 30: "impatient players may miss turn in advance by pressing unnecessary
    # spaces during ai controlled turns." The server resolves the whole enemy side in one
    # beat and is already waiting on the player while those turns are still being shown, so
    # a Space pressed during the show ended a turn the player had not seen begin.
    #
    # The real client is the only player. A raider attacks it. The keyboard presses Space
    # in pairs, half a second apart, every eight seconds: the first of a pair ends the
    # player's turn, the second lands while the raider's answer is being shown. No pair
    # may end two turns.
    pairs = 4
    presses = []
    for n in range(pairs):
        at = 1800 + n * 480
        presses += [(at, KEY_SPACE), (at + 30, KEY_SPACE)]
    write_keys(presses)
    game = join({"F2_INPUT_REPLAY": tracepath})
    time.sleep(14)
    text = logtext()
    joined = "control claimed by session" in text
    admin("xp 0 30000", 1.0)  # a few levels of hit points, so the player outlives the proof
    follower = LogFollower()
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(text) + 2), 1.5)
    admin("aggro 1", 1.0)
    time.sleep(18 + pairs * 8 + 6)
    alive = leave(game)
    game = None
    follower.stop = True
    os.remove(tracepath)
    ends = [when for when, line in follower.lines if "control cendturn slot=0" in line]
    doubles = sum(1 for a, b in zip(ends, ends[1:]) if b - a < 2.0)
    held = len(re.findall(r"client-viewer: end turn held back", client_debug_log()))
    check("the player was alone in a fight with a raider and pressed Space in pairs",
          alive and joined and "placed 1/1" in out and len(ends) >= 1,
          "%s; %d ends of turn accepted" % (out[:40], len(ends)))
    fixed("no pair ended two turns: the Space pressed while the raider's turn was being shown ended nothing",
          len(ends) >= 1 and doubles == 0,
          "%d ends of turn accepted for %d pairs, %d of them within two seconds of the one before;"
          " %d presses held back by the client" % (len(ends), pairs, doubles, held))


KEY_N, KEY_ESCAPE = 17, 41
PISTOL, AMMO_10MM_JHP = 8, 29


def wait_for_log(needle, mark, seconds):
    """Wait until the server log (from `mark` on) holds `needle`. True if it came."""
    until = time.time() + seconds
    while time.time() < until:
        if needle in logtext()[mark:]:
            return True
        time.sleep(0.3)
    return False


def prove_reloads():
    global game
    # GitHub issues 33 and 34, the two reloads of a gun, with the real client as the only
    # player and a real mouse.
    #
    # 33: "After reloading, weapon doesn't automatically switch to shoot mode." Vanilla's
    # hand-bar reload ends by cycling the slot's action on from RELOAD, which lands on the
    # primary attack; the client sent the reload and left the slot on RELOAD. Here the
    # player holds an empty 10mm pistol, cycles the slot to RELOAD (N twice: single, aimed,
    # reload) and clicks the slot twice. The first click reloads. The second must be the
    # shot's click (out of a fight that asks to start one), not another reload.
    #
    # 34: "Drag & dropping the appropriate ammo to the gun in the holster slot does
    # nothing." The viewer's inventory skipped that drop. The pistol is emptied again, the
    # inventory opened (I), and the ammo dragged from the top of the list onto the left
    # hand slot: the server must load the pistol from that stack.
    #
    # Screen geometry, 1280x720: the interface bar is 640 wide at the bottom middle and
    # its item button is at (267, 26), 188 by 67; the inventory window (499 by 377) is
    # centred, its list's first row at (44, 35), 64 by 48, its left hand slot at
    # (154, 286) to (244, 347). The cursor starts in the middle of the screen and every
    # move is relative.
    slot_x, slot_y = 320 + 267 + 94, 620 + 26 + 33
    win_x, win_y = (1280 - 499) // 2, (720 - 377) // 2
    row_x, row_y = win_x + 44 + 32, win_y + 35 + 24
    hand_x, hand_y = win_x + 199, win_y + 316
    write_keys([(1500, KEY_N), (1530, KEY_N), (1900, KEY_ENTER), (3300, KEY_I), (3560, KEY_ESCAPE)])
    with open(tracepath, "a") as trace:
        trace.write(mouse_lines([
            (1560, slot_x - 640, slot_y - 360, 0),
            (1590, 0, 0, 1), (1596, 0, 0, 0),
            (1770, 0, 0, 1), (1776, 0, 0, 0),
            (3400, row_x - slot_x, row_y - slot_y, 0),
            (3420, 0, 0, 1),
            (3440, hand_x - row_x, hand_y - row_y, 1),
            (3470, 0, 0, 0)]))
    drop_screenshots()
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_VIEWER_SHOT_EVERY": "60"} if keep is not None
                else {"F2_INPUT_REPLAY": tracepath})
    time.sleep(14)
    joined = "control claimed by session" in logtext()
    # An empty pistol in the left hand (the hand the bar starts on), its twelve rounds
    # loose in the pack. The debug unload puts the weapon away, so it is wielded after.
    admin("give %d" % PISTOL, 0.5)
    admin("unload %d" % PISTOL, 0.5)
    admin("wield 0", 1.0)
    mark = len(logtext())
    reloaded = wait_for_log("control reload hand=0 loaded=1", mark, 45)
    # The second click, three seconds after the first: a fight asked for, or a reload.
    time.sleep(6.0)
    first = logtext()[mark:]
    reloads = len(re.findall(r"control reload hand=0", first))
    asked_fight = "control cstart" in first
    check("the player held an empty pistol, set its slot to reload and clicked it: the pistol was reloaded",
          joined and reloaded, "reload lines %d" % reloads)
    fixed("after the reload the slot is back on the shot: the next click asks for a fight, not another reload",
          reloaded and reloads == 1 and asked_fight,
          "%d reloads sent; fight asked for %s" % (reloads, asked_fight))

    # Empty it again for the inventory's drag.
    time.sleep(3.0)
    admin("unload %d" % PISTOL, 0.5)
    admin("wield 0", 1.0)
    mark = len(logtext())
    loaded = wait_for_log("control invload ammo pid=%d weapon pid=%d" % (AMMO_10MM_JHP, PISTOL), mark, 60)
    time.sleep(2.0)
    alive = leave(game)
    game = None
    os.remove(tracepath)
    rows = re.findall(r"control invload ammo pid=%d weapon pid=%d packs=(\d+) rc=(-?\d+) rounds (\d+) -> (\d+) held=(\d)"
                      % (AMMO_10MM_JHP, PISTOL), logtext()[mark:])
    drop_screenshots()
    fixed("ammo dragged onto the pistol in the hand slot loaded it, and the pistol stayed in the hand",
          alive and loaded and rows[:1] == [("1", "0", "0", "12", "1")],
          "invload lines (packs, rc, rounds before, after, still held): %s" % rows[:2])


def prove_firstjoin():
    # GitHub issue 32 (bugs/058): "1.4.1 game does not boot up", a black screen for the
    # first player of every session. join.cmd's client connects twice: an `account` probe,
    # then the real connection, which waits for the join snapshot before it logs in. The
    # v1.4.1 server kept its world frozen until somebody had logged in (issue 16) and sent
    # a joiner's snapshot only on a live beat, so the two waited on each other for good.
    #
    # Every other proof here logs a wire bot in first, which is how this got out: the world
    # was always running by the time the real client arrived. So nothing else joins here.
    # The server is started the way start-server.cmd starts it and the client the way
    # join.cmd starts it, three times: a new name on a new game (through the creation
    # screen), the same name again on the now empty server, and once more after the server
    # was restarted from the quicksave the player made with F6.
    boot_as_start_server()
    alive, debug, text, lit = join_as_join_cmd("Sister", creation_keys(600), 55)
    made = "created character -> create" in debug
    check("a new player finished the creation screen on a new game with nobody else on the server",
          alive and made, "client running %s, creation line sent %s" % (alive, made))
    joined = "snapshot loaded" in debug and "control claimed by session" in text
    fixed("the first player was sent the world and logged in",
          joined, "snapshot loaded %s, login seen by the server %s"
          % ("snapshot loaded" in debug, "control claimed by session" in text))
    fixed("the game was drawn, not a black screen",
          len(lit) >= 3 and min(lit) > 0.3,
          "%d late screenshots, lit share of the world view %s" % (len(lit), ["%.2f" % v for v in lit[:4]]))
    if not joined:
        return  # nothing below can happen on a build with the defect

    # The same player again. The server is empty and frozen, and this time the probe is
    # not the first connection it ever saw. F6 (three presses, one is enough) quicksaves.
    alive, debug, text, lit = join_as_join_cmd("Sister", [(1500, KEY_F6), (1800, KEY_F6), (2100, KEY_F6)], 45)
    known = re.findall(r"client-viewer: account 'Sister' is (\w+)", debug)
    check("the empty, frozen server still answered that it knows the name, so no creation screen opened",
          alive and known == ["known"] and "created character" not in debug, "account answer %s" % known)
    check("the returning player was sent the world and logged in again",
          "snapshot loaded" in debug and "control claimed by session" in text and len(lit) >= 3 and min(lit) > 0.3,
          "snapshot loaded %s, login %s, %d late screenshots" % ("snapshot loaded" in debug,
                                                                 "control claimed by session" in text, len(lit)))
    saved = "quicksave -> slot 16 ok" in text and os.path.exists(os.path.join(gamedir, "data", "SAVEGAME", "SLOT16", "SAVE.DAT"))
    check("F6 quicksaved the world into slot 16", saved)

    # The host stops the server and starts it again from that save, as start-server.cmd
    # does when Enter is pressed. The player's account comes from the save.
    stop_server()
    boot_as_start_server(16)
    alive, debug, text, lit = join_as_join_cmd("Sister", None, 40)
    known = re.findall(r"client-viewer: account 'Sister' is (\w+)", debug)
    check("after a restart from the save the server knows the name and the player gets in, world drawn",
          alive and known == ["known"] and "snapshot loaded" in debug and "control claimed by session" in text
          and len(lit) >= 3 and min(lit) > 0.3,
          "account answer %s, snapshot loaded %s, login %s, %d late screenshots"
          % (known, "snapshot loaded" in debug, "control claimed by session" in text, len(lit)))


def turns_seen(bot):
    return [struct.unpack_from("<i", body, 0)[0] for body in bot.events(EVENT_TURN_START) if len(body) >= 4]


def slot_net(slot):
    rows = re.findall(r"\[actors\] srv slot=%d obj=\S+ netId=(-?\d+)" % slot, logtext())
    return int(rows[-1]) if rows else None


def prove_heldturn():
    global game
    # GitHub issue 16, the real client's half. Two players are in a fight that is waiting
    # on the second player, the real client. The host leaves and then the second player's
    # game is closed: nobody is bound, so the world freezes with the turn still theirs.
    # They come back alone through join.cmd's settings. Their game must be sent the frozen
    # fight, be told after its login that the turn is its own (a client only learns which
    # body is its own when it logs in, and a turn announced before that is somebody
    # else's as far as it can tell), and nobody may have taken a turn in between. A wire
    # connection that never logs in watches every announced turn; it binds no body, so it
    # does not thaw the world.
    host = Bot("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({})
    time.sleep(12)
    joined = len(re.findall(r"control claimed by session", logtext())) >= 2
    watcher = Bot("watcher")
    time.sleep(3.0)
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(logtext()) + 3), 1.0)
    admin("aggro 1", 1.0)
    held = False
    ended_at = -1
    deadline = time.time() + 70
    while time.time() < deadline and not held:
        turns = turns_seen(watcher)
        if turns and turns[-1] == slot_net(1):
            time.sleep(2.0)
            held = turns_seen(watcher) == turns
            continue
        if turns and turns[-1] == slot_net(0) and len(turns) != ended_at:
            ended_at = len(turns)
            host.send("cendturn", 0.5)
        time.sleep(0.2)
    host.s.close()
    time.sleep(2.0)
    alive = leave(game)
    game = None
    time.sleep(6.0)  # nobody bound
    check("two players were in a fight waiting on the real client's turn when both left",
          joined and held and alive and "placed 1/1" in out, out[:40])

    seen = len(turns_seen(watcher))
    if os.path.exists(os.path.join(gamedir, "debug.log")):
        os.remove(os.path.join(gamedir, "debug.log"))
    write_keys([(1500, KEY_SPACE), (2100, KEY_SPACE), (2700, KEY_SPACE)])
    mark = len(logtext())
    game = join({"F2_PLAYER_CREATE": "ask", "F2_INPUT_REPLAY": tracepath})
    foreign = []   # turns that were not the second player's, announced before they ended theirs
    announced = 0
    mine_before_end = 0
    ended = False
    until = time.time() + 60
    while time.time() < until and not ended:
        mine_now = len(re.findall(r"client_net: turn start, this player's turn", client_debug_log()))
        ended = "control cendturn slot=1" in logtext()[mark:]
        if not ended:
            mine_before_end = mine_now
            turns = turns_seen(watcher)
            own = slot_net(1)
            foreign += [turn for turn in turns[seen:] if turn != own]
            announced += len(turns) - seen
            seen = len(turns)
        time.sleep(0.3)
    time.sleep(3.0)
    alive = leave(game)
    game = None
    os.remove(tracepath)
    text = logtext()[mark:]
    debug = client_debug_log()
    back = "snapshot loaded" in debug and "control claimed by session" in text
    # One verdict for both older builds: v1.4.1 never sends the returning game the world
    # (issue 32), v1.4.0 sends it and runs the fight on without them (issue 16).
    fixed("the returning player's game got back into the frozen fight with the turn still theirs:"
          " nobody took a turn before they ended it themselves",
          alive and back and ended and foreign == [],
          "snapshot loaded %s, login %s, their end of turn accepted %s; %d turn announcements meanwhile,"
          " not theirs: %s" % ("snapshot loaded" in debug, "control claimed by session" in text, ended,
                               announced, foreign[:12]))
    if not expect_defect:  # an older build gets to this line a round late, which the check above shows
        check("their game knew the turn was its own before they ended it (told once more after the login)",
              back and mine_before_end >= 1,
              "%d 'this player's turn' lines in the client log before the end of turn" % mine_before_end)


class ShotWatcher:
    """Reads the screenshots as the client writes them, keeps the pixels of a few areas of
    each and deletes it. By default the areas are the hit point counter (interface bar
    x 473, y 40, four 9x17 digits) and the message log (x 23, y 24, 167x60); a bar wider
    than 640 (IFACE_BAR_WIDTH in f2_res.ini) keeps its buttons and counters on the right
    and gives the extra width to the log. `areas` names others: a function from the
    screen's (width, height) to a list of boxes. The client names a screenshot after
    the first free number, so a deleted one's name comes round again: a row's time is
    when that file was first seen, and one that does not read yet (half written) is left
    for the next pass."""

    def __init__(self, areas=None):
        self.rows = []  # (first seen, pixels of area 1, pixels of area 2, ...)
        self.seen = {}
        self.stop = False
        self.areas = areas
        self.bar = 640
        try:
            ini = open(os.path.join(gamedir, "f2_res.ini"), encoding="latin1").read()
            width = re.findall(r"(?m)^IFACE_BAR_WIDTH=(\d+)", ini)
            if width:
                self.bar = max(640, int(width[-1]))
        except OSError:
            pass
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def read(self, path):
        from PIL import Image
        im = Image.open(path).convert("RGB")
        w, h = im.size
        if self.areas is not None:
            return tuple(im.crop(box).tobytes() for box in self.areas(w, h))
        left, top, extra = (w - self.bar) // 2, h - 100, self.bar - 640
        return (im.crop((left + extra + 470, top + 38, left + extra + 512, top + 59)).tobytes(),
                im.crop((left + 23, top + 24, left + extra + 190, top + 84)).tobytes())

    def run(self):
        while True:
            stopping = self.stop
            for path in screenshots():
                first = self.seen.setdefault(path, time.time())
                try:
                    pixels = self.read(path)
                except Exception:
                    continue
                self.rows.append((first,) + pixels)
                del self.seen[path]
                try:
                    os.remove(path)
                except OSError:
                    pass
            if stopping:
                return
            time.sleep(0.02)

    def finish(self):
        self.stop = True
        self.thread.join(timeout=20)
        return sorted(self.rows)


def prove_hpcount():
    global game
    # GitHub issue 44: "HP is deducted on UI when damage happens on player screen, not
    # before. ... after every player turn when for example Player2 is attacked by several
    # dogs that player could predict for how many points he's going to be attacked before
    # that attack was animated and log produced."
    #
    # The server resolves the enemy side's turns a beat or two after the player's turn
    # ends, and they then take many seconds to play on the client. The hit points rode one
    # delta per beat, behind ALL of that beat's attacks, and the client adopted it as it
    # was decoded: the counter rolled down to the end of the enemy phase while the first
    # swing was still in the air.
    #
    # The real client is the only player, with two raiders beside it. It ends its turn
    # (Space, pressed again every 900 frames in case a press lands early), and the screen
    # is read off the screenshots, one every 8 frames: the hit point counter must not move
    # before the message log shows the first line of the enemy phase.
    write_keys([(1800 + 900 * n, KEY_SPACE) for n in range(6)])
    drop_screenshots()
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_VIEWER_SHOT_EVERY": "8", "F2_TRACE_EVENTS": "1"})
    watcher = ShotWatcher()
    time.sleep(14)
    text = logtext()
    joined = "control claimed by session" in text
    admin("xp 0 30000", 1.0)  # a few levels of hit points, so the player outlives the proof
    here = host_tile(text)
    placed = [admin("spawn %s 1 %d" % (RAIDER, here + step), 0.5) for step in (1, -1)]
    follower = LogFollower()
    admin("aggro 2", 1.0)
    ended = None
    until = time.time() + 150
    while time.time() < until and ended is None:
        ended = next((when for when, line in follower.lines if "control cendturn slot=0" in line), None)
        time.sleep(0.1)
    time.sleep(40)  # the enemy phase plays
    alive = leave(game)
    game = None
    follower.stop = True
    os.remove(tracepath)
    rows = watcher.finish()
    before = [row for row in rows if ended is not None and row[0] < ended - 0.3]
    after = [row for row in rows if ended is not None and row[0] >= ended - 0.3]
    still = len(before) >= 3 and before[-1][1:] == before[-2][1:] == before[-3][1:]
    check("the player was alone in a fight with two raiders, waiting on its own turn, and ended it",
          alive and joined and all("placed 1/1" in out for out in placed) and ended is not None and still,
          "%d screenshots before the end of turn (the last three alike: %s), %d after"
          % (len(before), still, len(after)))
    if not (ended is not None and before and after):
        fixed("the hit point counter does not move before the message log shows the enemy phase", False,
              "no screenshots to read")
        return
    base_counter, base_lines = before[-1][1], before[-1][2]
    counter_at = next((n for n, row in enumerate(after) if row[1] != base_counter), None)
    lines_at = next((n for n, row in enumerate(after) if row[2] != base_lines), None)
    check("the enemy phase was shown: the message log filled and the counter came down",
          counter_at is not None and lines_at is not None,
          "counter first moved in screenshot %s after the end of turn, the log in screenshot %s"
          % (counter_at, lines_at))
    if counter_at is None or lines_at is None:
        fixed("the hit point counter does not move before the message log shows the enemy phase", False)
        return
    fixed("the hit point counter does not move before the message log shows the enemy phase",
          counter_at >= lines_at,
          "counter first moved %.1f s after the end of turn (screenshot %d), the log %.1f s after (screenshot %d)"
          % (after[counter_at][0] - ended, counter_at, after[lines_at][0] - ended, lines_at))
    if not expect_defect:
        # The fixed client says what it did: every total it was sent in the fight was
        # parked, and each was adopted right behind the line that reports the blow.
        trace = [line for line in client_stderr().splitlines() if line.startswith(("[hp] ", "[console] "))]
        parked = [n for n, line in enumerate(trace) if line.startswith("[hp] own total") and "parked" in line]
        first = parked[0] if parked else len(trace)  # the fight's first total (the level-ups came before)
        adopted = [n for n, line in enumerate(trace)
                   if n > first and line.startswith("[hp] own total") and "adopted" in line]
        behind = [n for n in adopted if trace[n - 1].startswith("[console] shown: You were")]
        check("every new total waited for its own blow: each was adopted right behind a 'You were hit' line",
              len(parked) >= 2 and len(adopted) >= 2 and len(behind) == len(adopted),
              "%d totals parked, %d adopted, %d of them right behind the blow's own line"
              % (len(parked), len(adopted), len(behind)))


DENBUS1, DENBUS2 = 6, 7


def world_brightness(path):
    """Mean brightness (0..255) of the world view: everything above the interface bar."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    w, h = im.size
    data = list(im.crop((0, 0, w, h - 100)).resize((160, 90)).getdata())
    return sum(max(r, g, b) for r, g, b in data) / float(len(data))


def settled_brightness():
    """The world's brightness now: the newest finished screenshot, the older ones dropped."""
    shots = screenshots()
    value = world_brightness(shots[-2]) if len(shots) >= 2 else -1.0
    drop_screenshots()
    return value


def prove_nightmap(seat=1):
    global game
    # GitHub issue 37: "Go to Den, wait in West side until Midnight and go to East side.
    # ... Night magically changes into full day even though the game time still is 00:30.
    # When moving back to West side it didn't fix and was broken until next night."
    #
    # A viewer's own map load puts the light at full day; the script that darkens a map
    # at night runs on the server, and the light level only travelled as a delta, sent
    # when it CHANGED. A map load rebaselined that diff silently, so the new map's
    # darkness was never said.
    #
    # The real client is taken to the Den's west side and its east side by day (how
    # bright each is drawn is the yardstick), back west, on to midnight, east again and
    # west again. Then it leaves and joins again, at midnight: a player who joins at
    # night is sent the world the same way. How bright the world is drawn is read off
    # the screenshots. nightmap has the real client alone, in the host's seat; nightmap2
    # has it join a session a wire client hosts.
    drop_screenshots()
    host, joined = seat_join(seat, env={"F2_VIEWER_SHOT_EVERY": "40"})
    admin("entermap %d" % DENBUS1, 9.0)
    drop_screenshots()
    time.sleep(3.0)
    west_day = settled_brightness()
    admin("entermap %d" % DENBUS2, 9.0)
    drop_screenshots()
    time.sleep(3.0)
    east_day = settled_brightness()
    admin("entermap %d" % DENBUS1, 9.0)
    out = admin("timeskip 940", 8.0)  # 08:24 plus 15 h 40 min: just past midnight
    drop_screenshots()
    time.sleep(3.0)
    west_night = settled_brightness()
    admin("entermap %d" % DENBUS2, 9.0)
    drop_screenshots()
    time.sleep(3.0)
    east_night = settled_brightness()
    admin("entermap %d" % DENBUS1, 9.0)
    drop_screenshots()
    time.sleep(3.0)
    west_again = settled_brightness()
    alive = leave(game)
    game = None
    drop_screenshots()
    # The same player comes back, at midnight.
    game = join({"F2_VIEWER_SHOT_EVERY": "40"})
    time.sleep(16)
    drop_screenshots()
    time.sleep(3.0)
    west_joined = settled_brightness()
    back = leave(game)
    game = None
    drop_screenshots()
    check("the player saw both sides of the Den by day, and the west side go dark at midnight",
          alive and joined and west_day > 20 and east_day > 20 and 0 < west_night < 0.75 * west_day,
          "brightness west %.0f by day and %.0f at midnight, east %.0f by day; %s"
          % (west_day, west_night, east_day, out[:50]))
    fixed("crossing to the east side at midnight, it is night there too",
          0 < east_night < 0.75 * east_day,
          "east side drawn at brightness %.0f at midnight (%.0f by day)" % (east_night, east_day))
    fixed("and back on the west side it is still night",
          0 < west_again < 0.75 * west_day,
          "west side drawn at brightness %.0f after coming back (%.0f by day, %.0f at midnight before)"
          % (west_again, west_day, west_night))
    fixed("a player who joins at midnight is shown the night as well",
          back and 0 < west_joined < 0.75 * west_day,
          "west side drawn at brightness %.0f to the player who joined at midnight (%.0f by day)"
          % (west_joined, west_day))


def prove_nightmap2():
    prove_nightmap(2)


LEATHER_ARMOR = 1


def prove_armorview():
    global game
    # GitHub issue 28, first half: "for the player who actively equips the armor, the
    # inventory thumbnail shows them naked, while unequipping it updates the thumbnail to
    # show them wearing it."
    #
    # The body turning in the middle of the inventory is drawn from the armor slot. In a
    # viewer that slot changes when the server's answer arrives, and the body was only
    # worked out at the drop that ASKED for the change, on the slot as it still was: one
    # change behind, every time.
    #
    # The real client, alone, is handed a leather armor, opens the inventory (I), drags
    # the armor from the top of the list onto the armor slot and, nine seconds later,
    # back onto the list. The body's area is read off screenshots (one every 10 frames;
    # it turns through six facings a second, so each phase is a small set of pictures).
    #
    # Screen geometry, 1280x720: the inventory window (499 by 377) is centred; the
    # list's first row is at (46, 35), 64 by 48; the armor slot at (154, 183), 90 by 61;
    # the body at (176, 37), 60 by 100. The cursor starts in the middle of the screen
    # and every move is relative.
    win_x, win_y = (1280 - 499) // 2, (720 - 377) // 2
    row_x, row_y = win_x + 46 + 32, win_y + 35 + 24
    slot_x, slot_y = win_x + 154 + 45, win_y + 183 + 30
    write_keys([(1500, KEY_I)])
    with open(tracepath, "a") as trace:
        trace.write(mouse_lines([
            (1560, row_x - 640, row_y - 360, 0),
            (1900, 0, 0, 1), (1920, slot_x - row_x, slot_y - row_y, 1), (1950, 0, 0, 0),
            (2500, 0, 0, 1), (2520, row_x - slot_x, row_y - slot_y, 1), (2550, 0, 0, 0)]))
    drop_screenshots()
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_VIEWER_SHOT_EVERY": "10", "F2_TRACE_EVENTS": "1"})
    watcher = ShotWatcher(lambda w, h: [((w - 499) // 2 + 176, (h - 377) // 2 + 37,
                                         (w - 499) // 2 + 236, (h - 377) // 2 + 137)])
    time.sleep(14)
    joined = "control claimed by session" in logtext()
    admin("give %d" % LEATHER_ARMOR, 0.5)
    follower = LogFollower()

    def logged(needle, seconds):
        until = time.time() + seconds
        while time.time() < until:
            when = next((when for when, line in follower.lines if needle in line), None)
            if when is not None:
                return when
            time.sleep(0.1)
        return None

    worn_at = logged("control invwield pid=%d" % LEATHER_ARMOR, 90)
    off_at = logged("control invunwield armor", 60)
    time.sleep(8)
    alive = leave(game)
    game = None
    follower.stop = True
    os.remove(tracepath)
    rows = watcher.finish()
    debug = client_debug_log()
    check("the player opened the inventory, put the leather armor on and took it off again",
          alive and joined and worn_at is not None and off_at is not None
          and "inventory: screen up" in debug and "inventory: closed" not in debug,
          "armor on %s, off %s" % (worn_at is not None, off_at is not None))
    if worn_at is None or off_at is None:
        fixed("with the armor on, the body in the inventory is drawn wearing it", False, "no screenshots to read")
        return
    bare = set(row[1] for row in rows if worn_at - 4.0 <= row[0] <= worn_at - 0.7)
    worn = set(row[1] for row in rows if worn_at + 2.0 <= row[0] <= off_at - 0.7)
    off = set(row[1] for row in rows if off_at + 2.0 <= row[0] <= off_at + 7.5)
    check("the body was on screen and turning in all three phases",
          len(bare) >= 3 and len(worn) >= 3 and len(off) >= 3,
          "different pictures of the body: %d before, %d with the armor on, %d after" % (len(bare), len(worn), len(off)))
    fixed("with the armor on, the body in the inventory is drawn wearing it",
          len(worn) >= 3 and not (worn & bare),
          "%d of the %d pictures with the armor on are pictures of the bare body" % (len(worn & bare), len(worn)))
    fixed("with the armor off again, the body is the bare one again",
          len(off) >= 3 and len(off & bare) >= 3 and not (off & worn),
          "%d of the %d pictures after are pictures of the bare body, %d are the armored one's"
          % (len(off & bare), len(off), len(off & worn)))


PISTOL_10MM = 8
TUBBY = 47  # dtalk takes the script's index: scripts.lst line 48


def prove_tradeunload():
    global game
    # GitHub issue 38: "Try to unload trader guns from Barter window. ... Holding LMB
    # doesn't open Context Menu. Simple click for Binoculars info doesn't work too in the
    # Barter window."
    #
    # The viewer's trade screen only ever handled the HAND cursor's click (the drag). Under
    # the arrow, which the right mouse button switches to, a click did nothing: no look,
    # and no action menu when held.
    #
    # The real client, alone, carries a loaded 10mm pistol to Tubby in the Den. The
    # operator opens the conversation; from there it is all the player's mouse: a click on
    # the dialog's Barter button, a right-click (arrow), a click on the pistol at the top
    # of its own list (look), a held click with the cursor drawn 14 pixels down (the
    # menu's second line: Unload), and a click on the first thing in Tubby's list (look).
    #
    # Screen geometry, 1280x720: the dialog frame (640 by 480) is centred; its lower
    # panel starts 290 down and the Barter button is at (593, 41) in it, 14 by 14; the
    # trade window is at (80, 290) in the frame and its lists' first rows are at
    # (29, 35) and (388, 35), 64 by 48. The cursor starts in the middle of the screen and
    # every move is relative.
    frame_x, frame_y = (1280 - 640) // 2, (720 - 480) // 2
    barter_x, barter_y = frame_x + 593 + 7, frame_y + 290 + 41 + 7
    mine_x, mine_y = frame_x + 80 + 29 + 32, frame_y + 290 + 35 + 24
    his_x, his_y = frame_x + 80 + 388 + 32, frame_y + 290 + 35 + 24
    with open(tracepath, "w") as trace:
        trace.write(mouse_lines([
            (2400, barter_x - 640, barter_y - 360, 0), (2430, 0, 0, 1), (2436, 0, 0, 0),
            (2700, 0, 0, 2), (2706, 0, 0, 0),
            (2760, mine_x - barter_x, mine_y - barter_y, 0), (2820, 0, 0, 1), (2826, 0, 0, 0),
            (2940, 0, 0, 1), (3040, 0, 14, 1), (3070, 0, 0, 0),
            (3300, his_x - mine_x, his_y - (mine_y + 14), 0), (3360, 0, 0, 1), (3366, 0, 0, 0)]))
    drop_screenshots()
    extra = {"F2_INPUT_REPLAY": tracepath, "F2_TRACE_EVENTS": "1"}
    if keep is not None:
        extra["F2_VIEWER_SHOT_EVERY"] = "120"
    game = join(extra)
    time.sleep(10)
    joined = "control claimed by session" in logtext()
    admin("give %d" % PISTOL_10MM, 0.5)
    admin("entermap 6", 12.0)  # the Den, business district: Tubby's store
    admin("movdone", 1.0)
    admin("dtalk %d" % TUBBY, 2.0)
    mark = len(logtext())
    opened = wait_for_log("[barter] SEND begin", mark, 90)
    unloaded = wait_for_log("f2_server: barter unload", mark, 45)
    time.sleep(10)  # the look at Tubby's first item comes five seconds after the unload
    alive = leave(game)
    game = None
    os.remove(tracepath)
    drop_screenshots()
    text = logtext()[mark:]
    menu = [line for line in client_stderr().splitlines() if line.startswith("[trade-menu]")]
    check("the player carried a pistol to Tubby and opened the trade with the dialog's Barter button",
          alive and joined and "control dbarter" in text and opened,
          "barter asked for %s, opened %s" % ("control dbarter" in text, opened))
    fixed("under the arrow a click on an item looks at it: the player's own pistol, and the first thing Tubby has",
          any("click: look at pid %d (slot key 1000)" % PISTOL_10MM in line for line in menu)
          and any("click: look at pid" in line and "(slot key 2000)" in line for line in menu),
          "; ".join(menu)[:300] or "no action menu line in the client's trace")
    done = re.findall(r"barter unload pid=%d list=0 (\w+) \((\d+) rounds\)" % PISTOL_10MM, text)
    fixed("a held click opens the action menu, and its Unload unloads the pistol where it lies",
          unloaded and done[:1] == [("unloaded", "12")]
          and any("held: 3 choices, chose unload for pid %d" % PISTOL_10MM in line for line in menu),
          "server: %s" % (done[:1] or "no unload asked for"))


def bar_width():
    """The interface bar's width: IFACE_BAR_WIDTH in the sandbox's f2_res.ini, 640 if unset."""
    try:
        ini = open(os.path.join(gamedir, "f2_res.ini"), encoding="latin1").read()
    except OSError:
        return 640
    width = re.findall(r"(?m)^IFACE_BAR_WIDTH=(\d+)", ini)
    return max(640, int(width[-1])) if width else 640


def prove_acturn():
    global game
    # GitHub issue 24: "Armor Class (AC) counter shows result as if player skipped turn
    # with current amount of Action Points (APs) left. With every AP spent current AC
    # drops by one. Expected: In vanilla Fallout2 current AC is updated with End Turn."
    #
    # The armor class stat adds a critter's unspent action points, except on its own
    # turn. A viewer runs no combat loop, so "whose turn" was never set there: every
    # moment counted as somebody else's turn, and the counter showed the bonus all
    # through the player's own turn, a point less with every action point spent.
    #
    # Two players and a raider well away. The host is a wire seat that ends its turns
    # at once, except the one right after the real client has opened its inventory and
    # ended its own turn: that one it holds for eight seconds, so there is something to
    # see. The real client, on its turn, opens the inventory (I, 4 action points),
    # closes it (Esc) and ends the turn (Space), again and again. The counter (interface
    # bar x 473, y 75) is read off screenshots taken every 10 frames.
    presses = []
    for n in range(10):
        at = 1800 + n * 1000
        presses += [(at, KEY_I), (at + 200, KEY_ESCAPE), (at + 500, KEY_SPACE)]
    write_keys(presses)
    host = Bot("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    drop_screenshots()
    game = join({"F2_INPUT_REPLAY": tracepath, "F2_VIEWER_SHOT_EVERY": "10"})
    bar = bar_width()
    watcher = ShotWatcher(lambda w, h: [((w - bar) // 2 + bar - 640 + 470, h - 100 + 73,
                                         (w - bar) // 2 + bar - 640 + 512, h - 100 + 94)])
    time.sleep(14)
    joined = "control claimed by session" in logtext()
    admin("xp 1 30000", 1.0)  # a few levels of hit points for the real client's character
    out = admin("spawn %s 1 %d" % (RAIDER, host_tile(logtext()) + 12), 1.0)
    follower = LogFollower()
    admin("aggro 1", 1.0)
    me = slot_net(0)
    turns = []  # (when the host's seat saw it, whose turn)
    opened = ended = None
    until = time.time() + 170
    while time.time() < until:
        seen = turns_seen(host)
        if len(seen) > len(turns):
            now = time.time()
            turns += [(now, net) for net in seen[len(turns):]]
            if turns[-1][1] == me:
                # Has the real client opened its inventory and then ended that same turn?
                for when in [w for w, line in follower.lines if "control invopen granted slot=1" in line]:
                    end = next((w for w, line in follower.lines if w > when and "control cendturn slot=1" in line), None)
                    if end is not None and not any(when - 2.5 <= t <= end - 0.05 for t, _net in turns[:-1]):
                        opened, ended = when, end
                if opened is not None:
                    time.sleep(8.0)  # the held turn
                    host.send("cendturn", 0.5)
                    break
                host.send("cendturn", 0.2)
        time.sleep(0.05)
    alive = leave(game)
    game = None
    follower.stop = True
    os.remove(tracepath)
    rows = watcher.finish()
    check("two players were in a fight; the real client opened its inventory on its own turn and ended that turn",
          alive and joined and "placed 1/1" in out and opened is not None,
          "inventory opened %s, turn ended %s; %d screenshots"
          % (opened is not None, ended is not None, len(rows)))
    if opened is None:
        fixed("the armor class counter stands still through the player's own turn, 4 action points spent", False,
              "no such turn seen")
        return
    own = set(row[1] for row in rows if opened - 2.5 <= row[0] <= ended - 0.3)
    before = [row for row in rows if opened - 2.5 <= row[0] <= opened - 0.3]
    held = set(row[1] for row in rows if ended + 1.5 <= row[0] <= ended + 7.0)
    fixed("the armor class counter stands still through the player's own turn, 4 action points spent",
          len(before) >= 2 and len(own) == 1,
          "%d different pictures of the counter from 2.5 s before the inventory opened to the end of the turn" % len(own))
    fixed("once the turn is ended the counter shows the unspent action points, as vanilla's does",
          len(held) >= 1 and not (held & own),
          "%d pictures of the counter while the other player held the next turn, %d of them seen during the own turn"
          % (len(held), len(held & own)))


def audit_client(label, seconds=12.0):
    """Ask the server for its mirror audit and read the real client's verdict: every
    syncable object's fields as the server holds them, compared in the client against its
    own copy of the world. Returns (differences that matter or None if no verdict came,
    their lines, objects compared, differences set aside).

    Set aside, because they are not world state: a critter's animation frame (the client's
    engine plays idle fidgets and walk cycles on its own); a critter the client is still
    gliding along a walk the server has already finished (the walk art in place of the
    standing one, with the tile and facing still catching up); and the two flag bits that
    say who owns an object's lifetime in each process (NO_REMOVE and NO_SAVE: the server
    keeps its player actors across a map change, a client's copies must go with the map,
    see objectApplyWireFlags)."""
    lifetime = 0x400 | 0x4
    mark = len(client_stderr())
    admin("audit", 0.2)
    until = time.time() + seconds
    while time.time() < until:
        text = client_stderr()[mark:]
        found = re.findall(r"\[audit\] (\d+) server objects, (\d+) mirrored, (\d+) divergences", text)
        if found:
            rows = re.findall(r"\[audit\] net=(\d+) pid=(-?\d+) (\w+): server=(-?\d+) \(0x[0-9A-Fa-f]+\) mirror=(-?\d+) ", text)
            other = [l for l in text.splitlines() if l.startswith("[audit] net=") and ("MISSING" in l or "EXTRA" in l)]
            walking = set()
            for net, pid, field, theirs, ours in rows:
                if field == "fid" and (int(pid) >> 24) == 1:
                    theirs, ours = int(theirs), int(ours)
                    same_body = (theirs & ~0x70FF0000) == (ours & ~0x70FF0000)
                    if same_body and ((theirs >> 16) & 0xFF) == 0 and ((ours >> 16) & 0xFF) in (1, 19):
                        walking.add(net)
            real = []
            aside = 0
            for net, pid, field, theirs, ours in rows:
                critter = (int(pid) >> 24) == 1
                if critter and field == "frame":
                    aside += 1
                elif net in walking and field in ("fid", "tile", "rotation"):
                    aside += 1
                elif field == "flags" and ((int(theirs) ^ int(ours)) & 0xFFFFFFFF & ~lifetime) == 0:
                    aside += 1
                else:
                    real.append("net %s pid 0x%X %s: server %s (0x%X), client %s (0x%X)"
                                % (net, int(pid), field, theirs, int(theirs) & 0xFFFFFFFF, ours, int(ours) & 0xFFFFFFFF))
            real += [l[8:] for l in other]
            return len(real), real, int(found[-1][0]), aside
        time.sleep(0.3)
    return None, [], 0, 0


def audit_check(name, label, settle=3.0):
    """One check: the client's copy of the world matches the server's, field for field.
    A difference counts when it is still there `settle` seconds later: one audit can catch
    a change in the middle of being shown (a door sliding, a critter turning)."""
    count, lines, objects, aside = audit_client(label)
    passing = 0
    if count:
        time.sleep(settle)
        first = lines
        count, lines, objects, aside = audit_client(label + ", again")
        if count is not None:
            lines = [line for line in lines if line in first]
            passing = len(first) - len(lines)
            count = len(lines)
    check(name, count == 0,
          "no verdict from the client" if count is None
          else "%d objects compared, %d differences%s%s%s"
          % (objects, count,
             " (%d more were gone %.0f s later: a change being shown)" % (passing, settle) if passing else "",
             " (%d more were a walk or an idle animation in progress)" % aside if aside else "",
             (": " + " | ".join(lines[:8])) if lines else ""))
    return count, lines


def seat_join(seat, keys=None, env=None):
    """Start the real client in the given seat: 1 = alone, the host's seat (slot 0);
    2 = joining a session a wire client already hosts (slot 1). `keys` is its recorded
    keyboard, if it is to press anything, `env` more of its environment. Returns (the
    wire host or None, whether the real client got that seat)."""
    global game
    host = None
    if seat == 2:
        host = Host()
        time.sleep(2.5)
        host.send("login Tester", 3.0)
    env = dict({"F2_TRACE_EVENTS": "1"}, **(env or {}))
    if keys:
        write_keys(keys)
        env["F2_INPUT_REPLAY"] = tracepath
    game = join(env)
    time.sleep(14)
    slots = re.findall(r"account 'Brother' -> slot (\d+)", logtext())
    return host, bool(slots) and int(slots[-1]) == seat - 1 and game.poll() is None


def prove_syncwalk(seat=1):
    global game
    # Not one fix: the whole of them, seen from the real client's own copy of the world.
    # The server's audit sends every syncable object as the server holds it (tile, art,
    # frame, facing, flags, light, hit points, action points, combat results, inventory),
    # and the client compares that against what it is showing. The real client is walked
    # through the things the v1.4.2 fixes touch, and the audit must come back clean after
    # each: arrival, a map change, the Den's orphans making their move beside the host (a
    # script's animation shown, issue 40), midnight and a second map change (issue 37),
    # Bess lying in Modoc (issue 42), one more player joining, which sends everybody the
    # world again, and a raider killed in a fight.
    #
    # syncwalk has the real client alone, in the host's seat. syncwalk2 has it join a
    # session a wire client hosts, the seat of every other player.
    #
    # The fight is audited while it is still on, with a player's turn held (nobody ends
    # one): the server waits there, so the client has shown everything and the two must
    # agree. A fight in mid-flow is no place to compare, the client plays each blow in
    # turn and is seconds behind by design. And the fight is last because the fixture
    # cannot end one cleanly: the raider's friends on the map turn on the host once the
    # operator's damage kills it (probed with `fightprobe`).
    host, seated = seat_join(seat)
    check("the real client joined, alone, as the host" if seat == 1
          else "the real client joined a session another player hosts", seated)
    audit_check("on arrival in Arroyo the client's world matches the server's", "arrival")

    admin("entermap %d" % DENBUS1, 10.0)
    admin("movdone", 2.0)
    audit_check("after the map change to the Den it matches", "den")

    # Beside an orphan, on each side of it in turn, until it tries the host's pocket.
    mark = len(logtext())
    seqs = len(re.findall(r"\[presseq\] RECV", client_stderr()))
    at = host_tile(logtext())
    tried = False
    for target in (25889, 19707):
        for step in (1, -1, 200, -200):
            admin("warp %d" % (target + step - at), 0.2)
            at = target + step
            if wait_for_log("[gesture]", mark, 5):
                tried = True
                break
        if tried:
            break
    time.sleep(3.0)
    shown = len(re.findall(r"\[presseq\] RECV", client_stderr())) - seqs
    check("an orphan made its move beside the host and the client was sent the animation and played it",
          tried and shown >= 1 and game.poll() is None,
          "server shipped a script gesture %s; sequences the client received since: %d" % (tried, shown))
    audit_check("after the orphan's animation it matches", "gesture")

    admin("timeskip 940", 6.0)
    admin("entermap 7", 10.0)
    audit_check("at midnight on the Den's east side it matches", "night")

    admin("entermap %d" % 18, 10.0)  # Modoc: Bess lies by the slaughterhouse
    audit_check("in Modoc it matches, Bess lying down included", "modoc")

    late = Host()
    time.sleep(2.5)
    late.send("login Late", 8.0)
    arrived = "account 'Late' -> slot" in logtext()
    check("one more player joined in Modoc, which sends every client the world again", arrived and game.poll() is None)
    audit_check("after that join it still matches", "late join")

    # The fixture sets the critter nearest the host on it and kills the critter nearest
    # the host, and the other players' actors stand right beside it: the host steps away
    # first, so that the raider put beside it is the nearest both times.
    admin("warp 6", 0.5)
    here = host_tile(logtext()) + 6
    mark = len(logtext())
    out = admin("spawn %s 1 %d" % (RAIDER, here + 1), 1.5)
    raider = re.findall(r"\[evt\] SPAWN\s+net=(\d+) pid=%d" % int(RAIDER, 16), logtext()[mark:])
    admin("aggro 1", 4.0)
    fight = "COMBAT ENTER" in client_debug_log()
    seen = len(client_stderr())
    admin("cdamage 999", 3.0)
    # The art the client was sent for the raider: a death is anim 20 and up.
    arts = re.findall(r"\[fid\] net=%s apply 0x[0-9a-f]+ -> 0x([0-9a-f]+)" % (raider[-1] if raider else "none"),
                      client_stderr()[seen:])
    died = any(((int(art, 16) >> 16) & 0xFF) >= 20 for art in arts)
    time.sleep(4.0)
    on = "COMBAT EXIT applied" not in client_debug_log()
    check("a raider was set on the host, a fight began on the client and the raider was killed in it",
          "placed 1/1" in out and fight and died and game.poll() is None,
          "raider net %s; fight seen by the client %s; the client was sent the raider's death %s; the fight is still on %s"
          % (raider[-1] if raider else "?", fight, died, on))
    audit_check("in that fight, on a held turn, it matches (the corpse included)", "kill")
    alive = leave(game)
    game = None
    check("the client ran through all of it without stopping", alive)


def prove_syncwalk2():
    prove_syncwalk(2)


def prove_doorsync(seat=1):
    global game
    # Found by the audit above (bugs/077), two things about a used door in the client's
    # copy of the map.
    #
    # One: the slide played, so the door LOOKED open, but its flags (does it block, does it
    # stop light and shots) arrive as a state change that the client holds back until the
    # slide has played, and outside a fight nothing let go of it again except five seconds
    # in which nothing on the whole map moved or was shown. In a town that is anything
    # from five seconds to never: the door stayed a wall to the client, and the movement
    # cursor showed the red X on every tile behind it.
    #
    # Two: a door used twice in quick succession (a double click) sends two slides, the
    # second reaches the client's engine while the door is still playing the first, and
    # the engine refuses it. The door then stood open on screen and shut on the server
    # (or the other way round) until the next map change.
    #
    # The host's actor uses the door nearest to it in the Den. A slide takes half a second;
    # three seconds after it the client's copy of that door must be the server's (before
    # the fix the flags could not have arrived yet). It is used again, and then twice at
    # once. doorsync has the real client in the host's seat (it is its own actor at the
    # door); doorsync2 has it watch another player's actor do it.
    host, seated = seat_join(seat)
    check("the real client joined, alone, as the host" if seat == 1
          else "the real client joined a session another player hosts", seated)
    admin("entermap %d" % DENBUS1, 10.0)
    admin("movdone", 2.0)
    time.sleep(2.0)

    def use_door(word, times=1):
        mark = len(logtext())
        admin(NL.join(["usedoor"] * times), 0.3)
        wait_for_log("[presseq] SEND", mark, 5)
        time.sleep(0.5)
        shipped = len(re.findall(r"\[presseq\] SEND", logtext()[mark:]))
        doors = re.findall(r"\[presref\] obj=\S+ netId=(\d+)", logtext()[mark:])
        door = doors[0] if doors else "?"
        time.sleep(2.5)
        count, lines, objects, aside = audit_client("door " + word)
        wrong = [line for line in lines if line.startswith("net %s " % door)]
        time.sleep(3.0)
        later, lines, objects, aside = audit_client("door " + word + ", again")
        still = [line for line in lines if line.startswith("net %s " % door)]
        heard = count is not None and later is not None
        return (shipped >= times and heard and game.poll() is None, wrong,
                "door net %s; slides the server sent: %d; three seconds on %s; six seconds on %s"
                % (door, shipped,
                   ("the client's copy differs: " + " | ".join(wrong)) if wrong
                   else "the client's copy matches" if heard else "no verdict from the client",
                   "it still differs" if still else "it matches"))

    ok, wrong, detail = use_door("used")
    check("the host used the nearest door, the server moved it and sent every client the slide", ok, detail)
    fixed("three seconds later the client's copy of that door is the server's (the same flags: it blocks, or it does not, on both)",
          ok and not wrong, detail)
    ok, wrong, detail = use_door("used again")
    if expect_defect:
        # What the client holds here depends on whether the first use's flags found their
        # five quiet seconds, so a build with the defect is not judged on it.
        print("SKIP used once more: not judged on a build with the defect  [" + detail + "]")
    else:
        check("used once more, the door is back as it was, on the server and in the client's copy", ok and not wrong, detail)
    # Twice at once, as a double click does: the second slide reaches the client's engine
    # while the door is still playing the first, and the engine refuses it.
    ok, wrong, detail = use_door("used twice at once", 2)
    check("the host used the door twice at once and the server sent both slides", ok, detail)
    fixed("after the two slides the door stands as the server holds it (the same frame, the same flags)",
          ok and not wrong, detail)
    alive = leave(game)
    game = None
    check("the client was still running at the end", alive)


def prove_doorsync2():
    prove_doorsync(2)


def prove_auditwatch():
    global game
    # A probe, not a proof: the real client alone in the Den beside the orphans, audited
    # every two seconds for forty seconds. Prints what differs each time, to tell a
    # difference that lasts from one caught in the middle of a change.
    game = join({"F2_TRACE_EVENTS": "1"})
    time.sleep(14)
    admin("entermap %d" % DENBUS1, 10.0)
    admin("movdone", 2.0)
    at = host_tile(logtext())
    admin("warp %d" % (25889 + 1 - at), 0.5)
    seen = {}
    for n in range(20):
        count, lines, objects, aside = audit_client("watch %d" % n, 8.0)
        for line in lines:
            seen.setdefault(line, []).append(n)
        print("audit %2d: %s real, %s aside%s" % (n, count, aside, (": " + " | ".join(lines[:3])) if lines else ""))
        time.sleep(1.5)
    for line, when in seen.items():
        print("   in audits %s: %s" % (when, line))
    check("probe ran", leave(game))
    game = None


def prove_fightprobe():
    global game
    # A probe, not a proof: who fights whom when a raider is put beside the host and set on
    # it. PROBE_SEAT (1 or 2), PROBE_WARP (tiles the host steps aside first) and
    # PROBE_SPAWN (the raider's offset from the host) come from the environment.
    seat = int(os.environ.get("PROBE_SEAT", "1"))
    warp = int(os.environ.get("PROBE_WARP", "0"))
    offset = int(os.environ.get("PROBE_SPAWN", "1"))
    host, seated = seat_join(seat, [(600 + 120 * n, KEY_SPACE) for n in range(200)])
    if os.environ.get("PROBE_MAP"):
        admin("entermap %s" % os.environ["PROBE_MAP"], 10.0)
        admin("movdone", 2.0)
    here = host_tile(logtext())
    if warp:
        admin("warp %d" % warp, 0.5)
        here += warp
    out = admin("spawn %s 1 %d" % (RAIDER, here + offset), 1.5)
    seen = len(client_stderr())
    admin("aggro 1", 4.0)
    admin("cdamage 999", 3.0)
    until = time.time() + 25
    while time.time() < until and "COMBAT EXIT applied" not in client_debug_log():
        admin("cendturn", 0.5)
    print("placed:", "placed 1/1" in out, " fight over:", "COMBAT EXIT applied" in client_debug_log())
    for line in re.findall(r"\[console\] shown: (.*)", client_stderr()[seen:])[:24]:
        print("   " + line)
    check("probe ran", leave(game))
    game = None
    if os.path.exists(tracepath):
        os.remove(tracepath)


def prove_corpsesync(seat=1):
    global game
    # Found by the audit walk (bugs/078): a critter killed while a replay of its own was
    # still being shown ended, in the client's copy, with the wrong corpse.
    #
    # The client holds a critter's final state (the corpse art, the flat flag) until the
    # replay it belongs to has played. It kept one bucket per critter and emptied it at
    # the end of whichever of the critter's replays finished first. A raider that has just
    # attacked three times has three replays queued on the client; killed one second in,
    # its corpse state arrived while the first or second was playing, landed when that one
    # ended, and the replays still queued then played over it: it stood up to attack
    # again, and the death at the end left it in the animation's last frame with the flat
    # flag toggled back off. No blood pool under it (the bloody art is the server's, and
    # it had already been overwritten), and it was drawn as a standing object.
    #
    # A raider is put beside the host and set on it; one second later, with its attacks
    # still being shown, the operator kills it. Nobody ends a turn, so the fight waits on
    # a player and the client shows everything it has. Then the raider's corpse in the
    # client's copy must be the server's. corpsesync has the real client in the host's
    # seat, corpsesync2 in the other.
    host, seated = seat_join(seat)
    check("the real client joined, alone, as the host" if seat == 1
          else "the real client joined a session another player hosts", seated)
    # The fixture sets the critter nearest the host on it and kills the critter nearest
    # the host, and the other player's actor stands right beside it: the host steps away.
    here = host_tile(logtext())
    if seat == 2:
        admin("warp 6", 0.5)
        here += 6
    mark = len(logtext())
    out = admin("spawn %s 1 %d" % (RAIDER, here + 1), 1.5)
    raider = re.findall(r"\[evt\] SPAWN\s+net=(\d+) pid=%d" % int(RAIDER, 16), logtext()[mark:])
    net = raider[-1] if raider else "none"
    seen = len(client_stderr())
    admin("aggro 1", 0.6)
    admin("cdamage 999", 1.0)
    time.sleep(9.0)
    text = client_stderr()[seen:]
    # In the order the client logged them: each attack of the raider's arrives as a
    # sequence with the raider as its actor, the kill as one with none, and a sequence is
    # logged again when its turn comes to be played.
    kill = re.search(r"\[presseq\] RECV bytes=\d+ actor=0 ", text)
    before = text[:kill.start()] if kill else ""
    attacks = len(re.findall(r"\[presseq\] RECV bytes=\d+ actor=%s " % net, before))
    played = before.count("[preplay]")
    arts = re.findall(r"\[fid\] net=%s apply 0x[0-9a-f]+ -> 0x([0-9a-f]+)" % net, text)
    died = any(((int(art, 16) >> 16) & 0xFF) >= 20 for art in arts)
    check("a raider attacked the host and was killed while its attacks were still being shown",
          "placed 1/1" in out and died and attacks >= 1 and played <= attacks and game.poll() is None,
          "raider net %s; its attacks the client had been sent when the kill arrived: %d, of which it had begun to show %d; the client was sent its death %s"
          % (net, attacks, played, died))
    count, lines, objects, aside = audit_client("corpse")
    time.sleep(3.0)
    later, again, objects, aside = audit_client("corpse, again")
    wrong = [line for line in again if line in lines and line.startswith("net %s " % net)]
    fixed("ten seconds on the raider's corpse in the client's copy is the server's (the same art, the same flags)",
          count is not None and later is not None and not wrong,
          ("the client's copy differs: " + " | ".join(wrong)) if wrong
          else "it matches" if later is not None else "no verdict from the client")
    alive = leave(game)
    game = None
    check("the client was still running at the end", alive)


def prove_corpsesync2():
    prove_corpsesync(2)


def boot_with(exe, extra):
    """A server from the given program with the proofs' own settings (admin port, traces),
    plus `extra`. The log is appended to."""
    global srv, log
    env = clean_env()
    env.update({"F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport), "F2_SERVER_PACE_MS": "100",
                "F2_AUTOSAVE_SECS": "0", "F2_SERVER_KEEPALIVE": "1", "F2_TRACE_EVENTS": "1"})
    env.update(extra)
    log = open(logpath, "a")
    srv = unthrottle(subprocess.Popen([exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT))
    time.sleep(8)


def host_actor(text):
    """(tile, art, things in the pack) of the host's actor as the server last logged it,
    or None if this server does not log it."""
    rows = re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=-?\d+ pid=\S+ tile=(-?\d+) elev=\d+ flags=\S+ fid=(\S+) invLen=(\d+)", text)
    return rows[-1] if rows else None


def prove_oldsave():
    global game
    # "Saves from every earlier version load unchanged" is what the changelog says, so it
    # is checked: a world is made and saved by each RELEASED server kept in the sandbox,
    # and the server under test is started on that save with the real client joining as
    # the saved host.
    #
    # The world: the host gains experience and a pistol, the party travels to the Den, the
    # clock is run forward and somebody there is killed. What the old server holds at the
    # moment of the save (the host's tile, art, pack and experience, and how many objects
    # the map has) is what the new server must hold after loading it, and the real
    # client's copy must match the new server's field for field.
    olds = [(label, os.path.join(gamedir, name)) for label, name in
            (("v1.4.1", "f2_server-v141.exe"), ("v1.4.0", "f2_server-v140.exe"),
             ("v1.3.2", "f2_server-v132.exe"), ("v1.3.1", "f2_server-v131.exe"))
            if os.path.exists(os.path.join(gamedir, name))]
    check("released servers to make the saves with are in the sandbox", len(olds) >= 1,
          ", ".join(label for label, _path in olds) or "none of f2_server-v141/v140/v132/v131.exe found")
    slot = os.path.join(gamedir, "data", "SAVEGAME", "SLOT16")
    for label, old_exe in olds:
        shutil.rmtree(slot, ignore_errors=True)
        for path in glob.glob(os.path.join(gamedir, "data", "MAPS", "*.SAV")):
            os.remove(path)
        open(logpath, "w").close()
        boot_with(old_exe, {"F2_SERVER_MAP": "arvillag.map"})
        host = Host()
        time.sleep(2.5)
        host.send("login Tester", 3.0)
        admin("xp 0 5000", 1.0)
        admin("give %d" % PISTOL_10MM, 0.5)
        admin("entermap %d" % DENBUS1, 9.0)
        admin("movdone", 1.5)
        admin("timeskip 300", 3.0)
        admin("cdamage 999", 3.0)
        time.sleep(2.0)
        xp_then = re.findall(r"now (\d+)", admin("xp 0 1", 1.0))
        mark = len(logtext())
        admin("audit", 1.5)
        objects_then = re.findall(r"state audit sent \((\d+) objects\)", logtext()[mark:])
        actor_then = host_actor(logtext())
        saved = admin("save 16 proof", 4.0)
        wrote = os.path.exists(os.path.join(slot, "SAVE.DAT"))
        stop_server()
        check("%s: the released server made a world in the Den and saved it" % label, wrote,
              "host %s, experience %s, %s objects on the map; %s"
              % (actor_then, xp_then[-1] if xp_then else "?", objects_then[-1] if objects_then else "?",
                 saved.strip().replace(NL, " ")[:60]))
        if not wrote:
            continue

        mark = len(logtext())
        boot_with(server_exe, {"F2_SERVER_LOAD": "16"})
        game = join({"F2_TRACE_EVENTS": "1", "F2_PLAYER_NAME": "Tester"})
        time.sleep(16)
        text = logtext()[mark:]
        seat = re.findall(r"control claimed by session \d+ \(slot (\d+)\)", text)
        check("%s: the server under test loaded that save and the real client joined as the saved host" % label,
              "slot 16 loaded, ready to serve" in text and bool(seat) and seat[-1] == "0" and game.poll() is None,
              "loaded %s; seat %s" % ("slot 16 loaded, ready to serve" in text, seat[-1] if seat else "none"))
        actor_now = host_actor(text)
        xp_now = re.findall(r"now (\d+)", admin("xp 0 1", 1.0))
        same_actor = actor_then is None or actor_now == actor_then
        same_xp = bool(xp_then) and bool(xp_now) and int(xp_now[-1]) == int(xp_then[-1]) + 1
        check("%s: the host is where it was saved, in the same art, with the same pack and experience" % label,
              same_actor and same_xp,
              "saved %s with %s experience; loaded %s with %s (one more was added to read it)"
              % (actor_then if actor_then else "(not logged by this version)", xp_then[-1] if xp_then else "?",
                 actor_now, xp_now[-1] if xp_now else "?"))
        count, lines, objects, aside = audit_client("old save")
        if count:
            time.sleep(3.0)
            first = lines
            count, lines, objects, aside = audit_client("old save, again")
            lines = [line for line in lines if line in first]
            count = None if count is None else len(lines)
        same_objects = not objects_then or objects == int(objects_then[-1])
        check("%s: the map holds what it held, and the client's copy of it matches the server's" % label,
              count == 0 and same_objects,
              "no verdict from the client" if count is None
              else "%s objects when saved, %d after loading; %d differences between server and client%s"
              % (objects_then[-1] if objects_then else "(not counted by this version)", objects, count,
                 (": " + " | ".join(lines[:6])) if lines else ""))
        alive = leave(game)
        game = None
        check("%s: the client was still running at the end" % label, alive)
        stop_server()
    shutil.rmtree(slot, ignore_errors=True)


def prove_hpcount2():
    global game
    # GitHub issue 44 from the seat it was reported from ("when for example Player2 is
    # attacked ... that player could predict for how many points he's going to be
    # attacked before that attack was animated"): the real client joins a session a wire
    # client hosts, as the second player.
    #
    # The fixture's raiders go for the host, so the real client's own character is hit by
    # the operator instead, and at the moment that matters: two raiders are set on the
    # host and the first one's attacks are still being shown on the real client when
    # three blows of 4 land on its character in one beat. Those blows are queued behind
    # what is being shown. The hit point counter must not move before the first of them
    # is played.
    #
    # The client's log is timestamped as it is written: when each recorded sequence
    # arrives ([presseq] RECV) and when its turn comes to be played ([preplay]), the same
    # two lines on every build. The counter is read off screenshots, one every 8 frames.
    drop_screenshots()
    host = Bot("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    game = join({"F2_VIEWER_SHOT_EVERY": "8", "F2_TRACE_EVENTS": "1"})
    watcher = ShotWatcher()
    time.sleep(14)
    slots = re.findall(r"account 'Brother' -> slot (\d+)", logtext())
    seated = bool(slots) and slots[-1] == "1" and game.poll() is None
    admin("xp 0 30000", 1.0)  # hit points for both, so they outlive the proof
    admin("xp 1 30000", 1.0)
    here = host_tile(logtext())
    # The host steps six tiles away and the raiders are put on either side of it there, so
    # that they are the two critters nearest it when they are set on it.
    admin("warp 6", 0.5)
    placed = [admin("spawn %s 1 %d" % (RAIDER, here + 6 + step), 0.5) for step in (1, -1)]
    time.sleep(1.0)
    clientlog = LogFollower(clientlogpath)
    time.sleep(0.5)
    admin("aggro 2", 0.4)
    # Back beside the second player, whose character is then the critter nearest the
    # host: the operator's damage takes the nearest.
    sent = time.time()
    admin(NL.join(["warp -6", "cdamage 4", "cdamage 4", "cdamage 4"]), 0.3)
    time.sleep(14)
    alive = leave(game)
    game = None
    clientlog.stop = True
    rows = watcher.finish()
    lines = [(when, line) for when, line in clientlog.lines if when >= sent - 0.2]
    every = [(when, line) for when, line in clientlog.lines]
    received = [(n, when, line) for n, (when, line) in
                enumerate([(w, l) for w, l in every if l.startswith("[presseq] RECV")])]
    played = [when for when, line in every if line.startswith("[preplay]")]
    blows = [(n, when) for n, when, line in received if when >= sent - 0.2 and " actor=0 " in line]
    arrived = blows[0][1] if blows else None
    shown = played[blows[0][0]] if blows and blows[0][0] < len(played) else None
    before = [row for row in rows if row[0] < sent]
    after = [row for row in rows if row[0] >= sent]
    moved = next((row[0] for row in after if before and row[1] != before[-1][1]), None)
    check("the real client was the second player in a fight, and three blows landed on its own character while a raider's attacks were still being shown",
          seated and alive and all("placed 1/1" in out for out in placed) and len(blows) >= 3
          and arrived is not None and shown is not None and shown - arrived >= 1.0,
          "blows received %d; the first arrived %s and was played %s after the command"
          % (len(blows), "%.1f s" % (arrived - sent) if arrived else "never",
             "%.1f s" % (shown - sent) if shown else "never"))
    if arrived is None or shown is None or moved is None:
        fixed("the hit point counter does not move before the blow is played", False,
              "counter moved: %s" % ("%.1f s after the command" % (moved - sent) if moved else "never"))
        return
    fixed("the hit point counter does not move before the blow is played",
          moved >= shown - 0.3,
          "the first blow arrived %.1f s after the command and was played at %.1f s; the counter first moved at %.1f s"
          % (arrived - sent, shown - sent, moved - sent))
    if not expect_defect:
        trace = [line for _when, line in lines if line.startswith(("[hp] ", "[console] "))]
        parked = [n for n, line in enumerate(trace) if line.startswith("[hp] own total") and "parked" in line]
        adopted = [n for n, line in enumerate(trace) if line.startswith("[hp] own total") and "adopted" in line]
        behind = [n for n in adopted if n > 0 and trace[n - 1].startswith("[console] shown: You were")]
        check("every new total waited for its own blow: each was adopted right behind a 'You were hit' line",
              len(parked) >= 3 and len(adopted) >= 3 and len(behind) == len(adopted),
              "%d totals parked, %d adopted, %d of them right behind the blow's own line"
              % (len(parked), len(adopted), len(behind)))


for path in glob.glob(os.path.join(gamedir, "data", "SAVEGAME", "SLOT*")):
    shutil.rmtree(path, ignore_errors=True)
for path in glob.glob(os.path.join(gamedir, "data", "MAPS", "*.SAV")):
    os.remove(path)
if os.path.exists(os.path.join(gamedir, "debug.log")):
    os.remove(os.path.join(gamedir, "debug.log"))

try:
    if what not in ("firstjoin", "oldsave"):  # those start the server their own way
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
    elif what == "firstjoin":
        prove_firstjoin()
    elif what == "heldturn":
        prove_heldturn()
    elif what == "reloads":
        prove_reloads()
    elif what == "earlyspace":
        prove_earlyspace()
    elif what == "lookclick":
        prove_lookclick()
    elif what == "corpseloot":
        prove_corpseloot()
    elif what == "hpcount":
        prove_hpcount()
    elif what == "armorview":
        prove_armorview()
    elif what == "nightmap":
        prove_nightmap()
    elif what == "tradeunload":
        prove_tradeunload()
    elif what == "acturn":
        prove_acturn()
    elif what == "syncwalk":
        prove_syncwalk()
    elif what == "auditwatch":
        prove_auditwatch()
    elif what == "syncwalk2":
        prove_syncwalk2()
    elif what == "doorsync":
        prove_doorsync()
    elif what == "doorsync2":
        prove_doorsync2()
    elif what == "fightprobe":
        prove_fightprobe()
    elif what == "corpsesync":
        prove_corpsesync()
    elif what == "corpsesync2":
        prove_corpsesync2()
    elif what == "oldsave":
        prove_oldsave()
    elif what == "nightmap2":
        prove_nightmap2()
    elif what == "hpcount2":
        prove_hpcount2()
    else:
        raise SystemExit("unknown proof '%s' (firstjoin, heldturn, hp, chat, sheet, invhp, clock, hands,"
                         " fidget, cancelui, createui, npcloot, corpseloot, lvlup, dialogdots, stealgear, lookclick, earlyspace, reloads, hpcount, armorview, nightmap, tradeunload, acturn, syncwalk, auditwatch, syncwalk2, doorsync, doorsync2, fightprobe, corpsesync, corpsesync2, oldsave, nightmap2, hpcount2, musicline or"
                         " tradescroll)" % what)
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
