# 063: Sneak stays on at a run

**Status**: FIXED (2026-10-02), proven on a sandbox with a wire bot; not yet confirmed in
live play.
**Files**: `src/server_control.cc` (`serverControlMove`), `src/server_anim.cc`
(`serverAnimMoveArtAvailable`), `tools/issue_wire_proof.py` (`sneakrun`).

## Symptom
GitHub issue 29: "I don't know if it is intended, but vanilla Fallout 2 sneak turns off
while you run, unless you have the Silent running perk. This is not just a visual box bug
but NPCs really perceive me as sneaking."

## Root cause
Vanilla has the rule in two places, and the dedicated server reaches neither.

* `_dude_run`, the run click's own handler, turns Sneak off unless the runner has Silent
  Running. On the server a run arrives as the `mv` verb and goes straight to the animation
  register, so nothing turned it off.
* The animation register itself makes a sneaking player without the perk WALK wherever a
  run is asked for them (the approach of a use, a pickup, a talk). The server's own move
  backend checked only whether the run art exists.

## Fix
`serverControlMove` ends the sneak on a run, perk permitting, as `_dude_run` does; the sheet
row carries the state back, so the indicator goes out on the player's screen. And a run
registered for a sneaking player without the perk is a walk, as in vanilla.

## Verification
`python -u tools/issue_wire_proof.py sneakrun ...`. The server logs the state only when it
is toggled, so each step ends with a toggle and reads what it turned into.

| server | walk, then toggle | run, then toggle | Silent Running: run, then toggle |
|---|---|---|---|
| v1.4.1 (`--expect-defect`, 3/3) | off (it was on) | off: the run had kept it on | off (kept) |
| fixed (3/3) | off (it was on) | ON: the run had ended it | off (kept) |
