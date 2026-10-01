# 053: "Music could not be restarted (see debug.log)" in the message window on a join

**Status**: FIXED (2026-09-30), proven on the client binaries; not yet confirmed in live play.
**Files**: `src/client_net.cc` (`musicWatchdog`), `tools/client_screen_proof.py` (`musicline`).

## Symptom
GitHub issue 18: "Sometimes joining players see this log. Debug.log file is nowhere to be
found in game folder."

## Root cause
The client's music watchdog restarts the background track whenever it stops (a join, a
rebaseline or a map load starves the mixer and the sound library retires the track). When
the restart itself failed once, the watchdog printed "Music 'X' could not be restarted (see
debug.log)" to the message window. The restart usually fails for the same reason the track
stopped, the mixer still starved by the join, and the watchdog tries again ten seconds
later anyway; the release's fallout2.cfg does not write a debug.log, so the line sent
players to a file that does not exist.

## Fix
The failure is logged (debug.log, when enabled) and the watchdog keeps trying; nothing is
shown. A missing music file still shows as silence, which the one-time audio notice on
join already explains for the cases it can detect.

## Verification
`python -u tools/client_screen_proof.py musicline ...` reads the client binary: the
message-window text must be gone and the quiet log line present.

| client | "could not be restarted (see debug.log)" | "could not be restarted (rc=%d); will keep trying" |
|---|---|---|
| v1.4.0 (`--expect-defect`, 2/2) | present | absent |
| fixed (1/1) | absent | present |

The restart loop itself is unchanged; the `clock` and `invhp` proofs run the client through
joins and screens.
