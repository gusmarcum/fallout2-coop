# 077: An opened door stays a wall in the client's copy of the map

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client in both seats;
not yet confirmed in live play.
**Files**: `src/client_present.cc` (`PresEntry::owed`, `PresEntry::played`,
`reserveEntry`, `clientCombatAnimReserve`, `clientCombatAnimNotePlayed`,
`advanceReplays`, `settleDoorFrame`, `resolveHeld`), `src/client_present.h`,
`src/client_net.cc` (`reserveSeqRef`, `onPresSeq`, `presentationPump`, `enqueue`,
`PresEvent::seqReserved`), `tools/client_screen_proof.py` (`doorsync`, `doorsync2`,
`syncwalk`, `syncwalk2`, `auditwatch`).

## Symptom
Nobody reported it. The mirror audit found it while every v1.4.2 fix was being checked
with the real client: in the Den, doors that NPCs had walked through were open on the
server and closed in the client's copy of the map. v1.4.1 does the same.

What a player gets from it: a door that has slid open on screen still blocks in the
client's own copy, so the movement cursor shows the red X on every tile behind it (the
cursor asks the client's copy for a path, `game_mouse.cc`), and the flags that let light
and shots through are still those of a closed door. The walk itself is the server's and
works. And a door used twice in quick succession (a double click, or a player closing
the door an NPC has just opened) is left standing open on screen and shut on the server,
or the other way round, until the map is loaded again.

## Root cause
Two things, both in how the client plays a recorded sequence (`EVENT_PRES_SEQ`).

**The hold that nothing let go of.** A door's slide is a recorded sequence, and its
state (the flags: does it block, does it stop light and shots) follows in the same beat
as an object delta. The client reserves every object a sequence names when the sequence
arrives, so that the state waits for the animation, and it holds the delta's art, flags
and facing for a reserved object. An attack's participants are made Active when the
attack plays and their held state lands when the animation ends. An object named by a
recorded sequence was never made Active (only the sequence's actor, and only in a
fight), so after the slide had played the door was still reserved, and the only way out
was the stall backstop: five seconds in which nothing on the whole map moved or was
shown. On a quiet map that is five seconds of a wall where the open door is. In a town
it is as long as anybody keeps walking: in the Den the probe saw one door wrong for the
whole 36 seconds it watched, and three wrong at once.

**The slide the engine refused.** The server does not send a door's frame after a slide
(the slide is the frame change; a frame beside it would snap the door past its own
animation). Two slides of one door that reach the client close together are both handed
to the engine at once, the engine refuses a second animation on an object that is still
playing one (`_check_registry`), and nothing else ever moves that door's frame.

## Fix
Each reserve now counts one replay as owed to the object (an attack it takes part in,
or a recorded sequence that names it, counted once per sequence), and the count goes
down when that replay plays, or is dropped. A reserved object whose last owed replay has
played, and which is no longer animating, gets its held state then
(`advanceReplays`). For a door that is half a second after the slide began: the flags
land as the slide ends.

And when an object leaves its reserve, a door is put in the frame its flags call for
(`settleDoorFrame`: open is the last frame, closed is frame 0, as `_check_door_state`
has it on the server), with the art offsets the slide would have applied. That covers a
refused slide, a dropped sequence and a cap alike.

Both are in the client only. The same count is what bugs/078 uses.

## Verification
`python -u tools/client_screen_proof.py doorsync ...` (the real client in the host's
seat, its own actor at the door) and `doorsync2` (the real client joins a session a wire
client hosts and watches that player's actor): in the Den the host uses the nearest door,
uses it again, then uses it twice at once. After each, the server's audit is compared
with the client's copy of that door.

| | v1.4.1 (`--expect-defect`, 6/6 in each seat) | fixed (7/7 in each seat) |
|---|---|---|
| three seconds after the door was used | flags: server 0xA0000010 (open), client 0 | the same on both |
| six seconds after | still differs | the same |
| used twice at once, three seconds on | frame: server 0 (closed), client 6 (open) | the same on both (the client's trace: `[door-settle] ... say closed: frame 6 -> 0`) |

On the fixed build the client's own trace has the flags landing 530 to 580 ms after the
door was reserved, which is the length of the slide.

`syncwalk` and `syncwalk2` (12/12 each) audit the whole map at nine points, the Den's
NPC-opened doors included.
