"""Self-test of the solo test kit, with nobody at the keyboard.

Runs the kit exactly as its launchers do (same server settings, same stand-in, same
one-word tool), and puts a fake wire client in the HOST's seat where the human would
sit with the real game. It then walks the test a person is asked to do and checks what
each screen was sent:

  quest     the rat god is dropped beside the host, attacks on sight, and is killed:
            his script's give_xp award, then the fight's kills
  skill     First Aid by the host
  raiders   two raiders dropped beside the host, attacked and killed
  reward    an operator award paid the way play pays one

usage: python dry_run.py <kit folder> <host name> <friend name>
"""
import os, re, shutil, socket, struct, subprocess, sys, threading, time

kit, HOST, FRIEND = sys.argv[1], sys.argv[2], sys.argv[3]
NET, ADMIN = 9800, 9801
NL = chr(10)
FIRST_AID = 6
KEENG_RAT = 0x0100012D
RAIDER = 0x010000EE
logpath = os.path.join(kit, "server-console.log")
standin_out = os.path.join(kit, "stand-in-output.txt")
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + ("  [" + detail + "]" if detail else ""))


def admin(line, wait=0.6):
    s = socket.create_connection(("127.0.0.1", ADMIN), timeout=5)
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
    return out.decode(errors="replace")


def tool(*words):
    out = subprocess.run([sys.executable, os.path.join(kit, "tools", "test_tool.py")] + list(words) + ["--admin", str(ADMIN)],
                         capture_output=True, text=True).stdout
    print("tool %s ->" % " ".join(words))
    for line in out.strip().splitlines():
        print("    " + line)
    return out


def logtext():
    try:
        return open(logpath, encoding="latin1").read()
    except OSError:
        return ""


def payouts(since):
    found = []
    for m in re.finditer(r"^\[xp\] (.+?) (-?\d+) by (.+?) ->(.*)$", logtext()[since:], re.M):
        shares = re.findall(r" (.+?) \+(-?\d+) \(xp \d+, level \d+\)", m.group(4))
        found.append({"what": m.group(1), "amount": int(m.group(2)), "earner": m.group(3),
                      "paid": [(n, int(g)) for n, g in shares], "raw": m.group(0)})
    return found


def once_each(line):
    return sorted(n for n, _g in line["paid"]) == sorted([HOST, FRIEND]) and len({g for _n, g in line["paid"]}) == 1


def sheet():
    rows = {}
    for s, name, level, xp in re.findall(r"sheet (\d+) \((.*?)\): level (\d+), xp (\d+)", admin("sheet", 0.1)):
        rows[name] = (int(level), int(xp))
    return rows


