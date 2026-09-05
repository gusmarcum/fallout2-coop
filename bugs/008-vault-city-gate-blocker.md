# 008 — Vault City inner gate: "You cannot get there" while the gate stands open

**Status**: FIXED (2026-09-05). No engine change survived; the cause was a regression
introduced by a talk-range change (reverted) plus stale objects baked into the saved map
(repaired with `tools/repair_vault_city_gate.py`).
**Files**: `src/server_control.cc` — `interactionRuleSatisfied` (talk rule); `tools/repair_vault_city_gate.py`

## Symptom
The gate guard on VCTYDWTN accepts the day pass and the gate opens (the door object at
tile 28717 unlocks and slides up, for the vanilla `game_ticks(10)` = ten seconds). Every
walk into the city and every "use" on the gate answers "You cannot get there", even from
the tile next to the gate. Other doors are unaffected. The server log shows the walks being
accepted and dropped at once: `interact ... DROPPED walk-ended-short (... beatsLeft=150)`.

## Root cause
Two vanilla scripts and one co-op timing difference.

1. `VIEntDor.int` (the gate) runs `map_enter_p_proc`: it creates a **Secret Blocking Hex**
   (pid 0x02000043, invisible scenery) on the gate's approach tile **28917**, closes and locks
   the gate, and arms `add_timer_event(self, 5, 2)`; `timed_event_p_proc` with fixed param 2
   destroys the blocker with `destroy_object(tile_contains_pid_obj(28917, 0, pid))`, one
   object per call. Tile 28917 is the only hex from which the gate tile 28717 can be entered
   (the wall row y=143 is solid except the gate, and 28917 is the gate's only southern
   neighbour), so a surviving blocker walls the city off no matter what the door does.
2. `VCGatGrd.int` (the guard): the "come in" node runs `remove_timer_event(gate)`, which
   removes **every** timer on the gate, then unlocks and opens it and arms the ten-second
   close. If that node runs before the five-tick cleanup has fired, the blocker is never
   destroyed. It then persists in the map's `.SAV`, the next entry adds another, and the
   cleanup keeps removing one while the rest stay (the live worlds carried two on the tile).
3. On the dedicated server the game clock counts beats, and the beat that loads a map (plus
   the map-change autosave on the next one) takes seconds of wall time, so a viewer has
   finished loading the map while the server clock is only a couple of ticks past
   `map_enter`. That alone is harmless as long as the conversation cannot start at once.
   Commit 56d2157 (2026-09-04, "Talk fires within vanilla's range: 9 hexes with line of
   sight") let it: both ways into Downtown put the player within nine hexes of the guard,
   so "come in" landed two ticks after the map load (live log: cleanup due at tick 410,
   removed at tick 407). That commit also reintroduced bug 001 (dialog firing before the
   approach walk). It is reverted (60e042f); the walk to adjacency restores the vanilla
   spacing between arrival and the first conversation.

## What was tried and reverted
- A scripted-close deferral (e6f6482) written on a misreading of the gate window as one
  second; it could re-arm the wrong script's timer or leave a door open but locked. Reverted.
- Engine-side dedupe/sweep of the blocking hex and a ten-tick post-load settle: both worked
  in the sandbox, but the owner asked for no engine changes that are not beyond doubt, and
  the vanilla mechanism works once the talk change is gone. Reverted (6b94a40, df2bc97).

## Repair of affected saves
`python tools/repair_vault_city_gate.py --world <game dir>` (or single `VCTYDWTN.SAV`
files; `--check` reports only). It parses the whole object list with the engine's record
layout, must consume the file to its last byte, deletes the stale records on 28917, fixes the
object counts, re-parses, and keeps a `.bak`. Flagging the leftovers non-blocking is NOT
enough: a leftover on the tile absorbs the script's next `destroy_object` and the fresh
blocker survives.

## How to recognise it again
Count objects with pid 0x02000043 on tile 28917 in `VCTYDWTN.SAV` (the pristine map has
none). More than the transient one written by a map-change autosave means the cleanup was
lost. In the server log, `queue drop (remove_events)` style traces are not in the tree any
more; the tell is the guard dialog `[dialog] ENTER` appearing within a few ticks of the
`map load VCTYDWTN` lines.
