# 069: The hit point counter runs ahead of the fight

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client in both seats; not
yet confirmed in live play.
**Files**: `src/object_delta.cc`, `src/object_delta.h` (`objectDeltaFlushHitPoints`),
`src/combat.cc` (`_damage_object`), `src/client_net.cc` (`kDudeHp`, `applyDudeHp`,
`dudeHpWaitsForPresentation`), `tools/client_screen_proof.py` (`hpcount`, `hpcount2`).

## Symptom
GitHub issue 44, "HP counter predicts future": "after every player turn when for example
Player2 is attacked by several dogs that player could predict for how many points he's
going to be attacked before that attack was animated and log produced."

## Root cause
Two halves, one on each side of the wire.

The server resolves the enemy side's turns within a beat or two of the player's end of
turn, and they then take many seconds to play on a client. Hit points have no event of
their own: they ride the object delta scan, which runs once at the END of a beat. A player
hit five times in a beat was sent five attack sequences and then ONE total.

The client adopted that total as it was decoded (`_dudeHpAuth = hp`) and the counter rolls
toward it every frame. The attack sequences meanwhile wait their turn on the presentation
queue. So the counter counted down to the end of the enemy phase while the first swing was
still in the air.

## Fix
Server: where a blow lands on a player (`_damage_object`), the player's new total goes on
the wire at once (`objectDeltaFlushHitPoints`: one hit point delta, the scan's shadow
advanced with it, so the beat-end scan does not send it twice). The stream now reads
attack, its two message lines, the total after it, next attack. Dedicated server only: the
probe streams and the goldens are unchanged. An older client applies the extra deltas as
it always did.

Client: a total for the viewer's own body that arrives while a fight is still being shown
(something queued or playing, and the fight on or its end still in the queue) is parked on
the presentation queue as `kDudeHp` and adopted when the queue reaches it, which is right
behind the attack that caused it and that attack's "You were hit" line. With nothing owed
(a stimpak, a rest, a trap out of combat) it is adopted at once, as before. A total is
never lost: one squeezed out of a full queue is applied, the queue's two clear paths are
both world reloads that reseed the counter from the snapshot, and a total parked for a
body the screen has since been moved off is dropped.

Against a v1.4.1 server the new client still waits, but for the one total per beat: the
counter moves after that beat's attacks, not blow by blow.

## Verification
`python -u tools/client_screen_proof.py hpcount ...`: the real client, alone, has two
raiders beside it, ends its turn, and the screen is read off screenshots taken every 8
frames. The counter must not move before the message log shows the first line of the
enemy phase.

| build | counter first moved | log first moved |
|---|---|---|
| v1.4.1 (`--expect-defect`, 3/3) | 0.2 s after the end of turn | 2.6 s after |
| fixed (4/4) | 3.4 s after, same screenshot as the log | 3.4 s after |

On the fixed build the client's own trace also shows 10 totals parked and all 10 adopted
directly behind a "You were hit" line.

`hpcount2` is the second player's seat, where the report came from: the real client joins
a session a wire client hosts, two raiders are set on the host, and while the first one's
attacks are still being shown the operator lands three blows on the real client's own
character in one beat. The client's log is timestamped as it is written, so when the
blow's sequence arrived and when its turn came to be played are both known.

| build | the first blow arrived | it was played | the counter first moved |
|---|---|---|---|
| v1.4.1 (`--expect-defect`, 2/2) | 0.1 s after the command | 4.4 s | 0.1 s |
| fixed (3/3) | 0.0 s | 3.3 s | 3.3 s |

Three totals parked, three adopted, each right behind its own "You were hit" line.
