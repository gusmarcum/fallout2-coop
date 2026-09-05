"""Headless proof of F6/F7 (quicksave / quickload) on a sandbox f2_server.

Boots the server on a slot copy, attaches two fake wire clients (bare `claim`, so slot 0 and
slot 1 are both driven), then walks through: quickload with no quicksave yet (refused),
quicksave, walk away, quickload (position rewound, both sessions rebound), quicksave refused
in combat, quickload IN combat (fight ends, world replaced), quickload while dead, and an
operator `load <slot>` while the world runs. Position is read from the F2_TRACE_EVENTS
"[actors] srv slot=0 ... tile=N" line that every baseline prints; a throwaway connection
forces a baseline when one is needed between steps.

usage: python f2dev-quicktest.py <f2_server.exe> <game dir> <slot> <net port> <cmd port>
"""
import os, re, socket, subprocess, sys, threading, time

exe, gamedir, slot, port, cmdport = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
NL = chr(10)
env = dict(os.environ)
env.update({"F2_SERVER_LOAD": slot, "F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
            "F2_SERVER_PACE_MS": "100", "F2_MOVIES": "0", "F2_AUTOSAVE_SECS": "40",
            "F2_TRACE_EVENTS": "1"})
logpath = os.path.join(gamedir, "quicktest-server.log")
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


def probe_baseline():
    """Force a rebaseline (a connect owes one) and return the newest slot-0 tile."""
    c = Client("probe")
    time.sleep(2.5)
    c.close()
    time.sleep(1.0)
    return actor_tile(0)


def actor_tile(slot_index):
    tiles = re.findall(r"\[actors\] srv slot=%d .* tile=(-?\d+)" % slot_index, logtext())
    return int(tiles[-1]) if tiles else None


a = Client("A")
a.send("claim", 3)
b = Client("B")
b.send("claim", 5)
check("both sessions claimed", count("control claimed by session") >= 2)
t0 = actor_tile(0)
t1 = actor_tile(1)
print("start tiles: slot0=%s slot1=%s" % (t0, t1))
check("slot 1 body reattached for B", t1 is not None and t1 != -1, "tile=%s" % t1)

# 1. F7 before any F6: refused, nothing happens.
a.send("quickload", 3)
check("quickload without a quicksave is refused", a.saw("There is no quicksave to load.") and count("reload slot") == 0)

# 2. F6.
a.send("quicksave", 4)
check("quicksave written", count("quicksave -> slot 16 ok") == 1)
check("quicksave announced", a.saw("quick-saved the game"))

# 3. Walk away, then F7: the tile comes back.
moved = None
for delta in (4, -4, 400, -400, 6, -6, 2, -2):
    a.send("mv %d 1" % (t0 + delta), 7)
    now = probe_baseline()
    if now is not None and now != t0:
        moved = now
        break
check("walk moved slot 0", moved is not None, "from %s to %s" % (t0, moved))
a.send("quickload", 6)
check("quickload ran", count("reload slot 16 ok") == 1)
check("quickload announced", a.saw("quick-loaded the game"))
after = actor_tile(0)
check("slot 0 back on the quicksave tile", after == t0, "tile=%s (saved %s)" % (after, t0))
check("both sessions rebound", count("reload: session") >= 2 and count("kicked") == 0)
check("slot 1 survives the reload", actor_tile(1) not in (None, -1), "tile=%s" % actor_tile(1))
check("no map-change autosave after reload", count("(map change)") == 0)
a.send("mv %d 1" % (t0 + 2), 4)
check("slot 0 still drives after reload", count("control mv") >= 2)

# 4. Combat: F6 refused, F7 ends the fight and rewinds.
admin("stress 1 0x010000EE 7", 6)
in_combat = count("aggro") > 0 or count("combat") > 0
a.send("quicksave", 3)
check("quicksave refused in combat", a.saw("You cannot save now"))
a.send("quickload", 7)
check("fight was live and ended by the load", count("ended by a load") == 1)
check("quickload in combat ran", count("reload slot 16 ok") == 2)
gone = admin("despawnall")
check("stress spawn gone with the old world", "skipped 1" in gone, gone.strip()[:80])
a.send("mv %d 1" % (t0 + 4), 4)
check("free-roam mv accepted after in-combat reload", count("control mv dropped") == 0 and count("control mv") >= 3)

# 5. Dead: F7 allowed, comes back alive.
admin("hurt 5000", 3)
a.send("mv %d 1" % (t0 + 2), 3)
check("dead actor refused a move", count("actor is dead") >= 1)
a.send("quickload", 7)
check("quickload while dead ran", count("reload slot 16 ok") == 3)
a.send("mv %d 1" % (t0 + 4), 4)
check("alive again after reload", count("actor is dead") == 1)

# 6. Operator live load of the boot slot.
out = admin("load %s" % slot, 7)
check("operator live load accepted", "reloading the running world" in out, out.strip()[:80])
check("operator live load ran", count("reload slot %d ok" % int(slot)) == 1)
check("slot 0 on the boot tile again", actor_tile(0) == t0, "tile=%s" % actor_tile(0))

# 7. Still serving, clean shutdown.
b.send("mv %d 1" % (t1 + 2), 3)
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

print("===== reload trace =====")
keys = ("quicksave", "reload", "claimed by session", "kicked", "parked", "reattached", "[actors] srv slot",
        "autosave", "dropped", "despawnall", "shutdown")
for line in text.splitlines():
    if any(k in line for k in keys):
        print(line.rstrip().encode("ascii", "replace").decode()[:160])
print("===== %d/%d checks passed =====" % (sum(1 for r in results if r[1]), len(results)))
sys.exit(0 if all(r[1] for r in results) else 1)
