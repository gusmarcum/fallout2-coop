// Standalone main-based regression for redosing permanent Jet withdrawal.
// Uses production item.cc with mocked engine services; no per-player addiction code.
// g++ -std=c++17 -O2 -flto -fwhole-program -ffunction-sections -fdata-sections \
//   -Isrc -I<SDL2-include> tests/jet_redose_persistent_withdrawal_test.cc \
//   -Wl,--gc-sections -o jet-redose-test
#ifdef NDEBUG
#error This test requires assertions enabled.
#endif
#include "../src/item.cc"
#include <array>
#include <cassert>
#include <list>
#include <map>

namespace fallout {
Object* gDude;
static Object actors[3]; // host and two independently controlled players
static std::map<int, Proto> protos;
static int globals[1000];
int* gGameGlobalVars = globals;
static std::map<Object*, int> playerFlags;
static bool dedicated = true, viewer = false, loading = false;
static unsigned int now;
static int rngCalls;
static int roll = 1;
static bool failQueueAdd = false;
static std::map<Object*, int> penalties;
static std::map<Object*, int> traitFlags;
static std::map<Object*, std::array<int, STAT_COUNT>> bonuses;
struct TestEvent { Object* owner; int type; unsigned int time; void* data; };
static std::list<TestEvent> events;
static std::list<TestEvent>::iterator cursor;
struct MemoryInts { std::vector<int> values; size_t position = 0; };

bool playerActorIs(Object* actor) { return actor == &actors[0] || actor == &actors[1] || actor == &actors[2]; }
int playerActorCount() { return 3; }
Object* playerActorAt(int slot) { return &actors[slot]; }
bool serverDedicatedActive() { return dedicated; }
bool clientViewerActive() { return viewer; }
bool _isLoadingGame() { return loading; }
bool objectIsPartyMember(Object* actor) { return playerActorIs(actor) || actor == &actors[1]; }
bool critterIsDead(Object*) { return false; }
int critterGetBodyType(Object*) { return BODY_TYPE_BIPED; }
int protoGetProto(int pid, Proto** proto) {
    assert(protos.count(pid) == 1);
    *proto = &protos.at(pid);
    return 0;
}
void dudeEnableState(int state, Object* actor) { playerFlags[actor ? actor : gDude] |= 1 << state; }
void dudeDisableState(int state, Object* actor) { playerFlags[actor ? actor : gDude] &= ~(1 << state); }
bool dudeHasState(int state, Object* actor) { return (playerFlags[actor ? actor : gDude] & (1 << state)) != 0; }
int critterGetBonusStat(Object* actor, int stat) { return bonuses[actor][stat]; }
int critterSetBonusStat(Object* actor, int stat, int value) { bonuses[actor][stat] = value; return 0; }
int critterGetStat(Object* actor, int stat) {
    return stat == STAT_CURRENT_HIT_POINTS ? 100 : 5 + bonuses[actor][stat];
}
int critterGetBaseStatWithTraitModifier(Object*, int) { return 100; }
void perkAddEffect(Object* actor, int perk) {
    penalties[actor]++;
    if (perk == PERK_JET_ADDICTION) bonuses[actor][STAT_MAXIMUM_ACTION_POINTS]--;
}
void perkRemoveEffect(Object* actor, int perk) {
    penalties[actor]--;
    if (perk == PERK_JET_ADDICTION) bonuses[actor][STAT_MAXIMUM_ACTION_POINTS]++;
}
int perkGetRank(Object*, int) { return 0; }
char* perkGetDescription(int) { return nullptr; }
bool traitIsSelected(int trait, Object* actor) { return (traitFlags[actor] & (1 << trait)) != 0; }
int debugPrint(const char*, ...) { return 0; }
bool messageListGetItem(MessageList*, MessageListItem*) { return false; }
char* statGetName(int) { return nullptr; }
char* critterGetName(Object*) { return nullptr; }
char* getmsg(MessageList*, MessageListItem*, int) { return nullptr; }
int randomBetween(int low, int high) { assert(low == 1 && high == 100); rngCalls++; return roll; }
void _combatKillCritterOutsideCombat(Object*, char*) { assert(false); }
Presenter* presenter() { static Presenter nullPresenter; return &nullPresenter; }
void* internal_malloc(size_t size) { return malloc(size); }
void internal_free(void* data) { free(data); }
int fileWriteInt32(File* stream, int value) {
    reinterpret_cast<MemoryInts*>(stream)->values.push_back(value);
    return 0;
}
int fileReadInt32(File* stream, int* value) {
    auto* memory = reinterpret_cast<MemoryInts*>(stream);
    if (memory->position == memory->values.size()) return -1;
    *value = memory->values[memory->position++];
    return 0;
}
int queueAddEvent(int delay, Object* owner, void* data, int type) {
    if (failQueueAdd) return -1;
    events.push_back({owner, type, now + delay, data});
    return 0;
}
void* queueFindNextEvent(Object* owner, int type) {
    while (cursor != events.end()) {
        auto& event = *cursor++;
        if (event.owner == owner && event.type == type) return event.data;
    }
    return nullptr;
}
void* queueFindFirstEvent(Object* owner, int type) {
    cursor = events.begin();
    return queueFindNextEvent(owner, type);
}
void _queue_clear_type(int type, QueueEventHandler* callback, Object* owner) {
    for (auto it = events.begin(); it != events.end();) {
        if (it->type != type || (owner != nullptr && it->owner != owner)) { ++it; continue; }
        // Like the production queue, unlink before invoking a handler that can
        // append a replacement event. A non-removing handler retains the original.
        auto current = it++;
        std::list<TestEvent> detached;
        detached.splice(detached.begin(), events, current);
        if (callback == nullptr || callback(detached.front().owner, detached.front().data) == 1) {
            free(detached.front().data);
        } else {
            events.splice(it, detached);
        }
    }
}
static void advanceTo(unsigned int time) {
    while (true) {
        auto next = events.end();
        for (auto it = events.begin(); it != events.end(); ++it) {
            if (it->time <= time && (next == events.end() || it->time < next->time)) next = it;
        }
        if (next == events.end()) break;

        TestEvent event = *next;
        events.erase(next);
        now = event.time;
        if (event.type == EVENT_TYPE_WITHDRAWAL) withdrawalEventProcess(event.owner, event.data);
        else drugEffectEventProcess(event.owner, event.data);
        free(event.data);
    }
    now = time;
}
static int countWithdrawal(Object* owner, int pid) {
    int count = 0;
    for (const auto& event : events) {
        if (event.owner == owner && event.type == EVENT_TYPE_WITHDRAWAL
            && static_cast<WithdrawalEvent*>(event.data)->pid == pid) count++;
    }
    return count;
}
static void reset() {
    for (const auto& event : events) free(event.data);
    events.clear();
    penalties.clear();
    traitFlags.clear();
    bonuses.clear();
    std::fill(std::begin(globals), std::end(globals), 0);
    now = 0;
    playerFlags.clear();
    rngCalls = 0;
    dedicated = false;
    viewer = loading = false;
    gDude = &actors[0];
    roll = 1;
    failQueueAdd = false;
}
static void take(Object* actor, int pid) {
    Object drug{};
    drug.pid = pid;
    assert(_item_d_take_drug(actor, &drug) == 1);
}
static void addProto(int pid, int perk) {
    auto& proto = protos[pid];
    proto.item.data.drug.addictionChance = 50;
    proto.item.data.drug.withdrawalOnset = 1;
    proto.item.data.drug.withdrawalEffect = perk;
    for (int& stat : proto.item.data.drug.stat) stat = -1;
}
} // namespace fallout

