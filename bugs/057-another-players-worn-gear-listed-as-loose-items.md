# 057: Another player's worn armor and held weapons are listed as loose items on an observer's screen

**Status**: FIXED (2026-09-30), proven on a sandbox with the real client; not yet confirmed in
live play.
**Files**: `src/client_net.cc` (the full inventory reconcile), `tools/client_screen_proof.py`
(`stealgear`).

## Symptom
GitHub issue 27: "Open other players inventory by being observer during barter or during
stealing attempt. Other player armor and holster is visible as free item in inventory list."

## Root cause
Every screen hides a critter's equipped gear by its in-hand and worn flags
(`equipmentDetach` pulls those items out of the list). A viewer's mirror of another player
gets those flags from the join blob and from the ordinary per-critter delta. But during a
steal session the thief's pack is rebuilt IN FULL from each delta (so items taken and
planted appear live), and that rebuild matched items by pid and copied the quantity and
ammo, never the flags: after the first delta of a session the thief's held weapon and worn
armor were flagless in the mirror, and from then on every screen that lists that player's
pack showed them as plain items.

## Fix
The full reconcile clears the equip flags on the items it keeps and sets them from the wire
on matched and created items, the way the viewer's own pack reconcile does. Containers and
corpses carry no equipped gear, so nothing changes for them. Under `F2_TRACE_EVENTS` the
client logs `[inv-full] net=N items=I worn=W held=H` after each rebuild.

## Verification
`python -u tools/client_screen_proof.py stealgear ...`: the host holds a spear, has its
Steal raised to 102, steals from a raider spawned beside it and plants a stick of dynamite
(the session stays open, the thief's pack changes); the second player's real client, event
trace on, rebuilds its mirror of the thief's pack.

| client | the thief's mirror after the rebuild (items, worn, held) |
|---|---|
| v1.4.0 | no flags set by that path (the code above); no log line to read |
| fixed (3/3) | (1, 0, 1): the spear, in hand |
