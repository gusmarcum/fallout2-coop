# 016 — The Navarro minefield leaves the player unable to use the mouse or open a menu

**Status**: FIXED (2026-09-08).
**Files**: `src/server_loop.cc` / `.h` (`serverUiLockSet`, `serverUiLockActive`),
`src/server_stubs.cc` (`gameUiDisable` / `gameUiEnable` / `gameUiIsDisabled`),
`src/interpreter_extra.cc` (`op_game_ui_disable` / `op_game_ui_enable`),
`src/map.cc` (release on map load), `src/client_net.cc` / `.h` + `src/main.cc` (watchdog)

## Symptom
Walking over the mines outside Navarro instead of following the trail. The mine explodes
and from that moment the player cannot open any menu, cannot pan the screen, and the mouse
cursor does not update; movement only happens if they spam left and right click. It never
recovers. Restarting the client clears it. Other explosions, grenades and rockets included,
do not do this. The server is healthy throughout and keeps accepting the player's moves.

## Root cause
`CIMine.int` (scripts.lst 1300, "Mines in Navarro") calls `game_ui_disable` in its
`spatial_p_proc` and **never calls `game_ui_enable` anywhere in the script**.

That is not a bug in vanilla. `gGameUiDisabled` is ONE boolean on ONE machine, and both the
scripts and the engine flip it: `actionExplode` opens with `gameUiDisable(1)` and closes
with `gameUiEnable()`, so the explosion the mine sets off is what hands the controls back.
The script never needed its own enable.

Co-op split that boolean across the wire and only reconnected one half. `op_game_ui_disable`
was routed through the presenter to the viewer, but `gameUiDisable` / `gameUiEnable`
themselves were **no-op stubs** on the dedicated server (server_stubs.cc), on the reasoning
that a headless server has no UI to gate. True of the server, false of the players watching
it: the engine's release never became a wire event, so the viewer was told to lock and never
told to unlock.

A sweep of all 1443 shipped scripts found **six** that disable the UI with no enable of
their own, all of which would leak the same way:

```
CIMINE.INT     Mines in Navarro
IIMINE.INT     Mines in Raiders Cave
IIPIT.INT      pit trap
MCDAVIN.INT    Modoc
MCMIRIA.INT    Modoc  (twice)
NIWILGRV.INT   New Reno
```

Another 66 pair them properly, which is why this looked like it was "only these mines".

## Fix
`serverUiLockSet` in server_loop.cc is now the single owner of vanilla's flag, and both the
script opcodes and the engine's `gameUiDisable`/`gameUiEnable` go through it. It is
edge-triggered exactly like vanilla's own `if (!gGameUiDisabled)` guards, so `actionExplode`
taking the lock on top of a script's lock stays silent and its closing `gameUiEnable()` is
the edge that frees the player.

The addressee is **remembered from the lock, not re-derived at release time**. The mine's
explosion is queued by the script and drained a beat later by the server's own tick, outside
the walking player's scope, so resolving "who is acting now" when the release comes would
credit the host and leave whoever actually stepped on the mine locked.

A lock is also released if it is still held when a map loads: the script that would have
released it is gone with the old map's script list, so at that point it can only be a leak.

Belt and braces, `main.cc` bounds the lock on the client at `kViewerUiLockMaxMs` (15 s), the
same bargain the screen-fade watchdog already makes at 6 s and for the same reason: fading
back or releasing early costs a beat, staying locked costs the session. It is longer than the
fade's bound because a real cutscene legitimately holds the controls for a while. With the
server fix in place this should never fire; it is there so that no script, present or future,
can brick a client.

## Verification
Sandbox on a copy of the live Navarro save, explosion triggered through the admin `explode`
probe, `F2_TRACE_WORLD=1`:

- Before: no input-lock traffic at all. The engine's release reached nobody.
- After: `input lock TAKEN for netId=1` followed by `input lock RELEASED for netId=1`,
  matched pairs, addressed to the player.

`F2_TRACE_WORLD` now prints both edges, so a future leak is one grep away.
