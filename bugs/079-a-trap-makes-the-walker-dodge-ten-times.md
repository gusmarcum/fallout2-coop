# 079: A trap makes the walker dodge ten times in a row

**Status**: FIXED (2026-10-13), proven on a sandbox; not yet confirmed in live play.
New in v1.4.2: a regression from bugs/074.
**Files**: `src/interpreter_extra.cc` (`opAnim`, `scriptAnimStillShown`,
`scriptAnimNoteShown`), `tools/issue_wire_proof.py` (`trap`).

## Symptom
GitHub issue 55: "1.4.2: In Arroyo temple, setting off a trap will force character into
an uninterruptable 10+ dodge loop. It was not present in prior versions."

## Root cause
The Temple's spear traps (`ATSrTrp0.int` to `ATSrTrpF.int`, floor triggers on the second
level of `arcaves.map`) move their spear one hex at a time, all inside one run of the
script, and at every hex call `anim()` on whoever stepped on the plate: a dodge (13) when
the spear is going to miss, a flinch (15) when it hits. The spear starts seven hexes from
the plate and ends on the walker or three hexes past, so that is seven or ten calls.

In the real engine the first call starts the animation and every later one is refused,
because the critter is still inside a sequence (`_check_registry`, `animation.cc`). The
script leans on that: the player flinches once.

On the dedicated server an animation is nothing, so a critter is never "still inside"
one. Until v1.4.1 that did not matter, because nothing a script animated was sent to the
players at all. bugs/074 (GitHub issue 40) made `anim()` something the players are shown:
each call is recorded and sent as a sequence of its own, named for its critter. A viewer
plays such sequences one after another per critter. All seven or ten arrived, and the
player stood through every one of them.

## Fix
The server remembers, per critter, until when the last `anim()` it sent is on the players'
screens (the recorder's own figure for the sequence, `presRecordCostMs`), and sends no
other `anim()` for that critter before then. What the opcode does to the critter's state
is applied every time, as before; only the showing is refused, which is all the real
engine refuses.

Only `anim()` is covered. `animate_stand_obj` and a script's own `reg_anim` bracket are
sent as before: the Den orphan's "hands up, then stand" (bugs/074's own proof) is an
`anim()` followed by an `animate_stand_obj`, and both still go out.

A pull request from the reporter (61) fixed the same symptom on the receiving side, by
sending these three reactions with no
critter named so that a viewer plays them at once and lets its own engine refuse the
repeats. The cause is on the sending side and is fixed there instead: the server no
longer sends what the real engine would not have played.

## Proof
`python -u tools/issue_wire_proof.py trap <f2_server.exe> <sandbox> 9400 9401`

The host is put a hex from the first trap and walks onto it. The spear's creation is read
off the server log, and the recorded sequences for the host are counted on the wire.

- v1.4.2 (`--expect-defect`): 7 flinches sent for one spear.
- fixed: 1 reaction sent, the script's other 9 calls refused (the log says so per call).
