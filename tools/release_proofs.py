"""Every sandbox proof, one after another, against one pair of binaries: the release check.

The golden gate pins determinism; these pin behaviour, each on the build that is about to
be released. They are run together because the one time they were not all run the way a
player plays, a release went out that nobody could host (bugs/058): `firstjoin` is first
for that reason, and it is the only proof in which nothing but the real client, started as
join.cmd starts it, ever connects to the server.

  wire     tools/issue_wire_proof.py, every mode (wire bots, no game window)
  screen   tools/client_screen_proof.py, every mode (the real client, no window)
  maps     tools/map_state_proof.py (visited maps survive a client start and a restart)

Each proof is its own process, so one that fails or hangs (20 minutes) does not stop the
rest. Their full output goes to <out dir>/<name>.out; this prints one line per proof.

--again N runs a proof that failed up to N more times and passes it if a later run
passes, saying which run that was. It is for a machine that is busy with something else:
a few proofs time key presses to a fraction of a second, and a stall of the whole machine
fails them on any build. A defect fails every run; read the .out of any proof that needed
a second one (each run's output is kept, as <name>.out, <name>.2.out, ...).

Seven of the screen proofs check the real client's whole copy of the world against the
server's, with the server's own audit: `syncwalk`, `doorsync` and `corpsesync` with the
client in the host's seat, the same three with a 2 on the end with it in the seat of a
player who joins, and `oldsave`, which loads a save made by each released server it finds
in the game folder (f2_server-v141.exe, -v140, -v132, -v131: keep copies there).

Nothing here touches a live world: point it at a sandbox copy. Needs Pillow.

usage: python -u release_proofs.py <f2_server.exe> <fallout2-ce.exe> <game dir> <net port>
                                   <cmd port> [--out <dir>] [--only name,name,...] [--again N]
"""
import os, re, subprocess, sys, time

args = [a for a in sys.argv[1:] if not a.startswith("--")]
out_dir = None
only = None
if "--out" in sys.argv:
    out_dir = sys.argv[sys.argv.index("--out") + 1]
    args.remove(out_dir)
if "--only" in sys.argv:
    value = sys.argv[sys.argv.index("--only") + 1]
    args.remove(value)
    only = value.split(",")
again = 0
if "--again" in sys.argv:
    value = sys.argv[sys.argv.index("--again") + 1]
    args.remove(value)
    again = int(value)
server_exe, client_exe, gamedir, port, cmdport = args[0], args[1], args[2], args[3], args[4]

HERE = os.path.dirname(os.path.abspath(__file__))
SCREEN = ["firstjoin", "heldturn", "hp", "chat", "sheet", "invhp", "clock", "hands", "fidget", "cancelui",
          "createui", "npcloot", "corpseloot", "lvlup", "dialogdots", "stealgear", "musicline", "lookclick", "earlyspace", "reloads", "tradescroll",
          "hpcount", "armorview", "nightmap", "tradeunload", "acturn",
          "syncwalk", "syncwalk2", "doorsync", "doorsync2", "corpsesync", "corpsesync2", "oldsave",
          "nightmap2", "hpcount2"]
WIRE = ["timer", "templexp", "rest", "cancel", "create", "reach", "retry", "lvlsfx", "ownline",
        "joinfreeze", "entryring", "sneakrun", "hostplace", "companions", "dogs", "rocks", "orders",
        "armoroff", "bess", "bunload", "gestures", "pronekill"]

runs = []
for mode in SCREEN:
    runs.append((mode, [os.path.join(HERE, "client_screen_proof.py"), mode, server_exe, client_exe,
                        gamedir, port, cmdport]))
for mode in WIRE:
    runs.append((mode, [os.path.join(HERE, "issue_wire_proof.py"), mode, server_exe, gamedir, port, cmdport]))
runs.append(("maps", [os.path.join(HERE, "map_state_proof.py"), server_exe, client_exe, gamedir, port, cmdport]))
if only is not None:
    unknown = [name for name in only if name not in [n for n, _ in runs]]
    if unknown:
        raise SystemExit("unknown proof: %s" % ", ".join(unknown))
    runs = [(name, cmd) for name, cmd in runs if name in only]

if out_dir is None:
    out_dir = os.path.join(gamedir, "release-proofs")
os.makedirs(out_dir, exist_ok=True)

failed = []
reruns = []
started = time.time()
for name, cmd in runs:
    t0 = time.time()
    for run in range(1, again + 2):
        path = os.path.join(out_dir, name + (".out" if run == 1 else ".%d.out" % run))
        with open(path, "w") as out:
            try:
                rc = subprocess.call([sys.executable, "-B", "-u"] + cmd, stdout=out, stderr=subprocess.STDOUT,
                                     timeout=1200)
            except subprocess.TimeoutExpired:
                rc = -1
                out.write("\nTIMED OUT after 20 minutes\n")
        text = open(path, encoding="utf-8", errors="replace").read()
        tally = re.findall(r"^(\d+)/(\d+) checks passed", text, re.M)
        passed, total = (int(tally[-1][0]), int(tally[-1][1])) if tally else (0, 0)
        ok = rc == 0 and total > 0 and passed == total
        time.sleep(3.0)  # let the ports and the client's single-instance lock go
        if ok:
            break
    if not ok:
        failed.append(name)
    elif run > 1:
        reruns.append("%s (run %d)" % (name, run))
    print("%s %-11s %2d/%-2d  %4.0f s%s" % ("PASS" if ok else "FAIL", name, passed, total, time.time() - t0,
                                           ("   on run %d" % run if run > 1 else "") if ok else "   (see %s)" % path))
    sys.stdout.flush()

print("")
print("%d of %d proofs passed in %.0f minutes%s" % (len(runs) - len(failed), len(runs),
                                                   (time.time() - started) / 60.0,
                                                   "" if not failed else "; FAILED: " + ", ".join(failed)))
if reruns:
    print("passed only on a later run: " + ", ".join(reruns))
sys.exit(1 if failed else 0)
