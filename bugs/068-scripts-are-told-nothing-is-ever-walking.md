# 068: Scripts are told nothing is ever walking: Grisham's wild dogs stand still

**Status**: FIXED (2026-10-02), proven on a sandbox with a wire bot; not yet confirmed in
live play.
**Files**: `src/server_anim.cc` (`animationIsBusyForScript`), `src/animation.cc` / `.h`,
`src/interpreter_extra.cc` (`opAnimBusy`), `tools/issue_wire_proof.py` (`dogs`).

## Symptom
GitHub issue 43: "Grisham's quest always fail. Scenario: accept Grisham's quest for
guarding his brahmin herd. Expected: wild dogs are approaching herd and attack brahmins.
Actual: wild dogs are standing still in top of the Brahmin Pasture map. After killing every
one of the dogs and saving all brahmins Grisham responds as if his herd was completely
killed and demands player to pay him for his losses."

## Root cause
Both halves are one bug.

The dogs' script (`mcAtkDog`) homes in on a brahmin with the stock idiom: ask to run to its
tile; while NOT `anim_busy(self_obj)` the move was refused (no path, too far), so pull the
destination one hex back toward yourself and ask again. It stops when a move gets under way
or the destination has come all the way back.

The dedicated server's `animationIsBusy` returns 0, always. It has to, for the engine's own
callers: they busy-wait on it (`while (animationIsBusy(x)) _process_bk();`), and nothing in
that pump advances a stepped walk. But the script op `anim_busy` used the same function, so
every ask looked refused. The loop walked the destination back to the dog's own feet, each
ask replacing the one before, and the one that stood went nowhere. The dogs never left the
top of the map.

The herd is on a clock. The pasture's map script (`MODBRAH`) sets a deadline when the party
first arrives, and writes the whole herd off (`GVAR_MODOC_BRAHMIN_ALIVE := -1`,
`kill_critter_type`) when the deadline passes with dogs still alive, or when the party
leaves the map with dogs still alive. In vanilla the dogs are on the herd at once and the
fight is decided well inside the deadline. The second half of the report is then an
inference, not something replayed here: a party that first had to go and find ten dogs
standing at the far end of the map most likely finished them after the deadline, with the
herd already written off, and Grisham read `-1`. (Leaving with a dog alive gives the same
`-1`; the sandbox showed that one: 10 on arrival, -1 after walking out.)

## Fix
`anim_busy` now asks `animationIsBusyForScript`. On a client that is `animationIsBusy`. On
the server it is "is a walk of this object still under way" (the stepped-walk registry),
which is what a script means by it. `animationIsBusy` itself stays 0 for the engine's
busy-waits.

Companions keep the old answer on purpose: their follow was tuned against it (bugs/027),
re-aiming at the leader on every heartbeat, and nothing was reported against how they move.

This is not specific to Modoc. Any script that homes in with that idiom was stuck the same
way.

## Verification
`python -u tools/issue_wire_proof.py dogs ...`: the host enters the pasture and waits forty
seconds, ending its turns. The dogs start on rows 38 to 43, the herd stands on rows 78 to 92.

| server | the dogs | a fight |
|---|---|---|
| v1.4.1 (`--expect-defect`, 3/3) | 7 of them took one to three steps, none left the top | none |
| fixed (3/3) | all 10 ran to row 70 or beyond (69 to 82 steps each) | started |

Grisham's own verdict was not played through. It reads the counter above, and with the dogs
attacking as in vanilla the quest runs on vanilla's terms again.
