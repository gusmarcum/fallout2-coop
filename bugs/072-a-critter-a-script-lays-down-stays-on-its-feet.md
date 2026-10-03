# 072: A critter a script lays down stays on its feet

**Status**: FIXED (2026-10-02), proven on a sandbox, on the wire and with the real client
in both seats; not yet confirmed in live play.
**Files**: `src/interpreter_extra.cc` (`scriptSettleCritterArt`, `opRegAnimFunc`,
`opRegAnimAnimate`, `scriptSequenceSettlePoses`, `opAnimateStand`,
`opAnimateStandReverse`), `tools/issue_wire_proof.py` (`bess`),
`tools/client_screen_proof.py` (`syncwalk`, `syncwalk2`).

## Symptom
GitHub issue 42: "Enter Modoc and approach brahmin Bess but don't use Doctor. Expected:
Bess lies on her side with injury to her leg. Actual: Bess stands as if she's healthy."

## Root cause
Bess's script (`mcBess`) lays her down on every map entry with a sequence of registered
animations: `reg_anim_animate` hit, fall back, and the lying single frame, between
`reg_anim_func` begin and end. In the real engine a critter is left in the art of the
last animation that played, and the end of a sequence stands it back up only if that
art is not a lying one (`_anim_set_end`, `_critter_is_prone`).

On the dedicated server an animation is nothing: `server_anim.cc` applies no art for
one (they are presentation, recorded for viewers at most, and a script's are not even
recorded). So the sequence left no trace and Bess stood on her broken leg for everyone. (Her
script knocks her over the same way when a healed Bess is pushed; that path was not
tested, but it ran through the same nothing.)

The same nothing, the other way round: the `anim()` opcode DOES set art on the server,
and the `animate_stand_obj` that scripts follow it with, which stands the critter again
in the real engine, did not. A Den orphan that had tried a pocket (hands raised, then
stand) kept its hands-raised art on the server for good, and every player who entered
the map afterwards was sent it that way. The mirror audit found that one (`syncwalk`).

## Fix
The server settles a critter's art after a script's animation, with the last animation
the script played on it (`scriptSettleCritterArt`): a fall or a lying single frame leaves
it lying (in the single frame); anything else leaves it standing. That runs when a script
closes its own sequence, and after `animate_stand_obj` and its reverse. Scripts only, out
of combat only (scripts cannot register animations in a fight), dedicated server only (a
client's real engine does this itself; the goldens are unchanged). The pose then reaches
viewers the way any art does: in the snapshot of a map being entered, or as an art
delta.

Any other script that lays a critter down this way was affected the same.

## Verification
`python -u tools/issue_wire_proof.py bess ...`: the host enters Modoc and Bess's art is
read off the snapshot; the operator makes the host a good doctor, the host sets her leg,
leaves the map and comes back.

| | v1.4.1 (`--expect-defect`, 2/2) | fixed (4/4) |
|---|---|---|
| Bess on arrival | art animation 0, standing | 48, lying on her back |
| after the Doctor skill succeeds | | 0, standing |
| after leaving and coming back | | 0, standing (she follows the host now) |

With the real client, in the host's seat and in a joining player's (`syncwalk`,
`syncwalk2`, 12/12 each): in Modoc the client's copy of every object matches the
server's, Bess lying included, and in the Den it matches after an orphan has raised its
hands and stood again.
