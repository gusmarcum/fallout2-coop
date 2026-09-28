# 034: The chat box closes the moment it opens during a fight

**Status**: FIXED (2026-09-28), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/main.cc` (the chat block of the viewer's frame loop),
`tools/client_screen_proof.py`.

## Symptom
GitHub issue 3: "open chat during combat: chat window disappears immediately, no chat
possible."

## Root cause
The chat box has a rule that a fight closes it: a box left open from peacetime would eat
the keys that drive the fight. The rule was written as a test that runs on every frame
(`if (conn.inCombat() && clientSayActive()) clientSayCancel()`), which was harmless while
the box could only be opened out of combat.

8994c8f added T as the key that opens the box during a fight and left that test in place.
So T opened the box and the next frame closed it. The letters typed after it were then
ordinary game keys, and the Enter meant to send the line asked the server to end combat
instead.

## Fix
The box is closed when a fight STARTS (the frame combat begins), not for as long as it
lasts. A box opened during the fight stays until the line is sent or cancelled.

While the box is open it takes every key, as it does out of combat. The END TURN and END
COMBAT buttons post the same key codes as SPACE and Enter, so with the box open they type
into it: send or cancel the line first.

## Verification
`python -u tools/client_screen_proof.py chat <f2_server.exe> <fallout2-ce.exe> <sandbox>
<port> <cmd port>`: real client with no window and a recorded keyboard that presses T,
types "hey" and presses Enter every few seconds; the host is attacked part way through, so
the fight cannot be called off. What the server received from the second player during the
fight:

| client | chat lines | "end combat" requests |
|---|---|---|
| v1.3.1 | 0 | 6 (`--expect-defect`: 4/4) |
| fixed | 6 | 0 (4/4) |

Screenshots of the fixed client show the box with "Say: hey_" while the action point
lights are lit.
