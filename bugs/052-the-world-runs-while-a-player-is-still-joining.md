# 052: The world runs while a connection is in but nobody is logged in, and a joining player's body takes a fight alone

**Status**: FIXED (2026-09-30), proven on a sandbox with wire bots; not yet confirmed in live
play.
**Files**: `src/server_main.cc` (the sim gate), `tools/issue_wire_proof.py` (`joinfreeze`).

## Symptom
GitHub issue 16: "Server was running, I joined the game (solo) and spawned where I left
last time (around geckos). Gecko attacked me instantly even before the 'server status' text
could load in the msg window. The weird part: Gecko had multiple consecutive turns (like
8-10) and damaged me badly before I finally received the server status and was able to
fight back. Expected behavior: Game should be paused until at least one player fully joins."

## Root cause
A keepalive server freezes its world when nobody is playing, and the test was "no client
connected" (`netSink.clientCount() == 0`). A session that has connected but not yet logged
in thawed it: the pre-join account query, the creation screen for a new name, and the load
all happen on a live connection before `login` binds a slot. During that window every body
is unpiloted. The host's body is never parked (slot 0 stays on the map), so a fight it was
in when its player left ran on: the combat barrier ends the turn of a body whose slot is
unbound, the enemies take theirs, and so on, round after round, until the login landed. The
player then watched the backlog play out as the join finished: "multiple consecutive turns".

Reproduced on v1.4.0 with a bot that reconnects and waits four seconds before logging in:
twelve turns ran in that window, the host's own among them (ended by itself).

## Fix
The world freezes while no slot is bound (`serverControlHasClaimant()`), not merely while no
client is connected. The inbound drain still runs on a frozen beat, so the login that binds
the first slot is served and thaws the world; the barrier then waits for that player as it
always did. A CMD-only server and non-keepalive runs are unchanged.

What remains: the beat in which a player drops still advances once before the freeze (the
gate is read before the drain that releases the slot), so one or two enemy turns of the
round in progress can run then. They would run anyway when the fight resumes.

## Verification
`python -u tools/issue_wire_proof.py joinfreeze ...`: the host, in a fight with a raider and
the villagers it pulled in, drops; the server sits with nobody in for six seconds; a
connection comes back and waits four seconds before logging in, then stays silent.

| server | turns streamed before the login | after the login |
|---|---|---|
| v1.4.0 (`--expect-defect`, 4/4) | 12 (851, 1856, 1079, 1150, 1079, 1091, 1042, 1003, 991, **1**, 977, 1042) | none in 22 s (the fight had moved on) |
| fixed (3/3) | none | the round in progress (1150, 1023, 1003, 991), then the host's turn, which waits |
