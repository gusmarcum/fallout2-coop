# 056: An observer of a trade cannot scroll any of its four lists

**Status**: FIXED (2026-09-30), proven on a sandbox with the real client; not yet confirmed in
live play.
**Files**: `src/inventory_ui.cc` (`barterScrollKey`, the trade loop), `tools/client_screen_proof.py`
(`tradescroll`).

## Symptom
GitHub issue 26: "Only player starting the dialog can use barter UI to scroll through barter
items. Other players cannot scroll and they don't see scrolling of the player in control,
only static first few items of both sides."

## Root cause
The trade loop gates everything on "is this viewer the driver", so that a spectator's
clicks and keys never become trade verbs. The scroll keys (the window's arrow buttons send
them) were inside that gate with the rest, though scrolling is a local view of mirrors
every viewer holds in full.

## Fix
The scroll keys for the four lists (the pack, the merchant's pack, the offer table, the buy
table) are handled by one helper, `barterScrollKey`, which every viewer may use; the driver
gate keeps the verbs. Scrolling stays local: an observer scrolls their own copy and does not
see the driver's scroll position, which is how vanilla's screen works too (there is no
"shared scroll" to mirror).

## Verification
`python -u tools/client_screen_proof.py tradescroll ...`: the host, carrying twelve things,
travels to the Den and opens a trade with Tubby through the debug port (`dtalk 47`,
`dbarter`); the second player's real client watches, and its recorded keyboard presses the
down arrow every second while the trade is up. The host's list in the observer's window is
read off the screenshots.

| client | changes of the observer's copy of the list between consecutive screenshots |
|---|---|
| v1.4.0 (`--expect-defect`, 2/2) | 0 |
| fixed (2/2) | 9 |
