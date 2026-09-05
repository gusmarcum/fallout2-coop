"""Sandbox checks for the 2026-09-05 door/elevator work, against a headless f2_server in
D:\\Games\\F2-Dev (ports 9500/9501, never the live or TEST worlds).

  python f2dev-sandbox.py elev <f2_server.exe>   # Navarro (SLOT16 copy): offers per walk, cancel release
  python f2dev-sandbox.py door <f2_server.exe>   # Navarro (SLOT16 copy): load-time normalization, open/close offsets
  python f2dev-sandbox.py bos  <f2_server.exe>   # fresh SFCHINA.MAP: Brotherhood door open -> auto-close timing

The fake client speaks the text verbs (claim / mv / use / elev / elevcancel) and parses the
F2NS wire only far enough to map netId -> (pid, tile, elev) from SNAPSHOT_OBJECT / SPAWN.
Server stderr is captured with wall-clock stamps so timings can be read off the log.
"""
import atexit, os, shutil, socket, struct, subprocess, sys, threading, time

GAMEDIR = os.environ.get("F2_SANDBOX_GAME", "D:/Games/F2-Dev")
SRC_SLOT = os.environ.get("F2_SANDBOX_SLOT", "D:/Games/F2-Friend-TEST/data/SAVEGAME/SLOT16")
NET, CMD = 9500, 9501
EVENT_SPAWN, EVENT_SNAPSHOT_OBJECT = 1, 8

mode, exe = sys.argv[1], sys.argv[2]
t0 = time.time()
lines = []
objects = {}  # netId -> (pid, tile, elev)


def stamp():
    return "%6.2f" % (time.time() - t0)


def start_server(env_extra):
    env = dict(os.environ)
    env.update({"F2_SERVER_NET": str(NET), "F2_SERVER_CMD": str(CMD), "F2_SERVER_PACE_MS": "100",
                "F2_MOVIES": "0", "F2_AUTOSAVE_SECS": "0", "F2_TRACE_WORLD": "1", "F2_TRACE_EVENTS": "1"})
    env.update(env_extra)
    srv = subprocess.Popen([exe], cwd=GAMEDIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    atexit.register(lambda: srv.poll() is None and srv.kill())

    def pump():
        for raw in srv.stdout:
            line = raw.decode("utf-8", "replace").rstrip()
            lines.append((time.time() - t0, line))
    threading.Thread(target=pump, daemon=True).start()
    # Let the world come up before a client connects (the listener is up long before).
    if wait_for("map load", 60) < 0:
        print("server never loaded a map; last lines:")
        dump([""], 0)
        srv.kill()
        sys.exit(1)
    time.sleep(2)
    return srv


class Wire:
    def __init__(self):
        deadline = time.time() + 30
        while True:
            try:
                self.s = socket.create_connection(("127.0.0.1", NET), timeout=5)
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.3)
        self.buf = b""
        self.raw = b"" # every byte ever received: the object finder scans this
        self.stop = False
        threading.Thread(target=self.reader, daemon=True).start()

    def reader(self):
        got_preamble = False
        while not self.stop:
            try:
                chunk = self.s.recv(1 << 16)
            except Exception:
                return
            if not chunk:
                return
            self.raw += chunk
            self.buf += chunk
            if not got_preamble:
                if len(self.buf) < 10:
                    continue
                self.buf = self.buf[10:]
                got_preamble = True
            while len(self.buf) >= 14:
                seq, sim_ts, payload_len, count = struct.unpack("<IIIH", self.buf[:14])
                if payload_len > (32 << 20):
                    self.buf = b""
                    break
                if len(self.buf) < 14 + payload_len:
                    break
                payload = self.buf[14:14 + payload_len]
                self.buf = self.buf[14 + payload_len:]
                p = 0
                while p + 4 <= len(payload):
                    etype, flags, elen = struct.unpack("<BBH", payload[p:p + 4])
                    body = payload[p + 4:p + 4 + elen]
                    p += 4 + elen
                    if etype in (EVENT_SPAWN, EVENT_SNAPSHOT_OBJECT) and len(body) >= 16:
                        net_id, pid, tile, elev = struct.unpack("<iiii", body[:16])
                        objects[net_id] = (pid & 0xFFFFFFFF, tile, elev)

    def send(self, line, wait=1.0):
        print("[%s] -> %s" % (stamp(), line))
        self.s.sendall((line + "\n").encode())
        time.sleep(wait)

    def close(self):
        self.stop = True
        try:
            self.s.close()
        except Exception:
            pass


