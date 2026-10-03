# 076: A critter killed while knocked down does not bleed, and its corpse is left standing

**Status**: FIXED (2026-10-02), proven on a sandbox on the wire; not yet seen with the
real client or confirmed in live play.
**Files**: `src/combat.cc` (`combatNoteKnockdownFall`, `combatKnockdownFall`,
`combatForgetKnockdownFall`, `_apply_damage`), `src/combat.h`, `src/actions.cc`
(`actionKnockdownFall`, `_show_damage_to_object`), `src/actions.h`, `src/critter.cc`
(`critterKill`, `_dude_standup`, `_critter_wake_clear`), `tools/issue_wire_proof.py`
(`pronekill`).

## Symptom
GitHub issue 39: "Every killed enemy leaves visible blood pool after finishing blow.
Actual: Sometimes killed enemy don't bleed at all. It is rare, but can be spotted
sometimes."

## Root cause
The blood under a corpse is an animation (`ANIM_FALL_BACK_BLOOD`, `ANIM_FALL_FRONT_BLOOD`),
chosen by the fall the critter is lying in. A critter killed on its feet falls and then
bleeds. One killed where it LIES does not fall again: it gets the blood alone, and the
fall is read off its art (`_show_damage_to_object`, the prone branch).

On the dedicated server an animation is nothing, so a knocked-down critter keeps its
STANDING art; that it is down is only in its flags. The prone branch read "standing",
`_action_blood` had no fall to match, and the kill was recorded with no animation at all.
`critterKill` has the same reading in it: prone, but no fall in the art, so it left the
art alone. The corpse stayed a flattened standing critter on the server (and so in every
snapshot after), and on a viewer whatever the earlier knockdown replay had left: lying,
no blood. That is the "sometimes": enemies finished off while down.

## Fix
The server keeps the fall. When a blow knocks a living critter down or out
(`_apply_damage`), the fall it is shown taking is worked out the way the recorded
sequence works it out (`actionKnockdownFall`: from the front onto its back, swapped for
want of art or room) and kept for that critter until it stands, wakes or dies.

- The prone branch of `_show_damage_to_object` uses the kept fall, so the kill is shown
  with the matching blood animation.
- `critterKill` leaves the corpse lying the same way up, in its blood where the art has
  that (which is what the kill is shown ending in).
- `_dude_standup` gets up with the animation that matches the fall. It always chose
  "prone to standing" on the server, for the same reason.

Dedicated server only in each place; a client's own engine has the fall in the art.

Not changed, and seen on the wire while proving this: a critter killed on its feet is
given the one generic corpse art by the server (face down in its blood) whatever death
was shown, and a living knocked-down critter keeps its standing art on the server, so a
player who joins mid-fight is sent it standing. Neither was reported.

## Verification
`python -u tools/issue_wire_proof.py pronekill ...`: the host knocks a raider down with a
forced critical aimed at the leg, and the operator kills it where it lies.

| | v1.4.1 (`--expect-defect`, 4/4) | fixed (4/4) |
|---|---|---|
| animations recorded for the raider in the kill | none | 34, the blood under a body on its back |
| art streamed for the corpse | none (it keeps its standing art) | 62, the single frame of 34 |
