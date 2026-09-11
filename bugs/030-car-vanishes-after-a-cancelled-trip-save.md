# 030: The car vanishes when a save made after a cancelled car trip is loaded

**Status**: FIXED (2026-09-11), not yet confirmed in live play.
**Files**: `src/worldmap.cc`, `src/worldmap.h` (`wmCarRepinPlacedTile`),
`src/server_worldmap.cc` (the trip-cancel tail).

## Symptom
Live report (solo world): after quickloading out of a random encounter, back in
Navarro, the car was gone. Walking out to the worldmap and back in made it reappear.

## Root cause
Proven on a copy of the loaded quicksave: `GVAR_CAR_PLACED_TILE` (633) was -1 while its
`NAVARRO.SAV` held the car object at tile 27686; the Navarro autosave beside it had
27686. Server log order: `interact FIRE use` on the car, `[wmsrv] driver enter ...
inCar=1`, `control wmesc`, `trip cancelled`, `quicksave -> slot 16`.

Using the car runs zsdrvcar's `use_p_proc`, which sets the gvar to 0, gives the car to
the party, then sets it to -1; the server driver's entry clears it to -1 again (sfall's
CarPlacedTileFix, `wmCarClearPlacedTile`). A trip that lands somewhere enters a map,
where the town script's `Check_Create_Car` re-pins it. A cancelled trip returns the
party to the same map without entering it (co-op only: vanilla's worldmap has no
cancel), so the gvar stayed cleared while the car stood there. On a later load,
zsdrvcar's `map_enter_p_proc` destroys the car because the gvar is not its tile, and
`Check_Create_Car` does nothing while loading (`if (not is_loading_game)`). The parked
area was intact, so the next real entry recreated the car.

## Fix
Every `map == -1` exit of the server driver calls `wmCarRepinPlacedTile`, which points
the gvar back at the car object on the current map, if there is one: the state
`Create_Car` left before the trip. A trip started on foot from a map without the car is
unaffected.

## Existing saves
A save made inside that window still loads without the car. Walking out to the worldmap
and back in recreates it.
