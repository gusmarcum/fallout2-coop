// Production item-use/withdrawal routines with a stub queue, stats and perk effects.
// No live game, network or save/load integration is exercised here.
// g++ -std=c++17 -O2 -flto -fwhole-program -ffunction-sections -fdata-sections \
//   -Isrc -I<SDL2-include> tests/jet_antidote_withdrawal_test.cc \
//   -Wl,--gc-sections -o jet-antidote-test
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
static Object actors[2];
static Proto antidoteProto;
static int globals[1000];
int* gGameGlobalVars = globals;
static int dudeFlags;
static unsigned int now;
static int penaltyStarts;
static int penaltyEnds;
static std::map<Object*, std::array<int, STAT_COUNT>> bonuses;
struct TestEvent { Object* owner; int type; unsigned int time; void* data; };
static std::list<TestEvent> events;
static std::list<TestEvent>::iterator cursor;

bool playerActorIs(Object* actor) { return actor == gDude; }
bool critterIsDead(Object*) { return false; }
int critterGetBodyType(Object*) { return BODY_TYPE_BIPED; }
int protoGetProto(int pid, Proto** proto) {
    assert(pid == PROTO_ID_JET_ANTIDOTE);
    *proto = &antidoteProto;
    return 0;
}
void dudeEnableState(int state, Object*) { dudeFlags |= 1 << state; }
void dudeDisableState(int state, Object*) { dudeFlags &= ~(1 << state); }
int critterGetBonusStat(Object* actor, int stat) { return bonuses[actor][stat]; }
int critterSetBonusStat(Object* actor, int stat, int value) { bonuses[actor][stat] = value; return 0; }
int critterGetStat(Object* actor, int stat) {
    return stat == STAT_CURRENT_HIT_POINTS ? 100 : 5 + bonuses[actor][stat];
}
int critterGetBaseStatWithTraitModifier(Object*, int) { return 100; }
void perkAddEffect(Object* actor, int perk) {
    assert(perk == PERK_JET_ADDICTION);
    for (int stat : {STAT_STRENGTH, STAT_PERCEPTION, STAT_MAXIMUM_ACTION_POINTS}) bonuses[actor][stat]--;
    penaltyStarts++;
}
void perkRemoveEffect(Object* actor, int perk) {
    assert(perk == PERK_JET_ADDICTION);
    for (int stat : {STAT_STRENGTH, STAT_PERCEPTION, STAT_MAXIMUM_ACTION_POINTS}) bonuses[actor][stat]++;
    penaltyEnds++;
}
int perkGetRank(Object*, int) { return 0; }
char* perkGetDescription(int) { return nullptr; }
bool traitIsSelected(int, Object*) { return false; }
int debugPrint(const char*, ...) { return 0; }
bool messageListGetItem(MessageList*, MessageListItem*) { return false; }
char* statGetName(int) { return nullptr; }
char* critterGetName(Object*) { return nullptr; }
char* getmsg(MessageList*, MessageListItem*, int) { return nullptr; }
int randomBetween(int low, int) { return low; }
void _combatKillCritterOutsideCombat(Object*, char*) { assert(false); }
Presenter* presenter() { static Presenter nullPresenter; return &nullPresenter; }
void* internal_malloc(size_t size) { return malloc(size); }
void internal_free(void* data) { free(data); }
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
        if (it->type == type && (owner == nullptr || it->owner == owner)
            && (callback == nullptr || callback(it->owner, it->data) == 1)) {
            free(it->data);
            it = events.erase(it);
        } else {
            ++it;
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
static void reset() {
    for (auto& event : events) free(event.data);
    events.clear();
    bonuses.clear();
    std::fill(std::begin(globals), std::end(globals), 0);
    now = 0;
    dudeFlags = penaltyStarts = penaltyEnds = 0;
    dudeSetAddiction(PROTO_ID_JET);
}
static void expectBonus(Object* actor, int expected) {
    for (int stat : {STAT_STRENGTH, STAT_PERCEPTION, STAT_MAXIMUM_ACTION_POINTS}) {
        assert(bonuses[actor][stat] == expected);
    }
}
static bool retained(const TestEvent& expected) {
    for (const auto& event : events) {
        if (event.owner == expected.owner && event.type == expected.type
            && event.time == expected.time && event.data == expected.data) return true;
    }
    return false;
}
} // namespace fallout

