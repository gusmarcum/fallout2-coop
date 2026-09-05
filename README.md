# Fallout 2 Co-op

Play Fallout 2 together. One PC runs a dedicated server that owns the world: scripts, combat,
dialogue, the worldmap, saves. Every player runs a client that shows that shared world and
sends what they do. Several people, one persistent game, each with their own character.

Built on [Fallout 2 Community Edition](https://github.com/alexbatalov/fallout2-ce), derived
from [Cahb/fallout2-ce-coop](https://github.com/Cahb/fallout2-ce-coop) v0.4, and developed
here as its own project. No game files are included: bring your own Fallout 2 (Steam or GOG,
US 1.02d). Licence: Sustainable Use (non-commercial), inherited from Fallout 2 Community
Edition.

## What this project adds

Everything below came out of real two-player sessions fixing AI mistakes from the original project, issues were manually traced to its cause in the engine,
fixed at the cause, and verified against a 41-scenario regression suite before it shipped.
The commit history carries the full reasoning for each one.

**The world now survives a reconnect.** Co-op players reconnect a lot. Before, a rejoining
client came back to a map where every visited town had turned unknown again, the Pip-Boy
showed finished quests as open, and dead players stood back up. All three had the same
shape: the server knew the truth, but a joining client was only ever sent the changes that
happened after it arrived. Joins now carry the whole city table, the whole quest-variable
table, and no longer rebuild a dead player's standing pose.

**Computers and terminals work.** Every talking piece of scenery in the game, the Gecko
power plant's robot terminal among them, starts its conversation through an engine request
that only the vanilla client loop ever serviced. The dedicated server never ran that loop, so
each of those terminals silently did nothing in co-op. The server tick now services the
request, and the conversation is attributed to the player who clicked, so their answers are
accepted.

**Companions know who they belong to.** The follow logic read the single-player "the
player" variable, which on a server with several players resolved to whoever the last action
left behind, usually the host. Companions beelined for the wrong person or flip-flopped
between two. Each party member now records who recruited them and follows that player,
falling back to the nearest one on the same floor.

**Companion combat orders in co-op.** Vanilla's Combat Control window runs a local loop on
the machine that opens it and edits a local copy of the companion's settings, which the
server never sees, so the feature was unreachable in co-op. The Combat Control button on a
companion now opens their orders as a dialogue node served by the server: burst, run away,
weapon preference, distance, target, chem use. Pick a line to cycle it, Done to return. Same
settings, same labels, saved with the game.

**Sound that tells you what is wrong.** The client's audio initialisation compared the SDL
result with the wrong failure value, so a refused audio device passed as open and a player
simply had no sound, with no error anywhere. The client now detects it, tries the other
audio drivers, and prints the reason on the message line if it still cannot play. Music that
died (a stall while another player joined, a movie that never resumed it) is restarted by a
watchdog instead of staying dead for the session. The watchdog also remembers a track
the client started on its own map load, so music that dies during a map change comes back
without a rejoin.

**Dialogue that works over the wire.** Stale reply options no longer draw over the new node.
Long replies page (Down, Page Down or SPACE forward, Up or Page Up back). The Review button
shows the conversation's history, which the client now records itself. Chat opens on `T`,
also in combat, where Enter is the end-combat key.

**Small things that mattered in play.** Two-handed weapons stopped occupying both hand slots.
Arming one explosive from a stack arms one, not the stack. A dead player presses `R` to get
back up instead of waiting for the operator. TAB opens the automap. Push works on companions.
A stuck wait cursor clears itself. The operator's `save` refuses at moments when it would
have failed silently, and a `gvar` console command exists for repairing a world's quest
flags.

**Quicksave and quickload.** Vanilla's `F6` and `F7`, server-side. `F6` writes the server's
slot 16; `F7` reloads it in place for every connected player, through the same rebuild each
client already performs after a map change, and the game says who pressed it. It works in
combat, where it ends the fight the way single-player's does, and while dead, so a failed
steal or a lost fight can be retried. The operator's `load <n>` takes the same path while a
world runs, so restoring a slot no longer needs a server restart.

**The server never waits on a slow client.** Every frame went out through a blocking send
with a five-second timeout, so a client that stopped reading its socket, which every client
does for a few seconds while it loads a new map, froze the whole world for everyone: movement
landed seconds late, queued clicks arrived in a burst, menus lagged and the music mixer
starved. Sends are now non-blocking with a per-client queue, and a client that takes nothing
for a minute is dropped instead of stalling the rest. Measured with a client that stops
reading: a 20 second freeze before, 0.2 seconds after.

**Companions survive a map change after a load.** The map save writes party members with
their keep-on-map flags cleared and nothing re-armed them after a load, so the first map
change after restoring a world deleted every companion's body and the next load dropped them
from the party. The flags are re-armed on load, and the console gained `party` (list) and
`partyadd <pid>` (re-attach a companion standing on the current map) for worlds already hit.

**A test harness that runs on Windows.** The engine's two golden suites, 41 headless
scenarios that replay fixed inputs and compare the resulting world state byte for byte, only
ran on Linux. Headless probes now run on Windows: exempt from the single-instance locks,
deterministic (the RNG seed no longer comes from the wall clock), and blessed against a
Windows result set. Every commit in this repository passes both suites.

## Quick start

**Host** (runs the server, and usually a client too)

1. Copy your Fallout 2 folder somewhere new, for example `D:\Games\Fallout2Coop`. That copy
   is the world; its `data\SAVEGAME` holds the co-op saves.
2. Put `f2_server.exe` and `fallout2-ce.exe` from a release into that folder.
3. Start the server from a `.cmd` file in that folder:

```bat
@echo off
cd /d "%~dp0"
set F2_SERVER_MAP=artemple.map
set F2_SERVER_NET=9300
set F2_SERVER_CMD=9301
set F2_SERVER_PACE_MS=100
set F2_AUTOSAVE_SECS=300
set F2_MOVIES=0
set F2_SERVER_NAME=Our game
f2_server.exe
pause
```

   To continue a saved world use `set F2_SERVER_LOAD=<slot>` instead of `F2_SERVER_MAP`.
   Slots 1 to 10 are manual saves, 11 to 15 the rotating autosaves, 16 the quicksave.
4. Join from the same PC:

```bat
@echo off
cd /d "%~dp0"
set F2_CLIENT_CONNECT=127.0.0.1:9300
set F2_PLAYER_NAME=Gus
set F2_PLAYER_CREATE=ask
fallout2-ce.exe
```

**Other players**

Put `fallout2-ce.exe` next to your own Fallout 2 files and start it with the host's address in
`F2_CLIENT_CONNECT` (for example `10.144.94.83:9300`) and your own `F2_PLAYER_NAME`. The first
time a name is seen you create a character; after that the same name is the same character.
Names must differ between players and stay the same across sessions.

A VPN such as ZeroTier is the recommended way to play over the internet. Do not forward the
game port to the internet: the wire has no authentication. The client reads `fallout2.cfg`
from the folder the exe is in, so keep it next to the game files.

## Keys in the client

| Key | What it does |
|---|---|
| `T` | open chat, also during combat (Enter still ends combat in a fight) |
| `TAB` | automap (out of combat) |
| `P` | Pip-Boy (holodisks, quests, automaps; refused in combat like vanilla) |
| `R` | when dead: get back up at 1 HP where you fell |
| `F6` / `F7` | quicksave / quickload (server slot 16). `F7` rewinds the game for everyone; works in combat and while dead; main screen only, as in vanilla |
| `Down` / `PgDn` / `SPACE` | next page of a long dialogue reply; `Up` / `PgUp` previous page |
| Review button | this conversation's history |
| Combat Control button | on a companion: their combat orders |
| hold left click on a companion | menu with Push |

## Server settings

Set these as environment variables before starting `f2_server.exe`.

| Variable | Default | Meaning |
|---|---|---|
| `F2_SERVER_MAP` | | boot a fresh world on this map |
| `F2_SERVER_LOAD` | | restore save slot 1-16 (11-15 = autosaves, 16 = quicksave) |
| `F2_SERVER_NET` | | game port for clients |
| `F2_SERVER_CMD` | | admin console port (see below); never expose it |
| `F2_SERVER_PACE_MS` | `0` | ms per beat; `100` is about real time |
| `F2_SERVER_HOST` | first to join | pin slot 0 (drives worldmap travel and map changes) to a player name |
| `F2_SERVER_NAME` | | name shown to clients |
| `F2_AUTOSAVE_SECS` | `300` | autosave interval into slots 11-15; `0` = off |
| `F2_SERVER_KEEPALIVE` | on if CMD set | keep running when the last player leaves |
| `F2_GAME_DIFFICULTY` / `F2_COMBAT_DIFFICULTY` | from cfg | `0` easy, `1` normal, `2` hard |
| `F2_MOVIES` | on | `0` skips scripted movies; use it if a joining client crashes on a cutscene |
| `F2_TRACE_WORLD` | off | `1` prints `[world]` lines for door, container and map-state changes |

## Admin console

Connect to the `F2_SERVER_CMD` port with a TCP tool (telnet, nc, or a small script) and send one
command per line. It answers once a client is connected.

| Command | Meaning |
|---|---|
| `status` | what is running |
| `saves` | list save slots |
| `save <1-16> [label]` | save the world (refused during combat, dialogue, travel, map change); 16 is the quicksave |
| `load <1-16>` | restore a slot; while a world runs it is reloaded in place for everyone (the `F7` path, by number) |
| `new <map.map>` | boot a fresh world (lobby only) |
| `revive <slot>` | stand a dead player up (players can also press `R`) |
| `give <pid> <count>` | give items to the host character; `count` is stacks (boxes for ammo) |
| `gvar <index> [value]` | read or set a global script variable (quest flags) |
| `party` | list the party as the server sees it |
| `partyadd <pid>` | re-attach a companion standing on the current map (89 = John Cassidy) |
| `say <channel> <text>` | a line to every client |
| `quit` | stop the server |

The admin port has no password. Keep it bound to localhost or a VPN interface only.

## Building on Windows

Install [MSYS2](https://www.msys2.org/), open the MINGW64 shell and run:

```bash
pacman -S --needed mingw-w64-x86_64-gcc mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja git diffutils procps-ng
cmake -S . -B build-win -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
      -DCMAKE_C_FLAGS=-std=gnu17 -DCMAKE_EXE_LINKER_FLAGS="-static -static-libgcc -static-libstdc++"
cmake --build build-win --target f2_server fallout2-ce -j4
```

The two exes in `build-win` depend only on Windows system libraries. SDL2 and zlib are fetched
and built during configure. Linux builds follow `DEDICATED_HOWTO.md`.

## Testing

```bash
export F2_GAME_DIR=/path/to/a/game/folder F2_BIN=$F2_GAME_DIR/fallout2-ce.exe
F2_GOLDEN_DIR=$PWD/tests/golden/server-win tests/golden/run_golden_server.sh
F2_GOLDEN_DIR=$PWD/tests/golden/legacy-win  tests/golden/run_golden.sh
```

Copy the client exe into the game folder first: it reads its config from its own directory,
and the Windows goldens were blessed on Hard difficulty. The Windows result sets live in
`tests/golden/server-win` and `legacy-win`; the Linux sets are the checked-in default. Both
suites pass on every commit of this repository.

## Known limits

- No authentication on the game port; the admin port has none either. Use a VPN.
- One client per PC (the engine's single-instance lock); headless test probes are exempt.
- The world is one map at a time; players travel together.
- A companion's recruiter is not stored in saves; after a load they follow the nearest player
  until re-recruited.
- The Restoration Project and other sfall hook-script mods are not supported: hook scripts do
  not run in this engine. Server and every client must have identical game data.

## Credits

- [Fallout 2 Community Edition](https://github.com/alexbatalov/fallout2-ce) by Alexander Batalov
  and contributors: the engine.
- [Cahb/fallout2-ce-coop](https://github.com/Cahb/fallout2-ce-coop): the dedicated server, the
  network client and the wire protocol this project is derived from.
- Fallout 2 is the work of Black Isle Studios and Interplay.

Licence: [Sustainable Use License](LICENSE.md).
