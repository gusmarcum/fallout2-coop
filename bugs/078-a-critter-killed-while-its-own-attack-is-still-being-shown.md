# 078: A critter killed while its own attack is still being shown is left with the wrong corpse

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client in both seats;
not yet confirmed in live play.
**Files**: `src/client_present.cc` (`advanceReplays`, the Active branch; `PresEntry::owed`,
`clientCombatAnimNotePlayed`, `clientCombatAnimPlay`), `src/client_net.cc`
(`attackNotePlayed`, `playPending`, `enqueue`), `tools/client_screen_proof.py`
(`corpsesync`, `corpsesync2`, `syncwalk`, `syncwalk2`).

## Symptom
Found by the mirror audit, in a fight: a raider that had just attacked was killed, and
in the client's copy its corpse had the art of the death animation's last frame where
the server holds the corpse art, and no flat flag where the server has one. On screen
that is a body with no blood pool under it, drawn in the order of a standing object.
v1.4.1 does the same.

This is very likely a second cause of GitHub issue 39 ("Sometimes killed enemy don't
bleed at all. It is rare, but can be spotted sometimes"); bugs/076 is the first. The
reporter has not been asked.

## Root cause
The server works a turn out at once; the client shows it one animation at a time and is
seconds behind in a busy fight. So that a critter's final state (the corpse art, the
flat flag, the facing) does not appear before the animation that leads to it, the client
holds those three fields of an object delta for an object that has a replay reserved or
playing, and lands them when the replay ends.

It kept ONE bucket per object and emptied it at the end of whichever of the object's
replays finished first. A raider that attacks three times has three replays queued on
the client. Killed one second later, its corpse state arrived while the first or second
was playing and landed when that one ended. The replays still queued then played over
it: the raider stood up to attack again, and the death at the end left it in the fall's
last frame, because the engine's own `_show_death` does not give a corpse its art (the
branch that would is dead code in the original: `anim < 48 && anim > 63`) and TOGGLES
the flat flag, which the early landing had already set. The bloody single frame and the
flag are the server's, and they had come and gone.

It takes a critter with an action of its own still being shown when the kill arrives:
an enemy killed right after it attacked or moved, by a second attacker, a companion, an
explosion or a script.

## Fix
What lands at the end of a replay still lands there, so nothing between two replays
looks different from before. But while more replays are owed to the object (the count
bugs/077 introduced: one per attack it takes part in and per recorded sequence that
names it, down by one as each plays), the bucket is kept, and it lands once more when
the last of them is over. The final state is then the server's, whatever played over it.

Client only.

## Verification
`python -u tools/client_screen_proof.py corpsesync ...` (the real client in the host's
seat) and `corpsesync2` (in a joining player's): a raider is put beside the host and set
on it, and one second later the operator kills it. Nobody ends a turn, so the fight
waits on a player and the client shows all it has. Ten seconds on, the audit is
compared with the client's copy of the raider.

| | v1.4.1 (`--expect-defect`, 4/4 in each seat) | fixed (4/4 in each seat) |
|---|---|---|
| attacks of the raider's the client had been sent when the kill arrived | 3, one of them begun | 3, one of them begun |
| the corpse's art | server 0x13F002C (the corpse), client 0x1119002C (the death's last frame) | the same on both |
| the corpse's flags | server 0x20000018, client 0x20000010 (not flat) | the same on both |

The fixed client's trace shows the bucket kept through the three replays still owed and
landing after the last (`[replay-more] ... 3 more replays are owed`, then
`[seq-settle]`).

`syncwalk` and `syncwalk2` (12/12 each) end with a raider killed in a fight and the whole
map audited on a held turn.
