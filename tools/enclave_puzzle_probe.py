"""Enclave puzzle-room check (bugs/015): press the terminal N times on a sandbox
f2_server in D:\\Games\\F2-Dev (ports 9500/9501, never a live world) and report, per
press, which doors opened and which closed.

The failure it looks for is a door that OPENS and then CLOSES inside one press.
QIPzlTrm's Term3 branch opens tiles 19496 and 20510 and then closes those same two;
vanilla's deferred slide makes the close a no-op, so vanilla leaves them open.

  python f2dev-puzzletest.py <f2_server.exe> [presses]
"""
import atexit, os, shutil, socket, struct, subprocess, sys, threading, time

GAMEDIR = os.environ.get("F2_SANDBOX_GAME", "D:/Games/F2-Dev")
SRC_SLOT = os.environ.get("F2_SANDBOX_SLOT", "")  # a save sitting on ENCTRP
TERMINAL_PID, TERMINAL_TILE = 0x020000B7, 17891
DUDE_TILE, DUDE_ELEV = 18091, 0
NET, CMD = 9500, 9501

exe = sys.argv[1]
presses = int(sys.argv[2]) if len(sys.argv) > 2 else 9
t0 = time.time()
lines = []


def prepare():
    if not SRC_SLOT:
        sys.exit("set F2_SANDBOX_SLOT to a save directory sitting on ENCTRP")
    dst = GAMEDIR + "/data/SAVEGAME/SLOT09"
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(SRC_SLOT, dst)
    path = dst + "/SAVE.DAT"
    data = bytearray(open(path, "rb").read())
    needle = struct.pack(">I", 0x01000000)
    at = data.find(needle, 0x7563)
    while at != -1:
        s = at - 44
        if s >= 0:
            (tile,) = struct.unpack(">i", data[s + 4:s + 8])
            (fid,) = struct.unpack(">I", data[s + 32:s + 36])
            (elev,) = struct.unpack(">i", data[s + 40:s + 44])
            if 0 <= tile < 40000 and 0 <= elev < 3 and (fid >> 24) == 1:
                data[s + 4:s + 8] = struct.pack(">i", DUDE_TILE)
                data[s + 40:s + 44] = struct.pack(">i", DUDE_ELEV)
                open(path, "wb").write(data)
                print("SLOT09 <- SLOT01 (ENCTRP); dude %d/e%d -> %d/e%d" % (tile, elev, DUDE_TILE, DUDE_ELEV))
                return
        at = data.find(needle, at + 1)
    print("WARNING: dude record not found; using the save's own position")


def start():
    env = dict(os.environ)
    env.update({"F2_SERVER_LOAD": "9", "F2_SERVER_NET": str(NET), "F2_SERVER_CMD": str(CMD),
                "F2_SERVER_PACE_MS": "100", "F2_MOVIES": "0", "F2_AUTOSAVE_SECS": "0",
                "F2_TRACE_WORLD": "1"})
    srv = subprocess.Popen([exe], cwd=GAMEDIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    atexit.register(lambda: srv.poll() is None and srv.kill())

    def pump():
        for raw in srv.stdout:
            lines.append((time.time() - t0, raw.decode("utf-8", "replace").rstrip()))
    threading.Thread(target=pump, daemon=True).start()
    deadline = time.time() + 90
    while time.time() < deadline:
        if any("ready to serve" in l for _, l in lines):
            break
        time.sleep(0.2)
    time.sleep(2)
    return srv


prepare()
srv = start()
raw = b""
deadline = time.time() + 30
while True:
    try:
        s = socket.create_connection(("127.0.0.1", NET), timeout=5)
        break
    except OSError:
        if time.time() > deadline:
            raise
        time.sleep(0.3)
stop = threading.Event()


def reader():
    global raw
    while not stop.is_set():
        try:
            chunk = s.recv(1 << 16)
        except Exception:
            return
        if not chunk:
            return
        raw += chunk


threading.Thread(target=reader, daemon=True).start()
s.sendall(b"claim\n")
time.sleep(6)

# netId of the terminal: SPAWN/SNAPSHOT payloads are netId,pid,tile,elev as LE int32.
needle = struct.pack("<ii", TERMINAL_PID, TERMINAL_TILE)
at = raw.find(needle)
term = None
if at >= 4:
    (term,) = struct.unpack("<i", raw[at - 4:at])
print("terminal netId=%s (%d bytes of wire seen)" % (term, len(raw)))
if term is None:
    print("could not find the terminal in the stream; aborting")
    srv.kill()
    sys.exit(2)

marks = []
for i in range(presses):
    marks.append(len(lines))
    s.sendall(("use %d\n" % term).encode())
    time.sleep(4)
marks.append(len(lines))

print("\npress   opened                          closed                         verdict")
bad = 0
for i in range(presses):
    seq = []
    for _, ln in lines[marks[i]:marks[i + 1]]:
        if "[world] door netId=" in ln and ("-> OPEN" in ln or "-> CLOSED" in ln):
            tile = int(ln.split("tile=")[1].split()[0])
            seq.append((tile, "OPEN" if "-> OPEN" in ln else "CLOSED"))
    seen, dup = {}, []
    for tile, act in seq:
        if tile in seen and seen[tile] != act:
            dup.append(tile)
        seen[tile] = act
    o = sorted({t for t, a in seq if a == "OPEN"})
    c = sorted({t for t, a in seq if a == "CLOSED"})
    if dup:
        bad += 1
    print("%-7d %-30s %-30s %s" % (i + 1, o, c, ("REVERSED IN ONE PRESS: %s" % sorted(set(dup))) if dup else "ok"))

print("\n%d of %d presses reversed a door they had just moved" % (bad, presses))
stop.set()
try:
    s.close()
except Exception:
    pass
try:
    a = socket.create_connection(("127.0.0.1", CMD), timeout=5)
    a.sendall(b"quit\n")
    time.sleep(1)
    a.close()
except Exception:
    pass
try:
    srv.wait(8)
except Exception:
    srv.kill()
with open(GAMEDIR + "/puzzletest-last.log", "w", encoding="utf-8") as f:
    for t, ln in lines:
        f.write("%7.2f  %s\n" % (t, ln))
print("full server log: %s/puzzletest-last.log" % GAMEDIR)
