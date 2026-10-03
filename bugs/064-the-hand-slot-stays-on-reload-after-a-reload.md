# 064: The hand slot stays on "reload" after a reload

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client and a real mouse;
not yet confirmed in live play.
**Files**: `src/main.cc` (the viewer loop's weapon-slot click),
`tools/client_screen_proof.py` (`reloads`).

## Symptom
GitHub issue 33: "Reloading in active hand bar doesn't change to attack type to shooting.
In original Fallout 2, it automatically switches to single shot after reload, now player
need to manually rightclick on the active hand bar."

## Root cause
Vanilla's hand-bar reload (`_intface_item_reload`) ends with `interfaceCycleItemAction()`,
which moves the slot on from RELOAD and lands on the weapon's primary attack. The viewer
does not run that function: the reload is the server's, so the click sends `reload` and
returns. The slot stayed on RELOAD, and the next click reloaded a full weapon.

## Fix
After sending the reload the viewer cycles the slot's action as vanilla does. In a fight
only when it is the player's turn and the action points are there, which is when vanilla
reloads at all; a reload the server is going to refuse leaves the slot alone.

## Verification
`python -u tools/client_screen_proof.py reloads ...`: the real client holds an empty 10mm
pistol, presses N twice (single shot, aimed shot, reload) and clicks the slot twice.

| build | the two clicks |
|---|---|
| v1.4.1 (`--expect-defect`, 3/3) | reload, reload |
| fixed (3/3) | reload, then the shot's click (out of a fight it asks to start one) |
