# 065: Ammo dragged onto a weapon in the inventory does not load it

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client and a real mouse
drag; not yet confirmed in live play.
**Files**: `src/inventory_ui.cc` (`inventoryViewerLoadAmmo`, the three drop sites),
`src/client_net.cc` / `.h` (`clientViewerLoadAmmo`), `src/server_control.cc` (the `invload`
verb), `src/server_stubs.cc`, `tools/client_screen_proof.py` (`reloads`).

## Symptom
GitHub issue 34: "Drag & dropping the appropriate ammo to the gun in the holster slot does
nothing. Expected: drag & dropping the appropriate ammo should reload the gun as in the
original Fallout 2."

## Root cause
Left out on purpose when the viewer's inventory was written. Every drop there is a wire
verb, and the ammo-load drop was skipped with a note that ammo was not streamed yet. Ammo
has been on the wire per item since then; the drop was never wired up. It matters beyond
convenience: the drag is how a player picks one kind of ammo over another, where the hand
bar's reload takes whatever fits.

## Fix
A new verb, `invload <ammo netId> <weapon netId> <packs>`, in the same family as `invwield`,
`invdrop` and `unload` (free inside the screen, and in a fight only inside an inventory
session the player paid for). The server runs vanilla's own loader, `weaponLoadAmmo`, on the
named stack, and the rounds, the used-up packs and the ready sound come back with the
inventory stream. The viewer's three drop sites (ammo onto a weapon in the list, in the left
hand, in the right hand) ask "how many" for a stack, as vanilla does, and send the verb.

One thing differs from the screen the loader was written for: there the hand items are
detached, so the loader's take-out of the weapon fails harmlessly. On the server it works,
and `itemRemove` strips the in-hand flag, which would put a held weapon away. The verb keeps
the flags across the call.

An older server does not know the verb and ignores it, so a new client on an old server
behaves as before.

## Verification
`python -u tools/client_screen_proof.py reloads ...`: the pistol is emptied, the inventory
opened with I, and the ammo dragged from the top of the list onto the pistol's hand slot.

| build | result |
|---|---|
| v1.4.1 (`--expect-defect`, 3/3) | nothing is sent, the pistol stays empty |
| fixed (3/3) | `invload ammo pid=29 weapon pid=8 packs=1 rc=0 rounds 0 -> 12`; the pistol stays in the hand |
