# 012 — Power armor does not raise a second player's Strength

**Status**: FIXED (2026-09-05).
**Files**: `src/inventory.cc` (`_adjust_ac`).

## Symptom
The friend (registry slot 1) wears Brotherhood T-51b power armor and his Strength stays at
its base value. The armor's class and damage resistances apply; the +3 Strength and the
radiation resistance the suit is supposed to grant do not. The host's own power armor works.

## Root cause
An armor's built-in perk (`PERK_POWERED_ARMOR` on the T-51b, the advanced-armor perks on the
later suits) is applied by `_adjust_ac`, which the server's `invwield` handler calls after
`_inven_wield`. Vanilla guards that step with `objectIsPartyMember(critter)`: only party
members get armor perks, and the dude is party member zero, so in single-player the guard is
always true for the player.

A second player's body is not in the party list. It is a registered player actor, not a
recruited companion, so `objectIsPartyMember` is false for it and `_adjust_ac` applied the
class and resistances (unconditional) but skipped the perk. The same guard on the unequip
side meant nothing was left behind either; the bonus simply never existed for slot 1 and up.

## Fix
`_adjust_ac` applies the perk when the critter is a party member **or** a player actor
(`playerActorIs`). With an empty registry `playerActorIs(critter)` is `critter == gDude`,
which for the dude is already covered by the party test, so single-player and both golden
suites evaluate the same condition value as before. The dedicated server logs
`armor perk <old> -> <new> for slot <n> (Strength now <x>)` on every player equip/unequip.

## Notes
- The perk's effect lives in the actor's bonus stats, which ride the per-actor sheet row in
  the save and on the wire, so it persists across saves and rebaselines exactly like the
  host's. A character who put the armor on under the old build has to take it off and put
  it back on once; there is no retroactive repair, deliberately (the engine cannot tell an
  unapplied perk from an applied one by looking at the stats).
- Proof: `tools/armor_perk_proof.py` runs a sandbox server with two fake clients, hands the
  host a T-51b, drops it, has the second player pick it up and wear it, and checks the
  Strength line for slot 1 before and after.
