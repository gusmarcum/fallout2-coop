# Changelog

Binaries for every version are on the
[releases page](https://github.com/gusmarcum/fallout2-coop/releases). The server and every
client must run the same version.

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
