# 048: A weapon an NPC picks up in a fight is invisible on other players' screens, and missing from its corpse

**Status**: FIXED (2026-09-30), proven on a sandbox with the real client; not yet confirmed in
live play.
**Files**: `src/client_net.cc` (the living-critter inventory delta), `tools/client_screen_proof.py`
(`npcloot`, and the client's stderr now goes to `client-screen-proof-client.log`).

## Symptom
GitHub issue 13, the follow-up to v1.4.0: "You can't loot a body if the NPC has an item they
acquired after the battle started (like the spear they picked up). After I kill them, that
spear just vanishes from their inventory (if it ever was there)."

## Root cause
Every viewer keeps a mirror of each critter's inventory, built from the join blob and kept up
by the inventory deltas the server streams. For a LIVING critter that is not the viewer's own
character, the delta was applied as equip flags only: the mirror's items were matched by pid
and had their in-hand and worn flags set from the wire, and a stack the mirror did not have
was skipped ("acceptable v1: a weapon the mirror is missing entirely"). The rebuild-by-free
path was kept away from living critters on purpose, because an attack replay in flight may
still reference their items (the object-lifetime hazard behind an earlier crash).

A spear taken off the ground in a fight (bugs/042) is exactly a stack the mirror never had.
So the viewer drew the critter bare-handed while the server had it swinging the spear, and
`critterGetWeaponForHitMode` resolved its attacks to a punch. When the critter died, the
corpse was reconciled in full only by a delta that carries its inventory, and nothing changes
in a pack at the moment of death, so the corpse's mirror never gained the spear either: the
loot screen, which shows the mirror, had no spear to take. The server had it in the corpse
the whole time.

## Fix
The living-critter path now creates a wire stack the mirror lacks (`objectCreateWithPid`,
`_obj_disconnect`, the wire's equip flags and ammo, `mirrorInventoryAppend`), the way the
dead-corpse path already makes its items. Adding an object frees nothing, so the lifetime
hazard that keeps this path from rebuilding does not apply. Items the server removed from a
living critter are still left in the mirror (harmless and unchanged).

## Verification
`python -u tools/client_screen_proof.py npcloot <f2_server.exe> <fallout2-ce.exe> <sandbox>
<port> <cmd port> [--expect-defect]`: a spear is dropped where the host stands, a bare-handed
raider is spawned three hexes from it and set on the host, and the second player's real client
watches with `F2_TRACE_EVENTS` on. The raider's weapon hunt takes the spear (server log
`[cpickup] critter=N item_net=M taken ... distance now 0`); the client's `[inv-apply] net=N
items=I rhandPid=P` line says what its mirror holds for that critter afterwards.

| client | the raider's mirror after the pickup (items, right hand pid) |
|---|---|
| v1.4.0 (`--expect-defect`, 3/3) | (0, -1): nothing, nothing in hand |
| fixed (3/3) | (1, 7): the spear, in hand |
