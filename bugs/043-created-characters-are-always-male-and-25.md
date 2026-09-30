# 043: A created character is always male and 25, whatever the creation screen said

**Status**: FIXED (2026-09-30), proven on a sandbox, the real creation screen included; not
yet confirmed in live play.
**Files**: `src/player_create.{h,cc}`, `src/server_control.cc` (`create`), `src/main.cc` (the
creation screen's line), `src/client_net.cc` (the local look), `tools/issue_wire_proof.py`
(`create`).

## Symptom
GitHub issue 14: "In the character creation screen, the selected sex and age are not saved in
the actual game. Everything resets to 25 years old and male."

## Root cause
The character a new player rolls is sent to the server as data, `create S P E C I A L t t t tr
tr` (`PlayerCreateSpec`), and the server builds the sheet from it. Sex and age were never part
of it. The applier resets the row first (so a new character does not inherit the host's),
which put both back to the defaults, male and 25, and nothing set them again.

## Fix
- `PlayerCreateSpec` carries `gender` and `age` (defaults male, 25), validated as the creation
  screen allows them (male or female, 16 to 35), and applied as base stats after the reset.
- The line gains two trailing numbers, `... tr tr sex age`. Wire-compatible both ways: an
  older server reads the first twelve and ignores the rest; an older client sends twelve and
  gets the old male, 25.
- The creation screen sends its base sex and age (base, not displayed: the displayed age adds
  the years of game time passed).
- The body: a female character is re-dressed at once in the female body of the current look
  (tribal or vault suit): `protoPlayerActorsUpdateLook` for a joining player,
  `_proto_dude_update_gender` for the host's own slot. Before, the row kept the host's seeded
  look until the next baseline.
- The viewer re-derives its own paper-doll body (`_art_vault_guy_num`) when it binds to a body
  of the other sex than the host's, and when its own row changes sex; it used to derive it
  from the host during the join and keep it.

## Verification
`python -u tools/issue_wire_proof.py create ...`: a new player sends
`create 5 6 5 7 6 6 5 -1 -1 -1 -1 -1 1 30` and logs in, and another sends an old twelve-number
line. The server's `[create]` trace reads back what landed.

| server | new line (female, 30) | old line |
|---|---|---|
| v1.3.2 | the spec never carried sex or age; the trace reads nothing back | the same |
| fixed (4/4) | female, 30, body art 4 (the female one) | male, 25, body art 11 |

`python -u tools/client_screen_proof.py createui ...`: the real client rolls a new character
on the real creation screen, keyboard only: female (S, Right, Enter), 30 (A, Up x5, Enter),
five points into Strength, three tagged skills, Done, and yes to the unnamed-character box.

| client + server | the line the creation screen sent | what the server built |
|---|---|---|
| v1.3.2 (`--expect-defect`: 3/3) | `create 10 5 5 5 5 5 5 0 1 2 -1 -1` | male, 25 |
| fixed (3/3) | `create 10 5 5 5 5 5 5 0 1 2 -1 -1 1 30` | female, 30, body art 4 |
