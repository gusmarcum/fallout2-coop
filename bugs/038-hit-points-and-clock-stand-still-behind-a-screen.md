# 038: The hit point counter and the pipboy clock stand still while a screen is open

**Status**: FIXED (2026-09-30), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/client_net.cc` (`viewerServiceTicker`, `ClientConnection::hudTick`),
`src/inventory_ui.cc` (the summary), `src/pipboy.cc` (the date and clock),
`tools/client_screen_proof.py` (`invhp`, `clock`).

## Symptom
GitHub issue 9: "Using consumables (powder, fruit) doesn't refresh HP instantly. It does,
however, if I close the inventory window." GitHub issue 10: "Resting (in pipboy) does not
refresh HP or Time indicator instantly."

## Root cause
Three places, one shape: the number is right in memory and nothing draws it.

1. The counter on the interface bar does not jump, it rolls toward the server's number a
   step per frame (`rollDudeHp`, bugs/033). That roll lived only in the presentation tick,
   and inside a screen the service ticker runs the presentation tick only while the world
   view is up. The inventory, pipboy, character sheet, skilldex and Options all switch the
   world view off, so the counter froze until the screen closed.
2. The inventory's own summary prints the hit points too. A heal arrives a moment after the
   item is used, after the reconcile that repaints the summary for the item that was eaten,
   so the summary showed the old number.
3. The pipboy draws its date and clock when it opens and from its own rest loop, which a
   viewer never runs (the server rests the world). The clock stood still after a rest until
   the pipboy was reopened.

## Fix
1. The ticker rolls the counter on the screens that switch the world off
   (`ClientConnection::hudTick`, the roll alone, not the presentation).
2. The inventory repaints its summary whenever the hit points it printed change.
3. The pipboy redraws its date and clock whenever the game minute changes.

## Verification
`python -u tools/client_screen_proof.py invhp ...`: the second player opens the inventory and
keeps it open, the operator puts them at 1 hit point; the counter, read off the screenshots by
colour as in `hp`, must turn red while the screen is still up.
`python -u tools/client_screen_proof.py clock ...`: the second player opens the pipboy and
keeps it open, the operator rests three hours; the pipboy's date and clock strip must change
in the screenshots while it is still up.

Both need pictures of an open screen, and `F2_VIEWER_SHOT_EVERY` used to capture from the
viewer's main loop only, which does not run while a screen is up. The service ticker now
captures too, every Nth tick of an open screen.

| client | invhp: late screenshots with a red counter | invhp: the inventory's own stats panel | clock: strip redrawn after the rest |
|---|---|---|---|
| fixed | 4 of 4 | steady before, changed after (4/4) | yes, and still before it (4/4) |

v1.3.2 cannot capture inside a screen, so it has no before-picture here; its defect is the
code above (the roll ran only in the presentation tick, which the ticker skipped with the
world view off).
