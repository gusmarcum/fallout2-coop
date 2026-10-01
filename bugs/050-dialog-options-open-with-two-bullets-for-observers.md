# 050: Dialog options open with two bullets on an observer's screen

**Status**: FIXED (2026-09-30), proven on a sandbox with the real client; not yet confirmed in
live play.
**Files**: `src/game_dialog.{h,cc}` (`gameDialogAddBakedOption`), `src/client_dialog.cc`,
`tools/client_screen_proof.py` (`dialogdots`).

## Symptom
GitHub issue 23: "Dialog options are separated by visual dots for every option. Observers see
double dots one beside other."

## Root cause
The server resolves every option's display text before it ships a dialog node, through the
same `gameDialogGetOptionText` its renderer uses, prefix included (the SFALL number, or the
bullet). A viewer added each wire option through `gameDialogAddTextOption`, which bakes the
prefix again for a text option: "\x95 \x95 What were you doing...".

## Fix
`gameDialogAddBakedOption` stores an option's text verbatim; the viewer adds wire options
through it, and logs each one (`client_dialog: option N "..."`).

## Verification
`python -u tools/client_screen_proof.py dialogdots ...`: the host opens a conversation with
Mynoc through the debug port (`dtalk 10`); the second player's real client watches the node.
Fixed (2/2): 3 options displayed, every one opening with a single bullet, "\x95 What were you
doing - trying to get me killed in the temple...". The older client has no such log line; its
double prefix is the code above.
