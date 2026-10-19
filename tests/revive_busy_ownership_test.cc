// Production busy-window regression with a stub clock and object lookup.
// g++ -std=c++17 -O0 -ffunction-sections -fdata-sections -Isrc -I<SDL2-include>
//   tests/revive_busy_ownership_test.cc -Wl,--gc-sections -o revive-busy-test
#ifdef NDEBUG
#error This test requires assertions enabled.
#endif
#include "../src/server_players.cc"
#include <cassert>
#include <cstdio>

namespace fallout {
Object* gDude = nullptr;
static Object actors[3];
static unsigned int now = 100;
unsigned int getTicks() { return now; }
unsigned int getTicksBetween(unsigned int end, unsigned int start) { return end - start; }
int debugPrint(const char*, ...) { return 0; }
// Unused engine entry points retained by the Windows linker. Fail if reached.
int gHexGridSize = 0;
bool critterIsDead(Object*) { std::abort(); }
int tileGetTileInDirection(int, int, int) { std::abort(); }
int tileDistanceBetween(int, int) { std::abort(); }
Object* _obj_blocking_at(Object*, int, int) { std::abort(); }
bool serverDedicatedActive() { std::abort(); }
Object* scriptGetSelf(Program*) { std::abort(); }
int scriptGetSid(Program*) { std::abort(); }
int scriptGetScript(int, Script**) { std::abort(); }
bool objectIsPartyMember(Object*) { std::abort(); }
Object* partyMemberLeader(Object*) { std::abort(); }
Object* objectFindByNetId(int id)
{
    return id >= 1 && id <= 3 ? &actors[id - 1] : nullptr;
}
}

int main()
{
    using namespace fallout;
    gPlayerActorCount = 3;
    for (int i = 0; i < 3; ++i) gPlayerActors[i] = &actors[i];

    serverActorBusyMarkByNetId(1, 1000); // reviver's gesture
    now += 200;
    serverActorBusyMarkByNetId(2, 600, 1); // patient waits 800 ms, then stands
    assert(serverActorBusyIs(0) && serverActorBusyIs(1));
    assert(!serverActorBusyIs(2));
    now += 800;
    assert(!serverActorBusyIs(0)); // patient must not extend reviver's busy mark
    assert(serverActorBusyIs(1));
    now += 599;
    assert(serverActorBusyIs(1));
    ++now;
    assert(!serverActorBusyIs(1));

    // Admin revive / missing / expired dependency: only the patient's duration.
    for (int dependency : { 0, 99, 1, 2 }) {
        serverActorBusyClearAll();
        serverActorBusyMarkByNetId(2, 600, dependency);
        assert(serverActorBusyIs(1) && !serverActorBusyIs(0));
        now += 600;
        assert(!serverActorBusyIs(1));
    }
    serverActorBusyMarkByNetId(99, 600, 1);
    assert(!serverActorBusyIs(0) && !serverActorBusyIs(1));

    // Dependency timing across the unsigned clock wrap.
    serverActorBusyClearAll();
    now = 0xFFFFFF00u;
    serverActorBusyMarkByNetId(1, 1000);
    now += 400;
    serverActorBusyMarkByNetId(2, 600, 1);
    now += 600;
    assert(!serverActorBusyIs(0) && serverActorBusyIs(1));
    now += 600;
    assert(!serverActorBusyIs(1));
    puts("Revive busy ownership tests passed.");
}
