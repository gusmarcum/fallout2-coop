# 083: A conversation a floor trigger opens can be answered by nobody

**Status**: FIXED (2026-10-13), proven on a sandbox with wire players; not yet confirmed
in live play.
**Files**: `src/script_request_handler_server.cc` (`dialogDriveBegin`),
`src/game_dialog.cc` (`_gdialogInitFromScript`), `src/client_dialog.cc`
(`clientModalWindowsSync`), `tools/issue_wire_proof.py` (`cartracks`).

## Symptom
GitHub issue 53: "Go back to car in Virgin Street after first parking there. Car is
stolen by T-Ray and player may enter the parking spot to open dialog and follow the
tracks to Chop Shop or leave it. ... Whichever dialog option is selected the screen goes
black and nothing else happens, it is locked and only Alt + F4 seem to work."

## Root cause
The parking spot is a floor trigger (`ntCar2`). When a player with good eyes steps on
it, its script opens a conversation by itself, with no talk involved:
`start_gdialog`, a reply and two lines ("follow the tracks", "leave it").

A conversation page is sent with one player named as the one being asked: `gDude` at
that moment, which under a floor trigger is whoever stepped on it. Who may ANSWER is a
separate record on the server, the conversation's driver, and it is filled from a note
that only the `talk` and `use` verbs leave. A script that opens a conversation by itself
leaves none. The driver was then "the host" by fallback, or whoever had last used
something (the note was never cleared when a use opened no conversation).

So the player who was shown the two lines sent the answer and the server dropped it
("host-only screen"); the host's own game showed the page as somebody else's and could
not answer either; and the server sat in the conversation's wait, which reads players'
lines and runs nothing else. The whole world stood still for everyone. A player who
restarted the game then waited on the join screen, because a server parked there takes
no new players in: that is the black screen.

A second way in: after the first trade of a session `_dialogue_state` stays 1 on the
server (the trade ends on it and nothing clears it there), and `_gdialogInitFromScript`
returned on that flag before it reached the server's part, so such a conversation was
not given a driver at all.

The same shape is in 6 scripts that open a conversation from a floor trigger (this one,
Vault City's raider spot, the Enclave's vertibird, three of the Restoration Project's)
and about 40 that do it from a use or a skill.

## Fix
- `dialogDriveBegin` names the driver itself: the slot of `gDude`, the same actor the
  page is addressed to. Talk and `dialogue_system_enter` are untouched (they already hold
  a driver when the script's `start_gdialog` runs). A conversation a script opens outside
  any player's scope is the host's, explicitly, and is abandoned when the host is not
  there, where it used to wait for good.
- `_gdialogInitFromScript` does the server's part before the two returns that are about
  windows.
- On a client, a conversation whose speaker never arrives (a floor trigger's hidden
  helper object can be made only when the conversation starts, after the world was sent)
  is shown around the player's own character after a second, where the window used to
  wait for the speaker for ever.

## Proof
`python -u tools/issue_wire_proof.py cartracks <f2_server.exe> <sandbox> 9400 9401`

Two wire players; the car is marked stolen and the SECOND player walks onto the parking
spot. The page must name that player and carry two lines. Answering "leave it" must end
the conversation and let the server's clock run on; in a fresh world, "follow the
tracks" must take the party to another map.
