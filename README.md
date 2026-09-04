# Fallout 2 Co-op

A dedicated server and a network client for Fallout 2, built on
[Fallout 2 Community Edition](https://github.com/alexbatalov/fallout2-ce). One PC runs the
server, which owns the world: scripts, combat, dialogue, the worldmap, saves. Each player runs
the client, which shows the shared world and sends what the player does. Several people play
one persistent game with their own characters.

This project started from [Cahb/fallout2-ce-coop](https://github.com/Cahb/fallout2-ce-coop)
v0.4 and is developed here as its own project. It carries about twenty fixes found in live
two-player sessions and a test harness that runs on Windows.

No game files are included. You need your own copy of Fallout 2 (Steam or GOG, US 1.02d).
Licence: Sustainable Use (non-commercial), inherited from Fallout 2 Community Edition.

## What you need

- Windows PCs for the host and every player (the server also builds and runs on Linux).
- Fallout 2 installed on each PC. The server needs a full copy of the game files too.
- A network path between the PCs. A VPN such as ZeroTier is the recommended way to play over
  the internet. Do not forward the game port to the internet: the wire has no authentication.

## Quick start

**Host (one PC runs the server and, usually, a client too)**

1. Copy your Fallout 2 folder somewhere new, for example `D:\Games\Fallout2Coop`. This copy is
   the world: its `data\SAVEGAME` holds the co-op saves.
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
   Slots 1 to 10 are manual saves, 11 to 15 the rotating autosaves.
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

The client reads `fallout2.cfg` from the folder the exe is in. Keep it next to the game files.

## Keys in the client

| Key | What it does |
|---|---|
| `T` | open chat, also during combat (Enter still ends combat in a fight) |
| `TAB` | automap (out of combat) |
| `P` | Pip-Boy (holodisks, quests, automaps; refused in combat like vanilla) |
| `R` | when dead: get back up at 1 HP where you fell |
| `Down` / `PgDn` / `SPACE` | next page of a long dialogue reply; `Up` / `PgUp` previous page |
| Review button | this conversation's history |
| Combat Control button | on a companion: their combat orders (burst, run away, weapon, distance, target, chems) |
| hold left click on a companion | menu with Push |

## Server settings

Set these as environment variables before starting `f2_server.exe`.

| Variable | Default | Meaning |
|---|---|---|
| `F2_SERVER_MAP` | | boot a fresh world on this map |
| `F2_SERVER_LOAD` | | restore save slot 1-10 (11-15 = autosaves) |
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
| `save <1-10> [label]` | save the world (refused during combat, dialogue, travel, map change) |
| `load <1-15>` / `new <map.map>` | restore a slot / boot a fresh world (lobby only) |
| `revive <slot>` | stand a dead player up (players can also press `R`) |
| `say <channel> <text>` | a line to every client |
| `quit` | stop the server |

The admin port has no password. Keep it bound to localhost or a VPN interface only.

## Fixed here compared with v0.4

Talking terminals and computers open their screens; a client whose audio device fails to open
is told so instead of playing silently, and music restarts itself after it dies; visited
worldmap locations survive a reconnect; dead players stay down after a reconnect; two-handed
weapons use one slot; old dialogue options no longer draw over new ones; long replies page;
the Review button works; chat during combat; automap; self-revive; companions follow the
player who recruited them; the companion combat-orders menu; arming an explosive arms one unit
of a stack, not all of them; a stuck wait cursor clears itself; the operator `save` refuses at
the wrong moment instead of failing. See the commit history for causes and details.

## Building on Windows

Install [MSYS2](https://www.msys2.org/), open the MINGW64 shell and run:

```bash
pacman -S --needed mingw-w64-x86_64-gcc mingw-w64-x86_64-cmake mingw-w64-x86_64-ninja git diffutils procps-ng
cmake -S . -B build-win -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
      -DCMAKE_C_FLAGS=-std=gnu17 -DCMAKE_EXE_LINKER_FLAGS="-static -static-libgcc -static-libstdc++"
cmake --build build-win --target f2_server fallout2-ce -j4
```

The two exes in `build-win` depend only on Windows system libraries. SDL2 and zlib are fetched
and built during configure. Linux builds follow the upstream instructions in `DEDICATED_HOWTO.md`.

## Testing

Two headless golden suites replay fixed scenarios and compare the world state dump against
checked-in results. On Windows:

```bash
export F2_GAME_DIR=/path/to/a/game/folder F2_BIN=$F2_GAME_DIR/fallout2-ce.exe
F2_GOLDEN_DIR=$PWD/tests/golden/server-win tests/golden/run_golden_server.sh
F2_GOLDEN_DIR=$PWD/tests/golden/legacy-win  tests/golden/run_golden.sh
```

Copy the client exe into the game folder first: it reads its config from its own directory.
The Windows results live in `tests/golden/server-win` and `legacy-win`; the Linux set is the
checked-in default. Both suites pass on every commit of this repository.

## Known limits

- No authentication on the game port; the admin port has none either. Use a VPN.
- One client per PC (the engine's single-instance lock); the headless test probes are exempt.
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
