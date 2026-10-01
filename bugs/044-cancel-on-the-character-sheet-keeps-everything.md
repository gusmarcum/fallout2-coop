# 044: Cancel on the character sheet keeps the skill points and perks it was meant to discard

**Status**: FIXED (2026-09-30), proven on a sandbox, the real character screen included; not
yet confirmed in live play.
**Files**: `src/sheet_intent.{h,cc}` (`sheetEditCancel`), `src/server_control.cc`
(`sheetcancel`), `src/character_editor.cc` (`characterEditorShowViewOnly`),
`src/client_net.{h,cc}`, `tools/issue_wire_proof.py` (`cancel`).

## Symptom
GitHub issue 12: "Cancel button on character screen will also accept allocated skill points /
perks."

## Root cause
In vanilla the character screen is a transaction: it snapshots the sheet when it opens, Done
keeps the changes, and Cancel, Esc and C restore the snapshot.

In co-op the server owns the sheet. Every + and every perk pick goes to the server as it is
clicked (`skillup`, `perkpick`, and the Tag!/Mutate! follow-ups) and is applied there at once,
and the screen's own restore was removed on purpose, because restoring the open-time snapshot
would wipe the rows the server streamed in. "Done" and "Cancel" both simply closed the screen,
so Cancel kept everything.

A snapshot restore on the server is not the answer either: the world does not pause while a
co-op sheet is open. A level earned from a teammate's kill, a heal, a drug wearing off, all of
that can land on the row while the screen is up, and a restore would throw it away.

## Fix
The server's edit session (the one that already holds the "-" baseline) keeps a record of the
visit's spends, oldest first: points bought, points walked back, perks taken, and each
follow-up's answer. `sheetcancel` walks them back newest first, each by its exact inverse:
a point bought is sold back (`skillSub` refunds what "-" would), a point walked back is bought
again, a perk comes off with its owed pick handed back, a Tag! is untagged, a Mutate! gets its
old traits back, Lifegiver gives back its extra 4 maximum and 4 hit points (never the last
one), Educated its 2 points. Anything that happened to the character outside the screen is
left alone.

Here and Now is the one exception: it pays out a whole level, which cannot be handed back, so
it stays and the player is told ("Here and Now cannot be taken back; everything else was.").

The screen sends `sheetcancel` before `sheetclose` when the PLAYER leaves with Cancel, Esc or
C (vanilla's rc 1). In v1.4.0 a screen the game closed itself (a fight starting under it, a
map change: the service ticker's forced close, bugs/035) kept what was spent; since the
follow-up (bugs/046) it cancels too, and only Done keeps. Quitting the game with the screen
open keeps what was spent. An older server ignores the verb, so an older server behaves as
before.

## Verification
`python -u tools/issue_wire_proof.py cancel ...`: the second player is funded with points and
levels, opens the sheet, buys three points, takes Educated (+2 points), takes Tag! and tags a
fourth skill, buys two points in it, and cancels.

| server | the row after Cancel | the next point bought in the first skill |
|---|---|---|
| v1.3.2 (`--expect-defect`) | still spent: unspent 96, owed perks x2 (were x4), fourth tag 12 | lands on 55 |
| fixed (5/5) | identical to the row before the screen opened (unspent 99, owed x4, no fourth tag) | lands on 49, as the first one did |

Done keeps its spends (unspent 99 -> 97).

`python -u tools/client_screen_proof.py cancelui ...`: the real client with 20 points to
spend, keyboard only. It opens the sheet, selects Small Guns (Tab x7), buys three points
(Right) and leaves with C; opens it again, buys two and leaves with Enter (Done); opens it a
third time, buys one, and the operator starts a fight under it. Each reading waits for the
server to see that visit end.

| client + server | after the C (Cancel) | after the Enter (Done) | after the fight closed it |
|---|---|---|---|
| v1.3.2 (`--expect-defect`: 4/4) | 17 (kept, no cancel sent) | 15 | 14 |
| fixed (4/4) | 20 (all three back) | 18 (two kept) | 17 (one kept, "closed by the game") |

The last column changed with bugs/046: a close the game forces now takes the point back
(18), and the proof expects that.

The first version of the Educated undo took back a flat 2 points. At the 99-point cap the +2
never lands, so that would have cost the player 2 points; the pick's own additions are now
measured when it is made, and exactly those come back off.
