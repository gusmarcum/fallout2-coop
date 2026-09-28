"""Headless proof of party experience on a sandbox f2_server.

The rule under test: the party earns as one entity. Whatever one player earns, every
player who is playing right now is paid in full, ONCE: the earner is not paid a second
time on top of their own award, and nobody is paid twice (src/stat.h, party experience).

Boots the server on a save slot that holds two player actors, attaches two fake wire
clients (bare `claim`: slots 0 and 1) and walks through:

  share       an award earned by the host pays both; an award earned by the second
              player pays both; the operator's `xp <slot>` still pays one seat only.
  once        every award above lands as EXACTLY its amount on each sheet, and the
              server's pay-out line names each player exactly once.
  level       a shared award that crosses a level threshold levels the teammate and
              tells them so on their own screen.
  skill       a real play path: the second player uses First Aid on the host, both are
              paid the same amount once, each reads a line worded for them.
  downed      a player on the floor is paid with the rest and is NOT healed by a
              level-up (the operator's `kill` still finds them dead).
  kill        an explosion kill while the teammate is down pays both through the
              ordinary kill pay-out, and a whole fight won by one player pays both
              when it ends.
  quest       the hostile in that fight carries a real quest script whose death proc
              calls give_xp(1000): the authored award pays both, once, and the
              script's own line reaches everyone.
  away        a disconnected player's body is parked and is not paid; they are paid
              again as soon as they are back.
  wipe        a blast that kills the last player standing pays nobody: a dead party
              banks nothing.
  switch      a second boot with F2_PARTY_XP=0 pays the earner alone.

Truth comes from the operator's `sheet` replies (the real rows), the server's stderr and
the console lines on the wire. The wire is one stream for every viewer and a line for one
player carries that player's netId, so the lines are parsed out of the stream and checked
against the address, not grepped.

usage: python party_xp_proof.py <f2_server.exe> <game dir> <slot> <net port> <cmd port>
"""
import os, re, socket, struct, subprocess, sys, threading, time

exe, gamedir, slot, port, cmdport = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
NL = chr(10)
FIRST_AID = 6
RAIDER = "0x010000EE"
SCHREBER_SCRIPT = 1058  # scripts.lst line of CcDoctor.int; its destroy_p_proc awards 1000
SCHREBER_XP = 1000
EVENT_COMBAT_ENTER = 12
EVENT_CONSOLE = 16
logpath = os.path.join(gamedir, "partyxp-server.log")
results = []
srv = None
log = None


def boot(extra_env, mode):
    global srv, log
    env = dict(os.environ)
    env.update({"F2_SERVER_LOAD": slot, "F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
                "F2_SERVER_PACE_MS": "100", "F2_MOVIES": "0", "F2_AUTOSAVE_SECS": "0",
                "F2_TRACE_EVENTS": "1"})
    env.pop("F2_PARTY_XP", None)
    env.update(extra_env)
    log = open(logpath, mode)
    srv = subprocess.Popen([exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT)
    time.sleep(7)


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ("  [" + detail + "]" if detail else ""))


class Client:
    def __init__(self, tag):
        self.tag = tag
        self.buf = bytearray()
        self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.stop = threading.Event()
        threading.Thread(target=self.drain, daemon=True).start()

    def drain(self):
        while not self.stop.is_set():
            try:
                data = self.s.recv(65536)
                if not data:
                    return
                self.buf += data
            except Exception:
                return

    def send(self, line, wait):
        print("%s -> %s" % (self.tag, line))
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
        """Every console line so far, as (text, addressee netId, channel). The body is a
        u16-counted string, then the addressee and the channel when the line has them."""
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


def admin(line, wait=1.0, quiet=False):
    if not quiet:
        print("admin -> " + line)
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
    return out.decode(errors="replace")


def logtext():
    if not log.closed:
        log.flush()
    return open(logpath, encoding="utf-8", errors="replace").read()


def count(text):
    return logtext().count(text)


def wait_for(cond, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.3)
    return cond()


def probe_baseline():
    """Force a rebaseline (a connect owes one) so the [actors] lines are fresh."""
    c = Client("probe")
    time.sleep(2.5)
    c.close()
    time.sleep(1.0)


def actor(slot_index, field):
    rows = re.findall(r"\[actors\] srv slot=%d obj=\S+ netId=(-?\d+) pid=\S+ tile=(-?\d+) elev=(-?\d+) flags=\S+ fid=\S+ invLen=(-?\d+)" % slot_index, logtext())
    if not rows:
        return None
    net, tile, elev, inv = rows[-1]
    return {"net": int(net), "tile": int(tile), "elev": int(elev), "inv": int(inv)}[field]


