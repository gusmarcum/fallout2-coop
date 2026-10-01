# 051: A line printed by one player's action reads as everyone's own

**Status**: FIXED (2026-09-30), proven on a sandbox with wire bots; not yet confirmed in live
play.
**Files**: `src/server_players.{h,cc}` (`playerInteractionActor`), `src/server_control.cc`
(`interactionFire`), `src/presenter_network.cc` (`consoleMessage`), `tools/issue_wire_proof.py`
(`ownline`).

## Symptom
GitHub issue 25: "Lockpick any door or container. Log shows info for every player as if they
are doing the lockpicking action ie. 'You failed to pick the lock'. Expected: 'Player2 failed
to pick the lock'."

## Root cause
A door's script answers a Lockpick attempt with `display_msg`, and the engine answers a locked
door or an overloaded pickup with its own lines; both reach the presenter as a plain broadcast
(`consoleMessage`), which every viewer prints as its own. The server already runs an
interaction's outcome as the acting player (`ServerActorScope`), but nothing told the
presenter whose action a line belonged to.

## Fix
`interactionFire` names the acting player for the length of the outcome
(`playerInteractionActorSet`, in core so the presenter can read it). The network presenter's
broadcast then goes two ways: the acting player gets the line as written, addressed to them;
everyone else gets it under that player's name, "Tester: You failed to pick the lock." The
text itself is not reworded (it comes from hundreds of scripts, in every tense), so the name
goes in front. With one player nothing changes, and lines outside an interaction (map
scripts, map-load lines) stay broadcasts.

## Verification
`python -u tools/issue_wire_proof.py ownline ...`: the host, loaded with 200 spears, picks up
one more off the ground (the `get` interaction), and the engine refuses it with "You cannot
pick up that item. You are at your maximum weight capacity.", which takes the same path as a
script's line. Read off the wire by addressee.

| server | to the host | to the second player | to everyone |
|---|---|---|---|
| v1.4.0 (`--expect-defect`, 5/5) | nothing | nothing | the line, once, unaddressed |
| fixed (4/4) | the line as written | "Tester: " + the line | nothing |
