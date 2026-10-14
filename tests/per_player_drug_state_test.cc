// Focused test of the production item.cc addiction/withdrawal routines.
// The surrounding engine is stubbed; this is not a game or network integration test.
// Run from the repository root (supply the SDL2 include directory):
// g++ -std=c++17 -O0 -ffunction-sections -fdata-sections -Isrc -I<SDL2-include> \
//   tests/per_player_drug_state_test.cc -Wl,--gc-sections -o /tmp/drug-state-test
// /tmp/drug-state-test
#ifdef NDEBUG
#error This test requires assertions enabled.
#endif
#include "../src/item.cc"
#include <cassert>
#include <map>
#include <cstdio>
namespace fallout {
int globals[1000] = {};
int* gGameGlobalVars = globals;
Object* gDude;
static Object actors[3];
static std::map<Object*, int> flags;
struct TestEvent { Object* owner; WithdrawalEvent event; };
static std::vector<TestEvent> events;
static size_t nextIndex;
static bool dedicated = true;
bool serverDedicatedActive() { return dedicated; }
int playerActorSlotOf(Object* obj) { for(int i=0;i<3;i++) if(obj==&actors[i]) return i; return -1; }
bool playerActorIs(Object* obj) { return playerActorSlotOf(obj)>=0; }
bool dudeHasState(int s, Object* obj) { return (flags[obj] & (1<<s))!=0; }
void dudeEnableState(int s, Object* obj) { flags[obj] |= 1<<s; }
void dudeDisableState(int s, Object* obj) { flags[obj] &= ~(1<<s); }
void* queueFindNextEvent(Object* obj, int type) {
 while(nextIndex<events.size()) { auto& e=events[nextIndex++]; if(e.owner==obj) return &e.event; } return nullptr;
}
void* queueFindFirstEvent(Object* obj, int type) { nextIndex=0; return queueFindNextEvent(obj,type); }
static std::map<Object*, int> effects;
void perkAddEffect(Object* obj, int perk) { effects[obj]++; }
void perkRemoveEffect(Object* obj, int perk) { effects[obj]--; }
char* perkGetDescription(int perk) { return nullptr; }
int perkGetRank(Object* obj, int perk) { return 0; }
bool traitIsSelected(int trait, Object* obj) { return false; }
int debugPrint(const char*, ...) { return 0; }
bool messageListGetItem(MessageList*, MessageListItem*) { return false; }
Presenter* presenter() { return nullptr; }
void* internal_malloc(size_t size) { return malloc(size); }
void internal_free(void* ptr) { free(ptr); }
bool objectIsPartyMember(Object*) { return false; }
int queueAddEvent(int delay, Object* obj, void* data, int type) {
 assert(type==EVENT_TYPE_WITHDRAWAL);
 events.push_back({obj,*static_cast<WithdrawalEvent*>(data)});
 free(data); return 0;
}

}
int main() {
 using namespace fallout;
 gDude=&actors[0];
 for(auto& actor:actors) actor.pid=0x01000000;
 // Shared legacy globals must not infect a newly initialized extra player.
 globals[GVAR_BUFF_OUT_ADDICT]=1;
 assert(itemIsAddictedByGvar(&actors[0],GVAR_BUFF_OUT_ADDICT));
 assert(!itemIsAddictedByGvar(&actors[1],GVAR_BUFF_OUT_ADDICT));
 // Each player can acquire the same addiction independently.
 dudeSetAddiction(&actors[1],PROTO_ID_BUFF_OUT);
 dudeSetAddiction(&actors[2],PROTO_ID_BUFF_OUT);
 dudeClearAddiction(&actors[1],PROTO_ID_BUFF_OUT);
 assert(!dudeIsAddicted(&actors[1],PROTO_ID_BUFF_OUT));
 assert(dudeIsAddicted(&actors[0],PROTO_ID_BUFF_OUT));
 assert(dudeIsAddicted(&actors[2],PROTO_ID_BUFF_OUT));
 // Clearing one addiction must not hide another (old any-addiction early-return bug).
 dudeSetAddiction(&actors[1],PROTO_ID_MENTATS);
 dudeSetAddiction(&actors[1],PROTO_ID_BUFF_OUT);
 dudeClearAddiction(&actors[1],PROTO_ID_BUFF_OUT);
 assert(dudeHasState(DUDE_STATE_ADDICTED,&actors[1]));
 dudeClearAddiction(&actors[1],PROTO_ID_MENTATS);
 assert(!dudeHasState(DUDE_STATE_ADDICTED,&actors[1]));
 // Beer and booze share the same addiction flag.
 dudeSetAddiction(&actors[1],PROTO_ID_BEER);
 assert(dudeIsAddicted(&actors[1],PROTO_ID_BOOZE));
 dudeClearAddiction(&actors[1],PROTO_ID_BOOZE);
 assert(!dudeIsAddicted(&actors[1],PROTO_ID_BEER));
 // Legacy extra migration uses only its own queued events.
 flags[&actors[1]]=0;
 events.push_back({&actors[1],{1,PROTO_ID_JET,PERK_JET_ADDICTION}});
 itemInitializePlayerAddictions(&actors[1]);
 assert(dudeIsAddicted(&actors[1],PROTO_ID_JET));
 assert(!dudeIsAddicted(&actors[1],PROTO_ID_BUFF_OUT));
 // Sheet flag-word round trip retains independent identity and initialized state.
 int saved=flags[&actors[1]];
 flags[&actors[1]]=0;
 flags[&actors[1]]=saved;
 events.clear();
 assert(dudeIsAddicted(&actors[1],PROTO_ID_JET));

 // A viewer reads the received personal flags, not the shared host globals.
 dedicated=false;
 assert(itemIsAddictedByGvar(&actors[1],GVAR_ADDICT_JET));
 assert(!itemIsAddictedByGvar(&actors[1],GVAR_BUFF_OUT_ADDICT));
 dedicated=true;
 // An extra's withdrawal starts and ends on that extra, while gDude is host.
 dudeSetAddiction(&actors[2],PROTO_ID_MENTATS);
 WithdrawalEvent onset{1,PROTO_ID_MENTATS,PERK_MENTATS_ADDICTION};
 withdrawalEventProcess(&actors[2],&onset);
 assert(effects[&actors[2]]==1 && effects[&actors[0]]==0);
 WithdrawalEvent recovery{0,PROTO_ID_MENTATS,PERK_MENTATS_ADDICTION};
 withdrawalEventProcess(&actors[2],&recovery);
 assert(effects[&actors[2]]==0);
 assert(!dudeIsAddicted(&actors[2],PROTO_ID_MENTATS));
 assert(dudeIsAddicted(&actors[2],PROTO_ID_BUFF_OUT));
 // Map exit must retain a player's withdrawal without undoing its effects.
 assert(_item_wd_clear(&actors[2],&recovery)==0);
 assert(effects[&actors[2]]==0);
 // Jet antidote callback: foreign owner is untouched; pending onset has no
 // stat effect to remove; active withdrawal is removed exactly once.
 _wd_obj=&actors[1];
 WithdrawalEvent jetOnset{1,PROTO_ID_JET,PERK_JET_ADDICTION};
 WithdrawalEvent jetActive{0,PROTO_ID_JET,PERK_JET_ADDICTION};
 assert(clearJetWithdrawal(&actors[2],&jetActive)==0);
 assert(clearJetWithdrawal(&actors[1],&jetOnset)==1);
 assert(effects[&actors[1]]==0);
 effects[&actors[1]]=1;
 assert(clearJetWithdrawal(&actors[1],&jetActive)==1);
 assert(effects[&actors[1]]==0 && effects[&actors[2]]==0);
 puts("PASS: independent addiction state, multiple addictions, alcohol grouping, legacy migration, viewer reads, withdrawal effects, map-exit preservation, Jet cure callback");
}