def sheet():
    """{slot: {"name", "level", "xp"}} from the operator's `sheet` verb: the real rows."""
    rows = {}
    for s, name, level, xp in re.findall(r"sheet (\d+) \((.*?)\): level (\d+), xp (\d+)", admin("sheet", 0.2, quiet=True)):
        rows[int(s)] = {"name": name, "level": int(level), "xp": int(xp)}
    return rows


def gains(before, after):
    return {s: after[s]["xp"] - before[s]["xp"] for s in after if s in before}


def once(gain, amount):
    """True when `gain` is ONE payment of `amount`: the amount itself, or the amount
    with the player's own Swift Learner (5% a rank, three ranks). Two payments never
    fit: twice the amount is past anything three ranks can add."""
    return gain in [amount + rank * 5 * amount // 100 for rank in range(4)]


def payouts(since):
    """The server's pay-out lines printed after log offset `since`. One per award:
    [xp] <what> <amount> by <earner> -> <name> +<gained> (xp N, level N), <name> ..."""
    found = []
    for m in re.finditer(r"^\[xp\] (.+?) (-?\d+) by (.+?) ->(.*)$", logtext()[since:], re.M):
        shares = re.findall(r" (.+?) \+(-?\d+) \(xp \d+, level \d+\)", m.group(4))
        found.append({"what": m.group(1), "amount": int(m.group(2)), "earner": m.group(3),
                      "paid": [(name, int(gained)) for name, gained in shares], "raw": m.group(0)})
    return found


def paid_once_each(line, names):
    """The pay-out line names exactly `names`, each one time."""
    return sorted(name for name, _gained in line["paid"]) == sorted(names)


def next_level_at(level):
    """XP total that reaches level+1 (stat.cc pcGetExperienceForLevel)."""
    n = level + 1
    return 1000 * (n // 2) * (n if n % 2 else n - 1)


def told(lines, net, phrase):
    """Console lines addressed to `net` that contain `phrase`."""
    return [text for text, addr, _chan in lines if addr == net and phrase in text]


def shutdown():
    admin("quit", 1)
    try:
        rc = srv.wait(15)
    except Exception:
        srv.kill()
        rc = "killed"
    log.close()
    return rc


# ---- BOOT 1: sharing on (the default) ------------------------------------------
boot({}, "w")
a = Client("A")
a.send("claim", 3)
b = Client("B")
b.send("claim", 5)
check("both sessions claimed", count("control claimed by session") >= 2)
probe_baseline()
netA, netB = actor(0, "net"), actor(1, "net")
print("netIds: A=%s B=%s  tiles A=%s B=%s" % (netA, netB, actor(0, "tile"), actor(1, "tile")))
check("both actors have netIds", netA not in (None, -1, 0) and netB not in (None, -1, 0))

s0 = sheet()
print("start: %s" % s0)
check("two characters on the sheet", 0 in s0 and 1 in s0, str(s0))
nameA, nameB = s0[0]["name"], s0[1]["name"]
both = [nameA, nameB]

# 1. share, and 2. once
since = len(logtext())
out = admin("partyxp 0 100")
s1 = sheet()
g = gains(s0, s1)
lines = payouts(since)
check("host earns 100: the host is paid once, not twice", once(g.get(0), 100), "gained %s" % g.get(0))
check("host earns 100: the teammate is paid the same award once", once(g.get(1), 100), "gained %s" % g.get(1))
check("one pay-out for the award, each player on it one time",
      len(lines) == 1 and paid_once_each(lines[0], both), str([l["raw"] for l in lines])[:200])
check("the server counted two recipients", count("partyxp earner=slot 0 amount=100 shared=1 recipients=2") == 1, out.strip()[:90])

since = len(logtext())
admin("partyxp 1 40")
s2 = sheet()
g = gains(s1, s2)
lines = payouts(since)
check("teammate earns 40: the earner is paid once, not twice", once(g.get(1), 40), "gained %s" % g.get(1))
check("teammate earns 40: the host is paid the same award once", once(g.get(0), 40), "gained %s" % g.get(0))
check("one pay-out for that award too, each player one time",
      len(lines) == 1 and paid_once_each(lines[0], both) and lines[0]["earner"] == nameB,
      str([l["raw"] for l in lines])[:200])

since = len(logtext())
admin("xp 1 30")
s3 = sheet()
g = gains(s2, s3)
check("operator `xp <slot>` pays one seat only", g.get(0) == 0 and once(g.get(1), 30), str(g))
check("operator `xp <slot>` is not a party award", len(payouts(since)) == 0)

# 3. level: one shared award big enough to level the second player
need = next_level_at(s3[1]["level"]) - s3[1]["xp"]
mark = len(a.console())
admin("partyxp 0 %d" % need, 2)
s4 = sheet()
check("a shared award levels the teammate", s4[1]["level"] == s3[1]["level"] + 1,
      "level %d -> %d on +%d" % (s3[1]["level"], s4[1]["level"], need))
new = a.console()[mark:]
check("the teammate is told on their own screen, one time", len(told(new, netB, "gone up a level")) == 1, str(new)[:160])

# 4. skill: First Aid by the second player on the host, skill raised so the roll lands
admin("sp 1 99", 0.2)
for _ in range(70):
    admin("skillup 1 %d" % FIRST_AID, 0.0, quiet=True)
admin("hurt 25", 1)
s5 = sheet()
mark = len(a.console())
since = len(logtext())
for attempt in range(3):
    b.send("skill %d %d" % (netA, FIRST_AID), 1)
    if wait_for(lambda: any("honing" in text for text, _addr, _chan in a.console()[mark:]), 12):
        break
time.sleep(1)
s6 = sheet()
g = gains(s5, s6)
new = a.console()[mark:]
lines = payouts(since)
check("skill use pays the player who used it once", g.get(1, 0) > 0 and once(g.get(1), 25), str(g))
check("skill use pays the teammate the same award once", once(g.get(0), 25), str(g))
check("one pay-out for the skill use, each player one time",
      len(lines) == 1 and paid_once_each(lines[0], both) and lines[0]["earner"] == nameB,
      str([l["raw"] for l in lines])[:200])
mine = told(new, netB, "honing")
theirs = told(new, netA, "honing")
check("the earner keeps the vanilla line", len(mine) == 1 and nameB not in mine[0], str(mine))
check("the teammate's line names who earned it", len(theirs) == 1 and ("from %s honing a skill" % nameB) in theirs[0], str(theirs))

# 5. downed: paid with the rest, levelled, not healed
out = admin("kill 1", 2)
check("second player is down", "is dead" in out, out.strip()[:60])
s7 = sheet()
need = next_level_at(s7[1]["level"]) - s7[1]["xp"]
admin("partyxp 0 %d" % need, 2)
s8 = sheet()
g = gains(s7, s8)
check("a downed player is paid with the rest, once", once(g.get(1), need) and once(g.get(0), need), str(g))
check("a downed player levels with the party", s8[1]["level"] == s7[1]["level"] + 1)
out = admin("kill 1", 1)
check("the level-up did not stand the corpse up", "already dead" in out, out.strip()[:60])

# 6. kill XP while the teammate is down: an explosion kill, then a fight
tileA = actor(0, "tile")
out = admin("spawn %s 1 %d" % (RAIDER, tileA + 3), 2)
s9 = sheet()
mark = len(a.console())
since = len(logtext())
admin("explode 150", 4)
s10 = sheet()
g = gains(s9, s10)
new = a.console()[mark:]
lines = payouts(since)
bounty = lines[0]["amount"] if lines else 0
check("an explosion kill pays the host once", bounty > 0 and once(g.get(0), bounty), "%s | %s" % (g, out.strip()[:70]))
check("an explosion kill pays the downed teammate the same, once", bounty > 0 and once(g.get(1), bounty), str(g))
check("one pay-out for the kill, each player one time",
      len(lines) == 1 and paid_once_each(lines[0], both), str([l["raw"] for l in lines])[:200])
check("each reads a pay-out line of their own",
      len(told(new, netA, "exp. points")) == 1 and len(told(new, netB, "exp. points")) == 1, str(new)[:200])

# The hostile is placed by hand, three hexes out where the first one stood, and `aggro 1`
# picks the nearest living critter. `stress` places at random, and on a busy map the
# nearest critter is then a resident: the fight becomes the party against the town.
#
# It carries Dr. Schreber's script (scripts.lst 1058), so killing it is ALSO a quest
# award: that script's destroy_p_proc runs the game's own give_xp(1000), which is the
# give_exp_points opcode plus the script's broadcast line. One fight, two awards: the
# authored one when the body drops, the kill purse when the fight ends.
admin("spawn %s 1 %d %d" % (RAIDER, tileA + 3, SCHREBER_SCRIPT), 2)
s11 = sheet()
mark = len(a.console())
since = len(logtext())
enters = len(a.events(EVENT_COMBAT_ENTER))
admin("aggro 1", 3)
fought = wait_for(lambda: len(a.events(EVENT_COMBAT_ENTER)) > enters, 10)
check("a fight started", fought)
if fought:
    for turn in range(30):
        if any(line["what"] == "kills" for line in payouts(since)):
            break
        a.send("cattack", 1.5)
        a.send("cattack", 1.5)
        a.send("cendturn", 2.5)
time.sleep(1)
s12 = sheet()
g = gains(s11, s12)
new = a.console()[mark:]
lines = payouts(since)
quest = [line for line in lines if line["what"] != "kills"]
purse = [line for line in lines if line["what"] == "kills"]
print("fight pay-outs: %s" % [line["raw"] for line in lines])
check("the script's award is one pay-out, each player one time",
      len(quest) == 1 and quest[0]["amount"] == SCHREBER_XP and paid_once_each(quest[0], both),
      str([l["raw"] for l in quest])[:220])
check("the script's award is paid as itself, not doubled",
      len(quest) == 1 and all(once(gained, SCHREBER_XP) for _name, gained in quest[0]["paid"]),
      str(quest[0]["paid"]) if quest else "")
check("everyone reads the script's own line",
      any(addr == 0 and str(SCHREBER_XP) in text for text, addr, _chan in new),
      str([text for text, addr, _chan in new if addr == 0])[-200:])
check("the fight's purse is one pay-out, each player one time",
      len(purse) == 1 and purse[0]["amount"] > 0 and paid_once_each(purse[0], both),
      str([l["raw"] for l in purse])[:220])
total = {name: sum(gained for line in lines for n, gained in line["paid"] if n == name) for name in both}
check("the sheets moved by exactly what was paid, the winner's",
      len(lines) == 2 and g.get(0) == total[nameA] and g.get(0, 0) > SCHREBER_XP, "%s vs %s" % (g, total))
check("the sheets moved by exactly what was paid, the downed teammate's",
      len(lines) == 2 and g.get(1) == total[nameB] and g.get(1) == g.get(0), "%s vs %s" % (g, total))
check("each reads an end-of-fight line of their own",
      len(told(new, netA, "exp. points")) == 1 and len(told(new, netB, "exp. points")) == 1, str(new)[-200:])
out = admin("revive 1", 2)
check("the teammate was still down, and gets up", "back at 1 HP" in out, out.strip()[:60])
admin("despawnall", 1)

# 7. away: a parked body is not paid
b.close()
check("the leaver's body is parked", wait_for(lambda: count("slot 1 body parked") >= 1, 20))
s13 = sheet()
since = len(logtext())
admin("partyxp 0 60")
s14 = sheet()
g = gains(s13, s14)
lines = payouts(since)
check("a player who left is not paid", once(g.get(0), 60) and g.get(1) == 0, str(g))
check("the pay-out names the one player who is here",
      len(lines) == 1 and paid_once_each(lines[0], [nameA]), str([l["raw"] for l in lines])[:200])

b = Client("B2")
b.send("claim 1", 3)
check("the returner's body is back", wait_for(lambda: count("slot 1 body reattached") >= 1, 20))
admin("partyxp 0 60")
s15 = sheet()
g = gains(s14, s15)
check("a player who came back is paid again, once", once(g.get(0), 60) and once(g.get(1), 60), str(g))

# 8. wipe: the teammate is down, the blast takes the raider AND the last player standing
admin("kill 1", 2)
probe_baseline()
tileA = actor(0, "tile")
admin("spawn %s 1 %d" % (RAIDER, tileA + 1), 2)
s16 = sheet()
since = len(logtext())
admin("explode 5000", 3)
s17 = sheet()
g = gains(s16, s17)
check("the blast left nobody standing", count("PARTY WIPE") >= 1)
check("a dead party banks nothing", g.get(0) == 0 and g.get(1) == 0 and len(payouts(since)) == 0, str(g))

rc = shutdown()
a.close()
b.close()
check("server exited cleanly", rc == 0, "rc=%s" % rc)

# ---- BOOT 2: the kill switch ----------------------------------------------------
boot({"F2_PARTY_XP": "0"}, "a")
a = Client("A")
a.send("claim", 3)
b = Client("B")
b.send("claim", 5)
t0 = sheet()
out = admin("partyxp 0 100")
t1 = sheet()
g = gains(t0, t1)
check("F2_PARTY_XP=0: the earner alone is paid, once", once(g.get(0), 100) and g.get(1) == 0, str(g))
check("F2_PARTY_XP=0: the reply says sharing is off", "sharing is off" in out, out.strip()[:90])
rc = shutdown()
a.close()
b.close()
check("second server exited cleanly", rc == 0, "rc=%s" % rc)

text = logtext()
bad = [l for l in text.splitlines() if re.search(r"Assert|abort|SIGSEGV|RELOAD FAILED|FAILED", l)]
check("no crash/abort/failure lines", not bad, "; ".join(bad)[:200])

print("===== party xp trace =====")
keys = ("[xp]", "admin xp", "admin partyxp", "kill:", "body parked", "body reattached", "admin stress",
        "admin spawn", "[explode]", "[splash]", "PARTY WIPE", "party wipe")
for line in text.splitlines():
    if any(k in line for k in keys):
        print(line.rstrip().encode("ascii", "replace").decode()[:190])
print("===== %d/%d checks passed =====" % (sum(1 for r in results if r[1]), len(results)))
sys.exit(0 if all(r[1] for r in results) else 1)
