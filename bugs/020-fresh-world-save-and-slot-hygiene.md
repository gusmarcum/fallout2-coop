# 020: A fresh dedicated world could not save, a failed save poisoned its slot, and a new world inherited the last one's maps

**Status**: FIXED (2026-09-09).
**Files**: `src/savegame.cc` (`savegameEnsureAutomapDb`, proto backup/restore in `_SaveBackup` /
`_RestoreSave`, `savegameEraseSlot`), `src/server_boot.cc` (`serverLoadMap` new-world wipe),
`src/server_main.cc` (`F2_SERVER_DEBUG_LOG`), `src/server_admin.cc` (save failure message).

Three defects in one family, found while verifying the seat-items feature on a fresh
two-seat sandbox world. None is new; all three are inherited from the split between the
vanilla single-process game and the headless server, and the live worlds never hit the first
two only because the host's own client runs in the same folder as the server.

## 1. A server started on a fresh map failed every save with "error 0"
`_GameMap2Slot` copies `MAPS\AUTOMAP.DB` into the slot and returns -1 when the file is
missing. Only the client creates that file (`automapCreate`, at game init; `automap.cc` is
client-side and the server stubs `automapSaveCurrent`). A loaded world gets it back from the
slot, so loaded worlds saved fine; a fresh dedicated world had no file and could not save at
all, on every build back to v1.1.0, with or without a second seat, before or after any map
change. On the owner's machine the host's client creates the file in the shared folder, which
is why this never showed in play. A friend hosting from a bare server folder would never have
been able to save a new world.

Fix: `savegameEnsureAutomapDb` writes the same empty database the client writes (version byte
1, size 1925, one offset per map and elevation, the first three maps -1) when the file is
absent, at the top of `_GameMap2Slot`.

## 2. A failed save left a slot that crashed on load
`_SaveBackup` renames `SAVE.DAT` and the map `.SAV` files aside and copies the automap; it
never touched `proto\critters\*.pro` and `proto\items\*.pro`, although `_GameMap2Slot` writes
those before the step that can fail. `_RestoreSave` brought everything else back, so the slot
ended up with the previous save's data and the failed world's companion protos, same pids,
different contents. The loader trusts the slot's protos for the party members `SAVE.DAT` names
and crashed (`objectAssignInventoryNetIds` walking an inventory that did not match). Measured
on a slot written at 21:56 that loaded cleanly, then failed a save at 22:45: every proto in it
carried the 22:45 timestamp and a different size, and three different builds crashed loading
it afterwards.

Fix: the proto folders are backed up (`.prb`) and restored with the rest, dropped on success,
and `savegameEraseSlot` (used to empty a recycled autosave slot and by the restore) clears
`.pro` files too, since the loader would read a leftover with a matching pid as this world's.

## 3. A new world inherited the previous world's visited maps
Vanilla's new game runs `_ResetLoadSave` (via `gameReset`), which empties the `MAPS` working
copies and the proto overrides. `serverLoadMap`, the `F2_SERVER_MAP` boot and the lobby's
`new`, never did. `mapLoadByName` prefers `MAPS\<map>.SAV` when it exists, so a fresh world
hosted from a folder that had seen another world found Navarro already looted and cleared on
its "first" visit. It also defeated the seat-items first-load rule, which is how it was caught.

Fix: `serverLoadMap` refreshes the patches path, clears `MAPS\*.SAV`, the automap database and
the proto overrides, and logs how many stale files it removed.

## Operator visibility
The engine's `debugPrint` stream, where the save and load code report the failing step, is
dropped on the dedicated server. `F2_SERVER_DEBUG_LOG=1` writes it to `f2_server-debug.log`
next to the exe, and the admin `save` failure message now says so instead of pointing at a
line the server never printed.

## Verification
Sandbox server, fresh two-seat world with no automap database: admin save succeeds and the
database appears (1925 bytes). Forced failure (the slot's `AUTOMAP.SAV` replaced by a
directory so the writer fails after the protos): the slot's 24 protos are byte-identical to
before the attempt, `SAVE.DAT` untouched, no backup leftovers, and the debug log names
"Error writing save function #3". New-world boot in a folder with 22 stale map files: the
console reports clearing them and Navarro loads fresh. Gate green on the final binaries.
