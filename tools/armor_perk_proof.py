"""Sandbox proof for bugs/012: an armor's perk (T-51b +3 Strength) applies to a second
player, not only to the host. Two fake clients (bare `claim` -> slots 0 and 1). The host is
given a T-51b (pid 3), wears it, takes it off, drops it; the second player picks it up, wears
it and takes it off. The server's "armor perk a -> b for slot N (Strength now X)" lines give
the before/after Strength per slot; equip minus unequip must be 3 for BOTH slots.
usage: python f2dev-armortest.py <f2_server.exe> <game dir> <slot> <net port> <cmd port>"""
import os, re, socket, subprocess, sys, threading, time

exe, gamedir, slot, port, cmdport = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
NL = chr(10)
env = dict(os.environ)
env.update({"F2_SERVER_LOAD": slot, "F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
            "F2_SERVER_PACE_MS": "100", "F2_MOVIES": "0", "F2_AUTOSAVE_SECS": "0", "F2_TRACE_EVENTS": "1"})
logpath = os.path.join(gamedir, "armortest-server.log")
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


def armor_net(dump_line_after):
    """The server answers a missed item verb by listing the actor's inventory with net ids."""
    text = logtext()[dump_line_after:]
    m = re.findall(r"\[net=(\d+) pid=3 qty=\d+\]", text)
    return int(m[-1]) if m else None


def perk_lines(slot_index):
    return re.findall(r"armor perk (-?\d+) -> (-?\d+) for slot %d \(Strength now (\d+)\)" % slot_index, logtext())


a = Client("A")
a.send("claim", 3)
b = Client("B")
b.send("claim", 5)
check("both sessions claimed", logtext().count("control claimed by session") >= 2)

admin("give 3 1")
mark = len(logtext())
a.send("invwield 0 0", 2)  # deliberate miss: dumps the host inventory with net ids
na = armor_net(mark)
check("host holds the T-51b", na is not None, "net=%s" % na)
a.send("invwield %s 0" % na, 3)
a.send("invunwield 2", 3)
host = perk_lines(0)
check("host equip/unequip logged", len(host) >= 2, str(host))
if len(host) >= 2:
    on, off = int(host[-2][2]), int(host[-1][2])
    check("host Strength +3 while wearing", on - off == 3 and host[-2][1] != "-1", "on=%d off=%d perk=%s" % (on, off, host[-2][1]))

a.send("invdrop %s 1" % na, 3)
mark2 = len(logtext())
# the dropped suit is a ground item now; its wire id is announced when it lands
tail = logtext()[mark2 - 4000:]
ground = re.findall(r"SPAWN\s+net=(\d+) pid=3 ", tail)
gnet = int(ground[-1]) if ground else na
print("ground armor net=%s" % gnet)
b.send("get %d" % gnet, 8)
mark3 = len(logtext())
b.send("invwield 0 0", 2)
nb = armor_net(mark3)
check("second player picked the T-51b up", nb is not None, "net=%s" % nb)
if nb is not None:
    b.send("invwield %s 0" % nb, 3)
    b.send("invunwield 2", 3)
second = perk_lines(1)
check("second player equip/unequip logged", len(second) >= 2, str(second))
if len(second) >= 2:
    on, off = int(second[-2][2]), int(second[-1][2])
    check("second player Strength +3 while wearing", on - off == 3 and second[-2][1] != "-1", "on=%d off=%d perk=%s" % (on, off, second[-2][1]))

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
    if any(k in line for k in ("armor perk", "invwield", "invunwield", "invdrop", "control get", "interact FIRE", "no dude item", "psht")):
        print(line.rstrip().encode("ascii", "replace").decode()[:170])
print("===== %d/%d checks passed =====" % (sum(1 for r in results if r[1]), len(results)))
sys.exit(0 if all(r[1] for r in results) else 1)
