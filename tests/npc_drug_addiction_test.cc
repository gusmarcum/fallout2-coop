// Production drug-use/withdrawal routines; stub queue, RNG, stats and perk effects.
// Checks decisions/draw counts, not the old incidental global RNG sequence.
// Includes a withdrawal payload round-trip, not a full game-save/network test.
// Inspired by sfall's NPCDrugAddictionFix and recurring Jet withdrawal event:
// https://github.com/sfall-team/sfall/blob/6c65e67342bda1488671601e417194199ec72a09/sfall/Modules/BugFixes.cpp#L4117-L4124
// g++ -std=c++17 -O2 -flto -fwhole-program -ffunction-sections -fdata-sections \
//   -Isrc -I<SDL2-include> tests/npc_drug_addiction_test.cc \
//   -Wl,--gc-sections -o npc-drug-addiction-test
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
static Object actors[3]; // player, companion, ordinary NPC
static std::map<int, Proto> protos;
static int globals[1000];
int* gGameGlobalVars = globals;
static int playerFlags;
static unsigned int now;
static int rngCalls;
static int roll = 1;
static std::map<Object*, int> penalties;
static std::map<Object*, std::array<int, STAT_COUNT>> bonuses;
struct TestEvent { Object* owner; int type; unsigned int time; void* data; };
static std::list<TestEvent> events;
static std::list<TestEvent>::iterator cursor;
struct MemoryInts { std::vector<int> values; size_t position = 0; };