int main()
{
    using namespace fallout;
    for (auto& actor : actors) actor.pid = 0x01000000;
    gDude = &actors[0];
    Object antidote{};
    antidote.pid = PROTO_ID_JET_ANTIDOTE;
    for (int& stat : antidoteProto.item.data.drug.stat) stat = -1;

    // Before withdrawal: cure without an inverse penalty, but finish the rebound.
    reset();
    _insert_withdrawal(gDude, 1, 1, PERK_JET_ADDICTION, PROTO_ID_JET);
    auto* rebound = static_cast<DrugEffectEvent*>(malloc(sizeof(DrugEffectEvent)));
    *rebound = {PROTO_ID_JET, {STAT_STRENGTH, STAT_PERCEPTION, STAT_MAXIMUM_ACTION_POINTS}, {-2, -2, -2}};
    queueAddEvent(20, gDude, rebound, EVENT_TYPE_DRUG);
    TestEvent savedRebound = events.back();
    for (int stat : rebound->stats) bonuses[gDude][stat] = 2;
    assert(_item_d_take_drug(gDude, &antidote) == 1);
    assert(globals[GVAR_ADDICT_JET] == 0);
    assert((dudeFlags & (1 << DUDE_STATE_ADDICTED)) == 0);
    assert(penaltyStarts == 0 && penaltyEnds == 0);
    expectBonus(gDude, 2);
    assert(events.size() == 1 && retained(savedRebound));
    advanceTo(1200); // past the cancelled withdrawal onset at tick 600
    expectBonus(gDude, 0);
    assert(penaltyStarts == 0 && events.empty());
    // A second antidote without addiction must not grant another stat bonus.
    assert(_item_d_take_drug(gDude, &antidote) == 1);
    expectBonus(gDude, 0);
    assert(penaltyEnds == 0);

    // Active withdrawal: undo the applied penalty once and cancel its end event.
    reset();
    _insert_withdrawal(gDude, 1, 1, PERK_JET_ADDICTION, PROTO_ID_JET);
    advanceTo(600);
    expectBonus(gDude, -1);
    assert(penaltyStarts == 1 && events.size() == 1);
    assert(_item_d_take_drug(gDude, &antidote) == 1);
    expectBonus(gDude, 0);
    assert(penaltyEnds == 1 && events.empty() && globals[GVAR_ADDICT_JET] == 0);

    // Jet's permanent penalty outlives its end event; it must still be cured.
    reset();
    _insert_withdrawal(gDude, 1, 1, PERK_JET_ADDICTION, PROTO_ID_JET);
    advanceTo(600 + 600 * 10080);
    assert(events.empty());
    expectBonus(gDude, -1);
    assert(_item_d_take_drug(gDude, &antidote) == 1);
    expectBonus(gDude, 0);
    assert(penaltyEnds == 1 && globals[GVAR_ADDICT_JET] == 0);

    // Cure only this actor's Jet: other drugs and other owners keep their events.
    reset();
    _insert_withdrawal(gDude, 1, 1, PERK_JET_ADDICTION, PROTO_ID_JET);
    _insert_withdrawal(gDude, 1, 2, PERK_MENTATS_ADDICTION, PROTO_ID_MENTATS);
    TestEvent ownMentats = events.back();
    globals[GVAR_MENTATS_ADDICT] = 1;
    _insert_withdrawal(&actors[1], 1, 3, PERK_JET_ADDICTION, PROTO_ID_JET);
    TestEvent foreignJet = events.back();
    assert(_item_d_take_drug(gDude, &antidote) == 1);
    assert(events.size() == 2 && retained(ownMentats) && retained(foreignJet));
    assert(globals[GVAR_MENTATS_ADDICT] == 1 && globals[GVAR_ADDICT_JET] == 0);
    expectBonus(&actors[1], 0);

    // Preserve the player-only guard on global clearing when treating an NPC.
    reset();
    _insert_withdrawal(&actors[1], 1, 1, PERK_JET_ADDICTION, PROTO_ID_JET);
    assert(_item_d_take_drug(&actors[1], &antidote) == 1);
    assert(globals[GVAR_ADDICT_JET] == 1);
    assert((dudeFlags & (1 << DUDE_STATE_ADDICTED)) != 0);
    for (auto& event : events) free(event.data);
    puts("PASS: pending/active/permanent Jet cure, rebound completion, repeated cure, owner/drug isolation, NPC global guard");
}
