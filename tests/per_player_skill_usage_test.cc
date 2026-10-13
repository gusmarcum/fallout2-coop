// Production usage-table tests with a stub clock, actor registry and memory stream.
// Build with assertions enabled and SDL2 headers:
// g++ -std=c++17 -O0 -ffunction-sections -fdata-sections -Isrc -I<SDL2-include> \
//   tests/per_player_skill_usage_test.cc -Wl,--gc-sections -o /tmp/skill-usage-test
#ifdef NDEBUG
#error This test requires assertions enabled.
#endif
#include "../src/skill.cc"
#include <cassert>
#include <vector>
#include <cstdio>
namespace fallout {
Object* gDude;
static Object actors[3];
static unsigned int now = 100;
unsigned int gameTimeGetTime() { return now; }
int playerActorSlotOf(Object* actor) {
    for (int i = 0; i < 3; i++) if (actor == &actors[i]) return i;
    return -1;
}
void playerSheetMarkDirty(Object*) {}
struct MemoryStream { std::vector<int> data; };
int fileWriteInt32List(File* stream, int* data, int count) {
    auto* memory = reinterpret_cast<MemoryStream*>(stream);
    memory->data.assign(data, data + count);
    return 0;
}
int fileReadInt32List(File* stream, int* data, int count) {
    auto* memory = reinterpret_cast<MemoryStream*>(stream);
    if (static_cast<int>(memory->data.size()) != count) return -1;
    std::copy(memory->data.begin(), memory->data.end(), data);
    return 0;
}
}
int main() {
    using namespace fallout;
    gDude = &actors[0];
    skill_use_slot_clear();
    for (int n = 0; n < 3; n++) assert(skillUpdateLastUse(SKILL_FIRST_AID, &actors[1]) == 0);
    assert(skillUpdateLastUse(SKILL_FIRST_AID, &actors[1]) == -1);
    assert(skillGetUsesToday(SKILL_FIRST_AID, &actors[0]) == 0);
    assert(skillGetUsesToday(SKILL_FIRST_AID, &actors[2]) == 0);
    assert(skillUpdateLastUse(SKILL_DOCTOR, &actors[1]) == 0);
    assert(skillUpdateLastUse(SKILL_FIRST_AID, &actors[2]) == 0);
    // Default subject follows the acting player, explicit subject ignores gDude.
    gDude = &actors[2];
    assert(skillGetUsesToday(SKILL_FIRST_AID) == 1);
    assert(skillGetUsesToday(SKILL_FIRST_AID, &actors[1]) == 3);
    // Per-slot persistence restores both skills without changing another actor.
    MemoryStream saved;
    assert(skillsUsageRowWrite(reinterpret_cast<File*>(&saved), 1) == 0);
    skillsPlayerActorSeedSlot(1);
    assert(skillGetUsesToday(SKILL_FIRST_AID, &actors[1]) == 0);
    assert(skillsUsageRowRead(reinterpret_cast<File*>(&saved), 1) == 0);
    assert(skillGetUsesToday(SKILL_FIRST_AID, &actors[1]) == 3);
    assert(skillGetUsesToday(SKILL_DOCTOR, &actors[1]) == 1);
    assert(skillGetUsesToday(SKILL_FIRST_AID, &actors[2]) == 1);
    // Preserve the existing cooldown rule; a later use replenishes only its owner.
    now += 25 * GAME_TIME_TICKS_PER_HOUR;
    assert(skillUpdateLastUse(SKILL_FIRST_AID, &actors[1]) == 0);
    assert(skillGetUsesToday(SKILL_FIRST_AID, &actors[2]) == 1);
    assert(skillsUsageRowRead(reinterpret_cast<File*>(&saved), -1) == -1);
    puts("PASS: actor isolation, separate skill budgets, subject resolution, usage-row persistence, cooldown");
}
