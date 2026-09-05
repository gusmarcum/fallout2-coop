# 010 — Sliding doors drawn above (or below) their doorway; a door "floats above itself"

**Status**: FIXED (2026-09-05).
**Files**: `src/object.cc` (`objectSetFrameWithArtOffsets`, `objectArtOffsetsForFrame`),
`src/proto_instance.cc` (`_check_door_state`, `doorArtOffsetsNormalizeAll`), `src/map.cc`
(normalization at load), `src/elevator_data.cc` (`elevatorCloseDoors`), `src/client_net.cc`
(`OBJECT_DELTA_FRAME` for doors).

## Symptom
A door in Navarro opens and "stays up", drawn well above its doorway, as if floating above
itself. Seen after a session of elevator rides, door use and quickloads.

## Root cause
The vault-style doors (`vdoorf.frm`, `vdoors.frm`, Navarro's interior doors; also the
elevator doors `velev*.frm`) do not slide inside their frames: each frame image gets shorter
and the FRM stores a per-frame **offset** (vdoorf: 0,-3,-7,-9,-10,-12,-11,-9 = 61 px up over
the eight frames). The engine keeps the running sum in `obj->x/y`, adding a frame's offset when
the animation enters it and subtracting it when the reversed animation leaves it. Anything that
sets a door's frame WITHOUT walking the offsets draws the sprite where the previous frame's
offsets left it. Three such paths existed:

1. **The headless server's own door closes.** `_check_door_state` is vanilla's
   animation-completion callback and re-syncs the frame from the open flag. In vanilla the
   animation has already reached the target frame, so the callback returns early. On the
   dedicated server no animation runs and the callback is what actually moves the frame — and
   its closing loop subtracted the offsets of frames N-1..0 where the animation subtracts N..1.
   On a vault door that is 9 px short per open/close cycle. The drift is written into the map
   `.SAV`, ships to every viewer in the join blob, and survives every quickload; a door cycled
   seven times sits a full door height too high.
2. **The elevator ride** closes the elevator doors with a bare `objectSetFrame(doors, 0)`
   (vanilla does the same), leaving the open frame's 26,-14 offset on the closed door. The
   viewer mirrors that frame change from `OBJECT_DELTA_FRAME` with another bare
   `objectSetFrame`, so a door the viewer had animated open (61 px up) came down to frame 0
   while staying 61 px up: the "door floating above itself". Opening it again animated from
   there, another 61 px higher.
3. Any other scripted frame change delivered to the viewer as `OBJECT_DELTA_FRAME`.

Every shipped map stores exactly the animation's cumulative offsets for doors saved open and
0,0 for closed ones (all 341 door records in the 155 maps checked), so a door's frame alone
determines where its sprite belongs.

## Fix
- `objectSetFrameWithArtOffsets(obj, frame, rect)` sets the frame and moves the sprite by the
  offsets the animation would have applied stepping from the current frame to the new one, in
  either direction. `objectArtOffsetsForFrame` gives the resting offsets for a frame.
- `_check_door_state` uses it in both branches (the open branch is unchanged in effect; the
  close branch is now exact). Vanilla single-player still returns early from both.
- `elevatorCloseDoors` uses it (also fixes the vanilla glitch).
- The viewer applies `OBJECT_DELTA_FRAME` to doors with it; other scenery keeps vanilla's bare
  frame set (`op_anim(1010)` sets frames without offsets in vanilla too).
- At every map load on the server, `doorArtOffsetsNormalizeAll` puts every door back on the
  offsets its frame implies, so worlds saved by earlier servers self-heal; shipped maps are
  already consistent and nothing moves.
- `F2_TRACE_WORLD` now prints `[world] door netId=.. frame=.. offsets=x,y` after each server
  door state change and one line per door the load normalization moved.

## Verification
`python D:\Games\f2dev-sandbox.py door <f2_server.exe>` against a copy of the Navarro
quicksave: the load prints the normalized doors, and an open/close cycle ends at
`frame=0 offsets=0,0`.
