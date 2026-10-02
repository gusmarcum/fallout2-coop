# 059: A critter crouches and grabs at a weapon its walk did not reach

**Status**: FIXED (2026-10-02), proven on a sandbox with a wire bot; not yet confirmed in
live play.
**Files**: `src/server_anim.cc` (`serverAnimDeferredWalkWillReach`, the forced reach
check), `src/pres_record.cc` / `.h` (`presRecordCutHere`), `tools/issue_wire_proof.py`
(`reach`).

## Symptom
GitHub issue 13, second follow-up: "I still experience animation loops. NPC tries to pick up
a spear from the ground from inappropriate range, and I believe he still have some action
points at this point." v1.4.1 had stopped the crouch of an attempt made with no action
points left (bugs/047). This is the attempt made WITH action points, but not enough of them
to reach the weapon.

## Root cause
An approach is one sequence in vanilla: walk (as far as the action points go), then a
forced `_is_next_to`, then the gesture. When the walk fell short the forced check ends the
sequence and the gesture is never shown.

On the server the sequence is recorded for the viewers and the walk is applied afterwards.
bugs/042 made the server judge the reach check after the real walk, so nothing is TAKEN
from out of reach. But what the viewers are SHOWN had already been recorded and shipped by
then: the walk, the crouch and the grab's sound, all five ops. A viewer has no reach check
of its own, so it played the walk and then the crouch from wherever the walker stopped, the
weapon still hexes away.

## Fix
The reach check is now answered when it is registered, for the recording's sake. With a walk
stashed, `serverAnimDeferredWalkWillReach` runs the commit's own arithmetic dry: the same
path, the same stop short of an object, the same cap, and the same charge per step
(`movementChargeApForStep`: the step is taken, then paid for). If the walk will not end next
to the target, `presRecordCutHere` marks the recording, and `presRecordSeqEnd` drops
everything recorded after the mark, with the transients and the cost those ops added. What
ships is what vanilla shows: the walk, and nothing more. A check that fails with no walk
stashed cuts the same way.

The commit still judges the real walk for what is taken. A script that stops the walker on
the way is the one thing the dry run cannot see; the worst case there is the old picture.

## Verification
`python -u tools/issue_wire_proof.py reach ...`: the host goes for a spear twelve tiles off
with nine action points, then for one six tiles off.

| server | far attempt, shipped | near attempt, shipped |
|---|---|---|
| v1.4.1 (5/6, the new check fails) | 5 ops: the walk, the crouch and its sound | 5 ops |
| fixed (6/6) | 3 ops: begin, the walk, end | 5 ops |
