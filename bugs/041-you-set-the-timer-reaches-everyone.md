# 041: "You set the timer" is shown to every player

**Status**: FIXED (2026-09-30), proven on a sandbox; not yet confirmed in live play.
**Files**: `src/proto_instance.cc` (`_obj_arm_explosive`), `tools/issue_wire_proof.py`
(`timer`).

## Symptom
GitHub issue 5: "Player1 starts timer for explosives. You set the timer message visible in
green for everyone. Expected: Message says 'Player1 sets the timer'."

## Root cause
Vanilla prints proto message 589 with `consoleMessage`, which on the dedicated server is a
broadcast. Every player read that they had just armed a charge.

## Fix
With more than one player actor, the line goes to the one who armed it (the server arms under
that player's actor scope, so `gDude` is them), and every other player is told "<name> sets
the timer." instead: the third-person line is also the warning they need. A single player, and
every golden, gets vanilla's broadcast unchanged.

## Verification
`python -u tools/issue_wire_proof.py timer ...`: two players log in, the host arms a stick of
dynamite (`useitem_armexplosive 51 180`). The lines are parsed out of the stream with their
addresses.

| server | "You set the timer." | the second player (netId 2) |
|---|---|---|
| v1.3.2 (`--expect-defect`) | broadcast (address 0) | nothing else |
| fixed | addressed to the host (netId 1) | "Tester sets the timer." |
