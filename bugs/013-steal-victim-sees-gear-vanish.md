# 013 — A player being stolen from sees their equipped items vanish

**Status**: FIXED on the viewer (2026-09-05); server behaviour unchanged and verified.
**Files**: `src/client_net.cc` (own-actor inventory reconcile).

## Symptom
Opening the steal screen on another PLAYER makes that player's worn armor and held weapons
disappear from their own screen at once: the interface bar's hand slots empty, the paperdoll
strips.

## What the server does (vanilla, kept)
`stealSessionRun` runs vanilla's steal loop headless. Its entry detaches the target's
equipped gear (`lootTargetDetach`: `itemRemove` of item1/item2/armor into a hidden box) so
the thief's list cannot contain it, and its exit reattaches it with the equip flags restored
(`lootTargetReattach`). `tools/inventory_proof.py` shows the host's worn T-51b
(flags 0x04000008) identical before and after a session opened on him by the second player.
Nothing is lost server-side.

## Why the victim's screen emptied
`stealEmitState` runs `objectDeltaScan` inside the parked session so every viewer's panels
update live. That scan also emits the VICTIM's own inventory delta, which lists their
pockets without the parked gear. The victim's viewer reconciles its own actor from that
list and removed the "missing" items — correct for any other removal, wrong for one the
server itself is about to undo.

## Fix
While this viewer is the target of an open steal session (`gViewerStealTargetNetId` is its
own net id), the own-actor reconcile keeps mirror items that were equipped and are absent
from the wire list, flags intact. The reattach at session end re-lists them under the same
net ids, so they are claimed by id and nothing duplicates. Every other viewer still sees the
victim's panel without the parked gear, as before.

## Also armed in the same build
- `invunwield` on the server logs whether the unequipped item merged back into a stack
  (owner-reported: a stimpak peeled into a hand and put back showing as 23 + 1; the sandbox
  merges 24 -> 23+1 -> 24, so the next report names the side that split).
- The viewer logs a `CONNECT` that pulls an item out of a mirrored inventory (the scene
  macro `rm_obj_from_inven` / `add_obj_to_inven` on a worn armor puts it on map tile 1 for
  an instant), for the "everything vanished after a scene" report.
