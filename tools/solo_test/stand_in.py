"""Stand-in for the second player, for testing co-op alone.

One PC runs one game client, so a player with nobody to test with cannot fill the second
seat with a real game. This fills it with a script instead. It logs in as the second
character and stays connected, so that seat counts as playing. It ends that character's
combat turns at once, so a fight moves at the speed of the one human. And it reports, in
plain words, what the second player's screen is being sent and what every experience award
paid to whom.

It never moves, fights, talks or picks anything up. It is a seat, not a bot.

usage: python stand_in.py --name <character> [--host 127.0.0.1] [--port 9800]
                          [--admin 9801] [--log server-console.log] [--all]

  --log   the server's console output, as a file. Every award is read from its "[xp]"
          lines, which is where "paid once each" comes from. Without it the report still
          shows the sheets and the second player's lines.
  --all   print every line sent to the second player, not only the ones about experience.
"""
import argparse, os, re, socket, struct, sys, threading, time

EVENT_MOVE = 2
EVENT_SNAPSHOT_OBJECT = 8
EVENT_COMBAT_ENTER = 12
EVENT_COMBAT_EXIT = 13
EVENT_TURN_START = 14
EVENT_CONSOLE = 16
EVENT_PLAYER_ROSTER = 38
EVENT_PARTY_WIPE = 68

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
parser.add_argument("--host", default="127.0.0.1")
parser.add_argument("--port", type=int, default=9800)
parser.add_argument("--admin", type=int, default=9801)
parser.add_argument("--log", default="")
parser.add_argument("--all", action="store_true")
args = parser.parse_args()

NL = chr(10)
lock = threading.Lock()
XP_WORDS = ("exp. points", "experience", " XP", "gone up a level")


def say(text=""):
    with lock:
        print(text)
        sys.stdout.flush()


def stamp():
    return time.strftime("%H:%M:%S")


def connect(port, seconds):
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            return socket.create_connection((args.host, port), timeout=3)
        except OSError:
            time.sleep(0.5)
    return None


def admin(line):
    try:
        s = socket.create_connection((args.host, args.admin), timeout=3)
    except OSError:
        return ""
    try:
        s.sendall((line + NL).encode())
        time.sleep(0.35)
        s.settimeout(0.5)
        out = b""
        try:
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                out += chunk
        except socket.timeout:
            pass
        return out.decode(errors="replace")
    finally:
        s.close()


# ---- the sheets: both characters' real rows, asked from the server -----------------
def read_sheets():
    rows = {}
    for slot, name, level, xp in re.findall(r"sheet (\d+) \((.*?)\): level (\d+), xp (\d+)", admin("sheet")):
        rows[int(slot)] = (name, int(level), int(xp))
    return rows


def sheets_line(rows, before=None):
    parts = []
    for slot in sorted(rows):
        name, level, xp = rows[slot]
        text = "%s: level %d, %s xp" % (name, level, format(xp, ","))
        if before and slot in before and before[slot][2] != xp:
            text += " (%+d)" % (xp - before[slot][2])
        if before and slot in before and before[slot][1] != level:
            text += " LEVEL UP"
        parts.append(text)
    return "   |   ".join(parts)


def watch_sheets(poll):
    """The sheets at the start, so there is something to compare against. After that
    every award line carries both new totals, so the server is only asked again when
    there is no award log to read: each question is a connection on its console, and a
    question every two seconds buries the server's own log."""
    last = {}
    for _ in range(20):
        last = read_sheets()
        if last:
            break
        time.sleep(1.0)
    if last:
        say("SHEETS   " + sheets_line(last))
    while poll:
        time.sleep(5.0)
        rows = read_sheets()
        if rows and rows != last:
            say("[%s] SHEETS   %s" % (stamp(), sheets_line(rows, last)))
            last = rows


# ---- the awards: the server prints one "[xp]" line for each, with every share on it ----
def watch_awards(path):
    offset = 0
    pending = b""
    while True:
        time.sleep(0.5)
        try:
            size = os.path.getsize(path)
            if size < offset:
                offset = 0  # a new server run started the file over
            if size == offset:
                continue
            with open(path, "rb") as f:
                f.seek(offset)
                data = f.read()
            offset += len(data)
        except OSError:
            continue
        pending += data
        *lines, pending = pending.split(b"\n")
        for raw in lines:
            line = raw.decode("latin1").strip()
            m = re.match(r"^\[xp\] (.+?) (-?\d+) by (.+?) ->(.*)$", line)
            if not m:
                continue
            what, amount, earner, tail = m.group(1), int(m.group(2)), m.group(3), m.group(4)
            shared = "(not shared)" not in tail
            shares = re.findall(r" (.+?) \+(-?\d+) \(xp (\d+), level (\d+)\)", tail)
            names = [name for name, _g, _x, _l in shares]
            say()
            say("[%s] AWARD    %d experience, source: %s, earned by %s" % (stamp(), amount, what, earner))
            for name, gained, xp, level in shares:
                say("           %-14s +%-6s -> %s xp, level %s" % (name, gained, format(int(xp), ","), level))
            if not shared:
                say("           sharing is OFF on this server (F2_PARTY_XP=0): the earner alone is paid")
            elif len(set(names)) != len(names):
                say("           !! SOMEBODY IS ON THIS AWARD TWICE. That is a bug; keep this window's text.")
            elif len(names) == 1:
                say("           paid to the one player who is connected")
            else:
                say("           paid once each to %d players" % len(names))


