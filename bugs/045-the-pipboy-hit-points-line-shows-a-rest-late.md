# 045: The pipboy's Hit Points line shows a rest's heal one rest late

**Status**: FIXED (2026-09-30), proven on a sandbox with the real client; not yet confirmed
in live play.
**Files**: `src/pipboy.cc` (the main loop), `tools/client_screen_proof.py` (`clock`).

## Symptom
GitHub issue 10, the follow-up to v1.4.0: "HP counter is only get refreshed if I do a
second rest command (any of it will suffice)."

## Root cause
The alarm clock tab prints "Hit Points cur/max" above its rest options
(`pipboyDrawHitPoints`). Vanilla draws it when it renders the options
(`pipboyWindowRenderRestOptions`, which runs when the tab opens and on every click) and
again every frame of its own rest loop, which a viewer never runs: the server rests the
world and the heal arrives on the wire afterwards. bugs/038 gave the date and clock at the
top a watcher in the pipboy's main loop; the hit points line got none. So the number stood
until the next click redrew the options, and the heal from one rest showed up on the next.

## Fix
The main loop redraws the line whenever the character's hit points change while the alarm
clock tab is up (the same shape as the clock watcher). The pipboy also logs when it is up,
which tab it closed on, and each redraw of that line, like the inventory and the character
sheet already do.

## Verification
`python -u tools/client_screen_proof.py clock ...`, extended: the second player is put at 1
hit point, opens the pipboy with P and clicks its alarm clock (the replay's mouse lines), and
keeps it open; the operator rests slot 1 six hours (one heal step). The clock strip and the
hit points line are read off the screenshots, as before.

| client | the clock strip after the rest | the Hit Points line after the rest |
|---|---|---|
| v1.4.0 (`--expect-defect`) | redrawn (bugs/038) | still "1/44" |
| fixed (8/8) | redrawn: 0824 to 1424 | redrawn: "Hit Points 1/44" to "4/44", logged "alarm clock hit points line redrawn: 4/44" |
