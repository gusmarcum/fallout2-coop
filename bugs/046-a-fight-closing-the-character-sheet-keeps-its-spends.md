# 046: A fight closing the character sheet keeps what the player had spent on it

**Status**: FIXED (2026-09-30), proven on a sandbox with the real character screen; not yet
confirmed in live play.
**Files**: `src/character_editor.cc` (`characterEditorShowViewOnly`), `src/server_control.cc`
(a comment), `tools/client_screen_proof.py` (`cancelui`), `bugs/044` (the rule it changes).

## Symptom
GitHub issue 12, the follow-up to v1.4.0: "there is a special case when combat is initiated
while you are at character screen. Then character window will close with 'DONE' by default,
I believe 'Cancel' would be more appropriate since player is planning while other player may
initiate combat."

## Root cause
bugs/044 made Cancel a request to the server (`sheetcancel`) and chose, on purpose, that a
screen the game closes itself keeps what was spent: the service ticker's forced close (a
fight starting under the screen, a map change) was excluded from the Cancel. The reporter's
point stands: nobody chose Done, the plan was half made, and in co-op a teammate can start
the fight at any moment.

## Fix
A forced close is a Cancel too. `characterEditorShowViewOnly` sends `sheetcancel` before
`sheetclose` when the screen returned Cancel's rc OR the ticker's forced-close mark is set.
Only Done keeps. Quitting the game with the screen open still keeps what was spent: a client
that is going away may not get its cancel heard, and vanilla cannot quit from inside the
screen anyway. The server side is unchanged (`sheetcancel` walks the visit's spends back from
its own record, Here and Now excepted, bugs/044).

## Verification
`python -u tools/client_screen_proof.py cancelui ...`, the same keyboard as bugs/044: with 20
points to spend, buy three and leave with C (Cancel), buy two and leave with Enter (Done), buy
one and the operator starts a fight under the open sheet.

| client + server | after the C (Cancel) | after the Enter (Done) | after the fight closed it |
|---|---|---|---|
| v1.4.0 (`--expect-defect`) | 20 (back) | 18 (two kept) | 17 (one kept, "closed by the game", one cancel sent in all) |
| fixed | 20 (back) | 18 (two kept) | 18 (one back: "closed by the game (Cancel: spends walked back)", two cancels sent) |
