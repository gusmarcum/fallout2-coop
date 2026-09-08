# 018 — Taking power armour off twice charges you for it twice (Strength 9 → 1)

**Status**: FIXED (2026-09-08).
**Files**: `src/inventory.cc` (`_adjust_ac`, `invenArmorLedgerReset`), `src/inventory.h`,
`src/map.cc` (ledger reset on a server map load)

## Symptom
Rare, no known trigger. A player wearing Advanced Power Armor loses the suit's Strength
bonus **twice**: 9 becomes 1 rather than 5. Reported after [012](012-armor-perk-second-player.md)
widened armour perks to every player actor. It is sticky — taking the suit off and putting
it back on does not heal it, it only shifts the drift.

The server log had already recorded it, because 012 added the line that names every
transition:

```
f2_server: armor perk 68 -> -1 for slot 0 (Strength now 5)
f2_server: armor perk 68 -> -1 for slot 0 (Strength now 1)
```

Nine to five is the correct removal. Five to one is the same perk being removed a second
time. It repeated a few lines later with perk 69.

## Root cause
Everything `_adjust_ac` does is a DELTA: armour class, every damage resistance and damage
threshold, and the suit's own perk are each `bonus - old + new`. Nothing checks whether
`old` is currently applied, and `perkRemoveEffect` in particular subtracts the stat
modifier flat, with no notion of whether the perk is held. So a second removal of a suit
already taken off silently charges the player again.

Seven call sites adjust armour (`inventory.cc`, three in `interpreter_extra.cc`, several in
`inventory_ui.cc`), and 012 widening the perk from party members to every player actor let
more than one of them fire for a single unequip. **Which second site fires in this world is
not pinned down** — it is rare and has no known trigger — which is exactly why the fix
defends against all of them rather than chasing one.

Strength is simply the visible half. The armour class and the damage resistances were being
double-subtracted the same way and nobody noticed.

## Fix
A ledger of which armour's bonuses are currently applied to each body, keyed by object id.
`_adjust_ac` drops the `oldArmor` half of its work when the ledger says that suit's bonuses
are not on that body, and records the new state afterwards.

It only ever SUPPRESSES a removal it knows is redundant. A body the ledger has not seen is
trusted exactly as before, so the first call on any critter — and therefore every call in
single player and in both golden suites — behaves identically. The dedicated server logs
`armor bonuses for item id=N are not applied to critter id=M — redundant removal ignored`
whenever it catches one, so the next occurrence names the caller.

The ledger is cleared on a server map load: object ids are reused once a map is torn down,
and a stale entry could otherwise suppress a real unequip on whatever inherits the id.

## Notes
- No retroactive repair. A character already double-subtracted keeps the wrong bonus stats,
  because the engine cannot tell a missing armour bonus from a low base stat by looking.
  The admin console can read and set a seat's base SPECIAL if a world needs correcting.
- Gate green: server-loop 27/0, legacy 14/0.
