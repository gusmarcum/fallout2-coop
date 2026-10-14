# 081: The Bonus Move lights are never yellow

**Status**: FIXED (2026-10-13), proven on a sandbox with the real client; not yet
confirmed in live play.
**Files**: `src/combat.cc` (`combatSessionPlayerTurnBegin`), `src/client_net.cc`
(`onTurnStart`, `applyTurnStart`, the action point lights' redraws), `src/animation.cc`
(the per-step charge of a replayed walk), `tools/client_screen_proof.py` (`bonusdots`).

## Symptom
GitHub issue 58: "The extra action points granted by the Bonus Move perk are not
visually distinguishable from regular action points on the action point bar. Expected:
Action points granted by the Bonus Move perk should be displayed as yellow dots."

## Root cause
Three things, each enough on its own to hide them.

1. **The server sent the turn start before it had set the turn's budget.** The message
   carries the Bonus Move budget (`_combat_free_move`) to the players.
   `combatSessionPlayerTurnBegin` sent it first and set the budget a few lines later,
   so every turn start carried what the last turn had left: nothing.
2. **The client redrew the lights without the budget.** Four of the places that repaint
   the action point lights passed 0 for the bonus count, so even a budget that had
   arrived was painted over at the first change of action points.
3. **On a client the budget was spent by any critter's replayed steps.** A viewer
   replays a walk through its own engine, which charges each step, and the charge takes
   the Bonus Move budget first, whoever is walking. The budget on a viewer is the local
   player's own, mirrored for the lights and the move preview. An enemy still seen
   walking when the player's turn came round used it up before the player had moved.

## Fix
A pull request from the reporter (60) fixed the first two: the budget is set before the
turn start is sent, and the redraws pass it. It answered the third by holding the turn
start on the client until everything queued had been shown. That part is not taken: a
turn start is the one message a client must act on as it arrives (it is what lets the
player send the input the server is waiting for), and one that sits on the queue is lost
when a rebaseline empties the queue in the middle of a fight.

The third cause is fixed where it is instead: on a viewer, a replayed step of any critter
but the local player's own leaves the budget alone (`animation.cc`). The budget is also
cleared when the turn passes to somebody else, as in the original, and a turn that is
skipped (knocked out, lose turn) is given none on the server.

**Known limit**: a viewer does not know another player's Bonus Move budget, so that
player's free steps are charged against their action points in the replay. The walk is
shown to its end either way; the server's count is the one that matters.

## Proof
`python -u tools/client_screen_proof.py bonusdots <f2_server.exe> <fallout2-ce.exe> <sandbox> 9400 9401`

The real client is the only player and is given the perk. A raider is set on it from
twelve hexes away, so the raider spends its turns walking up while the player ends two
turns. The ten lights are read off screenshots (green, yellow, red, dark): in each of the
player's turns, once the lights have settled, two must be yellow.
