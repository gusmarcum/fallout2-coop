"""Headless proof of the player trade and the death rules on a sandbox f2_server.

Boots the server on a save slot that holds two player actors, attaches two fake wire
clients (bare `claim`: slots 0 and 1) and walks through:

  trade   invitation declined; invitation accepted; an offer moved onto the table; the
          other side refused `btake`; stealing from a player refused; both sides lock,
          both accept boxes go out, both answer yes, the trade completes; a second trade
          cancelled with `bdone`; a third trade ended by a live reload.
  death   `selfrevive` refused; a teammate's `revive` out of combat; looting a dead
          player refused; `revive` in combat charged 4 AP on the reviver's turn; the
          party wipe (both killed) plays the death screen and reloads the newest save.

Truth comes from the server's stderr (the same lines an operator reads) and from the
plain-text refusals/announcements the fake clients receive. netIds are read off the
F2_TRACE_EVENTS "[actors] srv slot=N ... netId=M" lines every baseline prints.

usage: python trade_death_proof.py <f2_server.exe> <game dir> <slot> <net port> <cmd port>
"""
import os, re, socket, subprocess, sys, threading, time

exe, gamedir, slot, port, cmdport = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
NL = chr(10)
env = dict(os.environ)
env.update({"F2_SERVER_LOAD": slot, "F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
            "F2_SERVER_PACE_MS": "100", "F2_MOVIES": "0", "F2_AUTOSAVE_SECS": "0",
            "F2_TRACE_EVENTS": "1"})
