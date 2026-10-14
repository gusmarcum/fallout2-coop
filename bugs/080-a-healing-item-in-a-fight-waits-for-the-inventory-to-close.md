# 080: A healing item used in a fight does not move the counter until the inventory closes

**Status**: FIXED (2026-10-13), proven on a sandbox with the real client; not yet
confirmed in live play. New in v1.4.2: a regression from bugs/069.
**Files**: `src/client_net.cc` (`Decoder::screenPump`, `hudPump`),
`tools/client_screen_proof.py` (`combatheal`).

## Symptom
GitHub issue 54: "it still persists during combat. After consuming a healing item, HP
will only be added after inventory is closed." A second player on the older issue 9:
"This one is again live in 1.4.2".

## Root cause
In a fight the client puts every message line on its presentation queue, so that a line
is shown with the attack it belongs to. Since bugs/069 (GitHub issue 44) a new hit point
total for the player's own character also goes on that queue whenever anything is on it
or a fight is on: the counter must not run ahead of a blow that has not been shown yet.

The screens that hide the world (inventory, pipboy, character sheet, skilldex, options)
switch the presentation pump off: under them only the counter's own roll runs
(bugs/038). So a stimpak taken from the inventory in a fight went like this: "You gained
14 hit points" was queued; the new total was parked behind it; and the queue did not
move again until the inventory was closed.

## Fix
A message line, a sound and the player's own hit points need no world to be shown. Under
a screen that hides the world the ticker now lets them through, in order, when they are
all that is queued (`screenPump`). With anything else in the line (an attack, a recorded
sequence, a turn start, the end of the fight) nothing is touched, so a total parked
behind a blow still waits for that blow to be shown: what bugs/069 fixed stays fixed.

A pull request from the reporter (63) took up every parked total while the inventory was
open, wherever it stood in the line. That shows a healing item at once, and it also lets
the counter drop ahead of a blow that is still waiting to be played (open the pack while
the last attacks of a fight are queued). The rule above is the narrower one.

## Proof
`python -u tools/client_screen_proof.py combatheal <f2_server.exe> <fallout2-ce.exe> <sandbox> 9400 9401`

The real client is the only player, hurt, in a fight with a raider. On its own turn it
opens the inventory (the server grants it for four action points) and leaves it open. The
operator has the character take a stimpak (`usedrug`, the call the inventory's Use
makes). The counter is read off screenshots taken every 8 frames.

- v1.4.2 (`--expect-defect`): the total is parked and not taken up; the counter has not
  moved 7 seconds later, when the client is stopped.
- fixed: the counter moves 0.1 s after the stimpak, with the inventory still open; the
  client's log shows the total parked and then adopted.

`hpcount` and `hpcount2` (bugs/069's own proofs) still pass on the same build.
