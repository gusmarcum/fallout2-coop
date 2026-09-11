# 031: A charge armed before a save explodes somewhere random, for no damage, after the load

**Status**: FIXED (2026-09-11), not yet confirmed in live play.
**Files**: `src/queue.cc` (`queueLoad`, new `queueFindEventOwner`); trace lines in
`src/queue.cc` (`_queue_do_explosion_`) and `src/actions.cc` (`actionExplode`).

## Symptom
Live report (solo world, San Francisco Chinatown): an armed plastic explosive planted on
Mai Da Chiang went off "somewhere random", did no damage, and never touched him. Every
attempt had a quickload between arming the charge and planting it.

## Root cause
Reproduced on a copy of the live quicksave with a dev server and a scripted wire client
(steal, plant, wait). The new trace named the object that detonated:
`[explode] pid=33554499 holder=(ground) net=1311 -> tile=16115 elev=0 dmg=0-0`. Pid
0x02000043 is `PID_BLOCKING_HEX`, an invisible walk-blocker, not the charge (armed
plastic explosive, pid 209).

The queue saves each event with its owner's object id, and `queueLoad` re-bound it by
walking every object and inventory and taking the FIRST object with that id. Ids are not
unique across maps: `scriptsNewObjectId` only avoids the ids of the current map's
top-level objects at the moment it hands one out, and never looks into inventories or
other maps. The charge (id 1428) was carried into San Francisco, whose map holds two
blocking hexes with id 1428 (tiles 16115 and 27677). After the load the timer belonged
to the blocker at 16115: `_queue_do_explosion_` found no holder, blew at that tile, got
0/0 from `explosiveGetDamage` (not an explosive pid), then destroyed the blocker. The
real charge kept its `OBJECT_QUEUED` flag with no event behind it, a dud in the victim's
pocket. With no load between arming and detonation the in-memory binding is correct,
which is why it looked random.

## Fix
`queueLoad` prefers a match that carries `OBJECT_QUEUED` (`queueAddEvent` sets it on
every owner and the flag is saved; the colliding blockers do not have it), and falls
back to the first match as before.

## Diagnostics
Server console, one pair per detonation:
`[explode] pid=.. holder=.. net=.. -> tile=.. elev=.. dmg=..-..` and
`[explode] center tile=.. elev=.. critter=.. net=.. dmg=.. extras=..`.

## Existing worlds
Each misfire destroyed the blocking hex it was bound to. A save made after one keeps
that hex missing, so one tile is walkable where it was blocked before.
