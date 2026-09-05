#include "server_trade.h"

#include <chrono>
#include <cstdio>
#include <cstring>

#include "combat.h" // isInCombat — a fight ends the trade
#include "critter.h" // critterIsDead / critterGetName
#include "game.h" // GameMode — another server modal claiming the world ends the trade
#include "game_dialog.h" // gameDialogServerNodeActive
#include "inventory.h" // stealSessionActive / invenRederiveWeaponFid
#include "item.h" // itemMoveForce / itemMoveAll / itemGetQuantity / objectGetCost / weights
#include "map.h" // mapGetLoadGeneration — a map change ends the trade
#include "msg_channel.h"
#include "obj_types.h"
#include "object.h"
#include "presenter.h"
#include "server_control.h" // serverControlSessionForSlot — is a party still connected
#include "server_players.h"
#include "stat.h" // critterGetStat / STAT_CARRY_WEIGHT — can they carry what they get
#include "wire_defs.h" // kNoSessionId

namespace fallout {

namespace {

enum class TradeState {
    kIdle,
    kInvited, // the target has the invitation box up
    kOpen, // both screens are up, tables are being arranged
    kConfirming, // both tables locked, both accept boxes are up
};

// End reasons, as the wire carries them (presenter.h tradeEnd).
enum {
    kEndCompleted = 0,
    kEndCancelled = 1,
    kEndDeclined = 2,
    kEndBailed = 3,
};

constexpr int kInviteSeconds = 30; // an unanswered invitation expires
constexpr int kConfirmSeconds = 60; // an unanswered accept box cancels the trade
constexpr int kOpenMinutes = 15; // two players idling in the screen
constexpr int kInviteMaxDistance = 3; // hexes the proposer may wander while waiting

TradeState gState = TradeState::kIdle;
int gSlotA = -1; // the proposer's registry slot
int gSlotB = -1; // the invited player's registry slot
Object* gTableA = nullptr;
Object* gTableB = nullptr;
bool gLockedA = false;
bool gLockedB = false;
int gPromptInvite = 0;
int gPromptA = 0;
int gPromptB = 0;
int gAnswerA = -1; // -1 unanswered, 0 no, 1 yes
int gAnswerB = -1;
unsigned int gGeneration = 0; // map load generation the screens opened in
std::chrono::steady_clock::time_point gDeadline;
int gNextPromptId = 1;

Object* actorA() { return gSlotA >= 0 ? playerActorAt(gSlotA) : nullptr; }
Object* actorB() { return gSlotB >= 0 ? playerActorAt(gSlotB) : nullptr; }

// critterGetName hands out a shared buffer; two names in one line need a copy.
void copyName(Object* who, char* out, size_t size)
{
    const char* name = who != nullptr ? critterGetName(who) : nullptr;
    snprintf(out, size, "%s", name != nullptr && name[0] != '\0' ? name : "Someone");
}

void say(Object* who, int channel, const char* text)
{
    if (who != nullptr) {
        presenter()->consoleMessageStyled(who->netId, channel, text);
    }
}

// Everyone who is NOT a party: the parties learn the same thing from the trade
// events, and a line they would only read after their screen closes is noise.
void tellOthers(const char* text)
{
    for (int slot = 0; slot < playerActorCount(); slot++) {
        if (slot == gSlotA || slot == gSlotB) {
            continue;
        }
        Object* other = playerActorAt(slot);
        if (other != nullptr && playerActorOnline(slot)) {
            presenter()->consoleMessageStyled(other->netId, kMsgChannelSystem, text);
        }
    }
}

bool slotOnline(int slot)
{
    return slot >= 0 && playerActorOnline(slot) && serverControlSessionForSlot(slot) != kNoSessionId;
}

int nextPromptId()
{
    int id = gNextPromptId++;
    if (gNextPromptId <= 0) {
        gNextPromptId = 1;
    }
    return id;
}

// The offer tables are vanilla's own scratch containers: pid -1, hidden, never on
// the wire (object.cc emits no SPAWN for a pid -1 object), destroyed WITH their
// contents — which is why every exit below sweeps them first.
Object* createTable()
{
    Object* table = nullptr;
    if (objectCreateWithFidPid(&table, -1, -1) == -1) {
        return nullptr;
    }
    table->flags |= OBJECT_HIDDEN;
    return table;
}

bool isEquipped(Object* item)
{
    return (item->flags & (OBJECT_IN_LEFT_HAND | OBJECT_IN_RIGHT_HAND | OBJECT_WORN)) != 0;
}

Object* findItemByPid(Object* owner, int pid)
{
    Inventory* inv = &(owner->data.inventory);
    for (int i = 0; i < inv->length; i++) {
        Object* item = inv->items[i].item;
        if (item != nullptr && item->pid == pid) {
            return item;
        }
    }
    return nullptr;
}

// Worn and held gear is never offered (a merchant trade stages it out of reach for
// the same reason), so the pack the other side sees leaves it out too.
int snapshot(Object* owner, Presenter::BarterStack* rows, int max, bool skipEquipped)
{
    int count = 0;
    if (owner == nullptr) {
        return 0;
    }
    Inventory* inv = &(owner->data.inventory);
    for (int i = 0; i < inv->length && count < max; i++) {
        Object* item = inv->items[i].item;
        if (item == nullptr || (skipEquipped && isEquipped(item))) {
            continue;
        }
        rows[count].pid = item->pid;
        rows[count].quantity = inv->items[i].quantity;
        count++;
    }
    return count;
}

void emitState()
{
    Object* a = actorA();
    Object* b = actorB();
    if (a == nullptr || b == nullptr || gTableA == nullptr || gTableB == nullptr) {
        return;
    }
    constexpr int kMaxRows = 64;
    Presenter::BarterStack invA[kMaxRows];
    Presenter::BarterStack invB[kMaxRows];
    Presenter::BarterStack tableA[kMaxRows];
    Presenter::BarterStack tableB[kMaxRows];

    Presenter::TradeView view;
    view.aNetId = a->netId;
    view.bNetId = b->netId;
    view.invACount = snapshot(a, invA, kMaxRows, true);
    view.invA = invA;
    view.invBCount = snapshot(b, invB, kMaxRows, true);
    view.invB = invB;
    view.tableACount = snapshot(gTableA, tableA, kMaxRows, false);
    view.tableA = tableA;
    view.tableBCount = snapshot(gTableB, tableB, kMaxRows, false);
    view.tableB = tableB;
    view.valueA = objectGetCost(gTableA);
    view.valueB = objectGetCost(gTableB);
    view.lockedA = gLockedA;
    view.lockedB = gLockedB;
    view.confirming = gState == TradeState::kConfirming;
    presenter()->tradeState(view);
}

// "2x Stimpak, 150x Bottle Caps" — for the accept box. Short, because the box
// is small; a long list ends in "...".
void describeTable(Object* table, char* out, size_t size)
{
    out[0] = '\0';
    if (table == nullptr) {
        return;
    }
    Inventory* inv = &(table->data.inventory);
    if (inv->length == 0) {
        snprintf(out, size, "nothing");
        return;
    }
    size_t used = 0;
    for (int i = 0; i < inv->length; i++) {
        Object* item = inv->items[i].item;
        if (item == nullptr) {
            continue;
        }
        char piece[96];
        const char* name = itemGetName(item);
        snprintf(piece, sizeof(piece), "%s%dx %s", used > 0 ? ", " : "",
            inv->items[i].quantity, name != nullptr ? name : "item");
        size_t need = strlen(piece);
        if (used + need + 4 >= size) {
            snprintf(out + used, size - used, "...");
            return;
        }
        memcpy(out + used, piece, need + 1);
        used += need;
    }
}

// After the swap `who` carries everything it has now plus the other table.
// (Its own offer already left the pack when it went on the table.)
bool canCarry(Object* who, Object* gets)
{
    int carry = critterGetStat(who, STAT_CARRY_WEIGHT);
    return objectGetInventoryWeight(who) + objectGetInventoryWeight(gets) <= carry;
}

void resetState()
{
    gState = TradeState::kIdle;
    gSlotA = -1;
    gSlotB = -1;
    gTableA = nullptr;
    gTableB = nullptr;
    gLockedA = false;
    gLockedB = false;
    gPromptInvite = 0;
    gPromptA = 0;
    gPromptB = 0;
    gAnswerA = -1;
    gAnswerB = -1;
    gGeneration = 0;
}

// An invitation that never became a trade: dismiss the box, tell the proposer.
void dropInvitation(const char* why)
{
    Object* a = actorA();
    Object* b = actorB();
    if (b != nullptr && gPromptInvite != 0) {
        presenter()->promptClose(b->netId, gPromptInvite);
    }
    char nameB[64];
    copyName(b, nameB, sizeof(nameB));
    char line[200];
    snprintf(line, sizeof(line), "No trade with %s: %s", nameB, why);
    say(a, kMsgChannelRefusal, line);
    fprintf(stderr, "f2_server: trade invitation slot %d -> %d dropped (%s)\n", gSlotA, gSlotB, why);
    resetState();
}

// The trade's one exit. Everything still on a table goes back to whoever put it
// there (a completed trade has already swapped and emptied them), the tables die,
// the accept boxes close, and both screens are told to come down with `text`.
void closeTrade(int reason, const char* text)
{
    Object* a = actorA();
    Object* b = actorB();
    int aNet = a != nullptr ? a->netId : 0;
    int bNet = b != nullptr ? b->netId : 0;

    if (gState == TradeState::kConfirming) {
        if (a != nullptr && gPromptA != 0) {
            presenter()->promptClose(aNet, gPromptA);
        }
        if (b != nullptr && gPromptB != 0) {
            presenter()->promptClose(bNet, gPromptB);
        }
    }

    if (gTableA != nullptr) {
        if (a != nullptr) {
            itemMoveAll(gTableA, a);
        }
        objectDestroy(gTableA, nullptr);
        gTableA = nullptr;
    }
    if (gTableB != nullptr) {
        if (b != nullptr) {
            itemMoveAll(gTableB, b);
        }
        objectDestroy(gTableB, nullptr);
        gTableB = nullptr;
    }
    if (a != nullptr) {
        invenRederiveWeaponFid(a);
    }
    if (b != nullptr) {
        invenRederiveWeaponFid(b);
    }

    fprintf(stderr, "f2_server: trade slot %d <-> %d closed: reason=%d (%s)\n", gSlotA, gSlotB, reason, text);
    presenter()->tradeEnd(aNet, bNet, reason, text);
    if (reason == kEndCompleted) {
        tellOthers(text);
    }
    resetState();
}

void openTrade()
{
    Object* a = actorA();
    Object* b = actorB();
    gTableA = createTable();
    gTableB = createTable();
    if (a == nullptr || b == nullptr || gTableA == nullptr || gTableB == nullptr) {
        if (gTableA != nullptr) {
            objectDestroy(gTableA, nullptr);
        }
        if (gTableB != nullptr) {
            objectDestroy(gTableB, nullptr);
        }
        gTableA = nullptr;
        gTableB = nullptr;
        dropInvitation("the trade could not be set up");
        return;
    }

    gState = TradeState::kOpen;
    gLockedA = false;
    gLockedB = false;
    gGeneration = mapGetLoadGeneration();
    gDeadline = std::chrono::steady_clock::now() + std::chrono::minutes(kOpenMinutes);

    char nameA[64];
    char nameB[64];
    copyName(a, nameA, sizeof(nameA));
    copyName(b, nameB, sizeof(nameB));
    fprintf(stderr, "f2_server: trade OPEN %s (slot %d, net %d) <-> %s (slot %d, net %d)\n",
        nameA, gSlotA, a->netId, nameB, gSlotB, b->netId);

    presenter()->tradeBegin(a->netId, b->netId);
    emitState();

    char line[200];
    snprintf(line, sizeof(line), "%s and %s are trading.", nameA, nameB);
    tellOthers(line);
}

void beginConfirm()
{
    Object* a = actorA();
    Object* b = actorB();
    if (a == nullptr || b == nullptr) {
        closeTrade(kEndBailed, "The trade was cancelled: a player is gone.");
        return;
    }
    char nameA[64];
    char nameB[64];
    copyName(a, nameA, sizeof(nameA));
    copyName(b, nameB, sizeof(nameB));

    // Weight, before anyone is asked: a yes to a trade that then fails on the
    // scales would read as the server going back on its word.
    char line[200];
    if (!canCarry(a, gTableB)) {
        snprintf(line, sizeof(line), "The trade was cancelled: %s cannot carry that much.", nameA);
        closeTrade(kEndCancelled, line);
        return;
    }
    if (!canCarry(b, gTableA)) {
        snprintf(line, sizeof(line), "The trade was cancelled: %s cannot carry that much.", nameB);
        closeTrade(kEndCancelled, line);
        return;
    }

    gState = TradeState::kConfirming;
    gAnswerA = -1;
    gAnswerB = -1;
    gPromptA = nextPromptId();
    gPromptB = nextPromptId();
    gDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(kConfirmSeconds);

    char givesA[160];
    char givesB[160];
    describeTable(gTableA, givesA, sizeof(givesA));
    describeTable(gTableB, givesB, sizeof(givesB));

    // The body carries two lines separated by '|'; the viewer splits them.
    char bodyA[400];
    char bodyB[400];
    snprintf(bodyA, sizeof(bodyA), "You give: %s|You get: %s", givesA, givesB);
    snprintf(bodyB, sizeof(bodyB), "You give: %s|You get: %s", givesB, givesA);
    presenter()->promptAsk(a->netId, gPromptA, "Accept this trade?", bodyA);
    presenter()->promptAsk(b->netId, gPromptB, "Accept this trade?", bodyB);
    fprintf(stderr, "f2_server: trade CONFIRM prompts %d (slot %d) and %d (slot %d): A gives [%s], B gives [%s]\n",
        gPromptA, gSlotA, gPromptB, gSlotB, givesA, givesB);
    emitState();
}

void commitTrade()
{
    Object* a = actorA();
    Object* b = actorB();
    if (a == nullptr || b == nullptr) {
        closeTrade(kEndBailed, "The trade was cancelled: a player is gone.");
        return;
    }
    char nameA[64];
    char nameB[64];
    copyName(a, nameA, sizeof(nameA));
    copyName(b, nameB, sizeof(nameB));
    char line[200];
    if (!canCarry(a, gTableB) || !canCarry(b, gTableA)) {
        snprintf(line, sizeof(line), "The trade was cancelled: someone cannot carry that much.");
        closeTrade(kEndCancelled, line);
        return;
    }

    // The swap: each table goes to the OTHER party. itemMoveAll merges stacks the
    // ordinary way, so caps land on caps and stimpaks on stimpaks.
    itemMoveAll(gTableA, b);
    itemMoveAll(gTableB, a);
    snprintf(line, sizeof(line), "%s and %s completed a trade.", nameA, nameB);
    closeTrade(kEndCompleted, line);
}

} // namespace

void serverTradePropose(Object* proposer, Object* target)
{
    if (proposer == nullptr || target == nullptr || proposer == target) {
        return;
    }
    int slotA = playerActorSlotOf(proposer);
    int slotB = playerActorSlotOf(target);
    if (slotA < 0 || slotB < 0) {
        return;
    }
    char nameA[64];
    char nameB[64];
    copyName(proposer, nameA, sizeof(nameA));
    copyName(target, nameB, sizeof(nameB));
    char line[200];

    if (gState != TradeState::kIdle) {
        say(proposer, kMsgChannelRefusal, "Another trade is already in progress.");
        return;
    }
    if (isInCombat()) {
        say(proposer, kMsgChannelRefusal, "You cannot trade during combat.");
        return;
    }
    if (critterIsDead(proposer)) {
        return;
    }
    if (critterIsDead(target)) {
        snprintf(line, sizeof(line), "%s is dead. Revive them instead.", nameB);
        say(proposer, kMsgChannelRefusal, line);
        return;
    }
    if (!slotOnline(slotB)) {
        snprintf(line, sizeof(line), "%s is not in the game right now.", nameB);
        say(proposer, kMsgChannelRefusal, line);
        return;
    }

    gState = TradeState::kInvited;
    gSlotA = slotA;
    gSlotB = slotB;
    gPromptInvite = nextPromptId();
    gDeadline = std::chrono::steady_clock::now() + std::chrono::seconds(kInviteSeconds);

    char title[128];
    snprintf(title, sizeof(title), "%s wants to barter with you.", nameA);
    presenter()->promptAsk(target->netId, gPromptInvite, title, "Open the trade screen?");
    snprintf(line, sizeof(line), "Waiting for %s to answer...", nameB);
    say(proposer, kMsgChannelSystem, line);
    fprintf(stderr, "f2_server: trade INVITE prompt %d: %s (slot %d) -> %s (slot %d)\n",
        gPromptInvite, nameA, slotA, nameB, slotB);
}

bool serverTradeInvolves(Object* actor)
{
    if (gState == TradeState::kIdle || actor == nullptr) {
        return false;
    }
    int slot = playerActorSlotOf(actor);
    return slot >= 0 && (slot == gSlotA || slot == gSlotB);
}

bool serverTradeActive()
{
    return gState == TradeState::kOpen || gState == TradeState::kConfirming;
}

bool serverTradePending()
{
    return gState == TradeState::kInvited;
}

bool serverTradeVerb(Object* actor, int sessionId, const char* verb, int pid, int quantity)
{
    (void)sessionId;
    if (!serverTradeActive() || actor == nullptr) {
        return false;
    }
    if (!serverTradeInvolves(actor)) {
        say(actor, kMsgChannelRefusal, "This isn't your trade.");
        return true;
    }
    bool isA = playerActorSlotOf(actor) == gSlotA;
    Object* self = actor;
    Object* myTable = isA ? gTableA : gTableB;
    bool& myLock = isA ? gLockedA : gLockedB;
    char name[64];
    copyName(actor, name, sizeof(name));
    char line[200];

    if (strcmp(verb, "bdone") == 0 || strcmp(verb, "bcancel") == 0) {
        snprintf(line, sizeof(line), "%s cancelled the trade.", name);
        closeTrade(kEndCancelled, line);
        return true;
    }
    if (gState == TradeState::kConfirming) {
        say(actor, kMsgChannelRefusal, "Answer the question first.");
        return true;
    }
    if (strcmp(verb, "bcommit") == 0) {
        // Offer = lock my table; pressed again = unlock, as long as the question is
        // not out yet. The second lock is what starts the accept boxes.
        myLock = !myLock;
        fprintf(stderr, "f2_server: trade %s %s their offer\n", name, myLock ? "locked" : "unlocked");
        if (gLockedA && gLockedB) {
            beginConfirm();
        } else {
            emitState();
        }
        return true;
    }
    if (strcmp(verb, "btake") == 0) {
        say(actor, kMsgChannelRefusal, "They have to offer it.");
        return true;
    }
    if (myLock) {
        say(actor, kMsgChannelRefusal, "Your offer is locked. Press Offer again to change it.");
        return true;
    }
    if (strcmp(verb, "boffer") == 0) {
        Object* item = findItemByPid(self, pid);
        if (item == nullptr) {
            say(actor, kMsgChannelRefusal, "That item is gone.");
            emitState();
            return true;
        }
        if (isEquipped(item)) {
            say(actor, kMsgChannelRefusal, "Unequip it first.");
            return true;
        }
        int available = itemGetQuantity(self, item);
        if (quantity <= 0 || quantity > available) {
            quantity = available;
        }
        itemMoveForce(self, myTable, item, quantity);
        fprintf(stderr, "f2_server: trade %s offers pid=%d qty=%d\n", name, pid, quantity);
        emitState();
        return true;
    }
    if (strcmp(verb, "bunoffer") == 0) {
        Object* item = findItemByPid(myTable, pid);
        if (item == nullptr) {
            say(actor, kMsgChannelRefusal, "That item is not on your table.");
            emitState();
            return true;
        }
        int available = itemGetQuantity(myTable, item);
        if (quantity <= 0 || quantity > available) {
            quantity = available;
        }
        itemMoveForce(myTable, self, item, quantity);
        fprintf(stderr, "f2_server: trade %s takes back pid=%d qty=%d\n", name, pid, quantity);
        emitState();
        return true;
    }
    return false;
}

bool serverTradeAnswer(Object* actor, int promptId, bool yes)
{
    if (actor == nullptr || gState == TradeState::kIdle || promptId == 0) {
        return false;
    }
    int slot = playerActorSlotOf(actor);
    char name[64];
    copyName(actor, name, sizeof(name));
    char line[200];

    if (gState == TradeState::kInvited) {
        if (slot != gSlotB || promptId != gPromptInvite) {
            return false;
        }
        fprintf(stderr, "f2_server: trade invitation %d answered %s by %s\n", promptId, yes ? "YES" : "NO", name);
        if (!yes) {
            snprintf(line, sizeof(line), "%s declined to trade.", name);
            Object* a = actorA();
            say(a, kMsgChannelSystem, line);
            resetState();
            return true;
        }
        Object* a = actorA();
        Object* b = actorB();
        if (a == nullptr || b == nullptr || critterIsDead(a) || !slotOnline(gSlotA) || isInCombat()
            || a->elevation != b->elevation || objectGetDistanceBetween(a, b) > kInviteMaxDistance) {
            dropInvitation("the trade could not start (someone moved away, left, or a fight began)");
            return true;
        }
        openTrade();
        return true;
    }

    if (gState == TradeState::kConfirming) {
        if (slot == gSlotA && promptId == gPromptA) {
            gAnswerA = yes ? 1 : 0;
        } else if (slot == gSlotB && promptId == gPromptB) {
            gAnswerB = yes ? 1 : 0;
        } else {
            return false;
        }
        fprintf(stderr, "f2_server: trade accept %d answered %s by %s (A=%d B=%d)\n",
            promptId, yes ? "YES" : "NO", name, gAnswerA, gAnswerB);
        if (!yes) {
            snprintf(line, sizeof(line), "%s declined the trade.", name);
            closeTrade(kEndDeclined, line);
            return true;
        }
        if (gAnswerA == 1 && gAnswerB == 1) {
            commitTrade();
        }
        return true;
    }
    return false;
}

void serverTradeCancel(const char* why)
{
    if (gState == TradeState::kIdle) {
        return;
    }
    if (gState == TradeState::kInvited) {
        dropInvitation(why != nullptr ? why : "cancelled");
        return;
    }
    char line[200];
    snprintf(line, sizeof(line), "The trade was cancelled: %s.", why != nullptr ? why : "cancelled");
    closeTrade(kEndBailed, line);
}

void serverTradeTick()
{
    if (gState == TradeState::kIdle) {
        return;
    }
    Object* a = actorA();
    Object* b = actorB();
    const char* why = nullptr;
    char detail[128];
    detail[0] = '\0';

    if (a == nullptr || b == nullptr) {
        why = "a player is gone";
    } else if (!slotOnline(gSlotA) || !slotOnline(gSlotB)) {
        char name[64];
        copyName(slotOnline(gSlotA) ? b : a, name, sizeof(name));
        snprintf(detail, sizeof(detail), "%s left the game", name);
        why = detail;
    } else if (critterIsDead(a) || critterIsDead(b)) {
        char name[64];
        copyName(critterIsDead(a) ? a : b, name, sizeof(name));
        snprintf(detail, sizeof(detail), "%s is dead", name);
        why = detail;
    } else if (isInCombat()) {
        why = "a fight started";
    } else if (gState != TradeState::kInvited && mapGetLoadGeneration() != gGeneration) {
        why = "the map changed";
    } else if (gameDialogServerNodeActive() || stealSessionActive()
        || GameMode::isInGameMode(GameMode::kDialog | GameMode::kBarter | GameMode::kWorldmap)) {
        why = "something else took the screen";
    } else if (std::chrono::steady_clock::now() > gDeadline) {
        why = gState == TradeState::kInvited ? "no answer"
            : gState == TradeState::kConfirming ? "nobody answered the accept box"
                                               : "the trade sat idle too long";
    } else if (gState == TradeState::kInvited
        && (a->elevation != b->elevation || objectGetDistanceBetween(a, b) > kInviteMaxDistance)) {
        why = "you walked away";
    }

    if (why == nullptr) {
        return;
    }
    serverTradeCancel(why);
}

} // namespace fallout
