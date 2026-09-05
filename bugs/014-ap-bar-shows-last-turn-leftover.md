# 014 — AP bar shows last turn's leftover at the start of a new turn

**Status**: FIXED on the viewer (2026-09-05). Display only; the server's AP was always right.
**Files**: `src/client_net.cc` (`applyTurnStart`), `src/client_present.cc/.h`
(`clientCombatAnimForgetAp`).

## Symptom
Rarely (owner: "1% of turns"), a player's turn begins with the action-point bar showing a
few points (4 of 11) although the server has the full budget and every action is priced
against 11. Spending one point redraws the bar correctly.

## Cause
The viewer defers an `OBJECT_DELTA_AP` for its own body while its own recorded walk is
still replaying (`clientCombatAnimDeferAp` parks the value in the walk's hold frame), so
the bar ticks down per hex instead of jumping ahead of the sprite. `resolveHeld` writes the
parked value to the object when the frame is reaped.

When the walk was the last action of the turn and the AI turns are short, the next round's
`TURN_START` (ap = 11) can arrive while that walk is still replaying. `applyTurnStart` sets
the mirror and the bar to 11; the reap then lands afterwards and writes last turn's leftover
(4) back onto the mirror; `tickApBar` sees shown (11) > authoritative (4) and sinks the bar
to 4. Nothing on the server moved.

## Fix
A turn start is the authoritative AP baseline. `applyTurnStart` now drops every AP value
still parked behind the player's own animation (`clientCombatAnimForgetAp`; the held
positions stay untouched) before applying the event's AP, and logs how many it dropped
("turn start dropped N stale AP value(s) parked behind our walk") so the next sighting is
confirmable from debug.log.