int main()
{
    using namespace fallout;
    for (int slot = 0; slot < 3; slot++) {
        actors[slot].pid = 0x01000000 + slot;
        actors[slot].netId = slot + 1;
    }
    Object* host = &actors[0];
    addProto(PROTO_ID_JET, PERK_JET_ADDICTION);
    addProto(PROTO_ID_MENTATS, PERK_MENTATS_ADDICTION);
    auto& jet = protos.at(PROTO_ID_JET).item.data.drug;
    jet.withdrawalOnset = 3;
    jet.stat[0] = STAT_MAXIMUM_ACTION_POINTS;
    jet.amount[0] = 2;
    jet.amount1[0] = -1;
    jet.amount2[0] = -1;
    jet.duration1 = 1;
    jet.duration2 = 2;

    // Pending onset and active withdrawal already have an event to reset:
    // never remove a penalty twice, duplicate an onset or reroll addiction.
    for (unsigned int redoseTime : {100u, 1800u}) {
        reset();
        take(host, PROTO_ID_JET);
        advanceTo(redoseTime);
        assert(penalties[host] == (redoseTime == 1800 ? 1 : 0));
        take(host, PROTO_ID_JET);
        assert(penalties[host] == 0 && rngCalls == 1);
        assert(countWithdrawal(host, PROTO_ID_JET) == 1);
        advanceTo(redoseTime + 1800);
        assert(penalties[host] == 1);
    }

    // After the end event expires (also the shape of an old loaded save),
    // redose suspends the penalty and restarts the complete cycle.
    reset();
    take(host, PROTO_ID_JET);
    advanceTo(1800 + 600 * 10080);
    assert(events.empty() && penalties[host] == 1);
    assert(bonuses[host][STAT_MAXIMUM_ACTION_POINTS] == -1);
    assert(globals[GVAR_ADDICT_JET] == 1);
    unsigned int redoseTime = now;
    take(host, PROTO_ID_JET);
    assert(penalties[host] == 0 && rngCalls == 1);
    assert(bonuses[host][STAT_MAXIMUM_ACTION_POINTS] == 2);
    assert(countWithdrawal(host, PROTO_ID_JET) == 1);
    assert(globals[GVAR_ADDICT_JET] == 1 && dudeHasState(DUDE_STATE_ADDICTED, host));
    advanceTo(redoseTime + 600);
    assert(bonuses[host][STAT_MAXIMUM_ACTION_POINTS] == 1 && penalties[host] == 0);
    advanceTo(redoseTime + 1200);
    assert(bonuses[host][STAT_MAXIMUM_ACTION_POINTS] == 0 && penalties[host] == 0);
    advanceTo(redoseTime + 1800);
    assert(penalties[host] == 1);
    advanceTo(redoseTime + 1800 + 600 * 10080);
    assert(events.empty() && penalties[host] == 1);
    take(host, PROTO_ID_JET);
    assert(penalties[host] == 0 && countWithdrawal(host, PROTO_ID_JET) == 1);

    // An unrelated withdrawal must not hide the missing Jet event. Another
    // actor's Jet event must neither count as ours nor be changed by the redose.
    reset();
    globals[GVAR_ADDICT_JET] = 1;
    dudeEnableState(DUDE_STATE_ADDICTED, host);
    penalties[host] = 1;
    _insert_withdrawal(host, 1, 20, PERK_MENTATS_ADDICTION, PROTO_ID_MENTATS);
    _insert_withdrawal(&actors[1], 1, 30, PERK_JET_ADDICTION, PROTO_ID_JET);
    auto oldEvents = events;
    take(host, PROTO_ID_JET);
    assert(penalties[host] == 0 && rngCalls == 0);
    assert(countWithdrawal(host, PROTO_ID_MENTATS) == 1);
    assert(countWithdrawal(&actors[1], PROTO_ID_JET) == 1);
    auto current = events.begin();
    for (const auto& original : oldEvents) {
        assert(current->owner == original.owner && current->data == original.data);
        assert(current->time == original.time);
        ++current;
    }

    // A clean player must not get a phantom penalty reversal or forced addiction.
    reset();
    roll = 100;
    take(host, PROTO_ID_JET);
    assert(penalties[host] == 0 && countWithdrawal(host, PROTO_ID_JET) == 0);
    assert(globals[GVAR_ADDICT_JET] == 0 && rngCalls == 1);

    // The player's global flag is not evidence of an NPC's permanent penalty.
    reset();
    globals[GVAR_ADDICT_JET] = 1;
    Object npc{};
    npc.pid = 0x01000099;
    take(&npc, PROTO_ID_JET);
    assert(penalties[&npc] == 0);

    // Queue allocation failure must not silently cure permanent withdrawal.
    reset();
    globals[GVAR_ADDICT_JET] = 1;
    penalties[host] = 1;
    failQueueAdd = true;
    take(host, PROTO_ID_JET);
    assert(penalties[host] == 1 && countWithdrawal(host, PROTO_ID_JET) == 0);
    reset();
    puts("PASS: permanent Jet redose, pending/active events, drug stages, repeated cycles, ownership, clean player, NPC and queue failure");
}

