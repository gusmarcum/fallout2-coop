# 073: The trade screen ignores the arrow cursor: no look, no action menu, no unload

**Status**: FIXED (2026-10-02), proven on a sandbox with a wire player and with the real
client and a real mouse; not yet confirmed in live play.
**Files**: `src/inventory_ui.cc` (the viewer's trade loop, the action menu, the server's
barter drain, `barterSnapshotTable`), `src/barter_intent.h` (`BARTER_INTENT_UNLOAD_ITEM`),
`src/server_control.cc` (`bunload`), `src/presenter.h`, `src/presenter_network.cc` (the
ammo behind `BARTER_STATE`), `src/client_net.cc`, `src/client_barter.cc`,
`src/client_barter.h` (the copies carry the ammo), `tools/issue_wire_proof.py`
(`bunload`), `tools/client_screen_proof.py` (`tradeunload`).

## Symptom
GitHub issue 38: "Try to unload trader guns from Barter window. Expected: You can use
context menu (hold Left Mouse Button on the gun and move mouse to select unload option).
Actual: Holding LMB doesn't open Context Menu. Simple click for Binoculars info doesn't
work too in the Barter window."

## Root cause
Three gaps, one behind the other.

The viewer's trade loop handled a left click only under the HAND cursor (the drag).
Under the arrow, which the right button switches to, a click on an item did nothing:
vanilla's loop calls the action menu there (a click looks, a held button opens the menu).

The menu's Unload asked the server to unload an item in the player's own pack by netId.
On the trade screen the four lists are copies built from the trade's own stream, with no
netIds, and three of the four are not the player's pack.

That stream was rows of (kind, count). A copy was built from the kind alone, and a gun
built from its proto is a fully loaded gun: every weapon on the trade screen read as
loaded, whatever the server's one held.

## Fix
The viewer's trade loop opens the action menu on an arrow click over any of the four
lists, as vanilla's does. In a trade between two players the menu is look alone (that
session moves stacks and nothing else).

A new verb, `bunload <pid> <list>`, feeds a new barter intent: the server finds a loaded
weapon of that kind in that list's real inventory and unloads it there
(`weaponUnloadIntoInventory`), so the rounds go where vanilla puts them: into the same
inventory. Unload the merchant's pistol and the rounds are the merchant's, to be bought
on their own.

`BARTER_STATE` carries, behind everything an older client reads, what each row's weapon
is loaded with. The copies take that load before they are added to their list, so an
empty gun and a loaded one stay two rows, the menu offers Unload on the right one, and a
look counts the right rounds. An older server sends none and the copies stay as before.

## Verification
`python -u tools/issue_wire_proof.py bunload ...`: the host carries a loaded 10mm pistol
into a trade with Tubby.

| | v1.4.1 (`--expect-defect`, 3/3) | fixed (4/4) |
|---|---|---|
| the pistol's row | kind and count only | 12 rounds of ammo kind 29 |
| `bunload 8 0` | nothing | pistol at 0 rounds, a stack of the ammo beside it |
| `bunload 8 1` (Tubby's own pistol) | | 0 still loaded, 1 empty; his loose ammo 2 -> 3 stacks |

`python -u tools/client_screen_proof.py tradeunload ...`: the real client clicks the
dialog's Barter button, right-clicks for the arrow, clicks its pistol (look), holds the
button on it and draws the cursor down to Unload, then clicks Tubby's first item.

| | v1.4.1 (`--expect-defect`, 3/3) | fixed (3/3) |
|---|---|---|
| arrow click | nothing | looks at the item, in either list |
| held click | nothing | menu of 3 (look, unload, cancel); Unload unloads the 12 rounds |