def admin(line, wait=1.0):
    s = socket.create_connection(("127.0.0.1", CMD), timeout=5)
    s.sendall((line + "\n").encode())
    time.sleep(wait)
    s.settimeout(1.0)
    out = b""
    try:
        while True:
            chunk = s.recv(4096)
            if not chunk:
                break
            out += chunk
    except Exception:
        pass
    s.close()
    text = out.decode("utf-8", "replace").strip()
    print("[%s] admin %s => %s" % (stamp(), line, text.replace("\n", " | ")))
    return text


gWire = None


def find_object(pid, tile, elev=None):
    for net_id, (p, t, e) in objects.items():
        if p == pid and t == tile and (elev is None or e == elev):
            return net_id
    # Fallback that does not depend on the frame parser: SPAWN / SNAPSHOT_OBJECT payloads
    # are netId, pid, tile, elev as little-endian int32, so the pid+tile pair pins the
    # record and the int32 before it is the netId.
    if gWire is not None:
        needle = struct.pack("<ii", pid, tile)
        at = gWire.raw.find(needle)
        while at != -1:
            if at >= 4:
                (net_id,) = struct.unpack("<i", gWire.raw[at - 4:at])
                (e,) = struct.unpack("<i", gWire.raw[at + 8:at + 12]) if at + 12 <= len(gWire.raw) else (None,)
                if net_id > 0 and (elev is None or e == elev):
                    return net_id
            at = gWire.raw.find(needle, at + 1)
    return None


