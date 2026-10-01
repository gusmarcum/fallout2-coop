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
  retry     issue 13, follow-up. The far attempt, then a second attempt in the same turn
            with no AP left: vanilla abandons it before it starts, so nothing may be
            recorded or shipped (v1.4.0 shipped the crouch from where the host stood).

--expect-defect inverts the checks of the fix, to show each defect on an older build.

Nothing here touches a live world: point it at a sandbox. Each mode empties the sandbox's
save slots and working maps first.

usage: python -u issue_wire_proof.py <timer|templexp|rest|cancel|create|reach|retry|lvlsfx|ownline|joinfreeze|all> <f2_server.exe>
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
RAIDER = "0x010000EE"
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


def prove_retry():
    # The ask that comes with NO action points left (GitHub issue 13, follow-up). The AI's
    # attack loop asks for a weapon on the ground again after a hunt that fell short, and
    # vanilla abandons that ask before it starts (nothing shown, rc -1). v1.4.0 recorded
    # and shipped the crouch from where the critter stood, once per ask, with the weapon
    # still on the ground ("a weird pickup animation loop"). The AI only produces the ask
    # in some turns (a raider that threw the spear and hunts it again), so the host asks
    # here, through the same actionPickUp: with the Bonus Move perk its two free moves
    # keep its turn alive at 0 AP (vanilla's H-12 rule ends a turn at 0 AP and no free
    # moves). Three spears at its feet cost 3 AP each (9 AP -> 0); the fourth lies three
    # hexes off. The server log says which: "[anim-cb] skipped: the sequence's reach check
    # already failed" followed by a shipped sequence is v1.4.0's crouch; "NOT attempted: no
    # action points left" is the fixed refusal.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    admin("xp 0 80000", 1.0)  # levels, so a perk is owed
    host.send("sheetopen", 0.5)
    host.send("perkpick 3", 0.8)  # Bonus Move: two free moves a turn
    host.send("sheetclose", 0.8)
    perk = re.findall(r"control perkpick slot=0 perk=3 rc=(-?\d+)", logtext())
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    admin("give %d" % SPEAR, 0.5)
    admin("drop %d" % SPEAR, 1.0)
    far = re.findall(r"CONNECT net=(\d+) pid=%d tile=%d " % (SPEAR, start), logtext())
    far = int(far[-1]) if far else -1
    admin("warp 3", 1.0)
    here = start + 3
    for _ in range(3):
        admin("give %d" % SPEAR, 0.5)
        admin("drop %d" % SPEAR, 1.0)
    near = [int(n) for n in re.findall(r"CONNECT net=(\d+) pid=%d tile=%d " % (SPEAR, here), logtext())]
    # A raider fourteen hexes past the host keeps the fight on; the spears are out of its
    # perception, so it comes for the host and not for them.
    out = admin("spawn %s 1 %d" % (RAIDER, here + 14), 1.5)
    admin("aggro 1", 3.0)
    ready = far > 0 and len(near) == 3 and "placed 1/1" in out and len(host.events(EVENT_COMBAT_ENTER)) >= 1
    check("the host has Bonus Move, three spears lie at its feet and a fourth three hexes off, a fight is on",
          ready and perk and perk[-1] == "0",
          "perk rc %s; near spears %s, far spear %d; %s" % (perk[-1:] or "none", near, far, out[:40]))
    mark = len(logtext())
    for _ in range(3):
        admin("pickup %d" % SPEAR, 1.5)
    three = logtext()[mark:]
    taken = re.findall(r"\[cpickup\] critter=1 item_net=(\d+) taken", three)
    check("the three spears at the host's feet were taken, 3 AP each, nine in all",
          sorted(int(n) for n in taken) == sorted(near), "taken %s of %s" % (taken, near))
    # The fourth ask, with no AP left.
    mark = len(logtext())
    admin("pickup %d" % SPEAR, 2.5)
    retry = logtext()[mark:]
    still_fighting = len(host.events(EVENT_COMBAT_EXIT)) == 0
    shipped = len(re.findall(r"\[presseq\] SEND ops=\d+ bytes=\d+ actor=1\b", retry))
    refused = "critter=1 item_net=%d NOT attempted: no action points left" % far in retry
    skipped = "reach check already failed" in retry
    gone = "DISCONNECT net=%d " % far in retry
    check("the fight was still on, and it was still the host's turn, when it asked for the fourth",
          still_fighting and "[cmove-rec] net=1 " not in three and ("[cmove-rec]" not in retry or refused),
          "combat exits %d" % len(host.events(EVENT_COMBAT_EXIT)))
    fixed("the ask with no AP left records and ships nothing and takes nothing, as in vanilla",
          shipped == 0 and refused and not skipped and not gone,
          "%d sequences shipped for the host; refused=%s; old skip line=%s; far spear taken=%s"
          % (shipped, refused, skipped, gone))
    if expect_defect:
        check("the old server shipped the crouch from where the host stood, the spear still three hexes off",
              shipped >= 1 and skipped and not gone, "%d shipped, skip line %s, taken %s" % (shipped, skipped, gone))
    shutdown()


