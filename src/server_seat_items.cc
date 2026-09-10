#include "server_seat_items.h"

#include <stdio.h>
#include <string.h>

#include "item.h"
#include "map.h"
#include "obj_types.h"
#include "object.h"
#include "platform_compat.h"
#include "proto.h"
#include "server_loop.h"
#include "server_players.h"

namespace fallout {

// One row per shipped item a second player cannot do without and the game places exactly
// once. A container is identified the way the map file identifies it, by (map, proto,
// tile, elevation); matching on the proto alone would hit every locker on the map.
// Measured against the shipped maps on 2026-09-09 (tools/f2data.py plus the state dump
// of a fresh load): Navarro carries nine Advanced Power Armors, eight of them worn by
// Enclave troopers and not lootable, and ONE in a Locker on the lower level; the oil
// rig's trap room carries ONE Mk II in a Locker behind the nine-door puzzle.
struct SeatItemRule {
    const char* map; // map file name without extension, matched without case
    int itemPid;
    int containerPid;
    int tile;
    int elevation;
};

static const SeatItemRule kSeatItemRules[] = {
    { "navarro", 0x0000015C, 0x00000086, 11317, 1 }, // Advanced Power Armor, Navarro base
    { "enctrp", 0x0000015D, 0x00000087, 19527, 0 }, // Adv. Power Armor MKII, oil rig trap room
};

// gMapHeader.name is "NAVARRO.MAP" on a fresh load (mapLoadByName upper-cases it and the
// saved-state path leaves ".SAV" on it); compare the stem only, any case.
static bool currentMapIs(const char* stem)
{
    const char* name = gMapHeader.name;
    size_t n = strlen(stem);
    if (compat_strnicmp(name, stem, n) != 0) {
        return false;
    }
    return name[n] == '\0' || name[n] == '.';
}

static int countInInventory(Object* owner, int pid)
{
    Inventory* inventory = &(owner->data.inventory);
    int total = 0;
    for (int index = 0; index < inventory->length; index++) {
        InventoryItem* entry = &(inventory->items[index]);
        if (entry->item != nullptr && entry->item->pid == pid) {
            total += entry->quantity;
        }
    }
    return total;
}

int serverSeatItemsOnFirstMapLoad()
{
    if (!serverDedicatedActive()) {
        return 0;
    }

    // Bit 0 of the header is set by _map_save_in_game when a map is written out, so it
    // is clear exactly on a map's first load from the shipped .MAP. A revisit loads the
    // .SAV, which already carries whatever this added the first time.
    if ((gMapHeader.flags & 1) != 0) {
        return 0;
    }

    int seats = playerActorCount();
    if (seats <= 1) {
        return 0;
    }

    int added = 0;
    for (const SeatItemRule& rule : kSeatItemRules) {
        if (!currentMapIs(rule.map)) {
            continue;
        }

        Object* container = nullptr;
        for (Object* obj = objectFindFirstAtLocation(rule.elevation, rule.tile); obj != nullptr; obj = objectFindNextAtLocation()) {
            if (obj->pid == rule.containerPid) {
                container = obj;
                break;
            }
        }

        const char* itemName = protoGetName(rule.itemPid);
        if (itemName == nullptr) {
            itemName = "?";
        }

        if (container == nullptr) {
            // Not fatal: a modded or edited map is allowed to move things. Say so once
            // instead of adding the item to the wrong place or to nothing.
            fprintf(stderr, "f2_server: seat items: %s: no container 0x%08X at tile %d elevation %d, %s not topped up\n",
                gMapHeader.name, rule.containerPid, rule.tile, rule.elevation, itemName);
            continue;
        }

        int before = countInInventory(container, rule.itemPid);
        int have = before;
        while (have < seats) {
            // Same recipe as the probe's `give` verb: create, take off the hex grid,
            // hand to the owner. A new object takes a netId at creation on the server
            // (object.cc), and the map-load tail renumbers the whole world anyway.
            Object* item = nullptr;
            if (objectCreateWithPid(&item, rule.itemPid) != 0 || item == nullptr) {
                break;
            }
            _obj_disconnect(item, nullptr);
            if (itemAdd(container, item, 1) != 0) {
                objectDestroy(item, nullptr);
                break;
            }
            have++;
            added++;
        }

        fprintf(stderr, "f2_server: seat items: %s at tile %d holds %d x %s (%d before, %d seats in the save)\n",
            objectGetName(container), rule.tile, have, itemName, before, seats);
    }

    return added;
}

} // namespace fallout
