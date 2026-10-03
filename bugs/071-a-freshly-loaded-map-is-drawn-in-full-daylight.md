# 071: A freshly loaded map is drawn in full daylight

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client in both seats; not
yet confirmed in live play.
**Files**: `src/server_loop.cc` (`serverEmitBaseline`), `tools/client_screen_proof.py`
(`nightmap`, `nightmap2`).

## Symptom
GitHub issue 37: "Go to Den, wait in West side until Midnight and go to East side. ...
Night magically changes into full day even though the game time still is 00:30. When
moving back to West side it didn't fix and was broken until next night."

## Root cause
The light level of a map is set by its script (darker at night), and scripts run on the
server only. A viewer's own map load puts the light at full day (`mapLoad`). The level
reached viewers one way: the world delta, which is a diff, sent when the level CHANGES.
A map load rebaselines that diff silently (`objectDeltaReset` takes the new map's level
as the starting point), so the level of a map that was just loaded was never said. The
viewer sat at full day until the level next moved, which at night is dawn. A player who
joined at night had the same daylight.

## Fix
The baseline every map change, load and join goes through now says the clock and the
light level outright, behind the snapshot. Dedicated server only: the probes' streams,
and so the goldens, are unchanged.

## Verification
`python -u tools/client_screen_proof.py nightmap ...`: the real client sees the Den's west
and east sides by day, waits on the west side until midnight, crosses east and comes
back; then it leaves and joins again, at midnight. The brightness of the world view is
read off the screenshots. `nightmap` has the real client alone, in the host's seat;
`nightmap2` has it join a session a wire client hosts.

| | west by day | west at midnight | east by day | east at midnight | west again | joined at midnight |
|---|---|---|---|---|---|---|
| v1.4.1, host's seat (`--expect-defect`, 4/4) | 66 | 25 | 62 | 62 | 66 | no picture (alone on v1.4.1 the join is issue 32's black screen) |
| v1.4.1, second seat (`--expect-defect`, 4/4) | 66 | 26 | 62 | 62 | 66 | 66 |
| fixed, host's seat (4/4) | 66 | 25 | 62 | 23 | 25 | 25 |
| fixed, second seat (4/4) | 66 | 26 | 62 | 23 | 26 | 26 |
