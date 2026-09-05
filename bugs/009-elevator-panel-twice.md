# 009 — Elevator panel opens twice; the second choice is ignored

**Status**: FIXED (2026-09-05).
**Files**: `src/script_request_handler_server.cc` (`elevatorSelect`), `src/server_control.cc`
(`serverControlElevatorOfferPending`, the `elevcancel` verb, release on disconnect),
`src/main.cc` + `src/client_net.cc` (`clientViewerElevatorCancel`).

## Symptom
Walking into an elevator (Navarro, every floor) raises vanilla's floor panel. After picking a
floor the ride happens, and then the panel comes up a second time. Whatever is picked on the
second panel does nothing: the party is already where the first choice put it. The server log
shows the shape exactly:

```
f2_server: elevator 19 offered to slot 0 (start level 0)
f2_server: elevator 19 offered to slot 0 (start level 0)
f2_server: elevator 19 offered to slot 0 (start level 0)
f2_server: interact FIRE use netId=1486 rc=0 actorTile=13896 targetTile=13696
f2_server: control elev slot=0 elevator=19 level=1 -> map=109 elev=1 tile=15099
f2_server: control elev with no elevator offered (session 3)
```

## Root cause
The request comes from the elevator's **spatial script** (`spatial_p_proc` →
`metarule(METARULE_ELEVATOR)` → `scriptsRequestElevator`), and a spatial script fires on every
hex a critter enters inside its trigger zone (`server_anim.cc` per-tile
`scriptsExecSpatialProc`, same as vanilla's `_object_animate`). In vanilla that does not matter:
the first request opens a modal panel and the ride clears the walk. On the dedicated server
the handler answers the request at once (stream `EVENT_ELEVATOR_PROMPT`, return -1) and the
walk continues, so a three-hex walk into the car produced three offers.

The viewer latches offers in a one-shot boolean (`_elevatorPending`): the first offer opened
the panel, the second and third re-armed the latch while the panel was up, and the main loop
opened the panel again after the ride. Its `elev` answer found the offer already consumed by
the first ride ("no elevator offered").

## Fix
- `elevatorSelect` streams nothing while the same player already holds an offer for the same
  elevator (`serverControlElevatorOfferPending`). One walk, one panel.
- The offer is released by the ride (`elev`), by the new `elevcancel` verb the client sends
  when the panel closes without a choice (Escape, or the screen could not open), on world
  reload (already), and now also when the session unbinds — a stale offer would otherwise deny
  that elevator to the next player in the slot.
- `elevcancel` bypasses the busy gate (it is not an action).

## Verification
`python D:\Games\f2dev-sandbox.py elev <f2_server.exe>` against a copy of the Navarro
quicksave: one "offered" line per approach walk (three with the previous build), the ride
applies, `elevcancel` followed by a re-entry raises a fresh offer.
