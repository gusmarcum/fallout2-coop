// Exercise the real proto row reader/writer, CritterProtoData serializer and
// new-player seeder. Only the integer stream is mocked; no game assets needed.
// g++ -std=c++17 -O2 -flto -fwhole-program -ffunction-sections -fdata-sections \
//   -Isrc -I<SDL2-include> tests/player_addiction_sheet_test.cc src/critter.cc \
//   -Wl,--gc-sections -o player-addiction-sheet-test
#ifdef NDEBUG
#error This test requires assertions enabled.
#endif
#include "../src/proto.cc"
#include <cassert>
#include <vector>

namespace fallout {
struct IntStream {
    std::vector<int> values;
    size_t position = 0;
};
int fileWriteInt32(File* file, int value)
{
    reinterpret_cast<IntStream*>(file)->values.push_back(value);
    return 0;
}
int fileReadInt32(File* file, int* value)
{
    auto* stream = reinterpret_cast<IntStream*>(file);
    if (stream->position >= stream->values.size()) return -1;
    *value = stream->values[stream->position++];
    return 0;
}
int fileWriteInt32List(File* file, int* values, int count)
{
    for (int i = 0; i < count; i++) fileWriteInt32(file, values[i]);
    return 0;
}
int fileReadInt32List(File* file, int* values, int count)
{
    for (int i = 0; i < count; i++) {
        if (fileReadInt32(file, &values[i]) == -1) return -1;
    }
    return 0;
}
}

int main()
{
    using namespace fallout;
    const int unrelatedFlags = (1 << DUDE_STATE_SNEAKING) | CRITTER_NO_STEAL;
    const int hostFlags = unrelatedFlags | (1 << DUDE_STATE_ADDICTED)
        | (1 << DUDE_STATE_ADDICTION_FIRST) | (1 << DUDE_STATE_ADDICTIONS_INITIALIZED);
    gDudeProto.data.flags = hostFlags;
    gDudeProto.data.baseStats[STAT_STRENGTH] = 7;
    protoPlayerActorSheetSeedSlot(1);
    auto* extra = protoPlayerActorSheetData(1);
    assert(extra->flags == unrelatedFlags);
    assert(extra->baseStats[STAT_STRENGTH] == 7 && gDudeProto.data.flags == hostFlags);

    // Host and extra flags survive the SAME row path used by disk appendix and
    // network sheet blocks. No version bump or additional integer was needed.
    const int extraFlags = unrelatedFlags | (1 << DUDE_STATE_ADDICTED)
        | (1 << DUDE_STATE_ADDICTION_LAST) | (1 << DUDE_STATE_ADDICTIONS_INITIALIZED);
    extra->flags = extraFlags;
    for (int slot : {0, 1}) {
        IntStream stream;
        auto* file = reinterpret_cast<File*>(&stream);
        assert(protoPlayerActorRowWrite(file, slot) == 0);
        assert(stream.values.size() == 1 + 2 * SAVEABLE_STAT_COUNT + SKILL_COUNT + 4);
        protoPlayerActorSheetData(slot)->flags = 0;
        assert(protoPlayerActorRowRead(file, slot) == 0);
        assert(protoPlayerActorSheetData(slot)->flags == (slot == 0 ? hostFlags : extraFlags));
    }
    // Old rows with no new bits remain readable and eligible for migration.
    IntStream legacy;
    gDudeProto.data.flags = 1 << DUDE_STATE_ADDICTED;
    assert(protoPlayerActorRowWrite(reinterpret_cast<File*>(&legacy), 0) == 0);
    gDudeProto.data.flags = 0;
    assert(protoPlayerActorRowRead(reinterpret_cast<File*>(&legacy), 0) == 0);
    assert(gDudeProto.data.flags == (1 << DUDE_STATE_ADDICTED));
    puts("PASS: personal flags and legacy rows round-trip; new players do not copy host addiction flags");
}
