# 022: A trade started from a dialogue line came back to a page with no options

**Status**: FIXED (2026-09-10).
**Files**: `src/game_dialog.cc` (`serverDialogRunPendingBarter`, `serverDialogPageIsBlankPlaceholder`,
the headless block of `_gdProcess`).

## Symptom
Klamath, the Duntons. After a trade you are on "Well, it's a pleasure doing business with
you. Need anything else?" Pick "Hmm...I think I forgot to barter for something." The trade
screen opens; leave it with Talk, and the dialogue window comes back with no reply and no
options. Nothing on it can be clicked. The only way out is Escape (the driver-only bail,
which sends `dend`). The greeting's own barter line does the same. The Barter button never
does. Every other player sees the same empty page. Reported from live play on 2026-09-10.

## Root cause
The shipped Dunton script requests the trade (`gdialog_mod_barter`), then shows a message
page with an empty message (`gsay_message`), and only registers the follow-up page (Node013,
message 240 plus four options) after that page has been dismissed. A `gsay_message` page is
the reply plus one engine "[Done]" line (list -2, message -2, no proc), run at once as a
nested `_gdProcess`. In the original game the ticker turns the pending trade request into
the trade window on the next frame, before the player can see that page; after the trade
the empty page shows with only [Done], the click ends it, and the script carries on to
Node013. So the original game does show an empty [Done] page after this trade.

The headless loop only looked at a pending trade after it had consumed an intent. So the
order flipped: the placeholder page was sent first and the server waited; the driver's click
on the blank line (or the Barter button) consumed the placeholder and started the trade; and
after the trade the loop took its "continue, not break" path and re-sent the current page,
whose only option the click had already cleared. Zero options, no reply, and a wait for a
`dsay` that could never come.

The Restoration Project's copy of this script does not end the page inside the barter
routine, which is why its source did not show the problem. The probe below runs the Steam
data's compiled script.

The Barter button was never affected because it does not go through `_gdProcessChoice`, so
the node it returns to is intact. Tubby's barter routine registers its reply and options
before the page ends, so it survived too.

## Fix
- A trade request that is already pending when a page comes up (mode 2 at the top of the
  headless iteration) is served before the page is emitted, the way the ticker serves it.
- An engine placeholder page is ended by the server when it has nothing to read: exactly
  one option, the -1/-1 (`gsay_end` with nothing registered) or -2/-2 (`gsay_message`
  "[Done]") engine line with no proc, and empty reply text. This is the one deliberate
  departure from the original game, which shows the empty [Done] page here; the click on
  it is the page's whole content, so the server performs it. A placeholder page that
  carries a reply is still shown.
- After a trade raised by an intent, the loop keeps `continue` when the choice registered
  a page of its own (choice result 0: the Barter button, Tubby), and ends the page like
  vanilla's keyboard path when the choice registered nothing (result -1).
- A page with no options is never sent; the server ends it and logs why.

## Verification
Headless probe against a copy of the Steam data, `kladwtwn.map`, script index 86 is the
Duntons:

```
F2_FAKE_CLOCK=1 F2_HEADLESS_PROBE=1 F2_SERVER_LOOP=1 F2_DIALOG_TRACE=1 \
F2_PROBE_MAP=kladwtwn.map F2_PROBE_SEED=42 F2_PROBE_TICKS=400 \
F2_PROBE_ACTIONS="280:dsay:0,282:bdone:0,284:dsay:0,286:bdone:0,300:dtalk:86" ./fallout2-ce.exe
```

Before: greeting (5 options), then a page with 1 blank option and no reply, then a page with
0 options and no reply, and Node013 only after the nested page unwound.
After: greeting (5 options), `pending trade served before the page (reenter=2)`, the empty
[Done] page ended by the server (a `[dialog] blank placeholder page` line on a live server),
then Node013 (4 options) straight away, and again after the second trade. No page with zero
options is ever sent.
`denbus1_barter` (Tubby) and `denbus1_dialog` produce dumps byte-identical to the untouched
v1.2.0 client in the same environment.
