"""Headless proof that a world keeps the maps it has visited (bugs/032).

The state of every map the party has left lives in a file, <patches>\\MAPS\\<MAP>.SAV. Every
Fallout 2 program erases those files when it starts, and the host's game client is started
in the world folder. This walks the path that lost them and checks the world on the far side:

  visit     a new world at Arroyo village: both spore plants in Hakunin's garden are killed
            (the quest award is paid), then the party walks to the bridge. The village is now
            a file on disk.
  join      the REAL client exe is started in the server's folder the way join.cmd starts it
            (no window: SDL dummy drivers), left running a few seconds, and closed.
  return    back to the village: the server must load it as VISITED, the plants must still be
            corpses, and the first-visit script (vault suit movie, temple award) must not run
            a second time.
  save      the world is saved; the slot must hold the state of BOTH maps.
  restart   the server is stopped and started again on that slot, the client joins again, and
            the party walks back into the village once more: still visited, plants still dead.
  quit      the client joins one last time and the player quits the way a player does (Esc,
            then Y), which runs the game's own shutdown: the working files must come through
            byte for byte.
  forget    the party stands on a random encounter map, saves, and leaves. The game does not
            persist those maps and erases that file itself; it must STAY erased, the server
            must not mistake its own clean-up for somebody else's.

Two programs are under test and either can be an old one, so the expectations are stated:

  --client-erases   the client under test is older than the fix and DOES erase the files on
                    start. With a fixed server they must be put back; the erase itself is
                    then expected and only reported.
  --expect-loss     the SERVER under test is older than the fix. Used to show the defect:
                    every check on the far side is expected to fail, and the run passes if it
                    does (the bug is reproduced).

Truth comes from the folder listing, the server's own lines (F2_TRACE_WORLD) and the baseline
each fresh connection is sent. Nothing here reads or writes a live world: point it at a
sandbox copy. It empties that folder's save slots and working maps before it starts.

usage: python -u map_state_proof.py <f2_server.exe> <fallout2-ce.exe> <game dir> <net port>
                                    <cmd port> [--client-erases] [--expect-loss]
"""
import glob, hashlib, os, re, shutil, socket, struct, subprocess, sys, threading, time

args = [a for a in sys.argv[1:] if not a.startswith("--")]
flags = [a for a in sys.argv[1:] if a.startswith("--")]
server_exe, client_exe, gamedir, port, cmdport = args[0], args[1], args[2], int(args[3]), int(args[4])
client_erases = "--client-erases" in flags
expect_loss = "--expect-loss" in flags

NL = chr(10)
PID_SPORE_PLANT = 0x01000010
MAP_DESERT = 1  # desert2, a random encounter map: maps.txt says saved=No. (0 is desert1,
                # but map 0 in a transition means "open the world map".)
MAP_VILLAGE = 4
MAP_BRIDGE = 5
GVAR_KILL_EVIL_PLANTS = 9
EVENT_SNAPSHOT_OBJECT = 8
EVENT_SNAPSHOT_BEGIN = 9
SAVE_SLOT = 16
logpath = os.path.join(gamedir, "map-state-proof-server.log")
mapsdir = os.path.join(gamedir, "data", "MAPS")
slotdir = os.path.join(gamedir, "data", "SAVEGAME", "SLOT%02d" % SAVE_SLOT)
results = []
srv = None
log = None


def check(name, ok, detail=""):
    """With --expect-loss the far side of the defect is expected to fail."""
    results.append((name, ok, detail))
    print(("PASS " if ok else "FAIL ") + name + ("  [" + detail + "]" if detail else ""))


def kept(name, ok, detail=""):
    """A check about the world being intact: inverted when the defect is being shown."""
    if expect_loss:
        check("(defect shown) NOT: " + name, not ok, detail)
    else:
        check(name, ok, detail)


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
        self.s.sendall((line + NL).encode())
        time.sleep(wait)

    def events(self):
        """Every (type, body) so far. Frame: 18-byte header (u32 seq, u32 sim, u32 payload
        length, u16 count, u32 entry base). Event: u8 type, u8 flags, u16 length."""
        data = bytes(self.buf)
        out = []
        if data[:4] != b"F2NS":
            return out
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
                out.append((etype, payload[ep + 4:ep + 4 + elen]))
                ep += 4 + elen
        return out

    def last_snapshot(self):
        """(map index, [objects]) of the newest baseline in the stream."""
        current = None
        newest = None
        for etype, body in self.events():
            if etype == EVENT_SNAPSHOT_BEGIN and len(body) >= 8:
                current = (struct.unpack_from("<i", body, 0)[0], [])
                newest = current
            elif etype == EVENT_SNAPSHOT_OBJECT and current is not None and len(body) >= 24:
                net, pid, tile, elev, fid, flags_ = struct.unpack_from("<iiiiiI", body, 0)
                current[1].append({"net": net, "pid": pid, "tile": tile, "fid": fid})
        return newest

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


