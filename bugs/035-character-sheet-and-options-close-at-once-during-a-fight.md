# 035: The character sheet and Options close the moment they open during a fight

**Status**: FIXED (2026-09-30), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/client_net.cc` (`viewerServiceTicker`), `src/character_editor.cc` and
`src/main.cc` (a log line each), `tools/client_screen_proof.py` (`sheet`).

## Symptom
GitHub issue 3, follow-up after the chat fix: "similar issue is for the character sheet [C]
window and options [O] as well, only during combat. Showing up for a couple of frames then
disappears." GitHub issue 11: "Character screen auto-closes in combat."

## Root cause
Same defect class as bugs/034. The service ticker that keeps the wire pumping while a screen
is open also closes screens when a fight starts: combat entry clears the screen of UI, and a
screen left open from peacetime would otherwise hold keys the fight needs. That rule was a
test on every frame of the fight (`if (inCombat()) inject ESC`), with only the inventory and
loot screens the server priced for this fight, and the worldmap, exempt.

So a character sheet or Options opened during a fight, which vanilla allows and which cost
nothing, was closed again by the next frame. The skilldex had the same fate; nobody had
reported it yet.

## Fix
The ticker now tracks the edge. A fight that STARTS while a screen is up still closes it, as
before (`gCombatStartedUnderScreen`, latched at the edge and held until the screen is gone).
The free screens, the character sheet, Options (preferences) and the skilldex, opened DURING
the fight stay until the player closes them. The priced screens (inventory, loot) keep their
old rule: only the server's sanction keeps one open in a fight.

A screen closed by the ticker is also marked (`clientViewerTakeForcedScreenClose`), because
the character sheet's ESC is vanilla's Cancel, which now walks the visit's spends back
(bugs/044): a fight starting under an open sheet must not throw away what was spent.

The client logs how long each sheet and each Options screen stayed up and who closed it
(`character sheet: closed after N ms by the player`).

## Verification
`python -u tools/client_screen_proof.py sheet <f2_server.exe> <fallout2-ce.exe> <sandbox>
<port> <cmd port>`: the real client with no window and a recorded keyboard that opens the
sheet with C and closes it with C three seconds later, then opens Options with O and closes
it with Enter. Two cycles in peace, a quiet gap in which a hostile is set on the host, then
cycles again during the fight. The sheets' lifetimes are timed from the server's
`sheetopen`/`sheetclose` lines, and whether the fight was on at each moment from the
COMBAT_ENTER/EXIT events on the wire.

| client | sheets in peace | sheets during the fight | "end combat" sent by the Enter meant for Options |
|---|---|---|---|
| v1.3.2 (`--expect-defect`: 4/4) | 3.1 s, 3.0 s | 0.0 s, 0.1 s, 0.0 s, 0.0 s, 0.0 s | 2 |
| fixed (7/7) | 3.1 s, 3.0 s | 3.0 s, 3.0 s | 0 |

Every cycle also opens the skilldex with S and closes it with S. The fixed client logged all
four Options screens and all four skilldex screens as closed by the player after about 3 s,
and no screen closed by the game (the skilldex and Options leave no server line, so the old
client cannot be timed on those two). The fight in the table ran from 30.6 s to 67.7 s; one
earlier fixed run lost its fight part way, which the proof reports as a failure of its own
setup ("and it lasted the whole window").
