#include "client_trade.h"

#include <cstdio>
#include <cstring>
#include <string>

#include "client_barter.h"
#include "client_dialog.h" // clientDialogActive — never build a second dialog session
#include "client_net.h" // clientViewerActive / clientViewerBarterVerb
#include "critter.h" // critterGetName
#include "debug.h"
#include "display_monitor.h"
#include "game.h" // gDude
#include "game_dialog.h" // the dialog session + node windows the trade screen draws over
#include "inventory.h" // inventoryTradeViewerSetHooks
#include "msg_channel.h"
#include "object.h" // objectFindByNetId

namespace fallout {

static bool gTradeOpen = false; // a trade I am party to is open on the server
static bool gTradeEndPending = false; // the server ended it; finalize on the main loop
static bool gTradeWindowsBuilt = false; // the dialog session/node windows are up for it
static bool gTradeMeIsA = false;
static int gTradeOtherNetId = 0;
static bool gTradeLockedMe = false;
static bool gTradeLockedThem = false;
static bool gTradeConfirming = false;
static std::string gTradeEndText;

static Object* tradeOther()
{
    return gTradeOtherNetId != 0 ? objectFindByNetId(gTradeOtherNetId) : nullptr;
}

// The one line of guidance the trade screen has room for: the dialog reply
// window above the trade strip, where a merchant trade shows "Ok, that's a good
// trade." Re-rendered by the screen's repaint hook, so it follows every STATE.
static void tradeRenderStatus()
{
    if (!gTradeWindowsBuilt) {
        return;
    }
    char other[64];
    Object* them = tradeOther();
    snprintf(other, sizeof(other), "%s", them != nullptr ? critterGetName(them) : "the other player");
    char text[256];
    if (gTradeConfirming) {
        snprintf(text, sizeof(text), "Both offers are locked. Answer the box to finish the trade.");
    } else if (gTradeLockedMe && !gTradeLockedThem) {
        snprintf(text, sizeof(text), "Your offer is locked. Waiting for %s to press Offer. Press Offer again to change yours.", other);
    } else if (gTradeLockedThem) {
        snprintf(text, sizeof(text), "%s locked their offer. Press Offer (M) when you are ready, or keep arranging.", other);
    } else {
        snprintf(text, sizeof(text), "Drag items onto your table, then press Offer (M). Talk (T) or Esc leaves the trade.");
    }
    gameDialogRenderSupplementaryMessage(text);
}

// The other player's pack is theirs: nothing is dragged out of it. They put what
// they want to give on their table, and the server refuses `btake` anyway — this
// just keeps the pickup gesture from starting.
static bool tradeCanTakeFromOther()
{
    return !clientTradeActive();
}

void clientTradeOnBegin(int aNetId, int bNetId)
{
    if (!clientViewerActive() || gDude == nullptr) {
        return;
    }
    int me = gDude->netId;
    if (me != aNetId && me != bNetId) {
        return; // someone else's trade
    }
    if (gTradeOpen) {
        // A BEGIN over an open trade: we missed the END. Same failure direction as
        // client_barter — re-open, never wedge.
        clientBarterOnEnd();
        clientBarterFinalize();
    }
    gTradeMeIsA = me == aNetId;
    gTradeOtherNetId = gTradeMeIsA ? bNetId : aNetId;
    gTradeLockedMe = false;
    gTradeLockedThem = false;
    gTradeConfirming = false;
    gTradeEndPending = false;
    gTradeEndText.clear();
    gTradeOpen = true;
    // The trade screen is a merchant barter in which the merchant is the other
    // player and the driver is me. Both mirrors come from the STATE stream.
    clientBarterOnBegin(gTradeOtherNetId, me);
    debugPrint("client_trade: trade opened with net=%d (I am %s)\n", gTradeOtherNetId, gTradeMeIsA ? "A" : "B");
}

void clientTradeOnState(int aNetId, int bNetId, const ClientBarterList lists[4],
    int valueA, int valueB, bool lockedA, bool lockedB, bool confirming)
{
    if (!gTradeOpen || gDude == nullptr) {
        return;
    }
    (void)aNetId;
    (void)bNetId;
    // Wire order: A's pack, B's pack, A's table, B's table. My side goes left.
    const ClientBarterList& myInv = gTradeMeIsA ? lists[0] : lists[1];
    const ClientBarterList& theirInv = gTradeMeIsA ? lists[1] : lists[0];
    const ClientBarterList& myTable = gTradeMeIsA ? lists[2] : lists[3];
    const ClientBarterList& theirTable = gTradeMeIsA ? lists[3] : lists[2];
    int myValue = gTradeMeIsA ? valueA : valueB;
    int theirValue = gTradeMeIsA ? valueB : valueA;
    gTradeLockedMe = gTradeMeIsA ? lockedA : lockedB;
    gTradeLockedThem = gTradeMeIsA ? lockedB : lockedA;
    gTradeConfirming = confirming;
    clientBarterOnState(myInv, theirInv, myTable, theirTable, myValue, theirValue, -1);
}

void clientTradeOnEnd(int aNetId, int bNetId, int reason, const char* text)
{
    (void)aNetId;
    (void)bNetId;
    (void)reason;
    if (!gTradeOpen) {
        return;
    }
    gTradeEndText = text != nullptr ? text : "";
    gTradeEndPending = true;
    clientBarterOnEnd(); // latches; the screen's loop breaks, the main loop finalizes
}

bool clientTradeActive()
{
    return gTradeOpen && !gTradeEndPending;
}

void clientTradeSyncWindows()
{
    if (!clientTradeActive() || gTradeWindowsBuilt || clientDialogActive()) {
        return;
    }
    Object* them = tradeOther();
    if (them == nullptr) {
        return; // not in the mirror yet; try again next frame
    }
    // What clientModalWindowsSync does for a conversation, minus the conversation:
    // the session windows (background + the world view where a talking head would
    // be, centred on the other player) and the node windows, with the option list
    // hidden so only the reply area stays — that is where the status line and an
    // inspected item's description render. gGameDialogSpeaker is what the barter
    // window builds its merchant proxy from, so it must be the other player.
    gGameDialogSpeaker = them;
    gGameDialogSpeakerIsPartyMember = false;
    gGameDialogHeadFid = -1;
    gGameDialogFidget = 0;
    _gdialogInitFromScript(-1, 0);
    gGameDialogSpeakerIsPartyMember = false; // barter.frm and "$", not the companion trade.frm
    gameDialogInitNodeWindows();
    // Draw one empty node: the reply window's draw callback is what caches the
    // handle gameDialogRenderSupplementaryMessage writes to (_demo_copy_title), and
    // a conversation would have drawn its first node by now. Without this the
    // status line and the inspected-item descriptions would hit a -1 (or stale)
    // handle and render nothing.
    gameDialogClearOptions();
    gameDialogSetReplyText("");
    gameDialogRenderNode();
    gameDialogSetOptionsWindowVisible(false);
    gTradeWindowsBuilt = true;
    inventoryTradeViewerSetHooks(tradeRenderStatus, tradeCanTakeFromOther);
    tradeRenderStatus();
    debugPrint("client_trade: session windows built for the trade\n");
}

void clientTradeAbortIfUnopened()
{
    // The barter open check just ran. If the trade is still active here and the
    // screen is not up, inventoryOpenTradeViewer refused (its proto/window guards)
    // — leave the trade instead of asking every frame.
    if (!clientTradeActive() || !clientBarterActive()) {
        return;
    }
    if ((GameMode::getCurrentGameMode() & GameMode::kBarter) != 0) {
        return;
    }
    debugPrint("client_trade: the trade screen would not open — leaving the trade\n");
    clientViewerBarterVerb("bdone", -1, 0);
    gTradeEndText = "The trade screen could not be opened.";
    gTradeEndPending = true;
    clientBarterOnEnd();
}

void clientTradeFinalize()
{
    if (!gTradeOpen || !gTradeEndPending) {
        return;
    }
    if (gTradeWindowsBuilt) {
        inventoryTradeViewerSetHooks(nullptr, nullptr);
        // Teardown order as clientModalWindowsSync: node windows, then the session.
        gameDialogExitNodeWindows();
        _gdialogExitFromScript();
        gTradeWindowsBuilt = false;
    }
    if (!gTradeEndText.empty()) {
        displayMonitorAddMessageStyled((char*)gTradeEndText.c_str(), kMsgChannelSystem);
    }
    debugPrint("client_trade: trade closed (%s)\n", gTradeEndText.c_str());
    gTradeOpen = false;
    gTradeEndPending = false;
    gTradeOtherNetId = 0;
    gTradeLockedMe = false;
    gTradeLockedThem = false;
    gTradeConfirming = false;
    gTradeEndText.clear();
}

} // namespace fallout
