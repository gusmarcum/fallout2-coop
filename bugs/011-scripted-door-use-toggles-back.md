# 011 — Scripted door opens and closes in the same beat (San Francisco Brotherhood door)

**Status**: FIXED (2026-09-05).
**Files**: `src/proto_instance.cc` (`_obj_use_door`).

## Symptom
The Brotherhood of Steel door in San Francisco (SFCHINA tile 24760, script `FSBroDor.int`)
"closes and opens repeatedly and won't let me in". With the access flag set (global 361 bit
0x800000), every use logs the open and the close together:

```
[world] door netId=2359 tile=24760 elev=0 -> OPEN
[world] door netId=2359 tile=24760 elev=0 -> CLOSED
f2_server: interact FIRE use netId=2359 rc=0 actorTile=24960 targetTile=24760
```

The viewer plays the open slide and the close slide back to back, and the door is shut again
before anyone can walk through. Without the access flag the script prints "You see a door with
no visible handle or lock." and does nothing, which is vanilla.

## Root cause
`FSBroDor.use_p_proc` (and many door scripts like it) answers a use with
`reg_anim_begin / obj_open(self) / reg_anim_end`, arms a five-second auto-close, and does NOT
call `script_overrides`. `_obj_use_door` therefore continues into the engine's default toggle
after the script returns.

In vanilla the script's `obj_open` is a deferred animation: the default toggle still sees the
door closed (`door->frame == 0`), registers an open of its own, and the two opens merge into
one open door. On the headless server the instant scheduler completes the script's open
inside the script call, so the toggle read the NEW frame, took the door for open, and closed
it again in the same beat.

## Fix
`_obj_use_door` remembers whether the door was open before the script ran. On the server,
if the script has flipped the door itself, the default toggle is skipped: the script's outcome
is exactly what vanilla's merged animations produce. Vanilla is untouched (with deferred
animations the frame cannot have changed at that point).

The door then behaves like vanilla: it opens on use and its script closes and locks it five
seconds later, so walk in right away.

## Verification
`python D:\Games\f2dev-sandbox.py bos <f2_server.exe>` boots a fresh SFCHINA.MAP, grants the
access bit over the admin channel, uses the door, and reports the time from OPEN to CLOSED:
same beat before the fix, about five seconds after it.
