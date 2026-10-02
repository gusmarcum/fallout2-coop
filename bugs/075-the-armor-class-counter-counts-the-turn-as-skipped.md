# 075: The armor class counter counts the turn as skipped

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/combat.cc`, `src/combat.h` (`combatViewerSetTurnObject`),
`src/client_net.cc` (`applyTurnStart` and the three places a fight's framing is dropped),
`tools/client_screen_proof.py` (`acturn`).

## Symptom
GitHub issue 24: "Armor Class (AC) counter shows result as if player skipped turn with
current amount of Action Points (APs) left. With every AP spent current AC drops by one.
Expected: In vanilla Fallout2 current AC is updated with End Turn."

## Root cause
The armor class stat adds a critter's unspent action points while a fight is on, except
on that critter's own turn (`critterGetStat`, `_combat_whose_turn() != critter`). The turn
is set by the combat loop, and a viewer runs none: there it was never set, every moment
counted as somebody else's turn, and the bonus was always in. The viewer redraws the
interface bar whenever the action points move, so the counter showed armor class plus
whatever action points were left, a point less with each one spent.

Display only. The server's own number, the one attacks are rolled against, was right.

## Fix
The viewer is told whose turn it is (TURN_START) and now passes that on to the stat
(`combatViewerSetTurnObject`), before the bar is redrawn; it is cleared when the fight or
the world goes. The counter stands still through the player's own turn and shows the
unspent action points once the turn has passed to someone else.

With one player and enemies that take their turns in a single server step, the turn is
back with the player almost at once and the bonus is hardly seen; with a second player
taking their turn it shows for as long as that takes.

## Verification
`python -u tools/client_screen_proof.py acturn ...`: two players in a fight. The real
client, on its own turn, opens the inventory (4 action points), closes it and ends the
turn; the other seat then holds its turn for eight seconds. The counter is read off
screenshots taken every 10 frames.

| | v1.4.1 (`--expect-defect`, 3/3) | fixed (3/3) |
|---|---|---|
| pictures of the counter during the own turn | 2 (it dropped with the action points) | 1 |
| the counter while the other player held the next turn | the same picture as before the turn ended | a different one |
