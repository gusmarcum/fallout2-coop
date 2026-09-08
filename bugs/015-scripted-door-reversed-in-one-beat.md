# 015 — A script that opens a door and then closes it leaves it shut (Enclave puzzle room)

**Status**: FIXED (2026-09-08), confirmed in live play.
**Files**: `src/proto_instance.cc` (`objectOpen`, `objectClose`, `doorScriptMoveClaim`)

## Symptom
In the Enclave trap room (ENCTRP, the nine-door puzzle guarding the Advanced Power Armor
Mk II), the terminal at tile 17891 never opens its doors. The player's screen shows the two
doors standing open; the server keeps blocking those hexes, so walking through fails
silently and the door "is open but acts like it's closed". Pressing the terminal again
changes nothing. The server log shows both doors moving twice inside one press:

```
f2_server: interact FIRE use netId=485 rc=0 actorTile=18091 targetTile=17891
[world] door netId=734 tile=19496 elev=0 -> OPEN
[world] door netId=905 tile=20510 elev=0 -> OPEN
[world] door netId=734 tile=19496 elev=0 -> CLOSED
[world] door netId=905 tile=20510 elev=0 -> CLOSED
```

## Root cause
`QIPzlTrm.int` (the puzzle terminal) dispatches on its own tile, one branch per terminal:

```
if (self.tile == 17891) call Term3
```

and `Term3` opens tiles 19496, 20510, 21516 and then closes 19496, 20490, 20510, 20520.
Two of the doors it opens are closed again in the same branch.

That is harmless in vanilla, and the reason is the deferred slide. `obj_open` acts only when
`obj->frame == 0` and `obj_close` only when `obj->frame != 0`, and in vanilla the slide is a
registered animation, so the frame holds its pre-run value for the whole script run.
Whichever of the two a branch calls FIRST is therefore the one that takes effect, and the
later reversal fails its own guard. Vanilla leaves a closed door open and an open door
closed, so the terminal toggles.

The headless server applies the slide immediately (`objectOpenClose`'s `serverLoopActive`
branch), so the frame had already moved when the reversal ran, its guard passed, and it
undid the first call. Both doors start closed in a fresh trap room, so that terminal could
never open anything.

The visual half: the viewer had begun the opening slide from the first `doorPresentSlide`
and never played the closing one on top of it, leaving an open door drawn over a hex the
server was still blocking with. Once the reversal is gone there is only one slide per press,
so the divergence has nothing to arise from. Two presentation sequences for one object
inside a single beat remain a latent client-side weakness; nothing in the shipped scripts
reaches it any more.

Same ancestor as [011](011-scripted-door-use-toggles-back.md) — the server doing at once
what vanilla defers — but a different site. 011 is the player's own door use
(`_obj_use_door`); this is the script opcodes. `objectOpen`/`objectClose` are called from
exactly one place, `interpreter_extra.cc`'s `obj_open`/`obj_close`, so the fix reaches
scripts only.

## Fix
`doorScriptMoveClaim`: on the server, the first scripted move of a given door within a beat
stands, and a reversal later in the same beat is ignored. The ledger is keyed by netId and
stamped with both the sim clock and the map-load generation, so it clears itself every beat
and cannot carry an entry across a map load or a quickload.

This reproduces vanilla in both directions, which matters: forcing the door open would have
been wrong. A door that starts OPEN makes `obj_open` the no-op and `obj_close` the call that
lands, so the terminal must still toggle it shut.

## Verification
`python tools/enclave_puzzle_probe.py <f2_server.exe>` presses that terminal nine times on a
sandbox server and reports, per press, which doors opened and which closed. Before: every
press reversed both doors and left them shut. After: zero reversals in nine presses, doors
toggling each time. Confirmed in live play the same day.
