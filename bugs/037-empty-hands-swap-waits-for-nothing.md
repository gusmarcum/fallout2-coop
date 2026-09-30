# 037: Swapping between two empty hands (punch and kick) shows the wait cursor for nothing

**Status**: FIXED (2026-09-30), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/main.cc` (the B key, `viewerHandSwitchAnimates`, the out-of-combat gate),
`tools/client_screen_proof.py` (`hands`).

## Symptom
GitHub issue 7: "During combat switch [B] unarmed attack from punch to kick and vice versa.
Game shows deadlock wait for couple of seconds as if an animation is being played, but
character doesn't do anything."

## Root cause
B flips the active hand at once and sends `hand <n>`; then the viewer waits for the server's
answer before it takes more input: in combat `actionPending`, out of combat
`handSwitchPending`. The wait is released by the switch's put-away and take-out replay.

The server records that replay only when there is something to put away or take out
(`serverControlSwapHand`: the weapon nibble of the current fid, and a weapon in the new
hand). Between two empty hands there is neither, nothing is sent, and the wait ran out its
whole timeout with the watch cursor up.

## Fix
The viewer asks the same question of its own mirror before it waits
(`viewerHandSwitchAnimates`). With nothing to animate it does not wait in combat, and out of
combat the latch still runs (a refusal can still put the hand back) but no longer blocks
input.

## Verification
`python -u tools/client_screen_proof.py hands ...`: the second player's hands are empty (the
server logs `oldCode=0 newCode=0` for their swaps). The keyboard presses B three times a
quarter second apart, every three seconds, first in peace and then in a fight. Presses the
server received, per burst:

| client | out of combat | in the fight, on the player's turn |
|---|---|---|
| v1.3.2 (`--expect-defect`) | 1 of 3 in each of 6 bursts | 1 of 3 in each of 14 bursts |
| fixed | 3 of 3 in each of 6 bursts | 3 of 3 in each of 14 bursts |

`viewerHandSwitchAnimates` is `serverControlSwapHand`'s own `oldCode`/`newCode` test on the
viewer's mirror, so a swap that does draw or holster a weapon still waits for it.