# ---- the wire: the second player's seat ---------------------------------------------
def main():
    say("=" * 74)
    say(" STAND-IN for %s  (wire %s:%d)" % (args.name, args.host, args.port))
    say(" This holds the second player's seat so the game counts two players.")
    say(" Leave this window open while you test. Close it to end the test.")
    say("=" * 74)

    sock = connect(args.port, 90)
    if sock is None:
        say("Could not reach the test server on port %d. Is it running?" % args.port)
        return 1
    sock.settimeout(None)
    sock.sendall(("login %s" % args.name + NL).encode())

    threading.Thread(target=watch_sheets, args=(not args.log,), daemon=True).start()
    if args.log:
        threading.Thread(target=watch_awards, args=(args.log,), daemon=True).start()

    buf = bytearray()
    session = None
    mine = {"net": 0, "slot": -1}
    host = {"session": -1}
    seated = False

    def send(line):
        try:
            sock.sendall((line + NL).encode())
        except OSError:
            pass

    def handle(etype, body):
        nonlocal seated
        if etype == EVENT_PLAYER_ROSTER and len(body) >= 2:
            count = struct.unpack_from("<H", body, 0)[0]
            pos = 2
            for _ in range(count):
                if pos + 15 > len(body):
                    break
                slot, net, sess, _alive, namelen = struct.unpack_from("<iiiBH", body, pos)
                pos += 15 + namelen
                if sess == session and session is not None:
                    if mine["net"] != net or mine["slot"] != slot:
                        mine["net"], mine["slot"] = net, slot
                    if not seated:
                        seated = True
                        say("[%s] Seated as %s (seat %d). The game now counts this player as playing." % (stamp(), args.name, slot))
                if slot == 0 and sess != host["session"]:
                    if sess != 0 and host["session"] in (-1, 0):
                        say("[%s] The host joined. Both players are in the game." % stamp())
                    elif sess == 0 and host["session"] > 0:
                        say("[%s] The host left the game." % stamp())
                    elif sess == 0:
                        say("[%s] Waiting for you to join (run the JOIN launcher)." % stamp())
                    host["session"] = sess
        elif etype == EVENT_CONSOLE and len(body) >= 2:
            n = struct.unpack_from("<H", body, 0)[0]
            text = body[2:2 + n].decode("latin1")
            tail = body[2 + n:]
            addr = struct.unpack_from("<i", tail, 0)[0] if len(tail) >= 4 else 0
            about_xp = any(word.lower() in text.lower() for word in XP_WORDS)
            if addr == mine["net"] and mine["net"] != 0 and (about_xp or args.all):
                say('[%s] %s\'s screen:   "%s"' % (stamp(), args.name, text))
            elif addr == 0 and about_xp:
                say('[%s] everyone\'s screen: "%s"' % (stamp(), text))
        elif etype == EVENT_TURN_START and len(body) >= 5:
            net, is_player = struct.unpack_from("<iB", body, 0)
            if is_player and net == mine["net"] and mine["net"] != 0:
                send("cendturn")  # a seat, not a fighter: hand the turn straight back
        elif etype == EVENT_COMBAT_ENTER:
            say("[%s] A fight started." % stamp())
        elif etype == EVENT_COMBAT_EXIT:
            say("[%s] The fight is over." % stamp())
        elif etype == EVENT_PARTY_WIPE:
            say("[%s] Everyone is down. The server reloads the last save." % stamp())
            send("wipeack")

    try:
        while True:
            data = sock.recv(262144)
            if not data:
                say("[%s] The server closed the connection. The test is over." % stamp())
                return 0
            buf += data
            if session is None:
                if len(buf) < 10:
                    continue
                if bytes(buf[:4]) != b"F2NS":
                    say("That port is not a co-op server.")
                    return 1
                session = struct.unpack_from("<i", buf, 6)[0]
                del buf[:10]
            # Frame: u32 seq, u32 sim, u32 payload length, u16 count, u32 entry base.
            while len(buf) >= 18:
                length = struct.unpack_from("<I", buf, 8)[0]
                if len(buf) < 18 + length:
                    break
                payload = bytes(buf[18:18 + length])
                del buf[:18 + length]
                ep = 0
                while ep + 4 <= len(payload):
                    etype, _flags, elen = struct.unpack_from("<BBH", payload, ep)
                    handle(etype, payload[ep + 4:ep + 4 + elen])
                    ep += 4 + elen
    except KeyboardInterrupt:
        say("Stopped.")
        return 0
    except OSError as error:
        say("[%s] Connection lost (%s). The test is over." % (stamp(), error))
        return 0
    finally:
        try:
            sock.close()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())
