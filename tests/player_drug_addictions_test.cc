// Production per-player drug-use, migration and withdrawal routines; mocked engine services.
// Checks decisions/draw counts, not the old incidental global RNG sequence.
// Not a full game-save/network test; see player_addiction_sheet_test.cc for the
// actual sheet-row serializer. Define TEST_WITH_DRUG_FIXES for the four-fix merge.
// g++ -std=c++17 -O2 -flto -fwhole-program -ffunction-sections -fdata-sections \
//   -Isrc -I<SDL2-include> tests/player_drug_addictions_test.cc \
//   -Wl,--gc-sections -o player-drug-addictions-test
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
void perkAddEffect(Object* actor, int) { penalties[actor]++; }
void perkRemoveEffect(Object* actor, int) { penalties[actor]--; }
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
        itemInitializePlayerAddictions();
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
    dedicated = true;
    viewer = loading = false;
    gDude = &actors[0];
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

static bool addicted(fallout::Object* actor, int pid)
{
    using namespace fallout;
    return itemIsAddictedByGvar(actor, drugGetAddictionGvarByPid(pid));
}

int main()
{
    using namespace fallout;
    for (int slot = 0; slot < 3; slot++) {
        actors[slot].pid = 0x01000000 + slot;
        actors[slot].netId = slot + 1;
    }
    Object* host = &actors[0];
    Object* second = &actors[1];
    Object* third = &actors[2];
    addProto(PROTO_ID_PSYCHO, PERK_PSYCHO_ADDICTION);
    addProto(PROTO_ID_MENTATS, PERK_MENTATS_ADDICTION);
    addProto(PROTO_ID_JET, PERK_JET_ADDICTION);
    addProto(PROTO_ID_BEER, -1);
    addProto(PROTO_ID_BOOZE, -1);
    addProto(PROTO_ID_JET_ANTIDOTE, PERK_JET_ADDICTION);
    protos.at(PROTO_ID_JET_ANTIDOTE).item.data.drug.addictionChance = 0;

    // Reconstruct identity from OWN events, regardless of stale/missing globals.
    // Migration never replays perk penalties or rewrites a queue node/payload.
    reset();
    globals[GVAR_PSYCHO_ADDICT] = 1;
    _insert_withdrawal(second, 1, 2, PERK_MENTATS_ADDICTION, PROTO_ID_MENTATS);
    _insert_withdrawal(third, 0, 9, PERK_PSYCHO_ADDICTION, PROTO_ID_PSYCHO);
    penalties[third] = 1;
    auto savedEvents = events;
    itemInitializePlayerAddictions();
    assert(!addicted(host, PROTO_ID_PSYCHO));
    assert(addicted(second, PROTO_ID_MENTATS) && !addicted(second, PROTO_ID_PSYCHO));
    assert(addicted(third, PROTO_ID_PSYCHO) && !addicted(third, PROTO_ID_MENTATS));
    assert(!dudeHasState(DUDE_STATE_ADDICTED, host));
    assert(dudeHasState(DUDE_STATE_ADDICTED, second));
    assert(globals[GVAR_PSYCHO_ADDICT] == 0 && globals[GVAR_MENTATS_ADDICT] == 0);
    assert(rngCalls == 0 && penalties[third] == 1);
    for (int repetition = 0; repetition < 2; repetition++) {
        itemInitializePlayerAddictions();
        assert(events.size() == savedEvents.size());
        auto original = savedEvents.begin();
        for (const auto& event : events) {
            assert(event.owner == original->owner && event.type == original->type);
            assert(event.time == original->time && event.data == original->data);
            ++original;
        }
    }

    // Own Jet events always identify addiction. The label/global fallback is
    // allowed only with NO withdrawal events (pending onset counts as well).
    for (int jetGlobal : {0, 1, 2}) {
        for (bool label : {false, true}) {
            for (int jetStage : {-1, 0, 1}) {
                for (int otherStage : {-1, 0, 1}) {
                    reset();
                    globals[GVAR_ADDICT_JET] = jetGlobal;
                    if (label) dudeEnableState(DUDE_STATE_ADDICTED, second);
                    if (jetStage != -1) _insert_withdrawal(second, jetStage, 1, PERK_JET_ADDICTION, PROTO_ID_JET);
                    if (otherStage != -1) _insert_withdrawal(second, otherStage, 1, PERK_MENTATS_ADDICTION, PROTO_ID_MENTATS);
                    itemInitializePlayerAddictions();
                    assert(addicted(second, PROTO_ID_JET)
                        == (jetStage != -1 || (otherStage == -1 && label && jetGlobal == 1)));
                    assert(addicted(second, PROTO_ID_MENTATS) == (otherStage != -1));
                    assert(!addicted(host, PROTO_ID_JET) && !addicted(third, PROTO_ID_JET));
                    assert(globals[GVAR_ADDICT_JET] == 0);
                    }
            }
        }
    }

    // Legacy party: one permanent Jet addiction, one Mentats addiction. Check
    // both host assignments and both Mentats stages. Antidote on the Mentats
    // recipient must not remove a nonexistent Jet penalty or touch either timer.
    for (bool jetOnHost : {false, true}) {
        for (int mentatsStage : {0, 1}) {
            reset();
            Object* jetActor = jetOnHost ? host : second;
            Object* mentatsActor = jetOnHost ? second : host;
            globals[GVAR_ADDICT_JET] = 1;
            dudeEnableState(DUDE_STATE_ADDICTED, jetActor);
            dudeEnableState(DUDE_STATE_ADDICTED, mentatsActor);
            penalties[jetActor] = 1;
            penalties[mentatsActor] = mentatsStage == 0 ? 1 : 0;
            _insert_withdrawal(mentatsActor, mentatsStage, 10, PERK_MENTATS_ADDICTION, PROTO_ID_MENTATS);
            auto originalEvent = events.front();
            itemInitializePlayerAddictions();
            assert(addicted(jetActor, PROTO_ID_JET));
            assert(!addicted(mentatsActor, PROTO_ID_JET));
            assert(addicted(mentatsActor, PROTO_ID_MENTATS));
            assert(globals[GVAR_ADDICT_JET] == (jetOnHost ? 1 : 0));
            take(mentatsActor, PROTO_ID_JET_ANTIDOTE);
            itemInitializePlayerAddictions();
            assert(penalties[jetActor] == 1);
            assert(penalties[mentatsActor] == (mentatsStage == 0 ? 1 : 0));
            assert(dudeHasState(DUDE_STATE_ADDICTED, mentatsActor));
            assert(!addicted(mentatsActor, PROTO_ID_JET));
            assert(events.size() == 1 && events.front().data == originalEvent.data);
            assert(events.front().time == originalEvent.time && events.front().owner == mentatsActor);
        }
    }
    // Host normalization must not erase evidence BEFORE extra players migrate.
    reset();
    globals[GVAR_ADDICT_JET] = 1;
    dudeEnableState(DUDE_STATE_ADDICTED, third);
    penalties[third] = 1;
    itemInitializePlayerAddictions();
    assert(addicted(third, PROTO_ID_JET) && !addicted(host, PROTO_ID_JET));
    assert(penalties[third] == 1 && events.empty());
    take(third, PROTO_ID_JET_ANTIDOTE);
    assert(!addicted(third, PROTO_ID_JET) && penalties[third] == 0);

    // No partial migration while save handlers/appendix rows are loading.
    reset();
    globals[GVAR_ADDICT_JET] = 1;
    loading = true;
    itemInitializePlayerAddictions();
    assert(!dudeHasState(DUDE_STATE_ADDICTIONS_INITIALIZED, host));
    assert(globals[GVAR_ADDICT_JET] == 1);
    dudeEnableState(DUDE_STATE_ADDICTED, second);
    loading = false;
    itemInitializePlayerAddictions();
    assert(addicted(second, PROTO_ID_JET));

    // Two independent successes for the same drug; redose does not reroll or
    // touch another player's onset. gDude intentionally points at a third actor.
    reset();
    gDude = third;
    take(host, PROTO_ID_PSYCHO);
    take(second, PROTO_ID_PSYCHO);
    assert(rngCalls == 2 && globals[GVAR_PSYCHO_ADDICT] == 1);
    assert(addicted(host, PROTO_ID_PSYCHO) && addicted(second, PROTO_ID_PSYCHO));
    assert(!addicted(third, PROTO_ID_PSYCHO) && gDude == third);
    now = 20;
    take(second, PROTO_ID_PSYCHO);
    assert(rngCalls == 2 && countWithdrawal(host, PROTO_ID_PSYCHO) == 1);
    for (const auto& event : events) {
        assert(event.time == (event.owner == host ? 600 : 620));
    }
    advanceTo(600);
    assert(penalties[host] == 1 && penalties[second] == 0);
    advanceTo(620);
    assert(penalties[host] == 1 && penalties[second] == 1);
    advanceTo(600 + 600 * 10080);
    assert(!addicted(host, PROTO_ID_PSYCHO) && addicted(second, PROTO_ID_PSYCHO));
    assert(globals[GVAR_PSYCHO_ADDICT] == 0 && penalties[host] == 0 && penalties[second] == 1);
    advanceTo(620 + 600 * 10080);
    assert(!dudeHasState(DUDE_STATE_ADDICTED, second) && penalties[second] == 0);

    // Extra-only addiction leaves host gvars clear; multiple addictions keep the
    // personal label and Karma entries after the first withdrawal recovers.
    reset();
    take(second, PROTO_ID_PSYCHO);
    now = 20;
    take(second, PROTO_ID_MENTATS);
    assert(globals[GVAR_PSYCHO_ADDICT] == 0 && globals[GVAR_MENTATS_ADDICT] == 0);
    advanceTo(600 + 600 * 10080);
    assert(!addicted(second, PROTO_ID_PSYCHO) && addicted(second, PROTO_ID_MENTATS));
    assert(dudeHasState(DUDE_STATE_ADDICTED, second));
    // Replicated flags must drive client Karma entries even with host globals 0.
    dedicated = false;
    viewer = true;
    assert(addicted(second, PROTO_ID_MENTATS) && !addicted(host, PROTO_ID_MENTATS));
    viewer = false;
    assert(!addicted(second, PROTO_ID_MENTATS)); // ordinary SP still uses globals
    dedicated = true;
    advanceTo(620 + 600 * 10080);
    assert(!dudeHasState(DUDE_STATE_ADDICTED, second));

    // Addiction chance uses the RECIPIENT's traits. Immediate and delayed stat
    // changes likewise stay on that actor, with another player bound as gDude.
    reset();
    traitFlags[host] = 1 << TRAIT_CHEM_RESISTANT;
    traitFlags[second] = 1 << TRAIT_CHEM_RELIANT;
    roll = 50;
    take(host, PROTO_ID_MENTATS);
    take(second, PROTO_ID_MENTATS);
    assert(!addicted(host, PROTO_ID_MENTATS) && addicted(second, PROTO_ID_MENTATS));
    assert(rngCalls == 2);
    auto& psycho = protos.at(PROTO_ID_PSYCHO).item.data.drug;
    psycho.stat[0] = STAT_STRENGTH;
    psycho.amount[0] = 2;
    psycho.amount1[0] = -2;
    psycho.duration1 = 1;
    take(second, PROTO_ID_PSYCHO);
    assert(bonuses[second][STAT_STRENGTH] == 2 && bonuses[host][STAT_STRENGTH] == 0);
    advanceTo(600);
    assert(bonuses[second][STAT_STRENGTH] == 0 && bonuses[host][STAT_STRENGTH] == 0);
    psycho.stat[0] = -1;
    psycho.amount[0] = psycho.amount1[0] = 0;

    // Alcohol has a shared identity within one actor, never between actors.
    reset();
    take(second, PROTO_ID_BEER);
    take(second, PROTO_ID_BOOZE);
    take(third, PROTO_ID_BOOZE);
    assert(rngCalls == 2 && countWithdrawal(second, PROTO_ID_BEER) == 1);
    assert(addicted(second, PROTO_ID_BOOZE) && globals[GVAR_ALCOHOL_ADDICT] == 0);

    // Active Jet antidote affects only its recipient, including when gDude is
    // another player. Preserve other withdrawals and BOTH players' rebounds.
    reset();
    take(host, PROTO_ID_JET);
    take(second, PROTO_ID_JET);
    take(second, PROTO_ID_PSYCHO);
    advanceTo(600);
    assert(penalties[host] == 1 && penalties[second] == 2);
    for (Object* actor : {host, second}) {
        auto* rebound = static_cast<DrugEffectEvent*>(malloc(sizeof(DrugEffectEvent)));
        *rebound = {PROTO_ID_JET, {STAT_STRENGTH, -1, -1}, {-2, 0, 0}};
        bonuses[actor][STAT_STRENGTH] = 2;
        queueAddEvent(20, actor, rebound, EVENT_TYPE_DRUG);
    }
    take(second, PROTO_ID_JET_ANTIDOTE);
    assert(addicted(host, PROTO_ID_JET) && !addicted(second, PROTO_ID_JET));
    assert(globals[GVAR_ADDICT_JET] == 1 && penalties[host] == 1 && penalties[second] == 1);
    assert(addicted(second, PROTO_ID_PSYCHO) && dudeHasState(DUDE_STATE_ADDICTED, second));
    advanceTo(620);
    assert(bonuses[host][STAT_STRENGTH] == 0 && bonuses[second][STAT_STRENGTH] == 0);
    take(host, PROTO_ID_JET_ANTIDOTE);
    assert(!addicted(host, PROTO_ID_JET) && globals[GVAR_ADDICT_JET] == 0);

    // A clean recipient cannot cure the host, even with the host's Jet gvar 1.
    reset();
    take(host, PROTO_ID_JET);
    advanceTo(600);
    take(second, PROTO_ID_JET_ANTIDOTE);
    assert(addicted(host, PROTO_ID_JET) && penalties[host] == 1 && penalties[second] == 0);
    assert(countWithdrawal(host, PROTO_ID_JET) == 1 && countWithdrawal(second, PROTO_ID_JET) == 0);

    // Personal Jet identity remains after its end event has vanished. Repeated
    // migration checks must not erase it just because only the extra is addicted.
    reset();
    take(second, PROTO_ID_JET);
    advanceTo(600 + 600 * 10080);
    itemInitializePlayerAddictions();
    assert(events.empty() && addicted(second, PROTO_ID_JET) && penalties[second] == 1);
    assert(globals[GVAR_ADDICT_JET] == 0);
    take(second, PROTO_ID_JET_ANTIDOTE);
    assert(!addicted(second, PROTO_ID_JET) && penalties[second] == 0);

    // Permanent Jet redose uses the recipient's identity even with a different
    // gDude and host globals clear. Only the recipient's penalty/onset changes.
    reset();
    take(second, PROTO_ID_JET);
    take(third, PROTO_ID_JET);
    advanceTo(600 + 600 * 10080);
    assert(events.empty() && penalties[second] == 1 && penalties[third] == 1);
    int callsBeforeJetRedose = rngCalls;
    take(second, PROTO_ID_JET);
    assert(penalties[second] == 0 && penalties[third] == 1 && penalties[host] == 0);
    assert(countWithdrawal(second, PROTO_ID_JET) == 1);
    assert(countWithdrawal(third, PROTO_ID_JET) == 0);
    assert(addicted(second, PROTO_ID_JET) && addicted(third, PROTO_ID_JET));
    assert(globals[GVAR_ADDICT_JET] == 0 && rngCalls == callsBeforeJetRedose);
    advanceTo(now + 600);
    assert(penalties[second] == 1 && penalties[third] == 1);

    // A clean recipient must not reverse a penalty just because the host is
    // permanently addicted. A failed addiction roll leaves it clean.
    reset();
    take(host, PROTO_ID_JET);
    advanceTo(600 + 600 * 10080);
    roll = 100;
    take(second, PROTO_ID_JET);
    assert(penalties[host] == 1 && penalties[second] == 0);
    assert(!addicted(second, PROTO_ID_JET) && countWithdrawal(second, PROTO_ID_JET) == 0);
    assert(globals[GVAR_ADDICT_JET] == 1);

#ifdef TEST_WITH_DRUG_FIXES
    // C remains independent on a real dedicated server as well: an NPC uses
    // queue evidence, never the currently bound player's personal addiction bits.
    reset();
    Object npc{};
    npc.pid = 0x01000099;
    take(host, PROTO_ID_PSYCHO);
    take(&npc, PROTO_ID_PSYCHO);
    assert(rngCalls == 2 && countWithdrawal(&npc, PROTO_ID_PSYCHO) == 1);
    now = 20;
    take(&npc, PROTO_ID_PSYCHO);
    assert(rngCalls == 2 && addicted(host, PROTO_ID_PSYCHO));
    take(second, PROTO_ID_PSYCHO);
    assert(rngCalls == 3 && addicted(second, PROTO_ID_PSYCHO));

    // The independent antidote/map-transition fixes must work with personal bits.
    reset();
    take(host, PROTO_ID_JET);
    take(second, PROTO_ID_JET);
    _queue_clear_type(EVENT_TYPE_WITHDRAWAL, _item_wd_clear);
    assert(countWithdrawal(second, PROTO_ID_JET) == 1);
    take(second, PROTO_ID_JET_ANTIDOTE);
    assert(!addicted(second, PROTO_ID_JET) && penalties[second] == 0);
    assert(countWithdrawal(second, PROTO_ID_JET) == 0 && countWithdrawal(host, PROTO_ID_JET) == 1);
    advanceTo(600);
    assert(penalties[host] == 1 && penalties[second] == 0);
#endif

    // A migrated host can continue in SP and return to co-op. Mode switches
    // retain the flags/globals/events that a save carries; this is not a full
    // disk-load integration test. Extra players' identities must stay untouched.
    reset();
    take(second, PROTO_ID_MENTATS);
    dedicated = false;
    take(host, PROTO_ID_JET);
    advanceTo(600 + 600 * 10080);
    assert(penalties[host] == 1 && countWithdrawal(host, PROTO_ID_JET) == 0);
    assert(globals[GVAR_ADDICT_JET] == 1);
    assert(dudeHasState(addictionStateForGvar(GVAR_ADDICT_JET), host));
    dedicated = true;
    itemInitializePlayerAddictions();
    assert(addicted(host, PROTO_ID_JET) && globals[GVAR_ADDICT_JET] == 1);
    take(host, PROTO_ID_JET_ANTIDOTE);
    assert(!addicted(host, PROTO_ID_JET) && penalties[host] == 0);

    // Conversely, a Jet cure in SP must not resurrect addiction on return.
    reset();
    take(host, PROTO_ID_JET);
    take(second, PROTO_ID_JET);
    advanceTo(600 + 600 * 10080);
    dedicated = false;
    take(host, PROTO_ID_JET_ANTIDOTE);
    assert(penalties[host] == 0 && globals[GVAR_ADDICT_JET] == 0);
    assert(!dudeHasState(addictionStateForGvar(GVAR_ADDICT_JET), host));
    assert(dudeHasState(addictionStateForGvar(GVAR_ADDICT_JET), second));
    dedicated = true;
    itemInitializePlayerAddictions();
    assert(!addicted(host, PROTO_ID_JET) && globals[GVAR_ADDICT_JET] == 0);
    assert(addicted(second, PROTO_ID_JET) && penalties[second] == 1);
    take(host, PROTO_ID_JET_ANTIDOTE);
    assert(penalties[host] == 0);

    // Natural recovery in SP also clears the persisted identity. Retain the
    // legacy indicator behavior, even with multiple addictions (separate fix).
    reset();
    take(host, PROTO_ID_PSYCHO);
    dedicated = false;
    take(host, PROTO_ID_MENTATS);
    int callsBeforeRedose = rngCalls;
    take(host, PROTO_ID_MENTATS);
    assert(rngCalls == callsBeforeRedose);
    advanceTo(600 + 600 * 10080);
    assert(penalties[host] == 0);
    assert(!playerHasAnyAddiction(host));
    dedicated = true;
    itemInitializePlayerAddictions();
    assert(!addicted(host, PROTO_ID_PSYCHO) && !addicted(host, PROTO_ID_MENTATS));
    assert(globals[GVAR_PSYCHO_ADDICT] == 0 && globals[GVAR_MENTATS_ADDICT] == 0);

    // Single-player still uses legacy globals, labels, RNG and event behavior.
    reset();
    dedicated = false;
    itemInitializePlayerAddictions();
    take(host, PROTO_ID_PSYCHO);
    assert(rngCalls == 1 && globals[GVAR_PSYCHO_ADDICT] == 1);
    assert(dudeHasState(DUDE_STATE_ADDICTED, host));
    assert(!dudeHasState(DUDE_STATE_ADDICTIONS_INITIALIZED, host));
    take(host, PROTO_ID_PSYCHO);
    assert(rngCalls == 1);
    advanceTo(600 + 600 * 10080);
    assert(penalties[host] == 0 && globals[GVAR_PSYCHO_ADDICT] == 0);
    reset();
    puts("PASS: per-player migration/Jet truth table, dose/RNG/stat isolation, recovery, labels, client Karma, host gvars, antidote, rebounds, SP");
}