EVENT_COMBAT_EXIT = 13


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


EVENT_SFX = 18
EVENT_SNAPSHOT_OBJECT = 8


def sfx_names(client):
    """Every sound effect name streamed to this client so far (EVENT_SFX: u16 length + name)."""
    names = []
    for body in client.events(EVENT_SFX):
        if len(body) >= 2:
            n = struct.unpack_from("<H", body, 0)[0]
            names.append(body[2:2 + n].decode("latin1"))
    return names


def actor_level(slot):
    found = re.findall(r"level (\d+)", admin("sheet %d" % slot, 0.3))
    return int(found[0]) if found else None


def prove_lvlsfx():
    # Issue 21, the server's half. The level-up sound was played where the level is
    # awarded, by the dedicated server, as a broadcast, and only for the host: the host's
    # level-up sounded on every player's screen and nobody else's ever did. The server
    # now sends no sound for it at all; each client plays its own when its sheet row
    # arrives (the screen proof `lvlup` reads that).
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    second = Client("Brother")
    time.sleep(2.5)
    second.send("login Brother", 4.0)
    before = actor_level(0)
    host_mark = len(sfx_names(host))
    second_mark = len(sfx_names(second))
    admin("xp 0 5000", 3.0)
    after = actor_level(0)
    host_sfx = sfx_names(host)[host_mark:]
    second_sfx = sfx_names(second)[second_mark:]
    check("the host went up a level", before is not None and after is not None and after > before,
          "level %s -> %s" % (before, after))
    fixed("the server streams no level-up sound for it (each client plays its own)",
          "levelup" not in host_sfx and "levelup" not in second_sfx,
          "sounds to the host %s, to the second player %s" % (host_sfx[-3:], second_sfx[-3:]))
    if expect_defect:
        check("the old server broadcast the host's level-up sound to the second player",
              "levelup" in second_sfx, "%s" % second_sfx[-3:])
    shutdown()


def prove_ownline():
    # Issue 25. A console line printed while one player's interaction fires (a door
    # script's "You failed to pick the lock" through display_msg, or the engine's own
    # lines) was a broadcast, so every player read it as their own. Now the player who
    # acted gets the line as written, addressed, and everyone else gets it under that
    # player's name. The line used here is the engine's: the host, loaded to its weight
    # limit, picks up a stack it cannot carry ("You cannot pick up that item. You are at
    # your maximum weight capacity."), which takes the same path as a script's line.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    second = Client("Brother")
    time.sleep(2.5)
    second.send("login Brother", 4.0)
    rows = re.findall(r"\[actors\] srv slot=(\d) obj=\S+ netId=(\d+) pid=\S+ tile=(-?\d+)", logtext())
    nets = {int(slot): int(net) for slot, net, _tile in rows}
    start = int([tile for slot, _net, tile in rows if slot == "0"][-1])
    admin("give %d" % SPEAR, 0.5)
    admin("drop %d" % SPEAR, 1.0)  # one spear at the host's feet
    stack = re.findall(r"CONNECT net=(\d+) pid=%d tile=%d " % (SPEAR, start), logtext())
    stack = int(stack[-1]) if stack else -1
    admin("give %d 200" % SPEAR, 0.5)  # 800 lbs: past any carry weight
    check("both players are in, a spear lies at the feet of the host, who is loaded past its limit",
          1 in nets and stack > 0, "players %s, spear net %d" % (nets, stack))
    host_mark = len(host.console())
    second_mark = len(second.console())
    host.send("get %d" % stack, 3.0)
    # The wire is one stream for every viewer; an addressed line carries the addressee's
    # netId and the other viewers drop it. So the host's stream shows every line, and
    # who each one is for.
    lines = [(t, a) for t, a, _c in host.console()[host_mark:]]
    plain = [t for t, a in lines if a == nets.get(0)]
    named = [t for t, a in lines if a == nets.get(1)]
    everyone = [t for t, a in lines if a == 0]
    check("the pickup was refused with a line", len(lines) >= 1 and "weight" in lines[0][0], "got %r" % lines[:2])
    fixed("the player who acted gets the line as written, addressed to them alone",
          len(plain) == 1 and plain[0].startswith("You cannot pick up") and not everyone,
          "to the host %r; to everyone %r" % (plain[:1], everyone[:1]))
    fixed("everyone else gets it under that player's name",
          len(named) == 1 and len(plain) == 1 and named[0] == "Tester: " + plain[0],
          "to the second player %r" % named[:1])
    if expect_defect:
        check("the old server broadcast one unaddressed line to both",
              len(everyone) == 1 and not plain and not named, "to everyone %r" % everyone[:1])
    shutdown()


