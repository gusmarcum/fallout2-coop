# 066: The host is left on old coordinates when another player triggers a map change

**Status**: FIXED (2026-10-02), proven on a sandbox with wire bots; not yet confirmed in
live play.
**Files**: `src/map.cc` (`_map_place_dude_and_mouse`), `src/command.cc` (`entermapas`),
`tools/issue_wire_proof.py` (`hostplace`).

## Symptom
GitHub issue 20. "Klamath Torr quest (grazing area): if host initiated the quest (speak
with Torr), everything works fine, both players got spawned to the northern area with
Brahmin. If the quest initiator (speaker) is not the host, only the speaker gets correctly
spawned. Other player gets spawned into the woods (depending on his current position at
Klamath downtown)." And from a three-player group: one player "keeping the same coordinates
from previous map copied over to the new one", every time at the Modoc Bed and Breakfast
cave, Grisham's pastures and Farrel's garden, landing behind cave walls and foliage (which
is also how issue 45's watch was reached).

## Root cause
A map change that a script asks for (`load_map`, with no arrival tile) runs under the scope
of the player whose dialog or use ran the script, so inside the load `gDude` is THAT
player. `mapLoad` puts `gDude` on the map's entering tile, and `_map_place_dude_and_mouse`
then plants "every other player" beside them, counting from slot 1. When the asker was the
host that is everybody. When the asker was not the host, slot 0 was neither `gDude` nor in
the loop: the host kept the tile number it had on the map it had just left, which on the
new map is some unrelated hex.

A trip that names its arrival tile (an exit grid) was never affected: `mapHandleTransition`
places the host and rings the others after the load, outside the scope.

The three-player report fits: the body that is never placed is the host's, whoever of the
others asked for the trip.

## Fix
The loop covers every slot except the one that is `gDude`.

`entermapas <map> <slot>` is a new operator verb for the proof: it stages the transition a
script's `load_map` would, asked for by a given player.

## Verification
`python -u tools/issue_wire_proof.py hostplace ...`: two players in Arroyo, the second asks
for the trip to the Den.

| build | where the host is after the trip |
|---|---|
| the same build with the old loop (`--expect-defect`, 3/3) | tile 20517, its Arroyo tile number, 36 hexes from the other player |
| fixed (2/2) | beside the player who asked, 1 hex apart |

The released v1.4.1 cannot run this proof (it has no `entermapas`), so the defect is shown
on a build of the current tree with only this loop put back.
