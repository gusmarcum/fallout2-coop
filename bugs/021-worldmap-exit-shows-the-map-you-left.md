# 021: Leaving the worldmap showed the map you had just left for a second or two

**Status**: FIXED (2026-09-10).
**Files**: `src/presenter.h` / `src/presenter_network.cc` (`worldmapEnd(bool mapLoadFollows)`),
`src/server_worldmap.cc` (the flag), `src/client_net.cc` / `.h` (hold latch, old-world mute),
`src/main.cc` (`viewerHoldForNewWorld`).

## Symptom
After a random encounter, you finish the fight, open the worldmap and click a destination.
For a second or two the screen shows you back at the encounter, and the people you killed
start cycling their lines every tenth of a second, until the game throws you into the place
you clicked. Reported from live play on 2026-09-10.

## Root cause
Order of events on the server when a trip ends: it tells every client the worldmap session
is over, wakes the scripts of the map it is still holding, and only then loads the
destination (or the encounter) and streams the new snapshot. The client tears the worldmap
screen down the moment it hears the end, and the only world it has to draw is the one it
left, so that is what it shows until the new snapshot lands and is applied. The original
game never has this gap: it loads the new map underneath the worldmap screen and takes the
screen away afterwards.

The "voice lines" are the same gap heard rather than seen. The client is a live viewer on a
stale world with nothing pacing it, so whatever the fight still had queued (death sounds,
floating text, the presentation backlog crowded fights build up) plays at full speed until
the snapshot clears it.

## Fix
- `worldmapEnd` carries whether a map load follows. The server knows at that point: the
  driver's `map != -1` means a `mapLoadById` is next, for a destination or an encounter.
- When it does, the client fades to black, blanks and disables the map renderer, and waits
  for the new snapshot to be applied (the load counter changes) before fading in on the
  destination, with a fifteen second watchdog. The same wait the party-wipe death screen
  uses. Escape on the worldmap, and a driver bail, send no flag, and the client returns to
  the old map at once as before.
- While it waits, the decoder drops sounds and floating text from the old world (the mute
  clears when the new world is applied), and no presentation is drained.

## Verification
Sandbox: the friend-TEST quicksave (party on Navarro's surface). The Fable bot logged in as
the host and walked the body onto a real exit grid (tile 33098, misc proto 21) over the wire;
a console travel intent toward San Francisco ended at once in a random encounter (map 74).
The real client, watching from the second seat, logged
`onWorldmapEnd — exiting (map load follows=1)` and
`worldmap trip ends in a map load; held on black 735 ms (new world applied)`.
Two lessons for the next probe of this kind: console `warp`/`walkto` do not arm the exit-grid
check the way a wire walk does, and Navarro's dense rows of misc proto 12 along the edges are
scroll blockers, not exit grids; the exit grids are protos 17 to 23 on the north and south
edges. Gate green on the final binaries.
