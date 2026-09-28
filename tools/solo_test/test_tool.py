"""One-word actions for the solo co-op test, sent to the test server's operator console.

usage: python test_tool.py <action> [amount] [--admin 9801]

  quest          drop Keeng Ra'at, the Klamath rat god, beside the host, carrying his own
                 script. He attacks on sight. Killing him runs the game's real quest
                 award (the script calls give_xp), then the fight pays its kills.
  raiders        drop two raiders beside the host. They do nothing until attacked.
  reward [n]     pay a quest-sized award (default 500) the way play pays one.
  sheets         show both characters' level and experience.
  heal           pass an hour and heal everyone (for a second round).
  clear          remove everything this tool dropped.
  stop           stop the test server.
"""
import re, socket, sys, time

NL = chr(10)
KEENG_RAT = "0x0100012D"   # PID_KEENG_RAT
RAT_GOD_SCRIPT = 829       # scripts.lst line of KCRatGod.int
RAIDER = "0x010000EE"

argv = [a for a in sys.argv[1:]]
port = 9801
if "--admin" in argv:
    at = argv.index("--admin")
    port = int(argv[at + 1])
    del argv[at:at + 2]
action = argv[0] if argv else ""
amount = int(argv[1]) if len(argv) > 1 else 500


def admin(line):
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=3)
    except OSError:
        print("The test server is not running (nothing answers on port %d)." % port)
        print("Start it with the START launcher first.")
        sys.exit(1)
    s.sendall((line + NL).encode())
    time.sleep(0.5)
    s.settimeout(0.7)
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
    return out.decode(errors="replace").strip()


def placed(reply):
    m = re.search(r"placed (\d+)/(\d+)", reply)
    return int(m.group(1)) if m else 0


if action == "quest":
    reply = admin("spawn %s 1 near %d" % (KEENG_RAT, RAT_GOD_SCRIPT))
    if placed(reply) == 1:
        print("Keeng Ra'at, the rat god, is standing right next to you.")
        print("He attacks on sight. Kill him.")
        print()
        print("What you should see in YOUR message log, one time each:")
        print('  the script\'s line and "You gain 300 experience points."   (the quest award)')
        print('  "... you earn N exp. points."                              (the kill, when the fight ends)')
        print("The stand-in window shows the same two awards paid to both characters.")
    else:
        print("The server could not place him: " + reply)
elif action == "raiders":
    reply = admin("spawn %s 2 near" % RAIDER)
    if placed(reply) > 0:
        print("%d raider(s) are standing right next to you. They are unarmed and do" % placed(reply))
        print("nothing until you attack. Attack one; the other joins in.")
        print()
        print('When the fight ends you should read "... you earn N exp. points." one time,')
        print("and the stand-in window shows the same amount paid to both characters.")
    else:
        print("The server could not place them: " + reply)
elif action == "reward":
    print(admin("partyxp 0 %d" % amount))
    print()
    print("Open your character screen: your experience went up by that amount, one time.")
    print("(An operator award prints nothing in the message log; a real quest does.)")
elif action == "sheets":
    for line in admin("sheet").splitlines():
        m = re.match(r"sheet (\d+) \((.*?)\): level (\d+), xp (\d+), unspent (\d+), owed perk (\S+)", line)
        if m:
            print("seat %s  %-14s level %-3s %10s xp   unspent skill points %-3s perk owed: %s"
                  % (m.group(1), m.group(2), m.group(3), format(int(m.group(4)), ","), m.group(5), m.group(6)))
elif action == "heal":
    print(admin("rest 60"))
elif action == "clear":
    print(admin("despawnall"))
elif action == "stop":
    admin("quit")
    print("The test server was told to stop.")
else:
    print(__doc__)
    sys.exit(2)