def wait_for(cond, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if cond():
            return True
        time.sleep(0.3)
    return cond()


class Player:
    """A fake game client in one seat: logs in by name and keeps what its screen is sent."""

    def __init__(self, name):
        self.name = name
        self.session = None
        self.net = 0
        self.lines = []      # (text, addressee)
        self.spawns = []     # (netId, pid)
        self.turns = 0       # my own turn starts
        self.enters = 0
        self.exits = 0
        self.buf = bytearray()
        self.s = socket.create_connection(("127.0.0.1", NET), timeout=60)
        self.s.settimeout(None)
        self.s.sendall(("login %s" % name + NL).encode())
        threading.Thread(target=self.read, daemon=True).start()

    def send(self, line, wait=0.0):
        print("%s -> %s" % (self.name, line))
        self.s.sendall((line + NL).encode())
        time.sleep(wait)

    def read(self):
        try:
            while True:
                data = self.s.recv(262144)
                if not data:
                    return
                self.buf += data
                if self.session is None:
                    if len(self.buf) < 10:
                        continue
                    self.session = struct.unpack_from("<i", self.buf, 6)[0]
                    del self.buf[:10]
                while len(self.buf) >= 18:
                    length = struct.unpack_from("<I", self.buf, 8)[0]
                    if len(self.buf) < 18 + length:
                        break
                    payload = bytes(self.buf[18:18 + length])
                    del self.buf[:18 + length]
                    ep = 0
                    while ep + 4 <= len(payload):
                        etype, _f, elen = struct.unpack_from("<BBH", payload, ep)
                        self.event(etype, payload[ep + 4:ep + 4 + elen])
                        ep += 4 + elen
        except OSError:
            return

    def event(self, etype, body):
        if etype == 38 and len(body) >= 2:  # roster
            pos = 2
            for _ in range(struct.unpack_from("<H", body, 0)[0]):
                if pos + 15 > len(body):
                    break
                _slot, net, sess, _alive, namelen = struct.unpack_from("<iiiBH", body, pos)
                pos += 15 + namelen
                if sess == self.session:
                    self.net = net
        elif etype == 16 and len(body) >= 2:  # console
            n = struct.unpack_from("<H", body, 0)[0]
            tail = body[2 + n:]
            self.lines.append((body[2:2 + n].decode("latin1"),
                               struct.unpack_from("<i", tail, 0)[0] if len(tail) >= 4 else 0))
        elif etype == 1 and len(body) >= 8:  # spawn
            net, pid = struct.unpack_from("<ii", body, 0)
            self.spawns.append((net, pid))
        elif etype == 14 and len(body) >= 5:  # turn start
            net, is_player = struct.unpack_from("<iB", body, 0)
            if is_player and net == self.net:
                self.turns += 1
        elif etype == 12:
            self.enters += 1
        elif etype == 13:
            self.exits += 1

    def mine(self, phrase, since=0):
        return [t for t, a in self.lines[since:] if a == self.net and phrase in t]

    def everyone(self, phrase, since=0):
        return [t for t, a in self.lines[since:] if a == 0 and phrase in t]

    def close(self):
        try:
            self.s.close()
        except OSError:
            pass


def fight(player, since, seen, targets=None, turns=30):
    """Take the host's turns until the fight's purse is paid: two attacks, end turn.
    With no targets the attack is the bare one (nearest hostile), which is right for
    something that attacked first. Critters that were standing about are named one at
    a time, moving on when the narration says the last one died.

    `seen` is the host's turn count from BEFORE the fight was provoked. Sampling it
    here instead loses the first turn whenever it began while the caller was still
    waiting for the fight to start, and the host then sits out the idle timeout."""
    mark = len(player.lines)
    for _ in range(turns * 12):
        if any(line["what"] == "kills" for line in payouts(since)):
            return True
        if player.turns > seen:
            seen = player.turns
            attack = "cattack"
            if targets:
                dead = len([t for t, a in player.lines[mark:] if a == player.net and "killed" in t])
                if dead >= len(targets):
                    # A fight the PLAYER opened among bystanders does not end by itself,
                    # in vanilla either: the bystanders are on another team and stay on
                    # the roster. The player ends it, with the End Combat button.
                    player.send("cendcombat", 2.0)
                    continue
                attack = "cattack %d" % targets[dead]
            player.send(attack, 1.2)
            player.send(attack, 1.2)
            player.send("cendturn", 0.5)
        time.sleep(0.4)
    return any(line["what"] == "kills" for line in payouts(since))


# ---- start the kit the way "1 START TEST.cmd" does ------------------------------------
shutil.rmtree(os.path.join(kit, "data", "SAVEGAME", "SLOT09"), ignore_errors=True)
shutil.copytree(os.path.join(kit, "test-save", "SLOT09"), os.path.join(kit, "data", "SAVEGAME", "SLOT09"))
env = dict(os.environ)
env.update({"F2_SERVER_LOAD": "9", "F2_SERVER_NET": str(NET), "F2_SERVER_CMD": str(ADMIN),
            "F2_SERVER_PACE_MS": "100", "F2_SERVER_HOST": HOST, "F2_SERVER_NAME": "Solo test",
            "F2_AUTOSAVE_SECS": "0", "F2_SERVER_KEEPALIVE": "0"})
env.pop("F2_PARTY_XP", None)
log = open(logpath, "w")
srv = subprocess.Popen([os.path.join(kit, "f2_server.exe")], cwd=kit, env=env, stdout=log, stderr=subprocess.STDOUT)
out = open(standin_out, "w")
standin = subprocess.Popen([sys.executable, "-u", os.path.join(kit, "tools", "stand_in.py"), "--name", FRIEND,
                            "--port", str(NET), "--admin", str(ADMIN), "--log", logpath],
                           cwd=kit, stdout=out, stderr=subprocess.STDOUT)
time.sleep(9)
gus = Player(HOST)
check("the host is seated", wait_for(lambda: gus.net != 0, 20), "netId %s" % gus.net)
check("both seats are taken", wait_for(lambda: len(sheet()) == 2, 10), str(sheet()))
start = sheet()
print("start: %s" % start)
time.sleep(3)

# ---- quest: the rat god, his script's award, then the kills ---------------------------
since, mark, enters, turns = len(logtext()), len(gus.lines), gus.enters, gus.turns
before = sheet()
reply = tool("quest")
check("the rat god was placed beside the host", "standing right next to you" in reply)
check("he attacks on sight: a fight starts by itself", wait_for(lambda: gus.enters > enters, 20))
check("the fight was won", fight(gus, since, turns))
time.sleep(1.5)
lines = payouts(since)
quest = [l for l in lines if l["what"] != "kills"]
purse = [l for l in lines if l["what"] == "kills"]
print("pay-outs: %s" % [l["raw"] for l in lines])
check("the quest script paid one award, once each", len(quest) == 1 and once_each(quest[0]), str([l["raw"] for l in quest])[:200])
check("the kills paid one purse, once each", len(purse) == 1 and once_each(purse[0]), str([l["raw"] for l in purse])[:200])
after = sheet()
total = sum(g for l in lines for n, g in l["paid"] if n == HOST)
check("the host's sheet moved by exactly what was paid", after[HOST][1] - before[HOST][1] == total and total > 0,
      "%d vs %d" % (after[HOST][1] - before[HOST][1], total))
check("the friend's sheet moved by exactly the same", after[FRIEND][1] - before[FRIEND][1] == total,
      "%d vs %d" % (after[FRIEND][1] - before[FRIEND][1], total))
check("the host reads the script's award line once", len(gus.everyone("experience points", mark)) == 1,
      str(gus.everyone("experience points", mark)))
check("the host reads the end-of-fight line once", len(gus.mine("exp. points", mark)) == 1, str(gus.mine("exp. points", mark)))

# ---- skill: First Aid by the host, skill raised so the roll lands ----------------------
admin("sp 0 99", 0.1)
for _ in range(70):
    admin("skillup 0 %d" % FIRST_AID, 0.0)
admin("hurt 20")
since, mark = len(logtext()), len(gus.lines)
before = sheet()
for attempt in range(3):
    gus.send("skill %d %d" % (gus.net, FIRST_AID), 1)
    if wait_for(lambda: payouts(since), 10):
        break
time.sleep(1)
lines = payouts(since)
after = sheet()
check("First Aid paid one award, once each", len(lines) == 1 and once_each(lines[0]), str([l["raw"] for l in lines])[:200])
check("both sheets moved by that award", lines and after[HOST][1] - before[HOST][1] == lines[0]["paid"][0][1]
      and after[FRIEND][1] - before[FRIEND][1] == lines[0]["paid"][0][1], "%s -> %s" % (before, after))
check("the host reads the vanilla skill line once", len(gus.mine("honing", mark)) == 1, str(gus.mine("honing", mark)))

# ---- raiders: passive until the host attacks one ---------------------------------------
since, mark, spawned, enters, turns = len(logtext()), len(gus.lines), len(gus.spawns), gus.enters, gus.turns
before = sheet()
reply = tool("raiders")
wait_for(lambda: len([s for s in gus.spawns[spawned:] if s[1] == RAIDER]) >= 1, 8)
raiders = [net for net, pid in gus.spawns[spawned:] if pid == RAIDER]
check("raiders were placed beside the host", len(raiders) >= 1, str(raiders))
time.sleep(4)
check("they do nothing until attacked", gus.enters == enters)
if raiders:
    gus.send("cstart", 2)
    wait_for(lambda: gus.enters > enters, 10)
check("the host can start the fight", gus.enters > enters)
check("the fight was won", fight(gus, since, turns, raiders))
time.sleep(1.5)
lines = payouts(since)
after = sheet()
check("the kills paid one purse, once each", len(lines) == 1 and once_each(lines[0]), str([l["raw"] for l in lines])[:200])
check("both sheets moved by that purse", lines and after[HOST][1] - before[HOST][1] == lines[0]["paid"][0][1]
      and after[FRIEND][1] - before[FRIEND][1] == lines[0]["paid"][0][1], "%s -> %s" % (before, after))
check("the host reads the end-of-fight line once", len(gus.mine("exp. points", mark)) == 1, str(gus.mine("exp. points", mark)))

# ---- reward, sheets, stop ---------------------------------------------------------------
since = len(logtext())
before = sheet()
tool("reward", "500")
after = sheet()
lines = payouts(since)
check("the reward paid 500, once each", len(lines) == 1 and once_each(lines[0]) and lines[0]["amount"] == 500,
      str([l["raw"] for l in lines])[:200])
check("both sheets moved by 500", after[HOST][1] - before[HOST][1] == 500 and after[FRIEND][1] - before[FRIEND][1] == 500)
tool("sheets")
time.sleep(3)
tool("stop")
try:
    rc = srv.wait(15)
except Exception:
    srv.kill()
    rc = "killed"
gus.close()
try:
    standin.wait(10)
except Exception:
    standin.kill()
log.close()
out.close()
check("the server stopped cleanly", rc == 0, "rc=%s" % rc)

text = open(standin_out, encoding="latin1").read()
print()
print("===== what the stand-in window showed =====")
print(text.rstrip())
print("===== end of the stand-in window =====")
check("the stand-in reported being seated", "Seated as %s" % FRIEND in text)
check("the stand-in reported the host joining", "The host joined" in text)
check("the stand-in reported every award", text.count("AWARD") == len(payouts(0)), "%d vs %d" % (text.count("AWARD"), len(payouts(0))))
check("the stand-in found nobody paid twice", "TWICE" not in text and text.count("paid once each to 2 players") == len(payouts(0)))
check("the stand-in showed the friend's own lines", ("%s's screen" % FRIEND) in text)
bad = [l for l in logtext().splitlines() if re.search(r"Assert|abort|SIGSEGV|RELOAD FAILED|FAILED", l)]
check("no crash or failure lines on the server", not bad, "; ".join(bad)[:200])
print("===== %d/%d checks passed =====" % (sum(1 for r in results if r[1]), len(results)))
sys.exit(0 if all(r[1] for r in results) else 1)
