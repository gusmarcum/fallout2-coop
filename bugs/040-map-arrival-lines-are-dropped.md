# 040: What a map prints as the party arrives never reaches the players (Temple of Trials XP)

**Status**: FIXED (2026-09-30), proven on a sandbox; not yet confirmed in live play.
**Files**: `src/presenter_network.cc` (the console emitters), `src/presenter.cc`,
`src/presenter.h` (`emissionsResumed`), `tools/issue_wire_proof.py` (`templexp`).

## Symptom
GitHub issue 6: "Finish quest of Temple of Trials. No log is visible, but rewards are awarded:
experience points, jumpsuit, water flask and money. Side note: unmarked quest of fixing well
for Feargus works fine and both players see log for 100 XP award."

## Root cause
The Temple pays out when the party first arrives in Arroyo: the village's map-enter script
gives the jumpsuit and the rest, pays the XP and prints three lines ("You are once more in the
village of your birth, Arroyo.", "You passed the trials of Arroyo.", "You gain 600 experience
points.").

A map-enter script runs inside `mapLoad`, and `mapLoad` suppresses everything the server would
emit while it builds the new world: the hundred or so object events it would otherwise ship
are covered by the baseline that follows. The console emitters obeyed the same switch, so the
lines were dropped with them. The rewards are sim state and arrived; the words did not. The
Feargus well pays out in the middle of a map, which is why that one showed.

## Fix
While emissions are suppressed the network presenter HOLDS message-log lines (text, address,
channel; at most 64) instead of dropping them, and sends them in order, unchanged, when the
window closes (`Presenter::emissionsResumed`, called by `presenterSetEmissionsSuppressed` on
the way out). They arrive after the "drop your world" transition and just before the new
world's baseline; the viewer's message log outlives the map switch.

Only the log lines are held. Floats and sounds belong to the world being torn down and are
still dropped.

## Verification
`python -u tools/issue_wire_proof.py templexp ...`: the server starts in the Temple, a player
logs in, and the operator walks the party into Arroyo (`entermap 4`, first visit).

| server | map transition to Arroyo on the wire | lines the player received on arrival |
|---|---|---|
| v1.3.2 (`--expect-defect`: 3/3) | yes | none |
| fixed (3/3) | yes | the three lines above |
