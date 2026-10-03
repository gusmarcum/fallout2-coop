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

## Follow-up (2026-10-02, with bugs/058)
The first version left one live beat: the gate was read before the drain that releases the
slot, so the beat in which the last player dropped still advanced. This write-up said the
enemy turns of that beat "would run anyway when the fight resumes", which missed the point:
the dropped player's own turn was ended in that beat (an unbound body does not hold a turn),
and a fight nearly always sits on the human's turn. So a player who quit mid-fight came back
a full round behind: v1.4.1 ran four enemy turns before giving the host a turn again.

`serverServe` now runs the drain first and asks the gate after it, so the beat that notices
the drop is frozen and the turn is still theirs when they return. Their login re-arms the
turn's idle budget and announces the turn again (bugs/058 says why the client needs that).

The same release fixes what this freeze broke in v1.4.1: a frozen server sent a joining
client no world at all, so nobody could start a session (GitHub issue 32, bugs/058).

## Verification
`python -u tools/issue_wire_proof.py joinfreeze ...`: the host, in a fight with a raider and
the villagers it pulled in, drops; the server sits with nobody in for six seconds; a
connection comes back and waits four seconds before logging in, then stays silent.

| server | turns streamed before the login | after the login |
|---|---|---|
| v1.4.0 (`--expect-defect`, 4/4) | 12 (851, 1856, 1079, 1150, 1079, 1091, 1042, 1003, 991, **1**, 977, 1042) | none in 22 s (the fight had moved on) |
| v1.4.1 (3/3 at the time) | none | the round in progress (1150, 1023, 1003, 991), then the host's turn, which waits |

Since the follow-up the proof drops the host on its own turn, reads "frozen" off the sim
clock stamped on the frames sent before the login, and repeats the run for a second player
who comes back alone (bugs/058 has the table): 9/9 on the fixed build, the turn still the
returning player's own.
