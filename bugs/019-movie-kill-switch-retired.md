# 019: Cutscenes never played, because a kill switch was set for a crash it did not cause

**Status**: FIXED (2026-09-09).
**Files**: `src/server_stubs.cc` (`gameMoviePlay`), `src/game_movie_state.cc`
(`gameMovieServerBarrier` timeout), `src/server_main.cc` (boot notice), `src/server_admin.cc`
(`movdone` console verb), `README.md`, `DEDICATED_HOWTO.md`.

## Symptom
No scripted cutscene ever played in the live worlds: not the tanker leaving San Francisco
for the oil rig, not the rig going up after the escape. The engine marked each movie as seen
and carried on as if it had been watched.

## Root cause
`F2_MOVIES=0` in both server launch files, and in the sample launch file in the README.

The switch went in on 2026-09-02 because a joining player's client crashed walking into the
Temple of Trials, which was read at the time as a client whose game data could not render
the cutscene. The real cause was mods installed on that player's copy of the game; an
unmodified client plays the cutscene fine. The switch was never revisited, and every world
started from the docs inherited a silent no-cutscenes setting.

## Fix
- `gameMoviePlay` on the dedicated server always projects the movie to the viewers. A
  leftover `F2_MOVIES=0` in the environment is reported once at boot and ignored.
- The reason the switch existed was a real hazard: the barrier that pauses the world for a
  cutscene was released only by a viewer's `movdone`, so a room where no client could render
  the movie parked the server until a restart. The barrier now also releases on its own after
  three minutes of wall clock, with a console line, and the operator can release it at any
  time with `movdone` on the command channel. First ack still wins, so a healthy room never
  waits past the movie itself.
- Documentation updated; the sample launch file no longer sets the variable.

## What was NOT changed
The viewer's playback pipeline, the seen ledger, the first-ack release policy and the
`EVENT_MOVIE_STOP` broadcast that ends everyone else's playback when one player skips.
Clients must run unmodified game data; the server cannot protect a client from its own mods.

## Verification
Gate on the final binaries: server-loop and legacy goldens. The goldens run the client binary
in probe mode and never reach the server stub, and the barrier is inert with no viewer
attached, so both suites are unchanged by construction. The `F2_MOVIES=0` notice, the
`movdone` verb and the timeout line were exercised by hand on the sandbox server.