bool playerActorIs(Object* actor) { return actor == &actors[0]; }
bool objectIsPartyMember(Object* actor) { return playerActorIs(actor) || actor == &actors[1]; }
bool critterIsDead(Object*) { return false; }
int critterGetBodyType(Object*) { return BODY_TYPE_BIPED; }
int protoGetProto(int pid, Proto** proto) {
    assert(protos.count(pid) == 1);
    *proto = &protos.at(pid);
    return 0;
}
void dudeEnableState(int state, Object*) { playerFlags |= 1 << state; }
void dudeDisableState(int state, Object*) { playerFlags &= ~(1 << state); }
int critterGetBonusStat(Object* actor, int stat) { return bonuses[actor][stat]; }
int critterSetBonusStat(Object* actor, int stat, int value) { bonuses[actor][stat] = value; return 0; }
int critterGetStat(Object* actor, int stat) {
    return stat == STAT_CURRENT_HIT_POINTS ? 100 : 5 + bonuses[actor][stat];
}
int critterGetBaseStatWithTraitModifier(Object*, int) { return 100; }
void perkAddEffect(Object* actor, int) { penalties[actor]++; }
void perkRemoveEffect(Object* actor, int) { penalties[actor]--; }
int perkGetRank(Object*, int) { return 0; }
char* perkGetDescription(int) { return nullptr; }
bool traitIsSelected(int, Object*) { return false; }
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
    bonuses.clear();
    std::fill(std::begin(globals), std::end(globals), 0);
    now = 0;
    playerFlags = rngCalls = 0;
    roll = 1;
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
    for (auto& actor : actors) actor.pid = 0x01000000;
    gDude = &actors[0];
    Object* companion = &actors[1];
    Object* npc = &actors[2];
    addProto(PROTO_ID_PSYCHO, PERK_PSYCHO_ADDICTION);
    addProto(PROTO_ID_JET, PERK_JET_ADDICTION);
    // Synthetic alcohol events exercise identity grouping, not an alcohol perk.
    addProto(PROTO_ID_BEER, -1);
    addProto(PROTO_ID_BOOZE, -1);
    addProto(PROTO_ID_JET_ANTIDOTE, PERK_JET_ADDICTION);

    // A player addiction must not suppress an unaddicted NPC's own first roll.
    reset();
    dudeSetAddiction(PROTO_ID_PSYCHO);
    take(companion, PROTO_ID_PSYCHO);
    assert(rngCalls == 1 && countWithdrawal(companion, PROTO_ID_PSYCHO) == 1);
    assert(globals[GVAR_PSYCHO_ADDICT] == 1);

    // A failed roll remains a failure; neither success nor failure infects player globals.
    reset();
    roll = 100;
    take(npc, PROTO_ID_PSYCHO);
    assert(rngCalls == 1 && events.empty() && globals[GVAR_PSYCHO_ADDICT] == 0);
    roll = 1;
    take(companion, PROTO_ID_PSYCHO);
    assert(rngCalls == 2 && globals[GVAR_PSYCHO_ADDICT] == 0 && playerFlags == 0);
    // Repeated dose reschedules the companion's event without another addiction roll.
    now = 20;
    take(companion, PROTO_ID_PSYCHO);
    assert(rngCalls == 2 && countWithdrawal(companion, PROTO_ID_PSYCHO) == 1);
    assert(events.front().time == 620);
    // Another NPC and the player still have independent chances to acquire addiction.
    take(npc, PROTO_ID_PSYCHO);
    assert(rngCalls == 3 && countWithdrawal(npc, PROTO_ID_PSYCHO) == 1);
    take(gDude, PROTO_ID_PSYCHO);
    assert(rngCalls == 4 && globals[GVAR_PSYCHO_ADDICT] == 1);
    take(gDude, PROTO_ID_PSYCHO);
    assert(rngCalls == 4);

    // Active non-Jet withdrawal is suppressed by a dose, then resumes and recovers.
    reset();
    take(companion, PROTO_ID_PSYCHO);
    advanceTo(600);
    assert(penalties[companion] == 1);
    take(companion, PROTO_ID_PSYCHO);
    assert(penalties[companion] == 0 && rngCalls == 1);
    assert(countWithdrawal(companion, PROTO_ID_PSYCHO) == 1);
    advanceTo(1200 + 600 * 10080);
    assert(penalties[companion] == 0 && events.empty());

    // Beer/booze retain the existing shared alcohol identity for NPCs too.
    reset();
    take(companion, PROTO_ID_BEER);
    take(companion, PROTO_ID_BOOZE);
    assert(rngCalls == 1 && events.size() == 1 && globals[GVAR_ALCOHOL_ADDICT] == 0);

    // Pending Jet cure: no extra stat compensation and no dependency on player Jet flag.
    reset();
    take(companion, PROTO_ID_JET);
    take(npc, PROTO_ID_JET);
    take(companion, PROTO_ID_JET_ANTIDOTE);
    assert(countWithdrawal(companion, PROTO_ID_JET) == 0 && penalties[companion] == 0);
    assert(countWithdrawal(npc, PROTO_ID_JET) == 1 && rngCalls == 2);
    advanceTo(600);
    assert(penalties[companion] == 0 && penalties[npc] == 1);
    take(npc, PROTO_ID_JET_ANTIDOTE);
    assert(penalties[npc] == 0 && events.empty());
    take(npc, PROTO_ID_JET_ANTIDOTE);
    assert(penalties[npc] == 0 && rngCalls == 2);

    // NPC antidote leaves other withdrawals and its own rebound deadline intact.
    reset();
    take(companion, PROTO_ID_JET);
    take(companion, PROTO_ID_PSYCHO);
    auto* rebound = static_cast<DrugEffectEvent*>(malloc(sizeof(DrugEffectEvent)));
    *rebound = {PROTO_ID_JET, {STAT_STRENGTH, -1, -1}, {-2, 0, 0}};
    bonuses[companion][STAT_STRENGTH] = 2;
    queueAddEvent(20, companion, rebound, EVENT_TYPE_DRUG);
    take(companion, PROTO_ID_JET_ANTIDOTE);
    assert(countWithdrawal(companion, PROTO_ID_JET) == 0);
    assert(countWithdrawal(companion, PROTO_ID_PSYCHO) == 1 && events.size() == 2);
    assert(events.back().data == rebound && events.back().time == 20);
    advanceTo(20);
    assert(bonuses[companion][STAT_STRENGTH] == 0 && rngCalls == 2);

    // Renew permanent Jet without reapplying its penalty; keep the old payload shape.
    reset();
    take(companion, PROTO_ID_JET);
    advanceTo(600 + 3 * 600 * 10080);
    assert(penalties[companion] == 1 && rngCalls == 1);
    assert(events.size() == 1 && countWithdrawal(companion, PROTO_ID_JET) == 1);
    TestEvent saved = events.front();
    auto* active = static_cast<WithdrawalEvent*>(saved.data);
    assert(active->field_0 == 0 && saved.time > now);
    MemoryInts stream;
    assert(withdrawalEventWrite(reinterpret_cast<File*>(&stream), active) == 0);
    assert(stream.values == std::vector<int>({0, PROTO_ID_JET, PERK_JET_ADDICTION}));
    void* restored = nullptr;
    assert(withdrawalEventRead(reinterpret_cast<File*>(&stream), &restored) == 0);
    free(saved.data);
    events.clear();
    assert(queueAddEvent(saved.time - now, saved.owner, restored, saved.type) == 0);
    // Existing active events (including older-save payloads) resume renewal as-is.
    advanceTo(saved.time);
    assert(penalties[companion] == 1 && events.size() == 1);
    take(companion, PROTO_ID_JET);
    assert(penalties[companion] == 0 && rngCalls == 1 && events.size() == 1);
    advanceTo(now + 600);
    assert(penalties[companion] == 1);
    dudeSetAddiction(PROTO_ID_JET);
    _insert_withdrawal(gDude, 1, 1, PERK_JET_ADDICTION, PROTO_ID_JET);
    take(companion, PROTO_ID_JET_ANTIDOTE);
    assert(penalties[companion] == 0 && globals[GVAR_ADDICT_JET] == 1);
    assert(countWithdrawal(gDude, PROTO_ID_JET) == 1);

    // Ordinary NPCs still lose withdrawal on map exit; companions keep theirs.
    reset();
    take(companion, PROTO_ID_JET);
    take(npc, PROTO_ID_JET);
    advanceTo(600);
    _queue_clear_type(EVENT_TYPE_WITHDRAWAL, _item_wd_clear);
    assert(penalties[companion] == 1 && countWithdrawal(companion, PROTO_ID_JET) == 1);
    assert(penalties[npc] == 0 && countWithdrawal(npc, PROTO_ID_JET) == 0);
    reset();
    puts("PASS: NPC/player isolation, success/failure and exact RNG counts, redose/recovery, alcohol, Jet cure/renewal, legacy payload, map cleanup");
}
