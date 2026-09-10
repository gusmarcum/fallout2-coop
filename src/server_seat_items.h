#ifndef FALLOUT_SERVER_SEAT_ITEMS_H_
#define FALLOUT_SERVER_SEAT_ITEMS_H_

namespace fallout {

// Seat items: gear the game ships exactly ONE of, that every player body needs on its
// own back. Fallout 2 places one Advanced Power Armor in Navarro and one Mk II in the
// oil rig's trap room, which is fair to one player and a problem for two: whoever
// takes the suit walks the Enclave base as one of them, and the other player does not.
//
// The first time the DEDICATED SERVER loads such a map, each listed item is topped up
// inside its own container to the number of player seats in the save (the host plus
// every extra body the save carries, online or parked). Owner ruling 2026-09-09:
// "duplicate them in their respective container compared on how many seats are in
// the save".
//
// Rules of the mechanism:
//   * never removes anything, only adds up to the seat count;
//   * runs once per map, on its first load (a revisit loads the map's .SAV, which
//     already carries the extra copies, and the header flag says so);
//   * never runs on a client or the headless probe, so the goldens and single player
//     are byte-identical by construction;
//   * a seat that joins after the map's first visit gets nothing retroactively; the
//     admin `give` verb covers that world.
//
// Called by mapLoad after the map-enter procs, inside the suppressed-emissions window,
// so the copies are simply part of the world every viewer is rebaselined onto.
// Returns the number of items added.
int serverSeatItemsOnFirstMapLoad();

} // namespace fallout

#endif /* FALLOUT_SERVER_SEAT_ITEMS_H_ */
