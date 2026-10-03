# 061: Space pressed while the enemy's turn is being shown ends the player's next turn

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/main.cc` (the viewer loop's end-turn and end-combat keys),
`tools/client_screen_proof.py` (`earlyspace`).

## Symptom
GitHub issue 30: "Players can queue end turns while it is not their turn. It is a minor
thing but impatient players may miss turn in advance by pressing unnecessary spaces during
ai controlled turns."

## Root cause
Nothing is queued. The server resolves the whole enemy side in one beat, so by the time a
viewer starts showing the first enemy attack, the server is already waiting on the player
again. The end-turn and end-combat keys were sent whatever the presentation was doing (they
are the way out of a wedged client, so they were deliberately exempt from the busy gate),
and the server accepts an end of turn from the actor whose turn it is. So a Space pressed
during the show reached a server whose current actor was this player, and ended a turn the
player had not seen begin.

## Fix
Space and Enter wait for the presentation like every other combat key: nothing is sent
while `combatBusy` is set, which is also vanilla (no input while animations play). The way
out of a wedged client stays, through the watchdog that was already there: after eight
seconds without any presentation progress `combatBusy` is cleared, and Space goes out
whatever the mirror believes. The client logs each press it held back.

## Verification
`python -u tools/client_screen_proof.py earlyspace ...`: the real client, alone, fights a
raider and presses Space in pairs half a second apart.

| build | result |
|---|---|
| v1.4.1 (`--expect-defect`, 2/2) | 4 ends of turn accepted, 2 of them within two seconds of the one before: each pair ended two turns |
| fixed (2/2) | no two ends of turn within two seconds; the client held back the second press of each pair |
