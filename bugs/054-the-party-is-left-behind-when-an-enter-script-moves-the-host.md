# 054: One player, or a companion, arrives far from the rest of the party on some maps

**Status**: INVESTIGATED (2026-10-01), NOT REPRODUCED; a candidate fix is parked as a patch
(`F2-Coop-Dev-Build/patches/issue-20-party-rering-after-enter-script.patch`) and is NOT in
v1.4.1. Waiting on a reproduction from the reporters.
**Files**: `tools/issue_wire_proof.py` (`entryring`, a regression check).

## Symptom
GitHub issue 20: "once when entering Torr Brahmin quest for the first time Player3 in 3
players game was spawned much to the left of the screen (about 20 hexes to the top left of
the screen). Next time when entering rat caves in Klamath Trapper Town with 3 players and
Sulik it spawned Sulik to half way to the right."

## What was found
On a map load the other players are ringed around the host, and the companions gathered
around theirs, in `_map_place_dude_and_mouse`, BEFORE the map's enter script runs. The
Klamath graze map's script (`klagraz.ssl`) moves the host on entry with
`override_map_start_hex(17704, 0, 1)` when the party arrives from the trapping caves
(`GVAR_LOAD_MAP_INDEX == 13`), which moves only the host (`opOverrideMapStart`). That looked
like the cause: a host moved by the script, the rest left where the ring was made.

It did not reproduce. With the gvar set and the map entered through a transition
(`entermap 14`), v1.4.0 and the fixed server both ended with the second player one hex from
the host at the script's hex (the `entryring` proof). The transition path re-rings the
players after the load, so the gap must come from another path or another cause (a
worldmap arrival, a scripted `load_map`, or the ring search itself: it looks six hexes
along the six directions only, and co-locates when all are blocked, so it never places
anyone twenty hexes away by itself).

## Parked candidate
After the enter and update procs, ring the online players again and re-sync the companions
when the host ended up more than six hexes from where the ring was made or on another
elevation. Harmless when the host did not move; not shipped because it was not shown to fix
the report. The reply asks the reporters which map and which route produced it.

## Verification
`python -u tools/issue_wire_proof.py entryring ...` is kept as a regression check of the
transition path: both players arrive on the graze map with the script having moved the
host, and they stand together.