logpath = os.path.join(gamedir, "tradetest-server.log")
log = open(logpath, "w")
srv = subprocess.Popen([exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT)
time.sleep(7)

results = []


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

    def saw(self, text):
        return text.encode() in self.buf

    def count(self, text):
        return self.buf.count(text.encode())

    def close(self):
        self.stop.set()
        try:
            self.s.close()
        except Exception:
            pass


def admin(line, wait=2.5):
    print("admin -> " + line)
    s = socket.create_connection(("127.0.0.1", cmdport), timeout=5)
    s.sendall((line + NL).encode())
    time.sleep(0.8)
    s.settimeout(1.0)
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


def last_int(pattern, default=None):
    found = re.findall(pattern, logtext())
    return int(found[-1]) if found else default


def wait_for(cond, timeout=15.0):
    """Poll the server log for a condition instead of trusting a fixed sleep: the
    approach walks and the beat pacing make exact timings vary between runs."""
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


a = Client("A")
a.send("claim", 3)
b = Client("B")
b.send("claim", 5)
check("both sessions claimed", count("control claimed by session") >= 2)
probe_baseline()
netA, netB = actor(0, "net"), actor(1, "net")
print("netIds: A=%s B=%s  tiles A=%s B=%s" % (netA, netB, actor(0, "tile"), actor(1, "tile")))
check("both actors have netIds", netA not in (None, -1, 0) and netB not in (None, -1, 0))

# ---- TRADE ---------------------------------------------------------------------
# 1. Invitation declined.
a.send("talk %d" % netB, 8)
inv1 = last_int(r"trade INVITE prompt (\d+):")
check("talk on a player sends an invitation", inv1 is not None, "prompt id=%s" % inv1)
check("B received the invitation box", b.saw("wants to barter with you"))
check("A told to wait", a.saw("Waiting for"))
b.send("answer %d 0" % (inv1 or 0), 3)
check("decline reaches A", a.saw("declined to trade"))

# 2. Invitation accepted -> trade open.
a.send("talk %d" % netB, 2)
wait_for(lambda: count("trade INVITE prompt") >= 2, 20)
inv2 = last_int(r"trade INVITE prompt (\d+):")
check("second invitation sent", inv2 is not None and inv2 != inv1, "prompt id=%s" % inv2)
b.send("answer %d 1" % (inv2 or 0), 1)
check("trade OPEN after the accept", wait_for(lambda: count("trade OPEN") == 1))

# 3. Offer 50 caps from A (the host gets them from the debug port), refusals.
admin("give 41 60", 2)
a.send("boffer 41 50", 1)
check("A's offer landed on the table", wait_for(lambda: count("offers pid=41 qty=50") == 1))
b.send("btake 41 1", 3)
check("btake refused", b.saw("They have to offer it."))
b.send("skill %d 10" % netA, 3)
check("stealing from a player refused", b.saw("You cannot steal from another player"))
check("no steal session opened", count("steal session OPEN") == 0)

# 4. Both lock, both accept boxes, both yes -> completed.
a.send("bcommit", 3)
check("A locked", count("locked their offer") == 1)
b.send("bcommit", 4)
ids = re.findall(r"trade CONFIRM prompts (\d+) \(slot 0\) and (\d+) \(slot 1\)", logtext())
check("both accept boxes went out", len(ids) == 1, str(ids))
pa, pb = (int(ids[-1][0]), int(ids[-1][1])) if ids else (0, 0)
check("A's box lists the caps", a.saw("You give: 50x"))
check("B's box lists the caps", b.saw("You get: 50x"))
a.send("boffer 41 5", 2)
check("moves refused while the question is out", a.saw("Answer the question first."))
a.send("answer %d 1" % pa, 3)
check("one yes does not complete", count("closed: reason=0") == 0)
b.send("answer %d 1" % pb, 4)
check("both yes -> completed", count("closed: reason=0") == 1)
check("completion announced", count("completed a trade") >= 1)

# 5. Cancel with bdone.
a.send("talk %d" % netB, 2)
wait_for(lambda: count("trade INVITE prompt") >= 3, 20)
inv3 = last_int(r"trade INVITE prompt (\d+):")
b.send("answer %d 1" % (inv3 or 0), 1)
check("third trade open", wait_for(lambda: count("trade OPEN") == 2))
b.send("bdone", 1)
check("bdone cancels", wait_for(lambda: count("closed: reason=1") == 1 and count("cancelled the trade") >= 1))

# 6. A live reload ends an open trade with the goods swept home.
a.send("talk %d" % netB, 2)
wait_for(lambda: count("trade INVITE prompt") >= 4, 20)
inv4 = last_int(r"trade INVITE prompt (\d+):")
b.send("answer %d 1" % (inv4 or 0), 1)
wait_for(lambda: count("trade OPEN") == 3)
a.send("boffer 41 5", 1)
check("fourth trade open with an offer", wait_for(lambda: count("trade OPEN") == 3 and count("offers pid=41 qty=5" + NL) == 1))
admin("load %s" % slot, 8)
check("reload ended the trade (bailed)", count("closed: reason=3") == 1 and count("the game was reloaded") >= 1)
check("reload ran", count("reload slot %d ok" % int(slot)) == 1)
probe_baseline()
netA, netB = actor(0, "net"), actor(1, "net")
print("netIds after reload: A=%s B=%s" % (netA, netB))

# ---- DEATH ---------------------------------------------------------------------
# 7. No self-revive; a teammate revives.
out = admin("kill 1", 3)
check("kill 1 worked", "is dead" in out, out.strip()[:60])
b.send("selfrevive", 3)
check("selfrevive refused", b.saw("You cannot get up on your own"))
a.send("loot %d" % netB, 3)
check("looting a dead player refused", a.saw("can be revived"))
a.send("revive %d" % netB, 10)
check("teammate revive fired", count("interact FIRE revive") == 1)
check("revive announced", a.saw("revived") and b.saw("revived"))
dead_before = count("actor is dead")
b.send("mv %d 1" % (actor(1, "tile") + 2), 3)
check("revived player acts again", count("control mv") >= 1 and count("actor is dead") == dead_before)

# 8. In combat: revive costs 4 AP on the reviver's own turn, and the body rejoins.
# B is killed BEFORE the fight: `stress` makes the nearest LIVE critter the hostile,
# and an adjacent teammate would be picked instead of the spawn (no fight at all).
# A dead body enters the fight in the non-combatant block; the revive must move it
# into the combatant block (the first "rejoins" line). Then B is killed again
# mid-fight and a round is allowed to pass, so the round-end sweep parks the corpse
# past the non-combatants — the case real play produces — before the second revive.
admin("kill 1", 2)
admin("stress 1 0x010000EE 7", 5)
check("a fight started", count("admin stress placed=1") == 1)
a.send("revive %d" % netB, 1)
check("combat revive fired", wait_for(lambda: count("interact FIRE revive") == 2, 25))
ap = last_int(r"interact FIRE revive net=\d+ by slot=0 ap=(-?\d+)")
check("combat revive charged 4 AP (10 -> at most 6 after the charge)", ap is not None and ap <= 6, "ap=%s" % ap)
check("first-round revive found the body still on the roster", count("revived while still on the roster") == 1)
check("no AP refusal on the revive", count("revive refused (ap=") == 0)
# A round passes: A ends the turn, B (alive again, on the roster) ends theirs.
a.send("cendturn", 3)
b.send("cendturn", 5)
admin("kill 1", 2)
a.send("cendturn", 3)
b.send("cendturn", 5)
a.send("revive %d" % netB, 1)
check("second combat revive fired", wait_for(lambda: count("interact FIRE revive") == 3, 25))
check("swept corpse rejoined the roster", wait_for(lambda: count("rejoins the fight") == 1, 5))
admin("load %s" % slot, 8)
check("world reset after the fight", count("reload slot %d ok" % int(slot)) == 2 and count("ended by a load") == 1)

# 9. Party wipe: newest save is the quicksave written now (slot 16).
a.send("quicksave", 2)
check("quicksave written for the wipe test", wait_for(lambda: count("quicksave -> slot 16 ok") == 1, 15))
admin("kill 1", 3)
check("one death is not a wipe", count("PARTY WIPE") == 0)
admin("kill 0", 4)
check("second death is a wipe", count("PARTY WIPE") == 1)
check("wipe announced, reload held for the death screens", wait_for(lambda: count("party wipe announced") == 1, 5))
check("everyone told", a.saw("Everyone is dead.") and b.saw("Everyone is dead."))
check("no reload before the acks", count("reload slot 16") == 0)
a.send("wipeack", 2)
check("one ack does not release the reload", count("finished the death screen") == 1 and count("reload slot 16") == 0)
b.send("wipeack", 1)
check("wipe reloads the newest save (slot 16) once everyone acked",
      wait_for(lambda: count("party wipe -> reload slot 16") == 1 and count("reload slot 16 ok") == 1, 15))
check("back-to-save announced", wait_for(lambda: a.saw("Back to the last save"), 5))
probe_baseline()
dead_before = count("actor is dead")
a.send("mv %d 1" % (actor(0, "tile") + 2), 3)
check("host alive after the wipe reload", count("actor is dead") == dead_before)

# 10. Clean shutdown.
admin("quit", 1)
try:
    rc = srv.wait(15)
except Exception:
    srv.kill()
    rc = "killed"
a.close()
b.close()
log.close()
text = logtext()
bad = [l for l in text.splitlines() if re.search(r"Assert|abort|SIGSEGV|stub|RELOAD FAILED|FAILED", l)]
check("server exited cleanly", rc == 0, "rc=%s" % rc)
check("no crash/abort/failure lines", not bad, "; ".join(bad)[:200])

print("===== trade/death trace =====")
keys = ("trade", "revive", "PARTY WIPE", "party wipe", "reload slot", "kill:", "quicksave", "steal", "rejoins")
for line in text.splitlines():
    if any(k in line for k in keys):
        print(line.rstrip().encode("ascii", "replace").decode()[:170])
print("===== %d/%d checks passed =====" % (sum(1 for r in results if r[1]), len(results)))
sys.exit(0 if all(r[1] for r in results) else 1)
