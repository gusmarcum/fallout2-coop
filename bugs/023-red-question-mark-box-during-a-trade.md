# 023: A small red box with a question mark in the top-left corner during a trade

**Status**: FIXED (2026-09-10), not yet confirmed in live play.
**Files**: `src/object_render.cc` (`_obj_render_post_roof`).

## Symptom
While a trade screen is open, a small red-framed box with a question mark sits in the
top-left corner of the map view, above the roofs, and does not move when the view scrolls.
Every player sees it. It goes away when the trade closes. Reported from live play on
2026-09-10, at Klamath with the Duntons.

## Root cause
The image is `art/items/reserved.frm`, item art 0, the engine's placeholder picture. The
trade screen (`inventoryOpenTrade`) creates a staging container to hold the merchant's
equipped gear for the duration of the trade: `objectCreateWithFidPid(&hiddenBox, 0,
PROTO_ID_JESSE_CONTAINER)`, art 0, never placed on a tile, never flagged hidden. The
original game never draws it because nothing repaints the map while its modal trade
window is up.

On the server that creation goes through `objectCreateWithFidPid`, which announces every
new object with a real proto to the viewers as a SPAWN carrying its birth flags. So each
viewer creates the box too: `objectSetLocation` fails on tile -1, the object stays on the
no-tile list, and the flags it arrived with do not include hidden. The post-roof render
pass draws every unhidden object on that list at its raw screen position, which for an
object that was never placed is (0, 0). The viewer keeps repainting the map during a trade,
so the placeholder shows until the server destroys the box at the end of the trade. It is
the same mechanism as the parked-body sticker fixed on 2026-09-05, with a different object.

## Fix
`_obj_render_post_roof` no longer draws an object that has no tile and still carries the
allocation's (0, 0) screen position. Nothing in the game ever legitimately shows one: the
no-tile list exists for the mapper's drag-and-drop, and an object being dragged has a real
position and still draws. With `F2_TRACE_EVENTS` set the client logs each object it skips
this way once, with pid, fid and netId, so any further case names itself.

The staging box itself is left as it is: the server cannot hide it before the announcement
(the flag would have to be set inside `objectCreateWithFidPid`), and it is never on the map.

## Verification
Not reproducible headlessly: the probe does not render. Check in live play: open a trade
from a conversation and from the Barter button, look at the top-left corner, then run a
client with `F2_TRACE_EVENTS=1` and look for `object_render: not drawing unplaced object
pid=0x... fid=0x00000000` in `debug.log` while the trade is open.