def boot(extra, mode):
    global srv, log
    env = dict(os.environ)
    for name in list(env):
        if name.startswith("F2_"):
            env.pop(name)
    env.update({"F2_SERVER_NET": str(port), "F2_SERVER_CMD": str(cmdport), "F2_SERVER_PACE_MS": "100",
                "F2_AUTOSAVE_SECS": "0", "F2_SERVER_KEEPALIVE": "1",
                "F2_TRACE_EVENTS": "1", "F2_TRACE_WORLD": "1"})
    env.update(extra)
    log = open(logpath, mode)
    log.write("===== boot %s =====%s" % (extra, NL))
    log.flush()
    srv = subprocess.Popen([server_exe], cwd=gamedir, env=env, stdout=log, stderr=subprocess.STDOUT)
    time.sleep(7)


def stop():
    global srv
    try:
        admin("quit", 1)
    except Exception:
        pass
    time.sleep(1.5)
    if srv is not None and srv.poll() is None:
        srv.kill()
    srv = None
    log.close()
    time.sleep(1.0)


def state_files():
    return sorted(os.path.basename(p).upper() for p in glob.glob(os.path.join(mapsdir, "*.SAV")))


def slot_files():
    """The map state files in the save slot (the automap and sfall's variables sit beside them)."""
    return sorted(os.path.basename(p).upper() for p in glob.glob(os.path.join(slotdir, "*.SAV"))
                  if os.path.basename(p).upper() not in ("AUTOMAP.SAV", "SFALLGV.SAV"))


def dude_tile():
    rows = re.findall(r"\[actors\] srv slot=0 obj=\S+ netId=(-?\d+) pid=\S+ tile=(-?\d+)", logtext())
    return int(rows[-1][1]) if rows else None


def owed_baseline():
    """A connect is owed a baseline, which also prints a fresh [actors] line."""
    probe = Client("probe")
    time.sleep(2.5)
    probe.close()
    time.sleep(1.0)


def look():
    """What a player joining right now would be shown: (map, plants standing, plants dead)."""
    fresh = Client("look")
    deadline = time.time() + 20
    snap = None
    while time.time() < deadline:
        snap = fresh.last_snapshot()
        if snap is not None and len(snap[1]) > 0:
            time.sleep(1.5)
            snap = fresh.last_snapshot()
            break
        time.sleep(0.3)
    fresh.close()
    time.sleep(1.0)
    if snap is None:
        return None, 0, 0
    plants = [r for r in snap[1] if r["pid"] == PID_SPORE_PLANT]
    # a corpse carries one of the single-frame death animations (48 and up) in its fid
    standing = sum(1 for r in plants if ((r["fid"] >> 16) & 0xFF) < 48)
    return snap[0], standing, len(plants) - standing


def travel(map_index):
    time.sleep(2.0)
    admin("entermap %d" % map_index, 4.0)
    # a map loaded as NEW may play its first-visit movie and wait for a viewer to end it
    for _ in range(2):
        admin("movdone", 1.0)
    time.sleep(2.0)


