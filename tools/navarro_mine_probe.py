"""Navarro minefield check (bugs/016): walk a sandbox f2_server's player across the
mined ground and report every scripted input lock the server takes and releases.

The failure it looks for is a lock with no matching release: CIMine calls
game_ui_disable and never game_ui_enable, relying on actionExplode's own cleanup,
which used to stop at the server and never reach the viewer.

  python f2dev-minetest.py <f2_server.exe> [tile ...]
"""
import atexit, os, shutil, socket, struct, subprocess, sys, threading, time

GAMEDIR = os.environ.get("F2_SANDBOX_GAME", "D:/Games/F2-Dev")
SRC_SLOT = os.environ.get("F2_MINE_SLOT", "")  # a save directory sitting on NAVARRO
NET, CMD = 9500, 9501

exe = sys.argv[1]
# A path across the mined ground north-west of the Navarro entrance. The two
# already-triggered plates in Gus's save sit at 15499 and 19907, so the field is the
# ground between them; these tiles walk through it.
TILES = [int(a) for a in sys.argv[2:]] or [
    19907, 19507, 19107, 18707, 18307, 17907, 17507, 17107,
    16707, 16307, 15907, 15507, 15499, 15899, 16299, 16699,
]
t0 = time.time()
lines = []


def prepare():
    if not SRC_SLOT:
        sys.exit("set F2_MINE_SLOT to a save directory sitting on NAVARRO")
    dst = GAMEDIR + "/data/SAVEGAME/SLOT09"
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(SRC_SLOT, dst)
    print("SLOT09 <- %s" % SRC_SLOT)


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


def drain():
    while not stop.is_set():
        try:
            if not s.recv(65536):
                return
        except Exception:
            return


threading.Thread(target=drain, daemon=True).start()
s.sendall(b"claim\n")
time.sleep(6)

for tile in TILES:
    s.sendall(("mv %d 1\n" % tile).encode())
    time.sleep(5)
time.sleep(6)

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

locks = [(t, l) for t, l in lines if "input lock" in l]
print("\n=== scripted input lock events ===")
for t, l in locks:
    print("  %6.2f  %s" % (t, l))
taken = sum(1 for _, l in locks if "TAKEN" in l)
released = sum(1 for _, l in locks if "RELEASED" in l)
print("\ntaken=%d released=%d -> %s" % (
    taken, released,
    "NO MINE TRIGGERED (inconclusive)" if taken == 0
    else ("OK, every lock was released" if released >= taken else "LEAK: a lock was never released")))
print("\n=== explosions / mine activity ===")
for t, l in lines:
    if any(k in l for k in ("SPAWN", "presseq", "Trap", "explod")):
        print("  %6.2f  %s" % (t, l[:130]))
with open(GAMEDIR + "/minetest-last.log", "w", encoding="utf-8") as f:
    for t, l in lines:
        f.write("%7.2f  %s\n" % (t, l))
print("\nfull server log: %s/minetest-last.log" % GAMEDIR)
