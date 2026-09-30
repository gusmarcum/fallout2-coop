"""Headless proofs for the server side of GitHub issues 5, 6, 10, 12 and 14.

Every check here is decided by the server: what it streams (the console lines on the
wire, parsed and checked against their address), what it logs, and what the operator's
`sheet` reply says about a row. The players are fake wire clients that log in by name,
so no game window is needed.

  timer     issue 5. The host arms a charge. "You set the timer." must go to the host
            alone, and the second player must be told "Tester sets the timer." instead.
  templexp  issue 6. The party walks out of the Temple of Trials into Arroyo for the
            first time, where the village's map-enter script pays the Temple XP and
            prints "You gain N experience points", the Temple line and the reputation
            line. Those lines must reach the players (they used to be dropped with the
            rest of what a map prints while it loads).
  rest      issue 10. The host is hurt and rests three hours, twice. The first rest
            counts 169 of the 180 minutes a heal needs (vanilla rounding) and heals
            nothing; the second must heal, because the count now carries over.
  cancel    issue 12. The second player opens the sheet, buys skill points, takes perks
            (Tag! with its follow-up included), and cancels. The row must be back where
            it was, skill values included. A sheet closed with Done keeps its spends.
  create    issue 14. A new player created female and 30 must arrive female and 30, in
            the female body. A creation line from an older client (no sex, no age) must
            still work and give the old male, 25.
  reach     issue 13. In a fight, a spear lies twelve hexes from the host and the host
            goes for it (the same actionPickUp an NPC's weapon hunt calls). One turn's walk
            cannot reach it, so nothing may be taken that turn; the next turn's walk reaches
            it and it is taken.

--expect-defect inverts the checks of the fix, to show each defect on an older build.

Nothing here touches a live world: point it at a sandbox. Each mode empties the sandbox's
save slots and working maps first.

usage: python -u issue_wire_proof.py <timer|templexp|rest|cancel|create|all> <f2_server.exe>
                                     <game dir> <net port> <cmd port> [--expect-defect]
"""
import glob, os, re, shutil, socket, struct, subprocess, sys, threading, time

args = [a for a in sys.argv[1:] if not a.startswith("--")]
expect_defect = "--expect-defect" in sys.argv
what, server_exe, gamedir, port, cmdport = args[0], args[1], args[2], int(args[3]), int(args[4])

NL = chr(10)
EVENT_MAP_TRANSITION = 11
EVENT_COMBAT_ENTER = 12
EVENT_CONSOLE = 16
DYNAMITE = 51
SPEAR = 7
ARVILLAG = 4
logpath = os.path.join(gamedir, "issue-wire-proof-server.log")
results = []
srv = None
log = None
clients = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ("  [" + detail + "]" if detail else ""))


def fixed(name, ok, detail=""):
    """A check of the fix: inverted when the defect is being shown."""
    if expect_defect:
        check("(defect shown) NOT: " + name, not ok, detail)
    else:
        check(name, ok, detail)


class Client:
    """A fake player: a wire connection that logs in by name and keeps the stream."""

    def __init__(self, tag):
        self.tag = tag
        self.buf = bytearray()
        self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.stop = threading.Event()
        threading.Thread(target=self.drain, daemon=True).start()
        clients.append(self)

    def drain(self):
        while not self.stop.is_set():
            try:
                data = self.s.recv(65536)
                if not data:
                    return
                self.buf += data
            except Exception:
                return

    def send(self, line, wait=0.4):
        self.s.sendall((line + NL).encode())
        time.sleep(wait)

    def events(self, wanted):
        """Bodies of every event of type `wanted` in the stream so far.
        Frame: 18-byte header (u32 seq, u32 sim, u32 payload length, u16 count, u32 entry
        base). Event: u8 type, u8 flags, u16 length."""
        data = bytes(self.buf)
        bodies = []
        if data[:4] != b"F2NS":
            return bodies
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

    def console(self):
        """Every console line so far, as (text, addressee netId, channel)."""
        lines = []
        for body in self.events(EVENT_CONSOLE):
            if len(body) < 2:
                continue
            n = struct.unpack_from("<H", body, 0)[0]
            tail = body[2 + n:]
            lines.append((body[2:2 + n].decode("latin1"),
                          struct.unpack_from("<i", tail, 0)[0] if len(tail) >= 4 else 0,
                          struct.unpack_from("<i", tail, 4)[0] if len(tail) >= 8 else 0))
        return lines

    def close(self):
        self.stop.set()
        try:
            self.s.close()
        except Exception:
            pass


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


