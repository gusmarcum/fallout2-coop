# 055: The Combat Control text menu offers no "use best weapon" or "wear best armor"

**Status**: FIXED (2026-09-30), proven on a sandbox with a wire bot; not yet confirmed in live
play.
**Files**: `src/game_dialog.cc` (`serverDialogPartyOrders`), `tools/issue_wire_proof.py`
(`orders`).

## Symptom
GitHub issue 22: "Combat Control button opens up text control for NPC behaviour ... but also
unabling giving order to pick best weapon and armor."

## Root cause
The vanilla Combat Control window cannot run on the server or a viewer (its own blocking SDL
loop, editing an AI packet only the server owns), so co-op serves the party member's orders
as a text node: the disposition and the six customizable orders, cycled by picking a line.
The window's two one-shot buttons, USE BEST WEAPON and USE BEST ARMOR, were never carried
over to the text node.

## Fix
Two more lines before "Done": "Use your best weapon" and "Wear your best armor". Picking
one runs exactly what the window's 'w' and 'a' handlers run: unwield, find the best weapon
carried (`_ai_search_inven_weap`), wield it and reload; or find the best armor carried
(`_ai_search_inven_armor`) and wear it (Goris excepted, as in the window). The server logs
`party orders <name>: use best weapon -> <item>` / `wear best armor -> <item>`.

## Verification
`python -u tools/issue_wire_proof.py orders ...`: a Cassidy is spawned beside the host with
the generic villager dialog script (a map-placed critter has an id below 18000 and never
counts as a party member; a spawned one does), made a party member (`partyadd 89`), talked
to, and Combat Control is pressed (`dparty`). The node's options are read off the wire and
the two new lines are picked.

| server | the Combat Control node | picking the new lines |
|---|---|---|
| v1.4.0 (`--expect-defect`) | 8 lines: disposition, six orders, Done | nothing to pick |
| fixed (3/3) | 10 lines, with "Use your best weapon" and "Wear your best armor" | the server logs "use best weapon -> none carried" and "wear best armor -> none carried" (the companion carried nothing) |

Whether it wields what it finds is the window's own code (`_ai_search_inven_weap`,
`_inven_wield`), unchanged; a companion with a spare weapon shows it in live play.
