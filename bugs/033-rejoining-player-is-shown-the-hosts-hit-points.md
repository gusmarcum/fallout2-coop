# 033: A player who joins is shown the host's hit points instead of their own

**Status**: FIXED (2026-09-28), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/client_net.cc` (`rebindLocalActor`), `tools/client_screen_proof.py`.

## Symptom
GitHub issue 2: "client1 joins after short logout, client2 remains in session. HP of client1
character is set to exactly the same as client2. Expected: HP of client1 is saved between
sessions."

## Root cause
Nothing was lost. The server keeps each player's hit points on their own body, parked or
not, and they were correct throughout. The number on the returning player's screen was
wrong.

The viewer's hit point counter does not jump, it rolls: `rollDudeHp` moves the SHOWN value a
little each frame toward `_dudeHpAuth`, the last value the server gave for "my" body. That
authority is seeded when a world is loaded (`applyBlob`), from whichever actor `gDude` aims
at then.

On a join the two things the client needs arrive in a fixed order: the world first, the
roster (which actor belongs to which session) after it. While the world loads the client
does not yet know which body is its own, so `gDude` is the host's and the authority is
seeded with the HOST's hit points. The roster then re-points `gDude` at the player's own
body (`rebindLocalActor`) and repaints the counter, correctly, for a moment; the authority
is left as it was, and the roll walks the player's counter to the host's number, where it
stays until the player is next hurt or healed, or the party changes map.

It needs a player who is not the host and whose hit points differ from the host's, which is
why a fresh pair at full health rarely shows it and a rejoin mid-adventure always does.

## Fix
`rebindLocalActor` seeds the authority from the body it has just bound, in the one place
where `gDude` changes hands.

## Verification
`python -u tools/client_screen_proof.py hp <f2_server.exe> <fallout2-ce.exe> <sandbox> <port>
<cmd port>`: real client with no window, screenshots every 40 frames. Host at 34 of 44,
second player at 1 (operator `kill` then `revive`), second player leaves and joins again.
The counter is read off the screenshots (it is red at low health).

| client | counter after the join |
|---|---|
| v1.3.1 | 034, white, in every frame (`--expect-defect`: 5/5) |
| fixed | 001, red (5/5) |
