# 028: An elevator panel stops opening after you pick the floor you are already on

**Status**: FIXED (2026-09-11), not yet confirmed in live play.
**Files**: `src/server_control.cc` (busy gate, `elev`), `src/elevator_data.cc` (`elevatorRideApply`).

## Symptom
Live report (solo world, Navarro's center elevator): pressing G on the panel while
already on the ground floor, then using the panel again, did nothing at all: no
panel, no message. A different elevator still worked, and riding it made the first
one work again. Server log: `elevator 19 offered to slot 0 (start level 0)`, then
`control elev dropped (actor busy, session 2)`, then every later use of that panel
fired with no offer line.

## Root cause
The panel is offered by the elevator's script while the rider's use animation is
still playing, and the out-of-combat busy gate drops a player's mutating verbs until
that animation's window closes. `elevcancel` was on the gate's bypass list; `elev`
was not. The client panel (`elevatorPickLevel`) animates its gauge for 1 to 3
seconds before answering with a different floor, which always outlasted the window,
but answering with the floor you are already on skips the gauge and answers at once,
inside it. The gate dropped the answer before the `elev` handler could release the
pending offer, and the repeat-offer guard from bugs/009 (`elevatorSelect`) then
answered every later request for that elevator silently. Only a ride on another
elevator (the pending offer is one value per slot), a reconnect or a reload cleared
it. The handler's two refusal paths (level out of range, no destination) had the
same leak.

## Fix
- `elev` joins the busy gate's bypass list. It answers a prompt the server itself
  issued, and the handler checks the offer, the level range and the destination on
  its own. Vanilla never made the panel's answer wait on the use animation either.
- The handler releases the offer before validating, so every answer, accepted or
  refused, ends the offer.
- A same-map ride that does not change floors moves only the rider (onto the car's
  tile, as vanilla does with `gDude`). Moving the other online players exists to keep
  the party off split elevations; on the rider's own floor it would only pull a second
  player into the car.
