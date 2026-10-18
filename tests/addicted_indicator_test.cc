// Production addiction queries/setters with stub player-state flag storage.
// No live game, network or save/load integration is exercised here.
// g++ -std=c++17 -O2 -flto -fwhole-program -ffunction-sections -fdata-sections \
//   -Isrc -I<SDL2-include> tests/addicted_indicator_test.cc \
//   -Wl,--gc-sections -o addicted-indicator-test
#ifdef NDEBUG
#error This test requires assertions enabled.
#endif
#include "../src/item.cc"
#include <cassert>

namespace fallout {
static int globals[1000];
int* gGameGlobalVars = globals;
static int playerFlags;
void dudeEnableState(int state, Object*) { playerFlags |= 1 << state; }
void dudeDisableState(int state, Object*) { playerFlags &= ~(1 << state); }
static bool indicatorEnabled() { return (playerFlags & (1 << DUDE_STATE_ADDICTED)) != 0; }
static void reset() {
    std::fill(std::begin(globals), std::end(globals), 0);
    playerFlags = 0;
}
} // namespace fallout

int main()
{
    using namespace fallout;
    reset();
    assert(!dudeIsAddicted(-1));

    // Any single addiction must be found, including entries after Nuka-Cola.
    for (const auto& drug : gDrugDescriptions) {
        reset();
        dudeSetAddiction(drug.drugPid);
        assert(dudeIsAddicted(drug.drugPid));
        assert(dudeIsAddicted(-1));
        assert(indicatorEnabled());
        assert(!dudeIsAddicted(-2)); // unknown PID does not match a real addiction
        dudeClearAddiction(drug.drugPid);
        assert(!dudeIsAddicted(-1));
        assert(!indicatorEnabled());
    }

    // Clearing either member of every distinct pair must retain the other one.
    // Test both orders, including cures where neither drug is Nuka-Cola.
    int pairs = 0;
    for (const auto& first : gDrugDescriptions) {
        for (const auto& remaining : gDrugDescriptions) {
            if (first.gvar == remaining.gvar) continue;
            reset();
            dudeSetAddiction(first.drugPid);
            dudeSetAddiction(remaining.drugPid);
            dudeClearAddiction(first.drugPid);
            assert(!dudeIsAddicted(first.drugPid));
            assert(dudeIsAddicted(remaining.drugPid));
            assert(globals[remaining.gvar] == 1);
            assert(dudeIsAddicted(-1));
            assert(indicatorEnabled());
            dudeClearAddiction(remaining.drugPid);
            assert(!dudeIsAddicted(-1));
            assert(!indicatorEnabled());
            pairs++;
        }
    }

    // Beer and booze still represent one addiction, not two independent flags.
    reset();
    dudeSetAddiction(PROTO_ID_BEER);
    assert(dudeIsAddicted(PROTO_ID_BOOZE));
    dudeClearAddiction(PROTO_ID_BOOZE);
    assert(!dudeIsAddicted(PROTO_ID_BEER));
    assert(!dudeIsAddicted(-1) && !indicatorEnabled());
    printf("PASS: each addiction, %d ordered drug pairs, last recovery, specific queries and shared alcohol flag\n", pairs);
}
