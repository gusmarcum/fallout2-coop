// Production map-exit callbacks and actor registry, with stub stats/perk effects.
// This is a callback-level regression test, not a live map/network/save test.
// Build with assertions enabled and SDL2 headers (MinGW or Linux g++):
// g++ -std=c++17 -O2 -flto -fwhole-program -ffunction-sections -fdata-sections -Isrc -I<SDL2-include> \
//   tests/drug_timers_map_transition_test.cc -Wl,--gc-sections -o drug-timers-test
#ifdef NDEBUG
#error This test requires assertions enabled.
#endif
#include "../src/item.cc"
#include "../src/server_players.cc"
#include <cassert>
#include <map>

namespace fallout {
Object* gDude;
static Object actors[5]; // host, two extras, companion, ordinary NPC
static std::map<Object*, int> strengthBonus;
static std::map<Object*, int> withdrawalPenalty;

bool objectIsPartyMember(Object* actor) { return actor == &actors[0] || actor == &actors[3]; }
int critterGetBonusStat(Object* actor, int stat) { return strengthBonus[actor]; }
int critterSetBonusStat(Object* actor, int stat, int value) { strengthBonus[actor] = value; return 0; }
int critterGetStat(Object* actor, int stat) {
    return stat == STAT_CURRENT_HIT_POINTS ? 100 : 5 + strengthBonus[actor];
}
int critterGetBaseStatWithTraitModifier(Object*, int) { return 100; }
void perkRemoveEffect(Object* actor, int) { withdrawalPenalty[actor]--; }
int debugPrint(const char*, ...) { return 0; }
bool messageListGetItem(MessageList*, MessageListItem*) { return false; }
char* statGetName(int) { return nullptr; }
char* critterGetName(Object*) { return nullptr; }
char* getmsg(MessageList*, MessageListItem*, int) { return nullptr; }
int randomBetween(int low, int) { return low; }
void _combatKillCritterOutsideCombat(Object*, char*) { assert(false); }
Presenter* presenter() { static Presenter nullPresenter; return &nullPresenter; }
} // namespace fallout

int main()
{
    using namespace fallout;
    for (auto& actor : actors) {
        actor.pid = 0x01000000; // OBJ_TYPE_CRITTER
    }
    gDude = &actors[0];
    playerActorClear();
    for (int slot = 0; slot < 3; slot++) {
        assert(playerActorRegister(&actors[slot]) == slot);
    }

    DrugEffectEvent rebound{};
    rebound.stats[0] = STAT_STRENGTH;
    rebound.stats[1] = rebound.stats[2] = -1;
    rebound.modifiers[0] = -2;
    WithdrawalEvent pending{1, PROTO_ID_BUFF_OUT, PERK_BUFFOUT_ADDICTION};
    WithdrawalEvent active{0, PROTO_ID_BUFF_OUT, PERK_BUFFOUT_ADDICTION};

    // A callback return of 0 tells the map-exit queue pass to retain the event.
    // Exercise repeated exits and every player, independently of gDude's scope.
    for (int actingSlot = 0; actingSlot < 3; actingSlot++) {
        gDude = &actors[actingSlot];
        for (int slot = 0; slot < 3; slot++) {
            Object* owner = &actors[slot];
            strengthBonus[owner] = 2;
            withdrawalPenalty[owner] = 1;
            for (int exit = 0; exit < 2; exit++) {
                assert(_item_d_clear(owner, &rebound) == 0);
                assert(_item_wd_clear(owner, &pending) == 0);
                assert(_item_wd_clear(owner, &active) == 0);
                assert(strengthBonus[owner] == 2);
                assert(withdrawalPenalty[owner] == 1);
            }
        }
    }

    // Retained delayed drug effects still apply to their owner, not the host.
    gDude = &actors[0];
    for (int slot = 1; slot < 3; slot++) {
        assert(drugEffectEventProcess(&actors[slot], &rebound) == 0);
        assert(strengthBonus[&actors[slot]] == 0);
        assert(strengthBonus[&actors[0]] == 2);
    }

    // Companion events still survive; ordinary NPC events still settle/remove.
    Object* companion = &actors[3];
    strengthBonus[companion] = 2;
    withdrawalPenalty[companion] = 1;
    assert(_item_d_clear(companion, &rebound) == 0);
    assert(_item_wd_clear(companion, &active) == 0);
    assert(strengthBonus[companion] == 2 && withdrawalPenalty[companion] == 1);
    Object* npc = &actors[4];
    strengthBonus[npc] = 2;
    withdrawalPenalty[npc] = 1;
    assert(_item_d_clear(npc, &rebound) == 1);
    assert(strengthBonus[npc] == 0);
    assert(_item_wd_clear(npc, &pending) == 1);
    assert(withdrawalPenalty[npc] == 1);
    assert(_item_wd_clear(npc, &active) == 1);
    assert(withdrawalPenalty[npc] == 0);

    // Single-player has no registered extras: the host/companion behavior stays.
    playerActorClear();
    assert(playerActorCount() == 1);
    assert(_item_d_clear(gDude, &rebound) == 0);
    assert(_item_wd_clear(gDude, &pending) == 0);
    assert(_item_wd_clear(gDude, &active) == 0);
    assert(_item_d_clear(companion, &rebound) == 0);
    assert(_item_wd_clear(companion, &active) == 0);
    puts("PASS: host/two extras retain drug and withdrawal events; owner isolation; NPC/companion and single-player behavior");
}