def wipe_sandbox():
    for path in glob.glob(os.path.join(gamedir, "data", "SAVEGAME", "SLOT*")):
        shutil.rmtree(path, ignore_errors=True)
    for path in glob.glob(os.path.join(gamedir, "data", "MAPS", "*.SAV")):
        os.remove(path)


def boot(mapname):
    global srv, log
    wipe_sandbox()
    env = dict(os.environ)
    for name in list(env):
        if name.startswith("F2_"):
            env.pop(name)
    env.update({"F2_SERVER_MAP": mapname, "F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
                "F2_SERVER_PACE_MS": "100", "F2_AUTOSAVE_SECS": "0", "F2_SERVER_KEEPALIVE": "1",
                "F2_TRACE_EVENTS": "1"})
    log = open(logpath, "w")
    srv = subprocess.Popen([server_exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT)
    time.sleep(7)


def shutdown():
    global srv, log
    for client in clients:
        client.close()
    del clients[:]
    try:
        admin("quit", 1)
    except Exception:
        pass
    time.sleep(1.5)
    if srv is not None and srv.poll() is None:
        srv.kill()
    srv = None
    if log is not None:
        log.close()
    log = None


def net_of_slot(slot):
    rows = re.findall(r"\[actors\] srv slot=%d obj=\S+ netId=(-?\d+)" % slot, logtext())
    return int(rows[-1]) if rows else None


def two_players():
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    second = Client("Brother")
    time.sleep(2.5)
    second.send("login Brother", 4.0)
    return host, second


def prove_timer():
    boot("arvillag.map")
    host, second = two_players()
    host_net, second_net = net_of_slot(0), net_of_slot(1)
    check("two players are in", host_net is not None and second_net is not None,
          "netIds %s and %s" % (host_net, second_net))
    admin("give %d" % DYNAMITE, 1.0)
    host.send("useitem_armexplosive %d 180" % DYNAMITE, 3.0)
    check("the host armed the charge", "useitem_armexplosive pid=%d seconds=180" % DYNAMITE in logtext())

    lines = second.console()
    you = [(text, addr) for text, addr, _ch in lines if text.startswith("You set the timer")]
    theirs = [(text, addr) for text, addr, _ch in lines if "sets the timer" in text]
    fixed("'You set the timer.' is addressed to the host alone",
          len(you) >= 1 and all(addr == host_net for _t, addr in you), repr(you[:2]))
    fixed("the second player is told 'Tester sets the timer.'",
          any(text == "Tester sets the timer." and addr == second_net for text, addr in theirs), repr(theirs[:2]))
    shutdown()


def prove_templexp():
    boot("artemple.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    before = len(host.console())
    admin("entermap %d" % ARVILLAG, 3.0)
    for _ in range(4):
        admin("movdone", 1.5)
    time.sleep(3)
    # The arrival itself, off the wire: EVENT_MAP_TRANSITION carries (map index, elevation).
    moves = [struct.unpack_from("<i", body, 0)[0] for body in host.events(EVENT_MAP_TRANSITION)
             if len(body) >= 4]
    check("the party arrived in Arroyo (the server told the player to change map)", ARVILLAG in moves,
          "map transitions %s" % moves)
    arrived = [line for line, _addr, _ch in host.console()[before:]]
    gained = [line for line in arrived if "experience" in line.lower()]
    fixed("the Temple's 'You gain ... experience points' line reaches the players",
          len(gained) >= 1, repr(gained[:2]))
    fixed("so do the rest of the lines the village prints on arrival",
          len(arrived) >= 3, "%d lines: %r" % (len(arrived), arrived[:4]))
    shutdown()


def rest_hp(text):
    return [int(hp) for hp in re.findall(r"control rest slot=0 3:00 kind=0 outcome=0 hp=(\d+)", text)]


def prove_rest():
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    admin("hurt 10", 1.0)
    # The operator's rest reports the hit points; one minute of it reads them (and counts
    # that one minute, which changes nothing below: 1 + 169 is still short of 180).
    out = admin("rest 1", 1.0)
    start = re.findall(r"hp (\d+) -> (\d+)", out)
    hurt = int(start[0][1]) if start else None
    host.send("rest 180", 4.0)
    host.send("rest 180", 4.0)
    hps = rest_hp(logtext())
    check("the host is hurt and two three-hour rests ran", hurt is not None and len(hps) == 2,
          "hp %s, then after each rest %s" % (hurt, hps))
    if hurt is not None and len(hps) == 2:
        check("the first three-hour rest heals nothing (169 of the 180 minutes, vanilla rounding)",
              hps[0] == hurt, "hp %d then %d" % (hurt, hps[0]))
        fixed("the second three-hour rest heals, because the count carried over", hps[1] > hps[0],
              "hp %d then %d" % (hps[0], hps[1]))
    shutdown()


def sheet(slot):
    return admin("sheet %d" % slot, 0.3)


def skill_value(text, skill, nth=-1):
    values = re.findall(r"control skillup slot=1 skill=%d rc=0 value=(-?\d+)" % skill, text)
    return int(values[nth]) if values else None


def prove_cancel():
    boot("arvillag.map")
    host, second = two_players()
    admin("sp 1 20", 0.5)
    admin("xp 1 80000", 1.0)
    admin("stat 1 in 8", 0.5)  # Educated needs Intelligence 6
    start = sheet(1)
    check("the second player has points and owed perks to spend", "unspent" in start, start)

    # Spend, then Cancel.
    mark = len(logtext())
    second.send("sheetopen")
    for _ in range(3):
        second.send("skillup 0")
    second.send("perkpick 18")  # Educated: +2 unspent points on top of the perk
    second.send("perkpick 51")  # Tag!, which owes a follow-up...
    second.send("tagpick 12")   # ...answered with a fourth tagged skill
    for _ in range(2):
        second.send("skillup 12")
    spent = sheet(1)
    session = logtext()[mark:]
    picks = len(re.findall(r"control perkpick slot=1 perk=\d+ rc=0", session))
    check("the spends landed before the Cancel: three points, Educated (+2 points), Tag! and a"
          " fourth tag, two points in it", spent != start and "skillup slot=1 skill=0 rc=0" in session
          and picks == 2 and "control tagpick slot=1 a=12 b=-1 rc=0" in session,
          "%s; %d perk picks taken" % (spent, picks))
    first_small_guns = skill_value(session, 0, 0)
    second.send("sheetcancel", 0.8)
    second.send("sheetclose", 0.8)
    after = sheet(1)
    fixed("after Cancel the row is back where it was: points, level, owed perks, tags",
          after == start, "before %s | after %s" % (start, after))

    # The skill values themselves: the next point bought must cost the same and land on
    # the same value as the first one did before the Cancel.
    mark = len(logtext())
    second.send("sheetopen")
    second.send("skillup 0")
    again = skill_value(logtext()[mark:], 0, 0)
    second.send("sheetcancel", 0.8)
    second.send("sheetclose", 0.8)
    fixed("after Cancel the skill values are back too (the same point lands on the same value)",
          again is not None and again == first_small_guns, "%s then %s" % (first_small_guns, again))

    # Done keeps what was spent.
    before_done = sheet(1)
    second.send("sheetopen")
    second.send("skillup 0")
    second.send("skillup 0")
    second.send("sheetclose", 0.8)
    after_done = sheet(1)
    points = lambda text: int(re.findall(r"unspent (-?\d+)", text)[0]) if "unspent" in text else None
    check("a sheet closed with Done keeps its spends",
          points(before_done) is not None and points(after_done) is not None
          and points(after_done) < points(before_done), "unspent %s then %s" % (points(before_done), points(after_done)))
    shutdown()


def prove_create():
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    new = Client("Sister")
    time.sleep(2.5)
    new.send("create 5 6 5 7 6 6 5 -1 -1 -1 -1 -1 1 30", 0.5)
    new.send("login Sister", 5.0)
    old = Client("Olduser")
    time.sleep(2.5)
    old.send("create 5 5 5 5 5 5 5 -1 -1 -1 -1 -1", 0.5)
    old.send("login Olduser", 5.0)
    text = logtext()
    made = re.findall(r"\[create\] slot=(\d+) SPECIAL:[ \d]+ maxhp=\d+ hp=\d+(.*)", text)
    check("both characters were created", len(made) >= 2, repr(made[:3]))
    sister = [rest for slot, rest in made if slot == "1"]
    olduser = [rest for slot, rest in made if slot == "2"]
    fixed("the character created female and 30 is female and 30",
          len(sister) == 1 and "gender=1 age=30" in sister[0], repr(sister[:1]))
    body = lambda rest: int(re.findall(r"fid=0x([0-9A-Fa-f]+)", rest)[0], 16) & 0xFFF if "fid=0x" in rest else None
    fixed("and she is in the female body, not the male one the row was seeded with",
          len(sister) == 1 and len(olduser) == 1 and body(sister[0]) is not None
          and body(sister[0]) != body(olduser[0]),
          "body art %s vs %s" % (body(sister[0]) if sister else None, body(olduser[0]) if olduser else None))
    check("a creation line from an older client still works: male, 25",
          len(olduser) == 1 and ("gender=0 age=25" in olduser[0] or "gender" not in olduser[0]), repr(olduser[:1]))
    shutdown()


def attempt(text, spear):
    """One pickup attempt, read off the server log: when the spear left the ground (the
    index of its DISCONNECT, or None), how many steps the host had walked by then, and the
    fixed server's own verdict line."""
    lines = text.splitlines()
    gone = next((i for i, line in enumerate(lines) if "DISCONNECT net=%d " % spear in line), None)
    steps = [i for i, line in enumerate(lines) if re.search(r"\[evt\] MOVE\s+net=1 ", line)]
    before = sum(1 for i in steps if gone is None or i < gone)
    verdict = re.findall(r"\[cpickup\] critter=1 item_net=%d (taken|NOT taken)[^(]*\(critter tile (-?\d+),"
                         r" item was at tile (-?\d+), distance now (\d+)\)" % spear, text)
    return gone, before, len(steps), (verdict[0] if verdict else None)


def reach_attempt(distance):
    """Boot, drop a spear where the host stands, move the host `distance` tiles on, start a
    fight, and have the host go for the spear (the actionPickUp an NPC's weapon hunt calls).
    Returns the attempt as read off the log, and the spear's netId."""
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    admin("give %d" % SPEAR, 0.5)
    admin("drop %d" % SPEAR, 1.0)
    dropped = re.findall(r"CONNECT net=(\d+) pid=%d tile=%d " % (SPEAR, start), logtext())
    spear = int(dropped[-1]) if dropped else -1
    admin("warp %d" % distance, 1.0)
    host.send("cstart", 3.0)
    ready = spear > 0 and len(host.events(EVENT_COMBAT_ENTER)) >= 1
    mark = len(logtext())
    admin("pickup %d" % SPEAR, 2.0)
    result = attempt(logtext()[mark:], spear)
    ap = re.findall(r"\[cmove-rec\] net=1 toObj=%d ap=(\d+)" % spear, logtext()[mark:])
    shutdown()
    return ready, result, (int(ap[0]) if ap else None)


def prove_reach():
    # Out of reach: 12 tiles, more than the host's AP can walk in one turn.
    ready, (gone, stepped, walked, verdict), ap = reach_attempt(12)
    check("far: the spear lies where the host stood, the host is 12 tiles on, a fight is on", ready,
          "host AP %s" % ap)
    fixed("far: this turn's walk (all of the host's AP) cannot reach the spear, so it stays on the ground",
          gone is None and verdict is not None and verdict[0] == "NOT taken" and int(verdict[3]) > 1,
          "walked %d steps; %s" % (walked, "spear taken after %d of them" % stepped if gone is not None
                                   else "verdict %r" % (verdict,)))
    if expect_defect:
        check("far: the old server took it before the host had taken a single step",
              gone is not None and stepped == 0, "spear taken after %d of %d steps" % (stepped, walked))

    # Within reach: 6 tiles, walkable this turn. Taken, after the walk.
    ready, (gone, stepped, walked, verdict), ap = reach_attempt(6)
    check("near: the spear lies where the host stood, the host is 6 tiles on, a fight is on", ready,
          "host AP %s" % ap)
    fixed("near: the walk reaches the spear and only then is it taken",
          gone is not None and walked >= 1 and stepped == walked and verdict is not None and verdict[0] == "taken",
          "walked %d steps, spear taken after %d of them; %r" % (walked, stepped, verdict))


modes = {"timer": prove_timer, "templexp": prove_templexp, "rest": prove_rest,
         "cancel": prove_cancel, "create": prove_create, "reach": prove_reach}
try:
    for name in (modes if what == "all" else [what]):
        if name not in modes:
            raise SystemExit("unknown proof '%s'" % name)
        print("== " + name)
        modes[name]()
finally:
    if srv is not None:
        shutdown()

failed = [name for name, ok, _detail in results if not ok]
print("")
print("%d/%d checks passed%s" % (len(results) - len(failed), len(results),
                                  " (the defects were reproduced as expected)" if expect_defect and not failed else ""))
for name in failed:
    print("   FAILED: " + name)
sys.exit(1 if failed else 0)
