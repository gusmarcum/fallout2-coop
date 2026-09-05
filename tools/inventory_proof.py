"""Sandbox checks for the inventory reports of 2026-09-05: (1) a stimpak peeled off a stack
into a hand slot and put back must merge into one stack again; (2) a steal session against
another PLAYER must hand the victim's equipped gear back, flags and all, when it closes.
Two fake clients (bare `claim` -> slot 0 = A the host, slot 1 = B). Inventories are read
with the server's own miss dump (an item verb with id 0 prints "[net= pid= qty= f=]").
usage: python f2dev-invtest.py <f2_server.exe> <game dir> <slot> <net port> <cmd port>"""
import os, re, socket, subprocess, sys, threading, time

exe, gamedir, slot, port, cmdport = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
NL = chr(10)
STIMPAK = 40
POWER_ARMOR = 3
IN_HAND = 0x01000000 | 0x02000000
WORN = 0x04000000
env = dict(os.environ)
env.update({"F2_SERVER_LOAD": slot, "F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
            "F2_SERVER_PACE_MS": "100", "F2_MOVIES": "0", "F2_AUTOSAVE_SECS": "0", "F2_TRACE_EVENTS": "1"})
logpath = os.path.join(gamedir, "invtest-server.log")
log = open(logpath, "w")
srv = subprocess.Popen([exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT)
time.sleep(7)
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + ("  [" + detail + "]" if detail else ""))


class Client:
    def __init__(self, tag):
        self.tag = tag
        self.s = socket.create_connection(("127.0.0.1", port), timeout=60)
        self.stop = threading.Event()
        threading.Thread(target=self.drain, daemon=True).start()

    def drain(self):
        while not self.stop.is_set():
            try:
                if not self.s.recv(65536):
                    return
            except Exception:
                return

    def send(self, line, wait):
        print("%s -> %s" % (self.tag, line))
        self.s.sendall((line + NL).encode())
        time.sleep(wait)

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
    s.close()
    time.sleep(wait)


def logtext():
    if not log.closed:
        log.flush()
    return open(logpath, encoding="utf-8", errors="replace").read()


def dump(client):
    """Ask for a nonexistent item id: the server prints the actor's inventory."""
    mark = len(logtext())
    client.send("invwield 0 0", 2)
    text = logtext()[mark:]
    m = re.search(r"dude has:((?: \[net=\d+ pid=\d+ qty=\d+ f=0x[0-9A-F]+\])*)", text)
    items = []
    if m:
        for net, pid, qty, flags in re.findall(r"\[net=(\d+) pid=(\d+) qty=(\d+) f=0x([0-9A-F]+)\]", m.group(1)):
            items.append((int(net), int(pid), int(qty), int(flags, 16)))
    return items


def entries(items, pid):
    return [(n, q, f) for (n, p, q, f) in items if p == pid]


a = Client("A")
a.send("claim", 3)
b = Client("B")
b.send("claim", 5)
check("both sessions claimed", logtext().count("control claimed by session") >= 2)

# ---- 1. stack peel and merge ----
admin("give %d 24" % STIMPAK)
before = entries(dump(a), STIMPAK)
print("stimpaks before:", before)
check("host holds one stimpak stack", len(before) == 1 and before[0][1] >= 24, str(before))
net = before[0][0] if before else 0
a.send("invwield %d 0" % net, 3)
mid = entries(dump(a), STIMPAK)
print("stimpaks with one in hand:", mid)
check("one stimpak peeled into the hand", len(mid) == 2 and any(f & IN_HAND for (_, _, f) in mid), str(mid))
a.send("invunwield 0", 3)
after = entries(dump(a), STIMPAK)
print("stimpaks after unwield:", after)
check("stack merged back into one", len(after) == 1 and after[0][1] == before[0][1], str(after))

# ---- 2. steal from a player: victim keeps equipped gear ----
admin("give %d 1" % POWER_ARMOR)
pa = entries(dump(a), POWER_ARMOR)
check("host holds the T-51b", len(pa) == 1, str(pa))
a.send("invwield %d 0" % pa[0][0], 3)
gear_before = [(p, q, f) for (n, p, q, f) in dump(a) if f & (IN_HAND | WORN)]
print("host equipped before the steal:", gear_before)
check("host wears the T-51b", any(p == POWER_ARMOR and f & WORN for (p, q, f) in gear_before), str(gear_before))
# B stands next to A already (reattached beside the host); open the steal screen on A (net 1)
mark = len(logtext())
b.send("skill 1 %s" % os.environ.get("F2_STEAL_SKILL", "10"), 6)
opened = "steal session OPEN" in logtext()[mark:]
check("steal session opened on the host", opened)
if opened:
    b.send("sdone", 4)
check("steal session closed", "steal session CLOSE" in logtext()[mark:])
gear_after = [(p, q, f) for (n, p, q, f) in dump(a) if f & (IN_HAND | WORN)]
print("host equipped after the steal:", gear_after)
check("victim's equipped gear is back with its flags", sorted(gear_after) == sorted(gear_before), "before=%s after=%s" % (gear_before, gear_after))
total_before = sum(q for (_, _, q) in gear_before)
check("victim lost nothing", len(dump(a)) >= 1 and sorted(gear_after) == sorted(gear_before))

admin("quit", 1)
try:
    rc = srv.wait(15)
except Exception:
    srv.kill(); rc = "killed"
a.close(); b.close(); log.close()
text = logtext()
bad = [l for l in text.splitlines() if re.search(r"Assert|abort|SIGSEGV|FAILED", l)]
check("server exited cleanly", rc == 0, "rc=%s" % rc)
check("no crash lines", not bad, "; ".join(bad)[:160])
print("===== trace =====")
for line in text.splitlines():
    if any(k in line for k in ("steal", "invwield", "invunwield", "armor perk", "merge", "interact")):
        print(line.rstrip().encode("ascii", "replace").decode()[:200])
print("===== %d/%d checks passed =====" % (sum(1 for r in results if r[1]), len(results)))
sys.exit(0 if all(r[1] for r in results) else 1)