def wait_for(substr, timeout, start_index=0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for i in range(start_index, len(lines)):
            if substr in lines[i][1]:
                return i
        time.sleep(0.1)
    return -1


def dump(keys, since=0.0):
    for t, line in lines:
        if t >= since and any(k in line for k in keys):
            print("  %6.2f  %s" % (t, line.encode("ascii", "replace").decode()))


def prepare_slot9(tile=17299, elevation=2):
    dst = GAMEDIR + "/data/SAVEGAME/SLOT09"
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(SRC_SLOT, dst)
    print("SLOT09 <- copy of TEST-world SLOT16 (Navarro quicksave)")
    # Move the player onto the floor under test. SAVE.DAT object records are big-endian
    # int32s: tile +4, fid +32, elevation +40, pid +44 (the dude is pid 0x01000000, the
    # only critter record in the file whose fid is a critter fid).
    path = dst + "/SAVE.DAT"
    data = bytearray(open(path, "rb").read())
    needle = struct.pack(">I", 0x01000000)
    at = data.find(needle, 0x7563)
    while at != -1:
        start = at - 44
        if start >= 0:
            (old_tile,) = struct.unpack(">i", data[start + 4:start + 8])
            (fid,) = struct.unpack(">I", data[start + 32:start + 36])
            (old_elev,) = struct.unpack(">i", data[start + 40:start + 44])
            if 0 <= old_tile < 40000 and 0 <= old_elev < 3 and (fid >> 24) == 1:
                data[start + 4:start + 8] = struct.pack(">i", tile)
                data[start + 40:start + 44] = struct.pack(">i", elevation)
                open(path, "wb").write(data)
                print("dude moved %d/e%d -> %d/e%d in SLOT09/SAVE.DAT" % (old_tile, old_elev, tile, elevation))
                return
        at = data.find(needle, at + 1)
    print("WARNING: dude record not found in SAVE.DAT; player stays where the save put him")


def finish(srv, wire):
    if wire is not None:
        wire.close()
    try:
        admin("quit", 0.5)
    except Exception:
        pass
    try:
        srv.wait(8)
    except Exception:
        srv.kill()
    with open(os.path.join(GAMEDIR, "sandbox-last.log"), "w", encoding="utf-8") as f:
        for t, line in lines:
            f.write("%7.2f  %s\n" % (t, line))
    print("full server log: %s (%d lines)" % (os.path.join(GAMEDIR, "sandbox-last.log"), len(lines)))


def connect():
    global gWire
    gWire = Wire()
    return gWire


def need(net_id, what):
    if net_id is None:
        print("could not find %s in the stream (%d bytes seen); aborting" % (what, len(gWire.raw) if gWire else 0))
        raise SystemExit(2)
    return net_id


if mode == "elev":
    prepare_slot9()
    srv = start_server({"F2_SERVER_LOAD": "9"})
    wire = connect()
    wire.send("claim", 6)
    print("objects seen: %d" % len(objects))
    # Elevator 19's control car (pid 0x02000026 'Elevator') on elevation 2, tile 13696 —
    # the one the live log shows being approached with three offers per walk.
    car = need(find_object(0x02000026, 13696, 2), "elevator car 13696/e2")
    print("elevator car netId at 13696/e2: %s" % car)
    n0 = len(lines)
    wire.send("use %d" % car, 45)
    offers = [l for t, l in lines[n0:] if "offered to slot" in l]
    print("OFFERS during the approach walk: %d" % len(offers))
    dump(["offered", "interact", "elev", "no path"], 0)
    wire.send("elev 1", 4)
    dump(["control elev"], 0)
    # Release path: approach the floor-1 car (14098/e1), cancel, approach again.
    car1 = need(find_object(0x02000026, 14098, 1), "elevator car 14098/e1")
    print("floor-1 car netId: %s" % car1)
    n1 = len(lines)
    wire.send("use %d" % car1, 30)
    offers1 = [l for t, l in lines[n1:] if "offered to slot" in l]
    print("OFFERS on the second walk (fresh offer expected: 1): %d" % len(offers1))
    wire.send("elevcancel", 2)
    n2 = len(lines)
    wire.send("mv 14498 1", 6)
    wire.send("use %d" % car1, 30)
    offers2 = [l for t, l in lines[n2:] if "offered to slot" in l]
    print("OFFERS after elevcancel + re-entry (expected 1): %d" % len(offers2))
    dump(["offered", "elevcancel", "control elev", "control mv", "interact FIRE", "no path"], 0)
    finish(srv, wire)

elif mode == "door":
    prepare_slot9()
    srv = start_server({"F2_SERVER_LOAD": "9"})
    wire = connect()
    wire.send("claim", 6)
    print("--- load-time normalization lines:")
    dump(["normalized", "door sprite"], 0)
    # A vdoorf door (pid 0x02000012) on elevation 2 at tile 17500, one row from the player.
    door = need(find_object(0x02000012, 17500, 2), "door 17500/e2")
    print("door netId at 17500/e2: %s" % door)
    n0 = len(lines)
    wire.send("use %d" % door, 10)
    wire.send("use %d" % door, 10)
    wire.send("use %d" % door, 10)
    wire.send("use %d" % door, 10)
    print("--- open/close cycles (expect frame=7 offsets=0,-61 then frame=0 offsets=0,0, twice):")
    dump(["[world] door", "interact FIRE", "no path"], lines[n0][0] if n0 < len(lines) else 0)
    finish(srv, wire)

elif mode == "bos":
    srv = start_server({"F2_SERVER_MAP": "SFCHINA.MAP"})
    wire = connect()
    wire.send("claim", 6)
    print("objects seen: %d" % len(objects))
    door = need(find_object(0x02000099, 24760, 0), "Brotherhood door 24760")
    print("Brotherhood door netId at 24760: %s" % door)
    cur = admin("gvar 361", 1.5)
    try:
        value = int(cur.split("=")[-1])
    except ValueError:
        value = 0
    admin("gvar 361 %d" % (value | 0x800000), 1.5)
    admin("gvar 361", 1.0)
    n0 = len(lines)
    wire.send("use %d" % door, 1)
    i_open = wait_for("netId=%d tile=24760 elev=0 -> OPEN" % door, 60, n0)
    print("OPEN at %s" % (("%.2f" % lines[i_open][0]) if i_open >= 0 else "never"))
    # Walk toward the building the moment it opens (the way a player would).
    wire.send("mv 24560 1", 1)
    i_close = wait_for("-> CLOSED", 30, i_open if i_open >= 0 else n0)
    print("CLOSED at %s" % (("%.2f" % lines[i_close][0]) if i_close >= 0 else "never"))
    if i_open >= 0 and i_close >= 0:
        print("open -> auto-close: %.2f s" % (lines[i_close][0] - lines[i_open][0]))
    time.sleep(2)
    wire.send("mv 24360 1", 8)
    wire.send("use %d" % door, 8)
    print("--- trace:")
    dump(["[world] door", "interact", "control mv", "no path", "refuse", "busy", "gvar", "elev", "dialog", "timer"], lines[n0][0] if n0 < len(lines) else 0)
    finish(srv, wire)
else:
    print("unknown mode")
