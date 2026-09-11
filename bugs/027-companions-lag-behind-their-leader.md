# 027: Companions lag behind their leader and stop short of where you are

**Status**: FIXED (2026-09-11), not yet confirmed in live play.
**Files**: `src/server_loop.cc` (`serverTick`).

## Symptom
Live report (solo world, Sulik + Vic in the party): companions trail well behind
the player, or stop somewhere the player USED to be and stand there "confused"
before catching up much later. Who they follow is correct; when they re-check is
the problem.

## Root cause
Out of combat, a companion only moves because its script's `critter_p_proc`
measures the distance to `dude_obj` (resolved to its leader in co-op) and orders
a run. The engine services critter procs round-robin: `_script_chk_critters`
fires ONE critter script per background tick, shared among every critter script
on the map. Vanilla pumps that tick once per rendered frame (tens of times a
second); the dedicated server pumps it once per beat (`_process_bk` in
`serverTick`, 10/s at the default `F2_SERVER_PACE_MS=100`). On a map with ~40
critter scripts a companion gets one follow check every ~4 seconds instead of
well under a second. It paths to where its leader was at check time, arrives,
and idles until its next turn in the cycle. The dilution also pauses entirely
while any player is in dialog or in combat (both global in co-op), which vanilla
also does, but from the much faster base rate.

## Fix
`serverTick` now gives party members a priority heartbeat: every 5 beats
(500 ms at the default pace) it fires each companion's `critter_p_proc`
directly, in addition to the vanilla round-robin, under the same gates the
round-robin honours (no dialog, no combat, no movie). Filters: critter-pid
party members only (never the dude, never player actors - extras are not
`gPartyMembers`), skipping hidden, dead, and script-less members.

Rapid refires are vanilla-safe by precedent: on a sparse map (few critter
scripts) the vanilla round-robin already reaches each critter many times a
second, so companion follow scripts are written to tolerate being re-entered
(distance thresholds, anim-busy guards). Wild critters keep the vanilla
round-robin cadence: aggro and perception pacing are untouched, as is
single-player (the heartbeat lives in the server loop only, which the client
viewer and the probe/golden legacy paths never run).

## Diagnostics
`F2_TRACE_PARTY=1` on the server prints one `[party]` roster line per member
every ~25 s (sid, tile, elevation, distance to leader), and flags a member
with `sid=-1` as "NO SCRIPT - cannot follow". Live report 2026-09-11: with
three companions, Cassidy specifically "won't follow correctly" while Sulik
and Vic do; admin `party` sampling showed him keeping up at the coarse level
(three samples over 50 s, always within a few rows of the party), so the
symptom is follow QUALITY, which this heartbeat addresses. If he still
misbehaves after this fix, the trace decides between a script problem and a
follow-loop problem.

## Not covered (known, separate)
The recruiter link (`ownerSlot`) is not persisted in saves; after a server
restart a companion follows the nearest player until re-recruited. Solo worlds
are unaffected (the leader is always the host). Tracked for a later pass.
