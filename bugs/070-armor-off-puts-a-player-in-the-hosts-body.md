# 070: Taking armor off puts a player in the host's body, and the inventory draws it one change behind

**Status**: FIXED (2026-10-02), proven on a sandbox with wire players and with the real
client and a real mouse; not yet confirmed in live play.
**Files**: `src/proto.cc`, `src/proto.h` (`protoPlayerActorBareFrmId`),
`src/server_control.cc` (`serverControlTakeArmorOff`, `invunwield`, `invdrop`),
`src/proto_instance.cc` (`_obj_remove_from_inven`), `src/interpreter_extra.cc`
(`_correctFidForRemovedItem`), `src/inventory_ui.cc` (the inventory loop's reconcile
repaint), `tools/issue_wire_proof.py` (`armoroff`), `tools/client_screen_proof.py`
(`armorview`).

## Symptom
GitHub issue 28, two reports in one:

1. "for the player who actively equips the armor, the inventory thumbnail shows them
   naked, while unequipping it updates the thumbnail to show them wearing it."
2. "Equipping and then unequipping any armor with a male character will turn him into
   female vault suit model for other player's point of view (tested with the other player
   being female if it matters). Putting armor back will turn him into male again."

And a third defect on the same slot, found while proving the second: dropping the armor
being worn, or the thing held in a hand, straight out of its slot did not drop it.

## Root cause
**The body.** With armor off a player goes back to their bare body, and every path that
worked that body out read it from the dude proto (`0x1000000`) or from
`_art_vault_guy_num`. Both describe the HOST. A second player of the other sex took
their armor off and was drawn in the host's body, for everyone, until they put armor on
again. `protoPlayerActorsUpdateLook` already said so in a comment ("a separate,
still-open facet").

**The inventory's body.** The figure turning in the middle of the inventory is drawn
from the armor and hand slots (`_adjust_fid`). In a viewer those slots change when the
server's answer arrives, and `_adjust_fid` only ran at the drop that ASKED for the
change, on the slots as they still were. So the figure was always one change behind:
bare after putting armor on, armored after taking it off.

**The drop.** The inventory screen drops a slot's item with one `invdrop` and no unwield
first, as vanilla's does. `itemDropStack` refuses an item still flagged as equipped, so
nothing was dropped. For armor the line before it had already taken the protection off:
the player stood in armor that stopped nothing.

## Fix
`protoPlayerActorBareFrmId(actor)`: the world's look (tribal, or the vault suit once its
movie has been seen) in the actor's OWN gender. The server's armor-off
(`serverControlTakeArmorOff`, used by `invunwield 2` and by the drop), the engine's
remove-from-inventory armor branch and the script path that corrects the art after
removing an item all use it for a second player.

The inventory loop's reconcile repaint now calls `_adjust_fid()` first.

`invdrop` takes an equipped item out of its slot before dropping it: armor through
`serverControlTakeArmorOff`, a held item through `_inven_unwield`.

## Verification
`python -u tools/issue_wire_proof.py armoroff ...`: the host is the stock man, the second
player a woman. The body streamed for her is read off the wire.

| | v1.4.1 (`--expect-defect`, 7/7) | fixed (8/8) |
|---|---|---|
| armor on | body 5 (the armor's) | body 5 |
| armor off | body 11, the host's | body 4, her own |
| armor dropped while worn | still in her pack, still drawn in it | on the ground, body 4, armor class back to 6 |
| spear dropped while held | still in her pack | on the ground |

`python -u tools/client_screen_proof.py armorview ...`: the real client drags a leather
armor onto the armor slot and back; the turning figure is read off screenshots as a set
of pictures per phase.

| | v1.4.1 (`--expect-defect`, 4/4) | fixed (4/4) |
|---|---|---|
| armor on | 6 of 6 pictures are the bare body | 0 of 6 |
| armor off | 0 of 6 pictures are the bare body | all are, none armored |
