# 039: Rests of three hours or less never heal, however often they are repeated

**Status**: FIXED (2026-09-30), proven on a sandbox; not yet confirmed in live play.
**Files**: `src/server_control.cc` (the `rest` verb), `tools/issue_wire_proof.py` (`rest`).

## Symptom
GitHub issue 10: "sleeping 3 hours or less will not heal me at all, no matter how many times I
click on wait 3 hours button (I have healing rate of 2). Longer periods will heal (like 4
hours heal 2 hp)."

## Root cause
Rest heals one step, the healing rate, per 180 rest minutes (`restHealCheck`). The minutes are
counted per animation frame and the per-frame share is rounded down, so a three hour rest
counts 169 of them and a four hour rest 224. That is vanilla, and vanilla keeps the count for
as long as the pipboy stays open, so the second three hour click tips it over and heals.

The co-op `rest` verb reset the count on every request ("this verb IS the session"), so every
click started again from nothing: 169 minutes, no heal, every time.

## Fix
The verb no longer resets the count. It carries from one rest to the next and a heal still
consumes it. Owner ruling: keep vanilla's rounding (a single three hour rest still heals
nothing; the next one does).

The operator's `rest` command still resets the count per command, so it keeps reporting one
rest in isolation.

## Verification
`python -u tools/issue_wire_proof.py rest ...`: the host is hurt to 34 hit points and rests
three hours twice through the player's verb.

| server | after the 1st rest | after the 2nd rest |
|---|---|---|
| v1.3.2 (`--expect-defect`) | 34 | 34 |
| fixed | 34 | 37 (healing rate 3) |
