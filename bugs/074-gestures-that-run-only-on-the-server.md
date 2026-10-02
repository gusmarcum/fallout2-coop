# 074: Gestures that run only on the server

**Status**: FIXED (2026-10-02), proven on a sandbox, on the wire and with the real client
in both seats; not yet confirmed in live play.
**Files**: `src/combat_ai.cc` (`_ai_magic_hands`), `src/interpreter_extra.cc`
(`scriptGestureRecordBegin`, `scriptGestureRecordShip`, `opAnimateStand`,
`opAnimateStandReverse`, `opAnim`, `scriptSequenceShow`), `tools/issue_wire_proof.py`
(`gestures`), `tools/client_screen_proof.py` (`syncwalk`, `syncwalk2`).

## Symptom
GitHub issue 40: "Enemy uses item in fight - Jet, Stimpak. Expected: Animation for use is
visible. Actual: No animation at all. Only indication of used item is log window. The same
goes for stealing kids in Den, no indication for their stealing attempts."

## Root cause
On the dedicated server an animation is nothing unless a record section is open to catch
it; what the section catches is shipped as a sequence that every viewer plays through its
own engine. Attacks, walks in a fight, weapon draws and getting up each open one. Two
families never did:

- the combat AI's item gesture (`_ai_magic_hands`: a stimpak or a chem taken, a reload,
  a dry weapon put away), raised hands and then the message line;
- everything a script animates: `anim()` and `animate_stand_obj` (the Den's orphans raise
  their hands at a pocket and stand again), and a script's own `reg_anim` sequences.

So the message line or the missing caps was all a player got.

## Fix
`_ai_magic_hands` records its bracket and ships it as the critter's sequence, in front of
the line that says what it did.

`animate_stand_obj` and its reverse do the same for a critter. So does `anim()` for a
critter's animations: its own bracket stays what it was (on the server that is the art
it sets), and the same ops are registered once more into a record section and shipped,
ending in the art the server now holds. A script's own sequence is kept as it is
registered and, when the script closes it, registered once more into a record section
and shipped, if it was animations only. A sequence with a walk in it is not shown (the
walk is the server's own stepped one, and a gesture replayed beside it would run at the
wrong moment).

Critters only: an animation on scenery leaves it on its last frame in the real engine,
which is state the server would have to hold too, and that is not attempted here. And
only a critter that has its network id: a map's scripts run while the map loads, before
the ids are handed out, and the recorder takes an object it cannot name for one the
sequence creates. Nothing is sent during a load, and the art is settled either way
(bugs/072).

Together with bugs/072 this is also how a viewer who is present sees a script lay a
critter down: the sequence is shown, and the art the server settles on is held on the
viewer until its own replay has finished (bugs/077 is what lets go of it then).

## Verification
`python -u tools/issue_wire_proof.py gestures ...`: each is read off the wire, as the
animations recorded for the critter in question.

| | v1.4.1 (`--expect-defect`, 4/4) | fixed (4/4) |
|---|---|---|
| a Den orphan tries the host's pocket | no sequence | hands raised (animation 11), then standing (0) |
| a raider fetches an empty pistol and finds it dry | no sequence | its raised hands (animation 11), then "Raider is out of ammo for the 10mm Pistol." |

A stimpak, a dose of Jet and a reload go through the same one function as the dry
pistol; they were not each set up.

With the real client, in the host's seat and in a joining player's (`syncwalk`,
`syncwalk2`, 12/12 each): the client is sent the orphan's sequences and plays them, and
afterwards its copy of every object on the map matches the server's.