EVENT_TURN_START = 14


def turn_starts(client):
    """The actor netId of every TURN_START streamed to this client so far, in order."""
    return [struct.unpack_from("<i", body, 0)[0] for body in client.events(EVENT_TURN_START) if len(body) >= 4]


def prove_joinfreeze():
    # Issue 16. A keepalive server froze its world only while NO client was connected; a
    # session that was connected but not yet logged in (the pre-join account query, the
    # creation screen, the load) thawed it with every body unpiloted. A player who had
    # left next to hostiles came back to find the fight had run on during their join,
    # their own turns ending by themselves, eight to ten enemy turns' worth. The world
    # now freezes until a slot is bound. Here: the host in a fight drops, the server sits
    # with nobody in, and a connection comes back and waits a while before logging in.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    out = admin("spawn %s 1 %d" % (RAIDER, start + 3), 1.0)
    admin("aggro 1", 1.0)
    time.sleep(2.0)
    fighting = len(host.events(EVENT_COMBAT_ENTER)) >= 1
    host.close()
    clients.remove(host)
    time.sleep(6.0)  # nobody in
    back = Client("Tester")
    time.sleep(4.0)  # connected, not logged in: a client busy with its pre-join handshake
    before = turn_starts(back)
    back.send("login Tester", 3.0)
    time.sleep(22.0)
    after = turn_starts(back)[len(before):]
    first_own = after.index(1) if 1 in after else -1
    check("the host was in a fight when it dropped, and a connection came back", fighting and "placed 1/1" in out,
          out[:40])
    fixed("the world stays frozen while the connection is in but not yet logged in (no turn runs)",
          before == [], "turns before the login: %s" % before[:12])
    fixed("after the login the host's turn comes within the round and then waits for the player",
          first_own >= 0 and after.count(1) == 1 and first_own <= 12,
          "turns after the login: %s" % after[:20])
    if expect_defect:
        check("the old server ran the fight during the join, the host's turns ending by themselves",
              len(before) >= 1 or after.count(1) >= 2,
              "before the login %s; host turns after it %d" % (before[:10], after.count(1)))
    shutdown()


EVENT_DIALOG_NODE = 32
EVENT_PROMPT_ASK = 63


def snapshot_objects(client):
    """(netId, pid, tile, elevation) of every object in the join snapshot so far."""
    rows = []
    for body in client.events(EVENT_SNAPSHOT_OBJECT):
        if len(body) >= 16:
            rows.append(struct.unpack_from("<iiii", body, 0))
    return rows


def last_tiles(client):
    """netId -> (tile, elevation) from the latest snapshot row of each object."""
    tiles = {}
    for net, _pid, tile, elev in snapshot_objects(client):
        tiles[net] = (tile, elev)
    return tiles


