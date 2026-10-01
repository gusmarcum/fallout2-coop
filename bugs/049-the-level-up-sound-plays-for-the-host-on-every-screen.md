# 049: The level-up sound plays for the host's level on every screen, and never for anyone else's

**Status**: FIXED (2026-09-30), proven on a sandbox with a wire bot and the real client; not yet
confirmed in live play.
**Files**: `src/stat.cc` (the award), `src/client_net.cc` (`onPlayerSheet`),
`tools/issue_wire_proof.py` (`lvlsfx`), `tools/client_screen_proof.py` (`lvlup`).

## Symptom
GitHub issue 21: "Level up notification is soundless. We all love this sound and without it
the game isn't the same."

## Root cause
Vanilla plays "levelup" where the level is awarded (`pcAddExperienceWithOptions`). On the
dedicated server that code runs with no speakers, and its `sfxPlay` is a broadcast to every
viewer; the call was also guarded `isHost`, from before the award became per-actor. So the
host's level-ups sounded on every player's screen, and nobody else's level-up made a sound
anywhere. "You have gone up a level." was already addressed to the earner (bugs/earlier);
the sound was the piece left behind.

## Fix
The dedicated server sends no sound for a level-up. Each viewer plays "levelup" itself when
the sheet row that arrives for its own character (`EVENT_PLAYER_SHEET`) carries a higher level
than the one it had, and logs `client_net: level-up sound (level A -> B)`. Single-player is
unchanged (the award still plays it locally there).

## Verification
`python -u tools/issue_wire_proof.py lvlsfx ...`: the host and a second player are in; the
operator gives the host 5000 XP (level 1 to 3). The sound effects on each player's stream are
read off the wire (`EVENT_SFX`).

| server | "levelup" streamed to the host | to the second player |
|---|---|---|
| v1.4.0 (`--expect-defect`, 3/3) | twice (a broadcast, one per level) | twice (the host's level-ups) |
| fixed (2/2) | none | none |

`python -u tools/client_screen_proof.py lvlup ...`: the second player's real client is in; the
operator gives it 80000 XP. Fixed (2/2): the client logs "level-up sound (level 1 -> 13)".
