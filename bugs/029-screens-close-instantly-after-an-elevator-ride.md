# 029: Inventory and other screens close on their first frame after an elevator ride

**Status**: FIXED (2026-09-11), not yet confirmed in live play.
**Files**: `src/elevator.cc`, `src/scripts.cc`, `src/scripts.h`, `src/main.cc`,
`src/interpreter_extra.cc`.

## Symptom
Live report (solo world, Navarro): after a reload, pressing I did nothing. The client
`debug.log` showed every press opening the screen and closing it straight away:
`inventory key: free roam -> opening the screen`, `inventory: screen up (window 5)`,
`inventory: closed by game state 5 after 1 frames`. Relaunching the client fixed it.

## Root cause
`GAME_STATE_5` means a conversation was requested but not yet entered. Vanilla's modal
loops close so the dialog can start, and vanilla's `gameHandleKey` starts it on the
next frame. The only thing that requests it is the `dialogue_system_enter` opcode, so a
script had run on the client. A viewer normally runs no scripts: the main loop's puppet
levers disable them, and a rebaseline load keeps map-enter procs off
(`mapSetViewerLoad`).

The leak was the vanilla elevator panel. `elevatorWindowInit` disables scripts and
`elevatorWindowFree` re-enables them unconditionally, while the viewer only re-applies
its `scriptsDisable` when a rebaseline arrives. Navarro's elevators never change maps,
so after a ride the viewer ran critter heartbeats and timed events locally until the
next load, and an NPC script that starts a conversation parked the client in state 5.
The viewer never calls `gameHandleKey`, so nothing consumed the request, and the later
reload re-disabled scripts without clearing the state.

## Fix
- `elevatorWindowFree` re-enables scripts only if `elevatorWindowInit` found them
  enabled (new `scriptsAreEnabled`). Single player is unchanged.
- The viewer's main loop disables scripts whenever it finds them enabled between loads,
  which covers any other vanilla modal with the same disable/enable pair.
- `dialogue_system_enter` is ignored on a viewer, so a stray script can never park it in
  state 5.

## Diagnostics
Client `debug.log`: `client-viewer: scripts were enabled between loads; disabling them
again`, and `client-viewer: ignored dialogue_system_enter from <name>` naming the
object whose script asked.
