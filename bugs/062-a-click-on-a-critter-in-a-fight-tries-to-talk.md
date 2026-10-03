# 062: In a fight, a click on a critter tries to talk to it instead of looking at it

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client and a real mouse
click; not yet confirmed in live play.
**Files**: `src/main.cc` (`viewerSendPrimaryVerb`), `tools/client_screen_proof.py`
(`lookclick`).

## Symptom
GitHub issue 31: "During combat, clicking on an NPC in look cursor mode shows the binoculars
icon is selected by default, yet the player character tries to talk to the NPC instead of
performing the default inspection. Then I get the 'You can't talk to anyone in combat'
message. Players have to hold mouse button and select binoculars again from the context
menu to read HP / status for NPCs."

## Root cause
The hover icon is vanilla's own code (`game_mouse.cc`): for a critter that can be talked to,
the primary action is TALK outside a fight and LOOK in one. The click is the co-op client's
(`viewerSendPrimaryVerb`), and it sent `talk` for every living critter. Icon and click
disagreed in exactly the case the reporter hit.

## Fix
In a fight the primary verb for a living critter is `look`.

## Verification
`python -u tools/client_screen_proof.py lookclick ...`: the real client, alone, has a raider
two tiles off, right-clicks to the arrow cursor, presses A to start a fight and clicks on
the raider (the recorded mouse moves from the middle of the screen onto the raider's chest;
the client's trace confirms which object the click landed on).

| build | the click in the fight |
|---|---|
| v1.4.1 (`--expect-defect`, 2/2) | `talk`, refused: "control talk dropped (in combat)" |
| fixed (2/2) | `look` at the raider |
