# 060: A corpse lists what the critter lost while it was alive: "That item is gone."

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client as the observer;
not yet confirmed in live play.
**Files**: `src/object_delta.cc` (`objectDeltaScan`), `tools/client_screen_proof.py`
(`corpseloot`).

## Symptom
GitHub issue 13, second follow-up: "if he originally had a spear but he threw at me and I
picked it up, his body will still have a visible loot on client side. But when I try to take
it, game says 'This item is gone'."

## Root cause
A viewer keeps a copy of every critter's pack. For a LIVING critter the copy is only kept
roughly: an inventory delta moves the equip flags, updates ammo, and (since bugs/048) adds a
stack the copy never had, but it never takes one away, because an attack replay in flight
may still hold the item object. So a spear the critter threw, a stimpak it used, or anything
taken off it stays in the viewer's copy.

The copy is put right in full (add, remove, quantities) when a delta carries the pack of a
critter that is dead. Nothing changes in a pack at the moment of death, so the death's delta
carried no pack and that reconcile never ran. The corpse kept the stale list, and the server,
whose list was right, refused the take.

## Fix
On the dedicated server, the delta of a critter whose `DAM_DEAD` bit was set this beat
carries its inventory whether or not the pack changed. Every viewer then rebuilds its copy
of the corpse's pack from the server's at the death, through the path that already existed
for it (removals unlinked now and freed after the fight). Older clients have that path too.
The probes' streams, and so the goldens, are unchanged.

## Verification
`python -u tools/client_screen_proof.py corpseloot ...`: a raider is given a stick of
dynamite in a steal session (which the observer's game mirrors in full while the session is
open), the dynamite is taken off the living raider again with no session open, and the
raider is killed. The observer's real client logs each rebuild of its copy.

| build | the observer's copy of the pack |
|---|---|
| v1.4.1 (`--expect-defect`, 3/3) | 1 item after the plant, never rebuilt again: the corpse lists the dynamite |
| fixed (3/3) | 1 item after the plant, rebuilt at the death with 0 |