def join_with_the_game(seconds=10):
    """Start the real client in the server's folder, as join.cmd does, with no window."""
    env = dict(os.environ)
    for name in list(env):
        if name.startswith("F2_"):
            env.pop(name)
    env.update({"F2_CLIENT_CONNECT": "127.0.0.1:%d" % port, "F2_PLAYER_NAME": "Brother",
                "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"})
    game = subprocess.Popen([client_exe], cwd=gamedir, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(seconds)
    alive = game.poll() is None
    listing = state_files()
    game.kill()
    try:
        game.wait(timeout=10)
    except Exception:
        pass
    time.sleep(2.0)
    return alive, listing


def fingerprints():
    found = {}
    for path in glob.glob(os.path.join(mapsdir, "*.SAV")):
        with open(path, "rb") as stream:
            found[os.path.basename(path).upper()] = hashlib.sha1(stream.read()).hexdigest()[:12]
    return found


def join_and_quit_properly():
    """The client joins and its keyboard (a recording) presses Esc, then Y to confirm, so
    the game shuts itself down instead of being killed."""
    trace = os.path.join(gamedir, "map-state-proof-keys.txt")
    with open(trace, "w") as stream:
        stream.write("# Esc, then Y" + NL)
        for at, key in ((480, 41), (570, 28)):  # SDL scancodes
            stream.write("K %d %d 1%s" % (at, key, NL))
            stream.write("K %d %d 0%s" % (at + 3, key, NL))
    env = dict(os.environ)
    for name in list(env):
        if name.startswith("F2_"):
            env.pop(name)
    env.update({"F2_CLIENT_CONNECT": "127.0.0.1:%d" % port, "F2_PLAYER_NAME": "Brother",
                "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy", "F2_INPUT_REPLAY": trace})
    game = subprocess.Popen([client_exe], cwd=gamedir, env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    in_the_world = fingerprints()
    deadline = time.time() + 45
    while time.time() < deadline and game.poll() is None:
        time.sleep(0.5)
    code = game.poll()
    if code is None:
        game.kill()
        try:
            game.wait(timeout=10)
        except Exception:
            pass
    time.sleep(2.0)
    os.remove(trace)
    return code, in_the_world, fingerprints()


def lines_since(mark, needle):
    return [line for line in logtext()[mark:].splitlines() if needle in line]


# a clean sandbox every run
for path in glob.glob(os.path.join(gamedir, "data", "SAVEGAME", "SLOT*")):
    shutil.rmtree(path, ignore_errors=True)
for path in glob.glob(os.path.join(mapsdir, "*.SAV")):
    os.remove(path)

try:
    # ---- visit -------------------------------------------------------------------------
    boot({"F2_SERVER_MAP": "arvillag.map"}, "w")
    a = Client("A")
    time.sleep(2.5)
    a.send("login Tester", 3.0)
    snap = a.last_snapshot()
    targets = [r["tile"] for r in snap[1] if r["pid"] == PID_SPORE_PLANT] if snap else []
    check("the village has its two spore plants", len(targets) == 2, str(targets))
    for tile in targets:
        admin("warp %d" % (tile + 1 - dude_tile()), 1.0)
        admin("cdamage 500", 2.0)
        for _ in range(4):
            a.send("cendturn", 0.8)
        owed_baseline()
    quest = admin("gvar %d" % GVAR_KILL_EVIL_PLANTS, 0.2)
    where, standing, dead = look()
    check("both plants are dead and the quest is paid", where == MAP_VILLAGE and standing == 0 and dead == 2
          and not quest.endswith("= 0"), "map=%s standing=%d dead=%d %s" % (where, standing, dead, quest))

    travel(MAP_BRIDGE)
    where, _, _ = look()
    before = state_files()
    check("on the bridge, the village is a file on disk", where == MAP_BRIDGE and "ARVILLAG.SAV" in before,
          "map=%s files=%s" % (where, before))

    # ---- join --------------------------------------------------------------------------
    mark = len(logtext())
    alive, during = join_with_the_game()
    check("the game client started and joined", alive and len(lines_since(mark, "control claimed by session")) > 0)
    erased = sorted(set(before) - set(during))
    print("files on disk while the client ran: %s (erased: %s)" % (during, erased))
    if client_erases:
        check("(old client) it erased the world's map files on start, as v1.3.1 does", len(erased) > 0, str(erased))
    else:
        check("starting the client erased nothing", len(erased) == 0, str(erased))

    # ---- return ------------------------------------------------------------------------
    mark = len(logtext())
    travel(MAP_VILLAGE)
    where, standing, dead = look()
    kept("the village is loaded as VISITED", len(lines_since(mark, "ARVILLAG.MAP: from saved .SAV")) == 1
         and len(lines_since(mark, "ARVILLAG.MAP: fresh .MAP")) == 0,
         str(lines_since(mark, "[world] map load"))[:200])
    kept("the plants are still dead", where == MAP_VILLAGE and standing == 0 and dead == 2,
         "map=%s standing=%d dead=%d" % (where, standing, dead))
    kept("the first-visit award is not paid a second time", len(lines_since(mark, "ArVillag.int")) == 0,
         str(lines_since(mark, "[xp]"))[:200])
    if client_erases and not expect_loss:
        check("the server says what happened and that it put the files back",
              len(lines_since(0, "were ERASED from")) >= 1, str(lines_since(0, "were ERASED from"))[:240])

    # ---- save --------------------------------------------------------------------------
    travel(MAP_BRIDGE)
    # an old client erases on every start: join once more so the save is written after one
    alive, during = join_with_the_game()
    saved = admin("save %d proof" % SAVE_SLOT, 3.0)
    in_slot = slot_files()
    check("the save was written", os.path.exists(os.path.join(slotdir, "SAVE.DAT")), saved[:120])
    kept("the save holds the state of both maps", "ARVILLAG.SAV" in in_slot and "ARBRIDGE.SAV" in in_slot, str(in_slot))

    # ---- restart -----------------------------------------------------------------------
    a.close()
    stop()
    boot({"F2_SERVER_LOAD": str(SAVE_SLOT)}, "a")
    a = Client("A")
    time.sleep(2.5)
    a.send("login Tester", 3.0)
    where, _, _ = look()
    check("the server came back up on the bridge", where == MAP_BRIDGE, "map=%s" % where)
    alive, during = join_with_the_game()
    print("files on disk after the restart, while the client ran: %s" % during)
    mark = len(logtext())
    travel(MAP_VILLAGE)
    where, standing, dead = look()
    kept("after a restart the village is still loaded as VISITED",
         len(lines_since(mark, "ARVILLAG.MAP: from saved .SAV")) == 1
         and len(lines_since(mark, "ARVILLAG.MAP: fresh .MAP")) == 0,
         str(lines_since(mark, "[world] map load"))[:200])
    kept("after a restart the plants are still dead", where == MAP_VILLAGE and standing == 0 and dead == 2,
         "map=%s standing=%d dead=%d" % (where, standing, dead))
    quest = admin("gvar %d" % GVAR_KILL_EVIL_PLANTS, 0.2)
    check("the quest is still paid", not quest.endswith("= 0"), quest)

    # ---- quit --------------------------------------------------------------------------
    travel(MAP_BRIDGE)
    mark = len(logtext())
    code, in_the_world, after = join_and_quit_properly()
    check("the client quit by itself on Esc, Y", code == 0, "exit code %s" % code)
    check("quitting the game changed no working file", in_the_world == after,
          "%s -> %s" % (in_the_world, after))
    travel(MAP_VILLAGE)
    where, standing, dead = look()
    kept("after the client quit the village is still loaded as VISITED",
         len(lines_since(mark, "ARVILLAG.MAP: from saved .SAV")) == 1
         and len(lines_since(mark, "ARVILLAG.MAP: fresh .MAP")) == 0,
         str(lines_since(mark, "[world] map load"))[:200])
    kept("after the client quit the plants are still dead", where == MAP_VILLAGE and standing == 0 and dead == 2,
         "map=%s standing=%d dead=%d" % (where, standing, dead))

    # ---- forget ------------------------------------------------------------------------
    travel(MAP_DESERT)
    where, _, _ = look()
    admin("save %d proof" % SAVE_SLOT, 3.0)
    on_the_map = state_files()
    check("a save on a random encounter map writes its working file",
          where == MAP_DESERT and "DESERT2.SAV" in on_the_map, "map=%s files=%s" % (where, on_the_map))
    mark = len(logtext())
    travel(MAP_BRIDGE)
    travel(MAP_VILLAGE)
    left_behind = state_files()
    check("leaving it erases that file and nothing puts it back", "DESERT2.SAV" not in left_behind
          and len(lines_since(mark, "were ERASED from")) == 0,
          "files=%s %s" % (left_behind, str(lines_since(mark, "were ERASED from"))[:120]))
    where, standing, dead = look()
    kept("and the village is as the party left it", where == MAP_VILLAGE and standing == 0 and dead == 2,
         "map=%s standing=%d dead=%d" % (where, standing, dead))
    a.close()
finally:
    if srv is not None:
        stop()

failed = [name for name, ok, _detail in results if not ok]
print("")
print("%d/%d checks passed%s" % (len(results) - len(failed), len(results),
                                  " (the defect was reproduced as expected)" if expect_loss and not failed else ""))
for name in failed:
    print("   FAILED: " + name)
sys.exit(1 if failed else 0)
