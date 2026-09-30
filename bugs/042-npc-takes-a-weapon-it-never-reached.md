# 042: An NPC takes a weapon from the ground it never reached ("telekinetic spear")

**Status**: FIXED (2026-09-30), proven on a sandbox; not yet confirmed in live play.
**Files**: `src/server_anim.cc` (held callbacks behind `_is_next_to`), `src/actions.cc`
(`actionPickUp`'s record branch, `actionIsNextToCallbackPtr`), `src/actions.h`,
`src/command.cc` (`pickup:PID` for the proof), `tools/issue_wire_proof.py` (`reach`).

## Symptom
GitHub issue 13: "I killed an enemy with a spear throw. Then, another approaching enemy picked
up my spear from under my feet with his telekinetic powers from like 20 hexes away and
equipped it. (He could only reach me on the next turn)."

## Root cause
An unarmed AI looks for a weapon on the ground (`_ai_search_environ`) and goes for it
(`_ai_retrieve_object` -> `actionPickUp`). Vanilla registers that as one sequence: the walk to
the item (capped at the AP left), a FORCED `_is_next_to` that ends the sequence when the walk
fell short, then the grab (`_obj_pickup`). Short of the item, nothing is taken, and the AI
remembers it and walks on next turn.

On the dedicated server, in combat, the pickup is recorded for the viewers. Two things of the
recording backend (`server_anim.cc`) met here:

1. The walk is STASHED and applied only at the commit, after the whole sequence was registered
   (the presentation must reach the wire before its state).
2. The state-bearing callbacks (`_obj_pickup`, `_obj_use`, ...) are applied the moment they are
   REGISTERED (the allowlist added so these outcomes stop evaporating), and `_is_next_to` is
   not one of them, so nothing ever asked it.

So the grab ran before the critter had taken a single step, from wherever it stood; the item
was then gone, and the walk that followed had nowhere to go. `actionPickUp` also applied
`_obj_pickup` a second time after the commit, a leftover from before the allowlist (itemAdd
refused the duplicate; the item's pickup script ran twice).

A first attempt at this fix (a reach check in `actionPickUp` after the commit) came too late
for the same reason and did nothing; the proof below caught it.

## Fix
In a record section, the walker's own state callbacks are HELD (`gDeferredCallbacks`), with
`_is_next_to` recorded between them as a gate, and the commit runs them after the real walk,
in order, stopping at a gate the walker does not pass: vanilla's order and vanilla's rule,
judged on the walk that actually happened. With no walk pending (no AP, no path) the gate is
judged at once and the rest of the sequence's state callbacks are skipped. Nothing changes
outside record sections, and the only record section that holds a walk and a state callback
together is `actionPickUp`'s.

`actionPickUp` no longer applies `_obj_pickup` itself, charges the pickup AP only for a pickup
that happened, and traces the verdict (`F2_TRACE_EVENTS`):
`[cpickup] critter=N item_net=M NOT taken: the walk did not reach it (critter tile T1, item was
at tile T2, distance now D)`; the recorder adds `[anim-cb] net=N is not next to net=M after its
walk ...`.

## Verification
`python -u tools/issue_wire_proof.py reach <f2_server.exe> <sandbox> <port> <cmd port>`: a
spear is dropped where the host stands, the host is moved away, a fight is started, and the
host goes for the spear (the debug `pickup:7`, which calls `actionPickUp` exactly as the AI's
weapon hunt does). The host has 9 AP. Read off the server log: the host's steps, and when the
spear left the ground.

| server | spear 12 tiles away | spear 6 tiles away |
|---|---|---|
| v1.3.2 (`--expect-defect`: 5/5) | taken before a single step | taken before a single step |
| fixed (4/4) | walked 9 steps, stopped 3 short, NOT taken | walked 5 steps, then taken |
