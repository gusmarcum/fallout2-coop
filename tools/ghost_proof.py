"""Headless proof for the parked-body ghost fix (2026-09-05).

An offline player's body travels in the join blob at tile -1; the loader could not
place it, left it on the floating list, and the viewer's post-roof render pass drew
it at screen (0,0): the teammate "sticker" glued to the top-left corner. The fix
hides a body the loader could not place and un-hides it when it is reattached.

The server runs the same loader (_obj_load_player_actor) when it live-loads a save
that holds a parked body, so the server binary can prove both halves:

  1. A claims slot 0, B claims slot 1, B leaves -> slot 1 parked (tile -1).
  2. A quicksaves, admin live-loads that save -> slot 1 restored from the save:
     tile -1 AND OBJECT_HIDDEN (0x1) set.            <- half one (hide on load)
  3. B returns -> reattached: on a tile, HIDDEN clear. <- half two (show on reattach)

Truth is the F2_TRACE_EVENTS "[actors] srv slot=N ... tile=T ... flags=0xF" block the
server prints with every baseline (each client connect emits one).

usage: python f2dev-ghosttest.py <f2_server.exe>   (sandbox D:/Games/F2-Dev, slot 9, 9500/9501)
"""
import os, re, socket, subprocess, sys, threading, time

exe = sys.argv[1]
gamedir, slot, port, cmdport = "D:/Games/F2-Dev", "9", 9500, 9501
NL = chr(10)
OBJECT_HIDDEN = 0x1
env = dict(os.environ)
env.update({"F2_SERVER_LOAD": slot, "F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport),
            "F2_SERVER_PACE_MS": "100", "F2_MOVIES": "0", "F2_AUTOSAVE_SECS": "0",
            "F2_TRACE_EVENTS": "1"})
logpath = os.path.join(gamedir, "ghosttest-server.log")
log = open(logpath, "w")
srv = subprocess.Popen([exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT)
time.sleep(7)

passed = failed = 0


def check(name, ok, detail=""):
    global passed, failed
    if ok:
        passed += 1
    else:
        failed += 1
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


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

    def close(self):
        self.stop.set()
        try:
            self.s.close()
        except Exception:
            pass


def admin(line, wait=2.0):
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
    log.flush()
    return open(logpath, encoding="utf-8", errors="replace").read()


def wait_for(pattern, seconds, start=0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        t = logtext()
        m = re.search(pattern, t[start:])
        if m:
            return start + m.end()
        time.sleep(0.5)
    return -1


ACTOR = re.compile(r"\[actors\] srv slot=(\d+) obj=\S+ netId=(-?\d+) pid=\S+ tile=(-?\d+) elev=\S+ flags=0x([0-9A-Fa-f]+)")


def baselines():
    """All baseline blocks so far: list of dict slot -> (tile, flags, netId)."""
    blocks = []
    cur = None
    for m in ACTOR.finditer(logtext()):
        s, net, tile, flags = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4), 16)
        if s == 0:
            cur = {}
            blocks.append(cur)
        if cur is not None:
            cur[s] = (tile, flags, net)
    return blocks


def snapshot(label):
    """Connect a probe (emits a baseline), return the newest block."""
    before = len(baselines())
    probe = Client("probe")
    deadline = time.time() + 15
    while time.time() < deadline and len(baselines()) <= before:
        time.sleep(0.3)
    probe.close()
    time.sleep(1.0)
    b = baselines()
    block = b[-1] if b else {}
    print("[%s] baseline #%d: %s" % (label, len(b), {k: ("tile=%d flags=0x%X net=%d" % v) for k, v in sorted(block.items())}))
    return block


def fmt(entry):
    return "tile=%d flags=0x%X" % (entry[0], entry[1]) if entry else "absent"


# ---- 1. two players, then B leaves ------------------------------------------------
a = Client("A")
a.send("claim", 3)
s1 = snapshot("A alone")
check("slot 0 is on the map for A", 0 in s1 and s1[0][0] != -1, fmt(s1.get(0)))
print("slot 1 in the save:", fmt(s1.get(1)))

b = Client("B")
b.send("claim", 5)
pos = wait_for(r"control claimed by session \d+ \(slot 1\)", 10)
check("B claimed slot 1", pos > 0)
s2 = snapshot("A+B")
check("slot 1 stands on a tile with B present", 1 in s2 and s2[1][0] != -1, fmt(s2.get(1)))
check("slot 1 not hidden with B present", 1 in s2 and (s2[1][1] & OBJECT_HIDDEN) == 0, fmt(s2.get(1)))

b.close()
pos = wait_for(r"slot 1 body parked \(owner disconnected\)", 40)
check("slot 1 parked after B left", pos > 0)
s3 = snapshot("B gone")
check("parked body is off-map (tile -1)", 1 in s3 and s3[1][0] == -1, fmt(s3.get(1)))

# ---- 2. save with the body parked, live-load it -----------------------------------
a.send("quicksave", 6)
pos = wait_for(r"quicksave -> slot 16 ok", 20)
check("quicksave written with slot 1 parked", pos > 0)
reply = admin("load 16", 8)
print("admin load ->", reply.strip()[:120])
pos = wait_for(r"quicksave -> slot 16 ok[\s\S]*\[actors\] srv slot=0", 30)
check("baseline printed after the live load", pos > 0)
s4 = snapshot("after live load")
check("restored parked body is off-map (tile -1)", 1 in s4 and s4[1][0] == -1, fmt(s4.get(1)))
check("restored parked body is HIDDEN (fix, half one)", 1 in s4 and (s4[1][1] & OBJECT_HIDDEN) != 0, fmt(s4.get(1)))
check("slot 0 untouched by the hide", 0 in s4 and s4[0][0] != -1 and (s4[0][1] & OBJECT_HIDDEN) == 0, fmt(s4.get(0)))

# ---- 3. B returns -----------------------------------------------------------------
mark = len(logtext())
b2 = Client("B2")
b2.send("claim", 5)
pos = wait_for(r"slot 1 body reattached \(owner returned\)", 20, mark)
check("slot 1 reattached when B returned", pos > 0)
s5 = snapshot("B back")
check("reattached body stands on a tile", 1 in s5 and s5[1][0] != -1, fmt(s5.get(1)))
check("reattached body is visible again (fix, half two)", 1 in s5 and (s5[1][1] & OBJECT_HIDDEN) == 0, fmt(s5.get(1)))

admin("quit", 1)
try:
    srv.wait(15)
except Exception:
    srv.kill()
a.close()
b2.close()
log.close()
print("RESULT: %d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
