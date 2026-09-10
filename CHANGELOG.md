# Changelog

Binaries for every version are on the
[releases page](https://github.com/gusmarcum/fallout2-coop/releases). The server and every
client must run the same version.

## Unreleased

### Added

- **One suit per player.** The game places exactly one Advanced Power Armor in Navarro and
  one Mk II in the oil rig's trap room. The first time the server loads one of those maps
  it tops the locker up to one suit per seat in the save, so a second player is not sent
  through Navarro without a disguise because the first one took the only suit. Nothing is
  removed, a revisit changes nothing, and the rule table in `src/server_seat_items.cc` is
  the place to add more.

### Changed

- **Cutscenes always play.** `F2_MOVIES=0` used to switch scripted movies off on the
  server, and the launch files this project shipped set it, so no cutscene ever reached
  the players: not the tanker leaving for the oil rig, not the rig going up. The switch
  was adopted for a client that crashed on the Temple of Trials cutscene, and that crash
  was the client's own mods, not the movie. The switch is retired; a launch file that
  still sets it gets one notice at boot and is otherwise ignored. Clients must run
  unmodified game data.
- **A cutscene can no longer park the server.** The movie barrier releases on the first
  player to finish or skip, as before, and now also on its own after three minutes if no
  player ever reports back, with a line on the console. The operator can release it by
  typing `movdone` on the command channel.

### Fixed

- **A server started on a fresh map can save.** The slot writer copies the automap
  database into the slot and gave up when the file did not exist. Only a client creates
  that file, so a dedicated server hosting a new world from its own folder failed every
  save with "error 0" until a client happened to run beside it. The server now writes
  the same empty database the client would have.
- **A new world starts from the shipped maps.** Starting the server on a fresh map in a
  folder that had hosted another world kept that world's map state files, and the loader
  prefers those, so places the old world had visited came up already looted and cleared.
  The server now clears them, like the game's own new game does.
- **A failed save no longer damages the slot.** The save backup covered the save file,
  the maps and the automap but not the companion protos, which are written before the
  step that can fail. A failed save restored everything else and left protos from the
  world that failed to save, and loading that slot crashed the game. The protos are now
  backed up and restored with the rest, and a recycled autosave slot is emptied of them
  too. `F2_SERVER_DEBUG_LOG=1` makes the server name the failing step in
  `f2_server-debug.log`.
- **The character creation screen opens once, not on every launch.** With
  `F2_PLAYER_CREATE=ask` the client opened the creation screen before connecting, because
  it could not know whether the server already had the name, and the server then threw the
  roll away for a returning player. The client now asks the server first and opens the
  screen only for a name the world does not know. A fresh world still asks everyone once.
- **Leaving the worldmap no longer flashes the map you just left.** Picking a destination
  (or being pulled into an encounter) closed the worldmap screen a second or two before
  the new map arrived, and in that gap you were shown the map you had left, with whatever
  its fight still had queued playing at full speed. The screen now holds on black until
  the new map is applied, the way the original game loads the new map underneath the
  worldmap. Escaping the worldmap still returns you to the old map at once.
- **The world trace no longer reports a correct saved-state load as a reset.** With
  `F2_TRACE_WORLD=1`, re-entering a visited map logged "fresh .MAP (no saved state)" for
  the inner load of the saved file, which made every revisit read like the very bug the
  line exists to expose. It now says "loading the saved state file".

## v1.1.0 (2026-09-08)

A bug-fix release with three changes you will notice. Everything here came out of one
long play session on the oil rig.

### Fixed

- **The Navarro minefield no longer takes your controls away.** Stepping on a mine left
  the player unable to open a menu, pan the screen or use the mouse, with clicks only
  half registering, until they restarted the game. The mine's script disables the
  interface and never re-enables it; in the original game the explosion's own code hands
  the controls back, because the flag is shared between the scripts and the engine on one
  machine. Co-op had split that flag across the wire and only reconnected the script half,
  so the release never reached the player. Six of the game's scripts leak a lock this way,
  including two in Modoc and one in New Reno, and this fixes all of them. The client also
  now releases any input lock held longer than fifteen seconds and says so, so no script
  can cost a session again.
- **A save made after Frank Horrigan dies is playable.** Loading one booted the world,
  served a single beat and kicked everybody out, which looked exactly like the client
  crashing on that map. The oil rig's entry script signals the game's ending on every
  entry once Horrigan is dead, and the serve loop honoured it. A keepalive server now
  logs that once and keeps running; stopping it on purpose is still `quit` on the command
  channel.
- **The nine-door puzzle in the Enclave works.** One of the terminals opens two doors and
  then closes those same two a few lines later. The original game's doors slide on a
  deferred animation, so the second instruction quietly does nothing and the doors stay
  open; the server applies the slide immediately, so it undid the first instruction and
  that terminal could never open anything. The doors also appeared open on screen while
  the server still blocked the way through them.
- **Power armour cannot be taken off twice.** Rarely, a suit's bonuses were removed twice
  over, dropping Advanced Power Armor's wearer from 9 Strength to 1 rather than 5, and it
  stuck. Armour class and every damage resistance were being double-subtracted the same
  way, unnoticed. The bonuses can now only be taken off the body they are actually on.

### Changed

- **Autosaves rotate through their five slots in order** — 11, 12, 13, 14, 15, then back
  to 11 — instead of always recycling whichever save was furthest behind in in-game time.
  The old rule kept the most-progressed saves longest, which sounds right and degenerates:
  load an earlier save and play on, and every autosave lands on the same slot forever. The
  trade is real and worth stating: after going back to an older save, the rotation will
  overwrite the newer, further-along ones within one lap. Manual slots are where a save
  worth keeping belongs.
- **The ending no longer asks whether you want to keep playing.** In a shared world the
  answer is always yes, and one player's dialog box would sit on their screen while
  everyone else played on. The slides and the credits still play in full first. Single
  player still asks.

## v1.0.0 (2026-09-07)

**Fallout 2 has been played from start to finish in co-op.** That is what the version
number is for. It is not a claim that nothing is left to fix; it means two people can
begin at the Temple of Trials, play the whole game together, and beat Frank Horrigan,
which is the bar this project was built to clear.

### New

- **The server owns the ending.** Winning already showed the slides, because a viewer
  runs map scripts locally and each client played the sequence off its own script
  execution. That worked, and play continued afterwards, but nothing coordinated it: the
  dedicated server drops the request, so it depended on each client happening to run a
  script the server had discarded. It is a wire event now, announced by the server, with
  the slides still chosen from the globals that world earned. No reload and no shutdown
  follows, and the closing "keep playing?" prompt cannot quit anyone out of a live
  session.
- **`ending`** on the operator console replays it on demand.
- **`stat <slot> [stat] [value]`** reads or repairs a seat's base SPECIAL. It prints base
  and current side by side, so an armour or drug bonus shows as the difference. Nothing
  could reach the seven base stats before, which made repairing a character a SAVE.DAT
  edit with the server down.

### Fixed

- **NCR shot the second player for a weapon he had already put away.** Holstering in
  vanilla means switching to your empty hand, not dropping anything, and a script reads
  the hand you are holding up. On a dedicated server the opcode asked a stub pinned to
  the left hand, so swapping was invisible, and the filter was applied only to the
  anchored player, so everyone else reported both hands unconditionally. The second
  player could never comply. Now every script-facing hand reader resolves the real
  active hand, for every player.
- **A client closed itself on the oil rig, instantly, every load.** Post-Horrigan the
  map's entry script signals the end of the game, and a viewer runs map scripts locally
  while loading a map to render it. The dedicated server was guarded against that; the
  client never was, so it set the terminal quit and exited. The map appeared for a
  fraction of a second and the window shut, with no crash dump because it was a clean
  exit. A viewer never self-quits from a script now.
- **Winning the game shut the server down.** `op_endgame_movie` bypasses the script
  request queue and calls straight into the headless branch that sets the terminal quit,
  so the world would have stopped mid-ending, moments after the players started watching.
- **A silent server death now names itself.** The terminal quit ended the serve loop with
  no log line, indistinguishable from a clean shutdown, so the clients being dropped a
  second later looked like the broken half. All five sources report themselves and the
  loop prints the tick it saw one on.

## v0.6.0 (2026-09-06)

### New

- **Trading between players.** Talk to another player to propose a trade; on yes both open
  the vanilla trade screen with each other while the world keeps running. Offer locks a
  table, two locked tables raise an accept box on both sides, two yeses swap. Stealing from
  a player is refused.
- **Death is a team matter.** No self-revive. A teammate revives a dead player by using the
  body, a healing item, First Aid or Doctor: free out of combat, 4 AP on their turn in a
  fight. A revived player gets their turns back. When nobody is left standing every client
  plays the death screen and the server reloads the most recently written save.
- **Quicksave and quickload.** `F6` writes server slot 16, `F7` reloads it in place for
  everyone, in combat and while dead. Admin `load <n>` works while a world runs.
- **Combat orders presets.** The companion orders menu has a Disposition line that cycles
  Custom, Coward, Defensive, Aggressive and Berserk.
- **Companions step aside** when they are the only thing blocking a walk or an approach,
  and the walk is retried.
- **Console**: `kill <slot>`, `spawn` takes a scripts.lst number so the NPC talks,
  `despawnall`; the server window reports a client that stops draining its stream.
- **Viewer `audit`** dumps the windows, the floating objects and every player-art critter
  into `debug.log`.

### Fixed

- Sliding doors and elevator doors drifted upward with every open-and-close cycle and the
  drift was saved; frames now step with the animation's art offsets and every door is put
  back in place at map load (bugs/010).
- Elevators asked for the floor twice (bugs/009). `Esc` on the panel cancels the ride.
- The San Francisco Brotherhood door opened and closed in the same beat (bugs/011).
- Power armor's +3 Strength and radiation resistance applied only to the host (bugs/012).
- A player being stolen from saw their worn gear vanish from their own screen (bugs/013).
- The action-point bar could open a turn showing last turn's leftover (bugs/014).
- An offline teammate's parked body was drawn at the top-left corner of the screen.
- A player's sprite followed whichever hand held a weapon instead of the active hand.
- Crash on death: two new messages were string literals the message log writes into.
- The death screen garbled the rest of a large screen.
- Music stayed silent after a change between two maps that share a track.
- Two client heap-corruption crashes: merged inventory stacks freed twice. Wire stacks are
  mirrored as their own slots, the engine reports every free to the mirror, and a live-object
  registry turns a stale pointer into a logged skip.
- The whole world froze while any client loaded a map: server sends were blocking. Sends
  are non-blocking with a per-client queue (20 s freeze before, 0.2 s after).
- Companions were lost on the first map change after a load; `party` and `partyadd <pid>`
  repair worlds already hit.
- Out-of-combat input could stay blocked behind a stuck animation; capped at 3 s and logged.
- The inventory screen logs why it closed, for the "I does nothing" report.
- `tools/repair_vault_city_gate.py` removes the stacked blocking hex that walls off the
  Vault City gate in an affected save (bugs/008).

### Under the hood

- CI builds the two shipped binaries with MSYS2 mingw-w64 and the shipping flags, plus a
  Linux x64 build and cppcheck; the dead phone, Mac and 32-bit matrix is gone.
- Sandbox proof scripts under `tools/`: trade and death (51 checks), quicksave (26), armor
  perks, the parked body (14), inventory.
- Bug notes 008 to 014 under `bugs/`.

### Upgrading from v0.5.0

- Update the server and every client together: the wire gained events and verbs.
- Saves carry over. Slot 16 is now reserved for the quicksave.
- `R` no longer revives you; a teammate does.
- Power armor worn before the update: take it off and put it back on once.
- Doors that drifted in an existing save are put back in place on the first load.

## v0.5.0 (2026-09-04)

First release as its own project.

- Reconnecting keeps the world: the whole worldmap city table and quest-variable table ride
  every join; dead players stay down.
- Terminals and computers open their conversations; the conversation is attributed to the
  player who clicked.
- Companions follow whoever recruited them.
- Companion combat orders as a dialogue menu served by the server.
- A failed audio device is detected and reported; music that dies is restarted by a watchdog.
- Dialogue: no stale options over new ones, long replies page, the Review button works,
  chat on `T` also in combat.
- Two-handed weapons use one slot; arming one explosive arms one; TAB opens the automap;
  Push works on companions; a stuck wait cursor clears itself; operator `save` refuses
  when it would fail; `gvar` console command.
- Windows test harness: the 41 golden scenarios run headless and deterministic on Windows.

## v0.4

The base: [Cahb/fallout2-ce-coop](https://github.com/Cahb/fallout2-ce-coop) v0.4.
