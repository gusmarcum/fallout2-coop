# 036: The idle head scratch blocks every click until it ends

**Status**: FIXED (2026-09-30), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/animation.cc` (`animationIsBusyIgnoringFidgets`), `src/main.cc` (the
out-of-combat input gate), `tools/client_screen_proof.py` (`fidget`).

## Symptom
GitHub issue 15: "The random head-scratching animation interrupts the gameplay flow and
displays a waiting icon; you can't perform any actions until it finishes."

## Root cause
The viewer blocks input out of combat while its own character is animating (feature A, the
out-of-combat twin of the combat busy gate): `oocBusy` read `animationIsBusy(gDude)`. That
function skips a one-step stand animation, but the dude's own fidget is two steps, its sound
and then the animation (`_dude_fidget` adds the sound only for the dude), so the head scratch
counted as an action: watch cursor, clicks eaten, until it finished.

Vanilla never waits on a fidget. `_dude_fidget` registers it INSIGNIFICANT, and the next
request for the same critter ends such a sequence (`_check_registry`). The viewer's move
click already does the same (`reg_anim_clear(gDude)` before `mv`, the "runs on one leg" fix),
but the click never got past the gate to do it.

## Fix
`animationIsBusyIgnoringFidgets` is `animationIsBusy` minus the sequences flagged
INSIGNIFICANT, and the out-of-combat gate uses it. The flag survives the trip to the viewer:
the server records `reg_anim_begin`'s options and the replay passes them back to
`reg_anim_begin`, and the viewer's own fidget ticker registers it the same way. A draw,
holster, door or pickup is still waited for.

Where the fidget comes from: only the client. The server never registers `_dude_fidget`
(its presenter's worldEnable is a no-op); a viewer strips the ticker after its first world
load, and the client presenter's worldEnable adds it back the first time any screen that
switched the world off (inventory, character sheet, pipboy, ...) closes. From then on the
client idles its own critters, its own character included.

## Verification
`python -u tools/client_screen_proof.py fidget ...`: the real client opens and closes the
inventory once (which turns the fidget on), then presses G (pick up here, gated by the same
out-of-combat block as a click) five times a second for 100 seconds. The server logs every G
it receives.

| client | presses received | silences over 0.7 s between two presses |
|---|---|---|
| v1.3.2 (`--expect-defect`) | 463 of 500 | 5, of 1.5 to 1.9 s: the fidgets |
| fixed | 500 of 500 | none (longest 0.38 s) |
