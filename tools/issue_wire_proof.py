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

  joinfreeze  issue 16 (and 32). The host drops out of a fight on its own turn, the server
            sits with nobody in, and a connection comes back and waits before logging in.
            It must be sent the world while it waits, with the sim clock standing still
            and the turn still the host's; the login gets the turn said once more. Then
            the same for a second player who comes back alone.

  sneakrun  issue 29. The host turns Sneak on and walks: it stays on. It runs: the run must
            end it, as vanilla's run click does. With the Silent Running perk the run
            keeps it.

  hostplace  issue 20. Two players stand in Arroyo and the SECOND one asks for a map change
            with no tile named, as a script's load_map does when that player's dialog runs
            it. The host must arrive beside them; it used to keep the tile number it had
            on the old map.

  companions  issues 20 and 41. Two players and a companion that follows the second one.
            Its owner changes floor: it goes with them. The other player changes floor: it
            stays where it stood. With no owner recorded it keeps to whoever is on its
            floor. After a map change it stands beside its owner, and a save and restart
            keeps who it follows.

  dogs      issue 43. The host enters Grisham's brahmin pasture and waits. The wild dogs
            must run down the map to the herd and attack it; they used to stand at the
            top, because the server answered every script's anim_busy with "no".

  rocks     issue 45. The host arms a stick of dynamite beside the rocks under Modoc's
            outhouse, leaves the map (which sets a ticking charge off, as in vanilla) and
            comes back: the quest flag must be set and the rocks gone.

  armoroff  issue 28. The host is a man and the second player a woman. She puts a leather
            armor on and takes it off: she must be back in her own body (she used to
            stand in the host's). She then drops the armor while wearing it, and a spear
            while holding it: both must leave her pack (neither did), and her armor class
            must be back where it started.

  bess      issue 42. The host enters Modoc: Bess the brahmin must be lying on her side
            (her script lays her down with a sequence of animations, which left no trace
            on the server). The host heals her leg: she must get up, and still be up in
            the next snapshot.

  bunload   issue 38, the server's half. The host carries a loaded pistol into a trade
            and asks for it to be unloaded where it lies: the trade's stream must say
            what a weapon is loaded with, and after the unload show the pistol empty and
            its rounds beside it. The same for a loaded weapon in the merchant's stock.

  gestures  issue 40. The host stands beside the Den's orphans until one tries its pocket,
            then fights a raider that was handed a stimpak, an empty pistol and its
            rounds. Both the orphan's move and the raider's raised hands must be sent to
            the players as recorded animations (neither ever was).

  pronekill  issue 39. The host knocks a raider down and the operator kills it where it
            lies. The kill must be shown with the blood animation of a lying critter and
            the corpse given a lying art in its blood (the server recorded no blood for a
            critter killed while down, and left its corpse in its standing art).

--expect-defect inverts the checks of the fix, to show each defect on an older build.

Nothing here touches a live world: point it at a sandbox. Each mode empties the sandbox's
save slots and working maps first.

usage: python -u issue_wire_proof.py <timer|templexp|rest|cancel|create|reach|retry|lvlsfx|ownline|joinfreeze|entryring|sneakrun|hostplace|companions|dogs|rocks|armoroff|bess|bunload|gestures|pronekill|orders|all> <f2_server.exe>
                                     <game dir> <net port> <cmd port> [--expect-defect]
                                     [--no-crouch-check]
"""
import glob, os, re, shutil, socket, struct, subprocess, sys, threading, time

args = [a for a in sys.argv[1:] if not a.startswith("--")]
expect_defect = "--expect-defect" in sys.argv
# `reach` on v1.3.2 shows issue 13 itself; its crouch check (bugs/059) is about v1.4.1.
no_crouch_check = "--no-crouch-check" in sys.argv
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

    def sim_times(self):
        """The sim clock stamped on every frame in the stream so far, in order."""
        data = bytes(self.buf)
        stamps = []
        if data[:4] != b"F2NS":
            return stamps
        pos = 10
        while pos + 18 <= len(data):
            length = struct.unpack_from("<I", data, pos + 8)[0]
            if pos + 18 + length > len(data):
                break
            stamps.append(struct.unpack_from("<I", data, pos + 4)[0])
            pos += 18 + length
        return stamps

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


def boot(mapname, load_slot=None):
    """Start the server on a map, or (load_slot) on a save made earlier in the same proof:
    the sandbox is then left as it is and the log is appended to."""
    global srv, log
    if load_slot is None:
        wipe_sandbox()
    env = dict(os.environ)
    for name in list(env):
        if name.startswith("F2_"):
            env.pop(name)
    env.update({"F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
                "F2_SERVER_PACE_MS": "100", "F2_AUTOSAVE_SECS": "0", "F2_SERVER_KEEPALIVE": "1",
                "F2_TRACE_EVENTS": "1"})
    if load_slot is None:
        env["F2_SERVER_MAP"] = mapname
    else:
        env["F2_SERVER_LOAD"] = str(load_slot)
    log = open(logpath, "w" if load_slot is None else "a")
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
    # What the viewers were shown for the attempt: the op count of each sequence shipped
    # for the host. Begin, the walk and end are three; the crouch and its sound make five.
    shown = [int(n) for n in re.findall(r"\[presseq\] SEND ops=(\d+) bytes=\d+ actor=1\b", logtext()[mark:])]
    shutdown()
    return ready, result, (int(ap[0]) if ap else None), shown


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
    ready, (gone, stepped, walked, verdict), ap, shown = reach_attempt(12)
    check("far: the spear lies where the host stood, the host is 12 tiles on, a fight is on", ready,
          "host AP %s" % ap)
    fixed("far: this turn's walk (all of the host's AP) cannot reach the spear, so it stays on the ground",
          gone is None and verdict is not None and verdict[0] == "NOT taken" and int(verdict[3]) > 1,
          "walked %d steps; %s" % (walked, "spear taken after %d of them" % stepped if gone is not None
                                   else "verdict %r" % (verdict,)))
    if expect_defect:
        check("far: the old server took it before the host had taken a single step",
              gone is not None and stepped == 0, "spear taken after %d of %d steps" % (stepped, walked))
    # The follow-up (bugs/059): a walk that falls short is shown as a walk and nothing
    # else. v1.4.1 still shipped the crouch and the grab's sound after it, played from
    # where the walker stopped ("tries to pick up a spear from inappropriate range").
    if not no_crouch_check:
        fixed("far: the viewers are shown the walk alone, no crouch at a spear it did not reach",
              shown == [3], "sequences shipped for the host, by op count: %s" % shown)

    # Within reach: 6 tiles, walkable this turn. Taken, after the walk.
    ready, (gone, stepped, walked, verdict), ap, shown = reach_attempt(6)
    check("near: the spear lies where the host stood, the host is 6 tiles on, a fight is on", ready,
          "host AP %s" % ap)
    fixed("near: the walk reaches the spear and only then is it taken",
          gone is not None and walked >= 1 and stepped == walked and verdict is not None and verdict[0] == "taken",
          "walked %d steps, spear taken after %d of them; %r" % (walked, stepped, verdict))
    if not no_crouch_check:
        check("near: the viewers are shown the walk, then the crouch and the grab",
              len(shown) == 1 and shown[0] >= 5, "sequences shipped for the host, by op count: %s" % shown)


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


def wait_for_turn_of(watcher, slot, enders):
    """Wait until the fight sits on `slot`'s turn. `enders` maps a slot to the client
    that ends that slot's turn when it comes up first. True once the turn has held."""
    deadline = time.time() + 60
    ended_at = -1
    while time.time() < deadline:
        turns = turn_starts(watcher)
        if not turns:
            time.sleep(0.2)
            continue
        if turns[-1] == net_of_slot(slot):
            time.sleep(2.0)
            if turn_starts(watcher) == turns:
                return True
            continue
        for other, client in enders.items():
            if turns[-1] == net_of_slot(other) and len(turns) != ended_at:
                ended_at = len(turns)
                client.send("cendturn", 0.5)
        time.sleep(0.2)
    return False


def prove_joinfreeze():
    # Issue 16. A keepalive server froze its world only while NO client was connected; a
    # session that was connected but not yet logged in (the pre-join account query, the
    # creation screen, the load) thawed it with every body unpiloted. A player who had
    # left next to hostiles came back to find the fight had run on during their join,
    # their own turns ending by themselves, eight to ten enemy turns' worth. The world
    # now freezes while no slot is bound.
    #
    # Here the host drops on its OWN turn, which is where a player who quits mid-fight
    # nearly always is (the enemy side takes its turns in a single beat; the fight then
    # sits waiting on the human). The server sits with nobody in, and a connection comes
    # back and waits a while before logging in, like a client busy loading the world.
    #
    # The returning connection IS sent the world while it waits (issue 32: the real client
    # will not log in before it has it), and with it the turn the fight is frozen on. So
    # "frozen" is read off the clock: every frame carries the sim time, and it must not
    # move before the login. The one turn announced with the world must be the host's
    # own, still: a body nobody is bound to has its turn ended at once, so the beat that
    # NOTICED the drop must already be a frozen one (v1.4.1 ran it live, and the player
    # came back a round behind). After the login the turn is said once more, because a
    # client only learns which body is its own when it logs in.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    out = admin("spawn %s 1 %d" % (RAIDER, start + 3), 1.0)
    admin("aggro 1", 1.0)
    held = wait_for_turn_of(host, 0, {})
    fighting = len(host.events(EVENT_COMBAT_ENTER)) >= 1 and "placed 1/1" in out
    host.close()
    clients.remove(host)
    time.sleep(6.0)  # nobody in
    back = Client("Tester")
    time.sleep(4.0)  # connected, not logged in
    own = net_of_slot(0)
    before = turn_starts(back)
    clock = back.sim_times()
    back.send("login Tester", 3.0)
    time.sleep(12.0)  # well inside the 60 s a player's turn waits for them
    after = turn_starts(back)[len(before):]
    mark = len(logtext())
    back.send("cendturn", 3.0)
    moved_on = turn_starts(back)[len(before) + len(after):]

    check("the host was in a fight, on its own turn, when it dropped, and a connection came back",
          fighting and held, out[:40])
    fixed("the world stays frozen while the connection is in but not yet logged in (the clock stands)",
          len(clock) >= 1 and len(set(clock)) == 1,
          "%d frames before the login, sim clock %s" % (len(clock), sorted(set(clock))[:4]))
    fixed("the fight is still on the host's turn when the connection comes back",
          before == [own], "host is %s; turns announced before the login: %s" % (own, before[:12]))
    fixed("after the login the turn is said once more and is still the host's: no enemy acted meanwhile",
          after == [own], "turns after the login: %s" % after[:20])
    if not expect_defect:  # on an older build the fight is somewhere else by now
        check("the turn is theirs to end: ending it is accepted and the fight moves on",
              len(moved_on) >= 1 and "not actor's turn" not in logtext()[mark:],
              "turns after the host ended its turn: %s" % moved_on[:12])
    shutdown()

    # The same for a player who is not the host. Both players leave with the fight
    # waiting on the second player's turn; the second player comes back alone.
    boot("arvillag.map")
    host, second = two_players()
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    out = admin("spawn %s 1 %d" % (RAIDER, start + 3), 1.0)
    admin("aggro 1", 1.0)
    held = wait_for_turn_of(second, 1, {0: host})
    fighting = len(second.events(EVENT_COMBAT_ENTER)) >= 1 and "placed 1/1" in out
    host.close()
    clients.remove(host)
    time.sleep(2.0)  # the second player is still in: the world runs, the turn waits on them
    still = turn_starts(second)
    still_theirs = bool(still) and still[-1] == net_of_slot(1)
    second.close()
    clients.remove(second)
    time.sleep(6.0)  # nobody in
    back = Client("Brother")
    time.sleep(4.0)
    own = net_of_slot(1)
    before = turn_starts(back)
    clock = back.sim_times()
    back.send("login Brother", 3.0)
    time.sleep(8.0)
    own_after = net_of_slot(1)
    after = turn_starts(back)[len(before):]
    mark = len(logtext())
    back.send("cendturn", 3.0)
    moved_on = turn_starts(back)[len(before) + len(after):]

    check("two players were in a fight waiting on the second one when both dropped",
          fighting and held and still_theirs, out[:40])
    fixed("the fight is still on the second player's turn when they come back alone, the clock standing",
          before == [own] and len(set(clock)) == 1,
          "second player is %s; turns announced before the login: %s; sim clock %s"
          % (own, before[:12], sorted(set(clock))[:4]))
    fixed("after the login their turn is said once more, so their client knows it is theirs",
          after == [own_after], "second player is %s; turns after the login: %s" % (own_after, after[:20]))
    if not expect_defect:  # on an older build the fight is somewhere else by now
        check("the turn is theirs to end: ending it is accepted and the fight moves on",
              len(moved_on) >= 1 and "not actor's turn" not in logtext()[mark:],
              "turns after they ended their turn: %s" % moved_on[:12])
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
    check("both players are in and the party arrived on the graze map (the host left Arroyo's tile)",
          1 in nets and host_at[0] is not None and second_at[0] is not None and host_at[0] != 20517,
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


def toggle_sneak(client):
    """Send the sneak toggle and return the state the server says it is now in."""
    client.send("sneak", 0.8)
    rows = re.findall(r"control sneak=(\d)", logtext())
    return rows[-1] if rows else "?"


def prove_sneakrun():
    # Issue 29: "Sneak stays active while running ... vanilla Fallout 2 sneak turns off while
    # you run, unless you have the Silent running perk. This is not just a visual box bug
    # but NPCs really perceive me as sneaking." Vanilla drops the state in the run click's
    # own handler (_dude_run), which a dedicated server never runs: the run reaches it as a
    # verb. The server only logs the state when it is toggled, so each step ends with a
    # toggle and reads what it turned INTO: "1" means it was off.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])

    first = toggle_sneak(host)
    host.send("mv %d 0" % (start + 3), 3.0)  # a walk
    after_walk = toggle_sneak(host)
    check("sneaking survives a walk (the toggle after it turns it off)", first == "1" and after_walk == "0",
          "on: %s; toggled after the walk: %s" % (first, after_walk))

    again = toggle_sneak(host)
    host.send("mv %d 1" % start, 3.0)  # a run
    after_run = toggle_sneak(host)
    fixed("a run ends sneaking (the toggle after it turns it back ON)", again == "1" and after_run == "1",
          "on: %s; toggled after the run: %s" % (again, after_run))

    # With Silent Running the run keeps it. The perk wants level 6, Agility 6 and Sneak 50.
    if after_run == "1":
        toggle_sneak(host)  # off, for a clean start
    admin("xp 0 80000", 1.0)
    admin("sp 0 99", 0.5)
    host.send("sheetopen", 0.5)
    for _ in range(60):
        host.send("skillup 8", 0.02)
    host.send("perkpick 15", 0.8)
    host.send("sheetclose", 0.8)
    perk = re.findall(r"control perkpick slot=0 perk=15 rc=(-?\d+)", logtext())
    silent_on = toggle_sneak(host)
    host.send("mv %d 1" % (start + 3), 3.0)
    silent_after = toggle_sneak(host)
    check("with Silent Running a run keeps the sneak (the toggle after it turns it off)",
          perk[-1:] == ["0"] and silent_on == "1" and silent_after == "0",
          "perk rc %s; on: %s; toggled after the run: %s" % (perk[-1:], silent_on, silent_after))
    shutdown()


def prove_hostplace():
    # Issue 20: "If the quest initiator (speaker) is not the host, only the speaker gets
    # correctly spawned. Other player gets spawned into the woods (depending on his current
    # position at Klamath downtown)." A map change a script asks for (load_map, with no
    # tile named) runs under the scope of the player whose dialog or use ran the script.
    # The load put that player on the map's entering tile and every OTHER player beside
    # them, counting from slot 1: when the asker was not the host, the host was neither,
    # and kept the tile number it had on the map it had just left.
    #
    # Two players stand in Arroyo. The second one asks for the trip to the Den (the
    # operator's `entermapas`, which stages the transition a script's load_map would).
    boot("arvillag.map")
    host, second = two_players()
    nets = {int(slot): int(net) for slot, net in re.findall(r"\[actors\] srv slot=(\d) obj=\S+ netId=(\d+) ", logtext())}
    host_before = last_tiles(host).get(nets.get(0), (None, None))
    trips_before = len(host.events(EVENT_MAP_TRANSITION))
    admin("entermapas 6 1", 10.0)
    nets = {int(slot): int(net) for slot, net in re.findall(r"\[actors\] srv slot=(\d) obj=\S+ netId=(\d+) ", logtext())}
    tiles = last_tiles(host)
    host_at = tiles.get(nets.get(0), (None, None))
    second_at = tiles.get(nets.get(1), (None, None))
    arrived = len(host.events(EVENT_MAP_TRANSITION)) > trips_before
    check("two players were in Arroyo and the second one's trip took the party to another map",
          1 in nets and arrived and host_at[0] is not None and second_at[0] is not None,
          "host was at %s; now host %s, second %s" % (host_before, host_at, second_at))
    distance = hex_distance(host_at[0], second_at[0]) if host_at[0] is not None and second_at[0] is not None else 999
    fixed("the host stands beside the player who asked for the trip",
          distance <= 6 and host_at[1] == second_at[1], "%d hexes apart" % distance)
    if expect_defect:
        check("the old server left the host on the tile number it had in Arroyo",
              host_at[0] == host_before[0], "host tile before %s, after %s" % (host_before[0], host_at[0]))
    shutdown()


def companion_row():
    """The operator's `party` line for the first companion: (tile, elevation, owner slot).
    The owner is None on a build whose listing does not print it."""
    out = admin("party", 0.3)
    row = re.search(r"\[1\] .*? tile=(-?\d+)(?: elev=(-?\d+) owner=(-?\d+))?", out)
    if row is None:
        return None, None, None
    return (int(row.group(1)), int(row.group(2)) if row.group(2) is not None else None,
            int(row.group(3)) if row.group(3) is not None else None)


def player_rows():
    """slot -> (tile, elevation) of every player body, off the server log's actor lines."""
    rows = {}
    for slot, tile, elev in re.findall(r"\[actors\] srv slot=(\d) obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+) elev=(-?\d+)",
                                       logtext()):
        rows[int(slot)] = (int(tile), int(elev))
    return rows


def prove_companions():
    # Issues 20 and 41 (bugs/067), the companions' half: "If current Companion Owner uses
    # the ladder, Companion refuses to go to the Next Elevation ... and starts to follow a
    # remaining Player"; "if a Player who doesn't own the Companion uses the ladder,
    # Companion still gets teleported"; "Recruitable NPCs aren't following players to some
    # maps". And the rule the reporter asked for: "Companion should belong to the Player
    # whom he originally followed."
    #
    # Two players and a spawned companion (Cassidy, wearing the generic villager script)
    # that follows the SECOND player. `elevate <slot> <floor>` puts one player on another
    # floor where they stand, as a ladder's script does.
    boot("arvillag.map")
    host, second = two_players()
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    admin("spawn 0x01000059 1 %d 9" % (start + 2), 1.5)
    out = admin("partyadd 89 1", 1.0)
    tile0, elev0, owner0 = companion_row()
    check("two players stand in Arroyo with a companion that follows the second one",
          "rc=0" in out and tile0 is not None, "%s; companion at tile %s" % (out[:70], tile0))

    # The owner takes the ladder: the companion goes with them.
    admin("elevate 1 1", 2.0)
    tile1, elev1, _owner = companion_row()
    fixed("its owner changed floor and the companion went with them",
          elev1 == 1, "companion on floor %s (tile %s)" % (elev1, tile1))
    # The other player follows up, then goes back down: not theirs, so it is left alone.
    admin("elevate 0 1", 2.0)
    admin("elevate 0 0", 2.0)
    tile2, elev2, _owner = companion_row()
    fixed("the other player changed floor twice and the companion stayed where it stood",
          elev2 == 1 and tile2 == tile1, "floor %s -> %s, tile %s -> %s" % (elev1, elev2, tile1, tile2))

    # With nobody recorded as its owner it keeps to whoever is on its floor, and goes with
    # a player who leaves it alone there.
    admin("partyadd 89 -1", 1.0)
    admin("elevate 0 1", 2.0)  # both players are on floor 1 with it now
    admin("elevate 0 0", 2.0)  # the host leaves: the second player is still there
    _tile, elev3, _owner = companion_row()
    admin("elevate 1 0", 2.0)  # the second player leaves too: it would be alone
    _tile, elev4, _owner = companion_row()
    fixed("with no owner recorded it stays while a player is on its floor and follows the last one off it",
          elev3 == 1 and elev4 == 0, "after the first player left: floor %s; after the last one: floor %s" % (elev3, elev4))

    # A map change the second player asks for: the companion arrives beside its owner.
    admin("partyadd 89 1", 1.0)
    admin("entermapas 6 1", 10.0)
    tile5, elev5, owner5 = companion_row()
    players = player_rows()
    near = (tile5 is not None and 1 in players and players[1][1] == elev5
            and hex_distance(tile5, players[1][0]) <= 6)
    fixed("after a map change the companion stands beside the player it follows",
          near, "companion %s floor %s; players %s" % (tile5, elev5, players))

    # A trip that names its arrival tile, as an exit grid does (back to Arroyo, twelve
    # hexes from the map's own entrance), with nobody recorded as the companion's owner,
    # which is what every companion was after a server restart. The group is moved to the
    # named tile after the load placed it at the map's entrance; the companion used to be
    # left at the entrance ("NPCs are staying in the first map", issue 41).
    admin("partyadd 89 -1", 1.0)
    admin("entermapat 4 %d" % (start + 12), 10.0)
    tile7, elev7, _owner = companion_row()
    players = player_rows()
    with_group = (tile7 is not None and 0 in players and players[0][1] == elev7
                  and hex_distance(tile7, players[0][0]) <= 6)
    fixed("after a trip that names its arrival tile the companion stands with the group",
          with_group, "companion %s floor %s; players %s; the map's own entrance is %d"
          % (tile7, elev7, players, start))
    admin("partyadd 89 1", 1.0)
    _tile, _elev, owner5 = companion_row()

    # And it still follows them after the world is saved and the server started again.
    saved = admin("save 5", 3.0)
    shutdown()
    boot(None, load_slot=5)
    host, second = two_players()
    _tile, _elev, owner6 = companion_row()
    fixed("the save kept who the companion follows",
          owner5 == 1 and owner6 == 1, "before the save: slot %s; after the restart: slot %s (%s)"
          % (owner5, owner6, saved[:40]))
    shutdown()


MODBRAH = 20


def mover_rows(text):
    """net -> (first row, last row, steps) of every object that moved, off the MOVE trace."""
    rows = {}
    for net, src, dst in re.findall(r"\[evt\] MOVE\s+net=(\d+) (-?\d+)->(-?\d+)", text):
        first, _last, steps = rows.get(net, (int(src) // 200, 0, 0))
        rows[net] = (first, int(dst) // 200, steps + 1)
    return rows


def prove_dogs():
    # Issue 43: "Grisham's quest always fail ... Wild dogs are standing still in top of the
    # Brahmin Pasture map. After killing every one of the dogs and saving all brahmins
    # Grisham responds as if his herd was completely killed."
    #
    # The dogs' script homes in on a brahmin with the stock idiom: ask to run to its tile;
    # while NOT anim_busy the move was refused, so pull the destination a hex back toward
    # yourself and ask again. The server answered anim_busy with 0 always, so every ask
    # looked refused, the destination was walked back to the dog's own feet, and the dogs
    # never left the top of the map. The herd's fate is on a clock the map starts when the
    # party arrives (the brahmin are slaughtered when it runs out with dogs still alive),
    # which is how a party that found and killed the dogs too late still lost the herd.
    #
    # Here the host enters the pasture and waits. The ten dogs start on rows 38 to 43 and
    # the herd stands on rows 78 to 92.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    mark = len(logtext())
    admin("entermap %d" % MODBRAH, 8.0)
    arrived = len(host.events(EVENT_MAP_TRANSITION)) >= 1 and admin("gvar 116", 0.2).endswith("= 10")
    # The fight that starts when the dogs arrive waits on the host each round: end its turns.
    until = time.time() + 40
    ended = 0
    while time.time() < until:
        turns = turn_starts(host)
        if turns and turns[-1] == 1 and len(turns) != ended:
            ended = len(turns)
            host.send("cendturn", 0.3)
        time.sleep(0.3)
    rows = mover_rows(logtext()[mark:])
    dogs = {net: v for net, v in rows.items() if v[0] <= 45}
    reached = sum(1 for first, last, _steps in dogs.values() if last >= 70)
    fights = len(host.events(EVENT_COMBAT_ENTER))
    check("the host entered Grisham's pasture, ten dogs alive at the top of it", arrived,
          "dogs alive: %s" % admin("gvar 116", 0.2))
    fixed("the dogs ran down the map to the herd",
          reached >= 5, "%d objects moved off rows 38 to 45, %d of them to row 70 or beyond; steps %s"
          % (len(dogs), reached, sorted(v[2] for v in dogs.values())[-5:]))
    fixed("and attacked it: a fight started", fights >= 1, "%d fights" % fights)
    shutdown()


MODSHIT, MODMAIN = 22, 18
SHITTER_ROCKS_PID, SHITTER_ROCKS_TILE = 0x02000051, 19298
GVAR_MODOC_SHITTY_DEATH = 297


def rocks_standing_after_last_load(client):
    """The same question, asked only of the objects sent since the newest map change."""
    data = bytes(client.buf)
    rows = []
    if data[:4] != b"F2NS":
        return False
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
            if etype == EVENT_MAP_TRANSITION:
                rows = []
            elif etype == EVENT_SNAPSHOT_OBJECT and elen >= 16:
                rows.append(struct.unpack_from("<iiii", payload, ep + 4))
            ep += 4 + elen
    return any(pid == SHITTER_ROCKS_PID and tile == SHITTER_ROCKS_TILE for _net, pid, tile, _elev in rows)


def prove_rocks():
    # Issue 45: "Cornelius watch is unobtainable. Use explosives to detonate methane
    # deposits in Modoc Bed & Breakfast caves. Expected: rubble blocking the way to
    # Cornelius watch is cleared. Actual: damage from explosion is applied to players, but
    # map didn't change and rubble was still blocking the way."
    #
    # The pile of rocks under the outhouse carries its own script. An explosion within
    # three hexes sets the quest flag and starts a chain of methane blasts through the
    # cave; the rocks themselves are only removed when the map is next ENTERED with the
    # flag set (vanilla: arm the charge, climb out, come back). Here the host arms a stick
    # of dynamite beside the rocks, walks out of the map before it goes off (leaving
    # detonates a ticking charge, as in vanilla), and comes back.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    admin("entermap %d" % MODSHIT, 8.0)
    at = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    before = rocks_standing_after_last_load(host)
    admin("give %d" % DYNAMITE, 0.5)
    host.send("invdrop 999999 1", 1.0)  # refused: the refusal lists the pack with netIds
    packs = re.findall(r"no dude item netId=999999 ignored \(dude has:(.*)\)", logtext())
    charge = re.findall(r"\[net=(\d+) pid=%d " % DYNAMITE, packs[-1]) if packs else []
    admin("warp %d" % (SHITTER_ROCKS_TILE + 2 - at), 1.0)
    host.send("useitem_armexplosive %d 60" % DYNAMITE, 1.0)
    if charge:
        host.send("invdrop %s 1" % charge[0], 1.0)
    flag_before = admin("gvar %d" % GVAR_MODOC_SHITTY_DEATH, 0.2)
    check("the host stands by the rocks under the outhouse with an armed stick of dynamite on the ground",
          before and bool(charge) and "control invdrop pid=" in logtext() and flag_before.endswith("= 0"),
          "rocks in the snapshot %s; charge net %s; %s" % (before, charge[:1], flag_before))
    mark = len(logtext())
    admin("entermap %d" % MODMAIN, 8.0)
    blown = re.findall(r"\[explode\] center tile=(\d+)", logtext()[mark:])
    flag_after = admin("gvar %d" % GVAR_MODOC_SHITTY_DEATH, 0.2)
    check("leaving the map set the charge off beside the rocks, and the quest flag is set",
          len(blown) >= 1 and not flag_after.endswith("= 0"), "blasts at %s; %s" % (blown[:3], flag_after))
    admin("entermap %d" % MODSHIT, 8.0)
    fixed("back in the cave the rocks are gone", not rocks_standing_after_last_load(host),
          "rocks in the newest snapshot: %s" % rocks_standing_after_last_load(host))
    shutdown()


EVENT_OBJECT_DELTA = 6
LEATHER_ARMOR = 1


def body_art(client, net):
    """The body art number (the low 12 bits of the fid) in the newest fid streamed for `net`."""
    art = None
    for body in client.events(EVENT_OBJECT_DELTA):
        if len(body) >= 10:
            who, mask = struct.unpack_from("<iH", body, 0)
            if who == net and mask & 1:
                art = struct.unpack_from("<i", body, 6)[0] & 0xFFF
    return art


def pack_net(client, pid):
    """The netId of the player's stack of `pid`. An impossible drop is refused with the
    whole pack listed, netIds included."""
    client.send("invdrop 999999 1", 1.0)
    packs = re.findall(r"no dude item netId=999999 ignored \(dude has:(.*)\)", logtext())
    found = re.findall(r"\[net=(\d+) pid=%d " % pid, packs[-1]) if packs else []
    return int(found[0]) if found else None


def prove_armoroff():
    # Issue 28, second half: "Equipping and then unequipping any armor with a male
    # character will turn him into female vault suit model for other player's point of
    # view (tested with the other player being female if it matters). Putting armor back
    # will turn him into male again for everyone's point of view."
    #
    # It matters: the body a player goes back to when armor comes off was read from the
    # dude proto, and that proto is the host's. Here the host is the stock man and the
    # second player a woman (the reporter's pair, the other way round). She is handed a
    # leather armor, puts it on and takes it off: the body the server streams for her is
    # read off the wire each time.
    #
    # Then the same slot's other exit, found on the way: she puts the armor on again and
    # DROPS it while wearing it, and drops a spear while holding it, each with the one
    # `invdrop` the inventory screen sends for a slot. Both must land on the ground.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    second = Client("Sister")
    time.sleep(2.5)
    second.send("create 5 6 5 7 6 6 5 -1 -1 -1 -1 -1 1 30", 0.5)
    second.send("login Sister", 5.0)
    text = logtext()
    his = re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=-?\d+ elev=\d+ flags=\S+ fid=0x([0-9A-Fa-f]+)", text)
    hers = re.findall(r"\[create\] slot=1 .*?fid=0x([0-9A-Fa-f]+)", text)
    his = int(his[-1], 16) & 0xFFF if his else None
    hers = int(hers[-1], 16) & 0xFFF if hers else None
    her = net_of_slot(1)

    def hand_over(pid):
        """The operator gives the host one, the host drops it, she picks it up."""
        admin("give %d" % pid, 0.5)
        net = pack_net(host, pid)
        host.send("invdrop %s 1" % net, 1.5)
        second.send("get %s" % net, 4.0)
        return pack_net(second, pid)

    def armor_rows():
        return re.findall(r"\[armor\] (\w+) slot=1 worn pid=(-?\d+) ac=(-?\d+) body=(\d+)", logtext())

    held = hand_over(LEATHER_ARMOR)
    check("the host is a man, the second player a woman, in different bodies, and she holds a leather armor",
          hers is not None and his is not None and hers != his and held is not None,
          "body art: his %s, hers %s; the armor is net %s in her pack" % (his, hers, held))

    second.send("invwield %s 0" % held, 2.0)
    worn = body_art(host, her)
    check("she puts the armor on and everyone is sent a new body for her",
          worn is not None and worn not in (his, hers), "body art with the armor on: %s" % worn)
    second.send("invunwield 2", 2.0)
    off = body_art(host, her)
    fixed("she takes it off and is back in her own body, not the host's",
          off == hers, "body art with the armor off: %s (hers %s, his %s)" % (off, hers, his))

    second.send("invwield %s 0" % pack_net(second, LEATHER_ARMOR), 2.0)
    again = body_art(host, her)
    second.send("invdrop %s 1" % pack_net(second, LEATHER_ARMOR), 2.0)
    dropped = body_art(host, her)
    left = pack_net(second, LEATHER_ARMOR)
    check("she puts it on again", again == worn, "body art %s" % again)
    fixed("she drops it while wearing it: it leaves her pack and she is back in her own body",
          left is None and dropped == hers,
          "armor still in her pack: %s; body art after the drop: %s (hers %s, his %s)"
          % (left is not None, dropped, hers, his))
    if not expect_defect:
        rows = armor_rows()
        acs = [(verb, int(pid), int(ac)) for verb, pid, ac, _body in rows]
        base = [ac for verb, pid, ac in acs if pid == -1]
        on = [ac for verb, pid, ac in acs if pid == LEATHER_ARMOR]
        check("her armor class rose with the armor and is back where it was after both ways of taking it off",
              len(on) >= 2 and len(base) >= 2 and len(set(base)) == 1 and min(on) > base[0]
              and acs[-1][0] == "invdrop" and acs[-1][1] == -1,
              "armor verbs on her: %s" % ", ".join("%s worn %d ac %d" % row for row in acs))

    spear = hand_over(SPEAR)
    second.send("invwield %s 0" % spear, 2.0)
    in_hand = pack_net(second, SPEAR)
    second.send("invdrop %s 1" % in_hand, 2.0)
    gone = pack_net(second, SPEAR)
    check("she is handed a spear and holds it", spear is not None and in_hand is not None,
          "spear net %s, in her hand as net %s" % (spear, in_hand))
    fixed("she drops the spear out of her hand: it leaves her pack", in_hand is not None and gone is None,
          "spear still in her pack: %s" % (gone is not None))
    shutdown()


BESS_PID, BESS_TILE = 0x010000BF, 24482
SKILL_DOCTOR = 7
ANIM_STAND, ANIM_FALL_BACK_SF = 0, 48


def snapshot_rows(client):
    """(netId, pid, tile, elevation, fid) of every object in the newest snapshot."""
    data = bytes(client.buf)
    rows = []
    if data[:4] != b"F2NS":
        return rows
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
            if etype == EVENT_MAP_TRANSITION:
                rows = []
            elif etype == EVENT_SNAPSHOT_OBJECT and elen >= 20:
                rows.append(struct.unpack_from("<iiiii", payload, ep + 4))
            ep += 4 + elen
    return rows


def last_fid(client, net, start):
    """The newest art streamed for `net`: its row in the newest snapshot, or a later delta."""
    fid = start
    for body in client.events(EVENT_OBJECT_DELTA):
        if len(body) >= 10:
            who, mask = struct.unpack_from("<iH", body, 0)
            if who == net and mask & 1:
                fid = struct.unpack_from("<i", body, 6)[0]
    return fid


def admin_lines(lines, wait=1.0):
    """Several operator lines on one connection (it is a line console, like telnet)."""
    s = socket.create_connection(("127.0.0.1", cmdport), timeout=5)
    s.sendall("".join(line + NL for line in lines).encode())
    s.settimeout(1.5)
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
    return out.decode(errors="replace")


def art_anim(fid):
    return (fid >> 16) & 0xFF


def prove_bess():
    # Issue 42: "Enter Modoc and approach brahmin Bess but don't use Doctor. Expected: Bess
    # lies on her side with injury to her leg. Actual: Bess stands as if she's healthy."
    #
    # Her script lays her down on every map entry with a sequence of registered
    # animations: hit, fall back, and the lying single frame. On the server an animation
    # is nothing, so the sequence left no trace and she stood. The server now settles the
    # pose a script's sequence ends on. Here the host enters Modoc and Bess's art is read
    # off the snapshot. Then the host, made a good doctor by the operator, heals her: the
    # script's own back-to-standing sequence must put her on her feet, and she must still
    # be on them in the next snapshot.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    admin("entermap %d" % MODMAIN, 8.0)

    def bess():
        rows = [row for row in snapshot_rows(host) if row[1] == BESS_PID]
        return rows[0] if rows else None

    cow = bess()
    check("the host entered Modoc and Bess is there, where the map puts her",
          cow is not None and cow[2] == BESS_TILE, "Bess in the snapshot: %s" % (cow,))
    if cow is None:
        shutdown()
        return
    fixed("Bess lies on her side: her leg is broken and nobody has seen to it",
          art_anim(cow[4]) == ANIM_FALL_BACK_SF,
          "her art's animation is %d (0 stands, 48 lies on her back)" % art_anim(cow[4]))
    if expect_defect:  # an older server has her on her feet from the start: nothing more to show
        shutdown()
        return

    out = admin_lines(["sp 0 300"] + ["skillup 0 %d" % SKILL_DOCTOR] * 140, 1.0)
    doctor = re.findall(r"skill %d -> \S+ \(value (\d+)," % SKILL_DOCTOR, out)
    at = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    admin("warp %d" % (BESS_TILE + 1 - at), 1.0)
    healed = False
    for _attempt in range(5):
        host.send("skill %d %d" % (cow[0], SKILL_DOCTOR), 3.0)
        healed = any("experience points" in text for text, _to, _channel in host.console())
        if healed:
            break
    up = last_fid(host, cow[0], cow[4])
    check("the host, a good doctor now, sets her leg and she gets up",
          healed and art_anim(up) == ANIM_STAND,
          "Doctor at %s%%; healed %s; her art's animation is now %d"
          % (doctor[-1] if doctor else "?", healed, art_anim(up)))
    admin("entermap %d" % MODBRAH, 8.0)
    admin("entermap %d" % MODMAIN, 8.0)
    again = bess()
    check("after leaving and coming back she is on her feet",
          again is not None and art_anim(again[4]) == ANIM_STAND,
          "Bess in the newest snapshot: %s" % (again,))
    shutdown()


EVENT_BARTER_STATE = 44
PISTOL_10MM = 8
DENBUS1 = 6
TUBBY = 47  # dtalk takes the script's index: scripts.lst line 48


def barter_state(client):
    """The newest trade state streamed: four lists of (pid, quantity, rounds loaded, ammo
    pid) in the order player's pack, merchant's pack, player's table, merchant's table.
    The last two fields are -1 where the stream does not say (an older server)."""
    bodies = client.events(EVENT_BARTER_STATE)
    if not bodies:
        return None
    body = bodies[-1]
    at = 0
    lists = []
    for _list in range(4):
        count = struct.unpack_from("<i", body, at)[0]
        at += 4
        rows = [list(struct.unpack_from("<ii", body, at + 8 * i)) + [-1, -1] for i in range(count)]
        at += 8 * count
        lists.append(rows)
    at += 12  # the two valuations and the last commit's result
    if len(body) >= at + 8 * sum(len(rows) for rows in lists):
        for rows in lists:
            for row in rows:
                row[2], row[3] = struct.unpack_from("<ii", body, at)
                at += 8
    return lists


def prove_bunload():
    # Issue 38, the server's half: "Try to unload trader guns from Barter window." Vanilla's
    # trade screen offers Unload on a loaded weapon in any of its four lists, and the
    # rounds go into the inventory the weapon lies in. The co-op trade is a stream of
    # (kind, count) rows and three move verbs, so there was nothing to ask with, and a
    # viewer could not even tell a loaded gun from an empty one.
    #
    # The host carries a loaded 10mm pistol into a trade with Tubby in the Den and asks
    # for it to be unloaded where it lies (`bunload <pid> <list>`, list 0 = the player's
    # pack). The next state must show the pistol empty and its rounds beside it. Then the
    # same for the first loaded weapon in the merchant's own stock, if he holds one.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    admin("give %d" % PISTOL_10MM, 0.5)
    admin("entermap %d" % DENBUS1, 10.0)
    admin("movdone", 1.0)
    admin("dtalk %d" % TUBBY, 4.0)
    host.send("dbarter", 5.0)
    before = barter_state(host)
    mine = [row for row in (before[0] if before else []) if row[0] == PISTOL_10MM]
    check("the host carries a 10mm pistol into a trade with Tubby",
          before is not None and len(mine) == 1,
          "the pistol's row in the pack list: %s" % (mine[:1],))
    if before is None:
        shutdown()
        return
    fixed("the trade's stream says what a weapon is loaded with",
          len(mine) == 1 and mine[0][2] > 0, "pistol row (pid, count, rounds, ammo pid): %s" % (mine[:1],))
    loaded = mine[0][2] if mine else -1
    ammo_pid = mine[0][3] if mine else -1

    host.send("bunload %d 0" % PISTOL_10MM, 2.0)
    after = barter_state(host)
    pistol = [row for row in after[0] if row[0] == PISTOL_10MM]
    rounds = sum(row[1] for row in after[0] if row[0] == ammo_pid) if ammo_pid > 0 else 0
    fixed("asked to unload it where it lies, the pistol is empty and its rounds are in the pack beside it",
          len(pistol) == 1 and pistol[0][2] == 0 and loaded > 0 and rounds >= 1,
          "pistol row now %s; %d stack(s) of ammo pid %d in the pack" % (pistol[:1], rounds, ammo_pid))

    stock = [row for row in after[1] if row[2] > 0]
    if expect_defect or not stock:
        if not expect_defect:
            check("(Tubby holds no loaded weapon in this world: the merchant's list was not exercised)", True,
                  "%d rows in his stock" % len(after[1]))
        host.send("bdone", 1.0)
        host.send("dend", 1.0)
        shutdown()
        return
    gun, held, in_gun, gun_ammo = stock[0]
    loose_before = sum(row[1] for row in after[1] if row[0] == gun_ammo)
    host.send("bunload %d 1" % gun, 2.0)
    final = barter_state(host)
    still = [row for row in final[1] if row[0] == gun and row[2] == in_gun]
    emptied = [row for row in final[1] if row[0] == gun and row[2] == 0]
    loose_after = sum(row[1] for row in final[1] if row[0] == gun_ammo)
    check("the same on the merchant's side: one of his loaded weapons is empty and the rounds are in HIS stock",
          len(emptied) >= 1 and loose_after > loose_before
          and sum(row[1] for row in still) == held - 1,
          "weapon pid %d (%d held, %d rounds each): %d still loaded, %d empty; his loose ammo %d -> %d stacks"
          % (gun, held, in_gun, sum(row[1] for row in still), sum(row[1] for row in emptied), loose_before, loose_after))
    host.send("bdone", 1.0)
    host.send("dend", 1.0)
    shutdown()


EVENT_PRES_SEQ = 31
ORPHAN_PIDS = (0x01000032, 0x01000033)
STIMPAK, AMMO_10MM = 40, 29
ANIM_MAGIC_HANDS_MIDDLE = 11
SKILL_STEAL = 10


def gestures(client, start=0):
    """Every recorded sequence streamed since `start` that is one animation and nothing
    else, as (object netId, animation, reversed). The event is: actor netId, the stream's
    version (a byte), its op count (u16), then the ops; begin = 1 + flags, animate = 5
    (reversed 6) + object, animation, delay, end = 2."""
    found = []
    for body in client.events(EVENT_PRES_SEQ)[start:]:
        if (len(body) == 7 + 5 + 13 + 1 and struct.unpack_from("<H", body, 5)[0] == 3
                and body[7] == 1 and body[12] in (5, 6) and body[25] == 2):
            ref, anim, _delay = struct.unpack_from("<iii", body, 13)
            found.append((ref, anim, body[12] == 6))
    return found


def prove_gestures():
    # Issue 40: "Enemy uses item in fight - Jet, Stimpak. Expected: Animation for use is
    # visible. Actual: No animation at all. Only indication of used item is log window. The
    # same goes for stealing kids in Den, no indication for their stealing attempts."
    #
    # On the server an animation is nothing unless a record section is open to catch it.
    # Neither the combat AI's item gesture nor anything a script animates opened one, so
    # none of it was ever sent. Both are read off the wire here: a recorded sequence that
    # is a single animation of the critter in question.
    #
    # First the Den's orphans. One within a hex of a player it can see picks their pocket
    # (their script's Attempted_Theft): anim() raises its hands (animation 11), and
    # animate_stand_obj stands it again (animation 0), whether or not anything was taken.
    # The host is put beside each orphan in turn, on each side of it, until one tries.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    tried = None
    count = 0
    for index in range(4):
        # The map is entered afresh for each orphan: the snapshot then says where it
        # stands (they wander), and the host is back at the entrance, whose tile the
        # server logs with every baseline.
        admin("entermap %d" % DENBUS1, 9.0)
        admin("movdone", 1.0)
        orphans = sorted(row for row in snapshot_rows(host) if row[1] in ORPHAN_PIDS)
        count = max(count, len(orphans))
        if index >= len(orphans):
            break
        net, _pid, tile, _elev, _fid = orphans[len(orphans) - 1 - index]
        at = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
        seen = len(host.events(EVENT_PRES_SEQ))
        for step in (1, -1, 200, -200):
            admin("warp %d" % (tile + step - at), 0.2)
            at = tile + step
            for _wait in range(5):
                time.sleep(1.0)
                anims = [anim for body in host.events(EVENT_PRES_SEQ)[seen:]
                         for ref, anim in sequence_animations(body) if ref == net]
                if anims and anims[-1] == 0:
                    tried = (net, anims)
                    break
            if tried:
                break
        if tried:
            break
    check("the host reached the Den and stood beside its orphans", count >= 2,
          "%d orphans in the snapshot" % count)
    fixed("an orphan's attempt on the host's pocket is sent to the players as that orphan's own animations: hands raised, then standing again",
          tried is not None and tried[1][:2] == [ANIM_MAGIC_HANDS_MIDDLE, 0],
          "orphan net %s: animations recorded for it, in order: %s" % (tried[0] if tried else None, tried[1] if tried else None))
    shutdown()

    # Then the fight. An empty 10mm pistol lies on the ground between the host and a
    # raider with nothing in its hands. The combat AI has the raider fetch the weapon,
    # find it dry with no rounds to be had, and put it away again: "out of ammo", which
    # goes through the AI's one item gesture, hands raised (animation 11), the same one a
    # stimpak, a dose of Jet or a reload uses.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    admin("xp 0 30000", 1.0)  # a few levels of hit points
    admin("give %d" % PISTOL_10MM, 0.3)
    admin("unload %d" % PISTOL_10MM, 0.5)
    pistol = pack_net(host, PISTOL_10MM)
    host.send("invdrop %s 1" % pistol, 1.5)
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    mark = len(logtext())
    out = admin("spawn %s 1 %d" % (RAIDER, start + 2), 1.5)
    spawned = re.findall(r"\[evt\] SPAWN\s+net=(\d+) pid=16777454", logtext()[mark:])
    raider = int(spawned[-1]) if spawned else -1
    seen = len(host.events(EVENT_PRES_SEQ))
    admin("aggro 1", 2.0)
    hands = []
    for _round in range(8):
        wait_for_turn_of(host, 0, {})
        hands = [g for g in gestures(host, seen) if g[0] == raider and g[1] == ANIM_MAGIC_HANDS_MIDDLE]
        if hands or len(host.events(EVENT_COMBAT_EXIT)) > 0:
            break
        host.send("cendturn", 1.0)
    lines = [text for text, _to, _channel in host.console()
             if text.startswith("Raider ") and "attacks" not in text and "missed" not in text and " hit " not in text]
    check("an empty pistol lay by the host, and a raider with empty hands was set on the host",
          raider > 0 and pistol is not None and "control invdrop pid=%d" % PISTOL_10MM in logtext(),
          "raider net %d; pistol net %s; %s" % (raider, pistol, out[:40]))
    fixed("the raider's handling of the dry pistol is sent to the players as its raised-hands animation",
          len(hands) >= 1,
          "%d such sequences for the raider; what the log said it did: %s" % (len(hands), lines[:3]))
    shutdown()


PRES_OP_SIZE = {1: 4, 2: 0, 3: 4, 4: 28, 5: 12, 6: 12, 7: 12, 8: 12, 9: 4, 10: 12, 11: 8, 12: 12, 13: 20, 14: 20,
                16: 16, 17: 12, 18: 8, 19: 9, 20: 28, 21: 24}
DAM_KNOCKED_OUT, DAM_KNOCKED_DOWN, DAM_DEAD = 0x01, 0x02, 0x80
ANIM_FALL_BACK_BLOOD, ANIM_FALL_FRONT_BLOOD = 34, 35
HIT_LOCATION_RIGHT_LEG = 4


def delta_fields(body):
    """netId and the scalar fields of an object delta (art, facing, flags, hit points,
    radiation, poison, action points, combat results), by name."""
    net, mask = struct.unpack_from("<iH", body, 0)
    at = 6
    fields = {}
    for bit, name in ((1, "fid"), (2, "rot"), (4, "flags"), (8, "hp"), (16, "rad"), (32, "poison"), (64, "ap"),
                      (128, "results")):
        if mask & bit:
            fields[name] = struct.unpack_from("<i", body, at)[0]
            at += 4
    return net, fields


def sequence_animations(body):
    """(object netId, animation) of every animate op in one recorded sequence, in order.
    Ops are a byte and fixed arguments, except the sound (15): object, a counted string,
    delay."""
    at = 7
    found = []
    while at < len(body):
        op = body[at]
        at += 1
        if op == 15:
            at += 4 + 2 + struct.unpack_from("<H", body, at + 4)[0] + 4
            continue
        size = PRES_OP_SIZE.get(op)
        if size is None:
            break
        if op in (5, 6):
            ref, anim, _delay = struct.unpack_from("<iii", body, at)
            found.append((ref, anim))
        at += size
    return found


def prove_pronekill():
    # Issue 39: "Every killed enemy leaves visible blood pool after finishing blow. Actual:
    # Sometimes killed enemy don't bleed at all. It is rare, but can be spotted sometimes."
    #
    # The blood is an animation, chosen by the fall the critter is lying in, and an enemy
    # killed where it LIES gets only that (it does not fall again). The server read the
    # fall off the critter's art, and on the server a knocked-down critter keeps its
    # standing art: no fall, no blood, and no lying art for the corpse either, which was
    # left a flattened standing critter in every snapshot after.
    #
    # The host knocks a raider down (a forced critical, aimed at the leg, as often as it
    # takes) and the operator kills it where it lies. What is shown, and the art the
    # corpse is given, are read off the wire.
    boot("arvillag.map")
    host = Client("Tester")
    time.sleep(2.5)
    host.send("login Tester", 3.0)
    admin("xp 0 60000", 1.0)  # hit points to stand a few rounds
    start = int(re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=\d+ pid=\S+ tile=(-?\d+)", logtext())[-1])
    mark = len(logtext())
    out = admin("spawn %s 1 %d" % (RAIDER, start + 1), 1.0)
    spawned = re.findall(r"\[evt\] SPAWN\s+net=(\d+) pid=16777454", logtext()[mark:])
    raider = int(spawned[-1]) if spawned else -1
    admin("aggro 1", 3.0)

    def results_since(count):
        return [f["results"] for body in host.events(EVENT_OBJECT_DELTA)[count:]
                for net, f in [delta_fields(body)] if net == raider and "results" in f]

    state = 0
    for _attempt in range(14):
        seen = len(host.events(EVENT_OBJECT_DELTA))
        admin("crithit 0", 0.1)
        host.send("cattack %d -1 %d" % (raider, HIT_LOCATION_RIGHT_LEG), 2.0)
        got = results_since(seen)
        if got:
            state = got[-1]
        if state & (DAM_DEAD | DAM_KNOCKED_OUT | DAM_KNOCKED_DOWN):
            break
        host.send("cendturn", 0.5)
        wait_for_turn_of(host, 0, {})
    down = bool(state & (DAM_KNOCKED_OUT | DAM_KNOCKED_DOWN)) and not state & DAM_DEAD
    check("a raider was knocked down by the host's blow and lay there alive",
          raider > 0 and down, "raider net %d; its combat results after the blow: 0x%X; %s" % (raider, state, out[:36]))

    seqs = len(host.events(EVENT_PRES_SEQ))
    deltas = len(host.events(EVENT_OBJECT_DELTA))
    admin("cdamage 999", 3.0)
    shown = [anim for body in host.events(EVENT_PRES_SEQ)[seqs:] for ref, anim in sequence_animations(body) if ref == raider]
    after = [f for body in host.events(EVENT_OBJECT_DELTA)[deltas:] for net, f in [delta_fields(body)] if net == raider]
    died = any(f.get("results", 0) & DAM_DEAD for f in after)
    arts = [(f["fid"] >> 16) & 0xFF for f in after if "fid" in f]
    check("the operator killed it where it lay", died, "deltas for the raider after the kill: %d" % len(after))
    fixed("the kill is shown with the blood of a critter lying down",
          len(shown) == 1 and shown[0] in (ANIM_FALL_BACK_BLOOD, ANIM_FALL_FRONT_BLOOD),
          "animations recorded for the raider in the kill: %s (34 and 35 are the blood under a body on its back, its front)" % shown)
    fixed("the corpse is given a lying art, in its blood, the same way up",
          len(arts) >= 1 and len(shown) == 1 and arts[-1] == shown[0] + 28,
          "art animation streamed for the corpse: %s (62 and 63 are the single frames of 34 and 35)" % arts[-1:])
    shutdown()


modes = {"timer": prove_timer, "templexp": prove_templexp, "rest": prove_rest,
         "cancel": prove_cancel, "create": prove_create, "reach": prove_reach, "retry": prove_retry,
         "lvlsfx": prove_lvlsfx, "ownline": prove_ownline, "joinfreeze": prove_joinfreeze,
         "entryring": prove_entryring, "sneakrun": prove_sneakrun, "hostplace": prove_hostplace, "companions": prove_companions, "dogs": prove_dogs, "rocks": prove_rocks, "armoroff": prove_armoroff,
         "bess": prove_bess, "bunload": prove_bunload, "gestures": prove_gestures, "pronekill": prove_pronekill, "orders": prove_orders}
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
