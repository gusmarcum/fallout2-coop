# 032: Every map but the current one resets: the dead stand up, loot is back, people forget you

**Status**: FIXED (2026-09-28), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/loadsave.cc` (`_InitLoadSave`), `src/game_lifecycle.cc`
(`gameInitWithOptions`), `src/server_loop.cc` + `src/client_net.h`
(`clientViewerRequested`), new `src/map_state_guard.cc` + `.h`, `src/map.cc`
(`mapLoadByName`, `_map_save_in_game`, `_MapDirEraseFile_`), `src/savegame.cc`
(`_GameMap2Slot`, `_SlotMap2Game`, `MapDirErase`), `src/server_boot.cc`,
`tools/map_state_proof.py`.

## Symptom
Three reports of one defect, from players and from the owner's own campaign:

- GitHub issue 4: the spore plants in Hakunin's garden are alive again when the party comes
  back to Arroyo village after finishing the quest.
- "If I shut down the server and restart it, loading a saved game only preserves the state
  of the area where the save was made. Every other area seems to reset: NPCs talk to me as
  if they're meeting me for the first time, dead NPCs are resurrected, and previously
  collected items respawn."
- The owner's world, weeks earlier: Gecko reset, Lynette in Vault City did not know him.
  Both were put down to a rollback to an older save at the time. That was wrong.

It happens on every map, with or without a restart, and it never happened on a test server
with no game client beside it, which is why it could not be reproduced before.

## Root cause
The state of a map the party has left is a file, `<patches>\MAPS\<MAP>.SAV`. Leaving a map
writes it, entering a map reads it (`mapLoadByName` loads the `.SAV` when it exists and the
shipped `.MAP` when it does not), and a save copies every one of them into its slot.

Vanilla erases `MAPS\*.SAV` and the proto overrides when the game starts, before the main
menu, to clear what the last session left behind: `_InitLoadSave` and `lsgInit`, both
called from `gameInitWithOptions`. The co-op client is the same program and runs the same
start-up. The host plays from the world folder (the release tells them to: `join.cmd` sits
next to `start-server.cmd`), so every start of the host's client erased the running
server's record of every map it had visited. The map in memory survived, because the
server writes it again when the party leaves.

From there:

- the next visit to any earlier map found no `.SAV`, loaded the shipped map, and ran its
  first-visit script again (Arroyo village pays the temple award a second time);
- every save written afterwards held only the maps left since the client started, so a
  restart kept "the area where the save was made" and little else;
- nothing looked wrong at the time of the erase. The loss showed up maps later.

Measured on the owner's live world: a level 20 campaign, and its six newest saves hold five
maps between them (Navarro, the NCR entrance, three San Francisco maps).

A friend's client on another PC erases its own folder and does no harm.

## Fix
Two changes, either of which is enough on its own, because the two programs are updated
together but only one of them is under the project's control on the host's PC.

**The client.** A process started to join a server (`F2_CLIENT_CONNECT` set, new
`clientViewerRequested`) skips the erase in `_InitLoadSave` and the `lsgInit` that follows
it. It has no session of its own to clean up. Single player, the headless probe and every
golden run the vanilla start-up unchanged.

**The server.** `f2_server` keeps the bytes of every working file it writes (on leaving a
map, on a save) or restores from a slot (on a load), and before it reads them (entering a
map, writing a save) it puts back any that have gone missing (`map_state_guard.h`). Only a
missing file is restored; a file that exists is never replaced. Files the server erases
itself (a new world, a load, a random encounter left behind) are forgotten through the two
functions that erase them. This covers what the client fix cannot: an older client, or the
original game, started in the world folder.

## Diagnostics
Server console, when the guard had to act:
`f2_server: 2 map state file(s) of this world were ERASED from data\MAPS by another program
(a Fallout 2 game or an older co-op client started in this folder); 2 put back, 0 could not
be written: ARBRIDGE.SAV, ARVILLAG.SAV`.

With `F2_TRACE_WORLD=1` every map load says which it was:
`[world] map load ARVILLAG.MAP: from saved .SAV (state kept)` or
`[world] map load ARVILLAG.MAP: fresh .MAP (no saved state: doors/loot reset)`.

## Verification
`python -u tools/map_state_proof.py <f2_server.exe> <fallout2-ce.exe> <sandbox> <port> <cmd
port>`: kills both plants, walks to the bridge, starts the real client in the server's
folder (no window), walks back, saves, restarts on the save, joins again, walks back again,
has the client quit on Esc and Y, and last saves on a random encounter map and leaves it.

| server | client | result |
|---|---|---|
| v1.3.1 | v1.3.1 | defect reproduced: files erased, village loaded new, plants standing, temple award paid again, the save holds the bridge only (`--client-erases --expect-loss`) |
| fixed | fixed | 21/21: nothing erased, village visited, plants dead, save holds both maps, same after a restart and after a clean quit |
| fixed | v1.3.1 | 22/22: the client erases, the server puts the files back four times and says so (`--client-erases`) |
| v1.3.1 | fixed | 21/21: the client fix on its own |

In every row the working file of the random encounter map is erased by the server when
the party leaves and stays erased. Gate: server-loop 27/0, legacy 14/0.

## Existing worlds
What was erased is gone: a map lost before the update loads as new on its next visit, once,
and is kept from then on. Quest progress, karma, reputation, the characters, the car and
the world map were never affected (they live in `SAVE.DAT`, not in the map files), so a
reset map meets a party whose quests there are already done. First-visit scripts run again
on such a map and may pay their award a second time.

## Still shared
`MAPS\AUTOMAP.DB` is created empty by every client start and removed by every client exit
(vanilla), in the same folder. The server writes an empty one when a save needs it
(bugs/020). The host's automap therefore does not survive a client restart. Not changed
here.
