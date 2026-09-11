# 026: Solo saves forget the host account, and a finished creation screen wipes the character

**Status**: FIXED (2026-09-11), not yet confirmed in live play.
**Files**: `src/player_sheet.cc` (`playerActorAppendixSave` / `playerActorAppendixLoad`),
`src/server_control.cc` (inline `login` path, `ClaimDisposition`, the drain's
re-check-by-name greet).

## Symptom
On a world with only one human (the gus1.2 playthrough), every server restart
prompts the returning player with the character creation screen, and after ESCing
it the greeting reads "No character was rolled - you joined as the default.
Reconnect under a new name (and finish the creation screen) to make your own."
Play afterwards is completely normal, because the "default" the player bound is
the host body from the save, i.e. their real character. Verified on disk: none of
the six gus1.2 saves contained a `PAC2`/`PACT` appendix at all.

## Root cause
The account name/token table is persisted only inside the save-file appendix, and
`playerActorAppendixSave` skipped the whole appendix at `extras <= 0` to keep a
single-player save byte-for-byte a vanilla save. So a SOLO co-op world never
recorded that any name owned slot 0. On the next `server-load`, the table came
back empty, the client's pre-join `account <name>` probe was answered "new",
`F2_PLAYER_CREATE=ask` reopened the creation screen, and the login bound the host
body as a brand-new account (`kNewDefault`).

## The dangerous half
`playerCreateApply`'s own comment states its protection: "an existing account
never carries a creation spec." A lost table removes exactly that protection.
With the name unknown, a FINISHED creation screen sent a spec, the inline login
applied it to the existing host body, and `playerCreateApply` resets level to 1,
XP/karma/reputation to 0, clears perks, and re-rolls stats and skills. One
keypress away from wiping a campaign character; only the habit of ESCing the
screen prevented it. The same hazard applied to any leveled body in a save made
before the account system existed (old two-player worlds): both players would be
offered creation screens on their first login, and finishing one wiped that
leveled character.

## Fix (three layers)
1. **Persist the table for solo worlds** (`player_sheet.cc`): the appendix is now
   written whenever slot 0 is account-owned, even with zero extras, as a short
   table-only form (magic, count 0, one-row table, events magic; no bodies, no
   sheet block since `playerSheetBlockWrite` emits nothing at count 0). The
   loader skips the sheet-block read at `extras == 0` to match. A never-logged-in
   single-player save still writes no appendix and stays vanilla-shaped.
2. **Established-body guard** (`server_control.cc`, inline login only): a new
   account landing on an existing body with earned progress (level > 1 or XP > 0)
   never has a creation spec applied over it; the spec is dropped with a console
   line and the player adopts the established character. The drain's spawn path
   stays unguarded on purpose: its body is freshly seeded from the host this
   beat, so its "progress" is clone residue and applying the spec there is the
   designed behaviour.
3. **Honest greetings**: two new dispositions say what actually happened
   (`kAdoptedExisting`: "This seat already held an established character - you
   joined as them"; `kRollRefused`: "Your new roll was NOT applied..."), instead
   of `kNewDefault`'s advice to go finish a creation screen. The drain's
   re-check-by-name rebind now greets `kResumedExisting` rather than claiming a
   character was created.

## Compatibility
- Old saves (no appendix, or v1 `PACT`) still load; their slots come back
  unowned, the prompt appears ONE more time, and the guard makes that safe. The
  first save written by the fixed build carries the table, and every restart
  after that resumes by name with no creation screen.
- A solo save written by the fixed build (table-only appendix) does NOT load on
  older co-op builds: the old loader reads the tail expecting a sheet block and
  refuses the save. Do not roll the exes back past this fix once new solo saves
  exist. Vanilla-tool compatibility is unaffected in the way it always was:
  the appendix sits past the last byte vanilla reads.
- The wire/blob format is untouched; the appendix functions are called from
  `savegame.cc` only.
