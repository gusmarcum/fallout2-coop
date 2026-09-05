#ifndef FALLOUT_CLIENT_TRADE_H_
#define FALLOUT_CLIENT_TRADE_H_

#include "client_barter.h" // ClientBarterList — the same row shape rides both streams

namespace fallout {

struct Object;

// Viewer half of the player-to-player trade stream (EVENT_TRADE_BEGIN/STATE/END,
// server_trade.cc). It owns almost nothing of its own: the screen is vanilla's
// trade window exactly as the merchant barter draws it, fed through client_barter's
// mirrors — this module just turns the symmetric wire state (party A, party B)
// into that screen's one-sided view (ME on the left, THEM on the right, MY
// offer table under my pack), and puts the dialog session windows the trade
// screen needs underneath, since there is no conversation to have built them.
//
// A viewer that is neither party ignores the whole stream.

void clientTradeOnBegin(int aNetId, int bNetId);
void clientTradeOnState(int aNetId, int bNetId, const ClientBarterList lists[4],
    int valueA, int valueB, bool lockedA, bool lockedB, bool confirming);
void clientTradeOnEnd(int aNetId, int bNetId, int reason, const char* text);

// True while THIS viewer is a party to an open trade (its screen should be up).
bool clientTradeActive();

// Main-loop integration, in this order around the barter open check:
//   clientTradeSyncWindows()  — before: builds the dialog session + node windows the
//                               trade screen draws over, once, when a trade opens.
//   (the barter open check opens the vanilla trade screen off client_barter)
//   clientTradeAbortIfUnopened() — right after: the screen refused to open (a
//                               proto the mirror lacks), so leave the trade rather
//                               than retry every frame.
//   clientTradeFinalize()     — after clientBarterFinalize: tears the windows down
//                               and prints the closing line once the trade ended.
void clientTradeSyncWindows();
void clientTradeAbortIfUnopened();
void clientTradeFinalize();

} // namespace fallout

#endif /* FALLOUT_CLIENT_TRADE_H_ */