def hex_distance(a, b):
    """A rough hex distance (rows are 200 tiles wide)."""
    return max(abs(a % 200 - b % 200), abs(a // 200 - b // 200))


def prove_entryring():
    # Issue 20. The Klamath graze map's enter script moves the player to hex 17704 when
    # the party arrives from the trapping caves (GVAR_LOAD_MAP_INDEX 27 == 13); the party
    # had been ringed around the host at the entering tile, 21 rows away, before that
    # script ran. The fixed server rings everyone again when the script moved the host.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    second = Client("Brother")
    time.sleep(2.5)
    second.send("login Brother", 4.0)
    rows = re.findall(r"\[actors\] srv slot=(\d) obj=\S+ netId=(\d+) ", logtext())
    nets = {int(slot): int(net) for slot, net in rows}
    admin("gvar 27 13", 0.5)  # "we came from the trapping caves"
    admin("entermap 14", 10.0)  # klagraz, the graze map
    tiles = last_tiles(host)
    host_at = tiles.get(nets.get(0), (None, None))
    second_at = tiles.get(nets.get(1), (None, None))
    moved = "map: the enter script moved the host" in logtext()
    check("both players are in and the party arrived on the graze map",
          1 in nets and "klagraz" in logtext().lower() and host_at[0] is not None and second_at[0] is not None,
          "host %s, second %s" % (host_at, second_at))
    check("the map's enter script moved the host away from the entering tile",
          host_at[0] is not None and hex_distance(host_at[0], 21937) > 6,
          "host at %s, entering tile 21937" % (host_at,))
    distance = hex_distance(host_at[0], second_at[0]) if host_at[0] is not None and second_at[0] is not None else 999
    fixed("the second player stands beside the host, not where the ring was made",
          distance <= 6 and host_at[1] == second_at[1],
          "%d hexes apart; server %s" % (distance, "ringed the party again" if moved else "did not re-ring"))
    if expect_defect:
        check("the old server left the second player where the ring had been made, far from the host",
              distance > 6, "%d hexes apart" % distance)
    shutdown()


def dialog_nodes(client):
    """Every dialog node streamed so far: (speaker netId, driver netId, reply, [option texts])."""
    nodes = []
    for body in client.events(EVENT_DIALOG_NODE):
        try:
            pos = 0
            speaker, driver, _reaction = struct.unpack_from("<iii", body, pos)
            pos += 12
            n = struct.unpack_from("<H", body, pos)[0]
            reply = body[pos + 2:pos + 2 + n].decode("latin1")
            pos += 2 + n
            n = struct.unpack_from("<H", body, pos)[0]
            pos += 2 + n  # audio file name
            pos += 4  # head fid
            count = struct.unpack_from("<H", body, pos)[0]
            pos += 2
            options = []
            for _ in range(count):
                n = struct.unpack_from("<H", body, pos)[0]
                options.append(body[pos + 2:pos + 2 + n].decode("latin1"))
                pos += 2 + n + 4  # text, then its reaction
            nodes.append((speaker, driver, reply, options))
        except struct.error:
            break
    return nodes


def prove_orders():
    # Issue 22. A party member's Combat Control is a text node in co-op; it offered the
    # disposition and the six orders, never the window's "use best weapon" and "wear best
    # armor". A villager is made a party member, the host talks to him and presses Combat
    # Control (`dparty`); the node must list the two new lines, and picking one must run
    # the window's handler (the server logs it).
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    # A spawned Cassidy (pid 89) wearing the generic villager dialog script (scripts.lst
    # line 10): a map-placed critter has an id below 18000 and never counts as a party
    # member, a spawned one does.
    mark = len(logtext())
    admin("spawn 0x01000059 1 %d 9" % (start + 2), 1.5)
    spawned = re.findall(r"\[evt\] SPAWN\s+net=(\d+) pid=16777305", logtext()[mark:])
    villager = int(spawned[-1]) if spawned else -1
    out = admin("partyadd 89", 1.0)
    host.send("talk %d" % villager, 8.0)  # walk-then-talk
    before = len(dialog_nodes(host))
    talking = before >= 1
    host.send("dparty", 3.0)
    nodes = dialog_nodes(host)
    orders = nodes[-1] if len(nodes) > before else None
    options = orders[3] if orders else []
    weapon = next((i for i, text in enumerate(options) if "best weapon" in text.lower()), -1)
    armor = next((i for i, text in enumerate(options) if "best armor" in text.lower()), -1)
    check("a spawned companion joined the party and the host opened a conversation with him",
          villager > 0 and "rc=0" in out and talking, "companion net %d; %s; nodes %d" % (villager, out[:50], before))
    fixed("the Combat Control node lists \"use your best weapon\" and \"wear your best armor\"",
          orders is not None and weapon >= 0 and armor >= 0, "options %r" % options[:12])
    if weapon >= 0:
        host.send("dsay %d" % weapon, 2.5)
    if armor >= 0:
        host.send("dsay %d" % armor, 2.5)
    host.send("dend", 1.5)
    log = logtext()
    ran = re.findall(r"party orders [^:\n]*: (use best weapon|wear best armor) -> ([^\n]*)", log)
    fixed("picking them runs the window's handlers (the server says what it found)",
          len(ran) == 2, "%r" % ran[:2])
    shutdown()


modes = {"timer": prove_timer, "templexp": prove_templexp, "rest": prove_rest,
         "cancel": prove_cancel, "create": prove_create, "reach": prove_reach, "retry": prove_retry,
         "lvlsfx": prove_lvlsfx, "ownline": prove_ownline, "joinfreeze": prove_joinfreeze,
         "entryring": prove_entryring, "orders": prove_orders}
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
