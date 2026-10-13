# 082: "Wear your best armor" is below the last line the window shows

**Status**: FIXED (2026-10-13), proven on a sandbox; not yet confirmed in live play.
A follow-up to bugs/056 (GitHub issue 22).
**Files**: `src/game_dialog.cc` (`serverDialogPartyOrders`), `tools/issue_wire_proof.py`
(`orderspages`, `orders`).

## Symptom
GitHub issue 22, after v1.4.2: "'Wear your best armor' doesn't show, it may be because
Fallout engine can only show 8 lines of text on one page and this would be the 9th. If I
press '9', NPC actually puts the best armor on, but this option is hidden."

## Root cause
A companion's Combat Control is a conversation page in co-op. v1.4.1 added the window's
two one-shot buttons to it as lines, which made ten: the preset, the six orders, "Use
your best weapon", "Wear your best armor" and "Done". A conversation window shows
eight. The ninth and tenth worked by their number keys and could not be seen, "Done"
included.

## Fix
Two pages, as the reporter suggested:

- first page: Use your best weapon / Wear your best armor / Change how you fight / Done
- second page: the preset, the six orders, Back

Four lines and eight. Picking an order still cycles it in place; Back returns to the
first page.

## Proof
`python -u tools/issue_wire_proof.py orderspages <f2_server.exe> <sandbox> 9400 9401`

A spawned companion, the host talks to him and opens Combat Control. Every page the
server sends must have eight lines or fewer, "Wear your best armor" must be on the first,
the orders on the second, and Back must lead to the first again. `orders` (bugs/056's
own proof: the two one-shots run the window's handlers) still passes.
