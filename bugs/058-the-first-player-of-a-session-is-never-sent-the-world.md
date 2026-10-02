# 058: The first player of a session is never sent the world: a black screen after joining

**Status**: FIXED (2026-10-02), proven on a sandbox with the real client started the way
`join.cmd` starts it and nobody else on the server; not yet confirmed in live play.
**Files**: `src/server_loop.cc` (`serverTick`, the frozen beat; `serverServe`, the order of
drain and gate), `src/server_control.cc` (`serverControlResumeHeldTurn`),
`src/client_net.cc` (one log line), `tools/client_screen_proof.py` (`firstjoin`,
`heldturn`), `tools/issue_wire_proof.py` (`joinfreeze`), `tools/release_proofs.py`.

## Symptom
GitHub issue 32, on v1.4.1: "Tried old save from 1.4.0 and starting new campaign. Start
server using 1.4.1 patch. Expected: server goes up and game is playable. Actual: there is
only black screen." A second player confirmed it and found that the v1.4.0 server with the
v1.4.1 client still worked. Nobody could host v1.4.1.

## Root cause
Two things that were each right on their own.

1. The client asks for the world before it logs in. `join.cmd` sets `F2_PLAYER_CREATE=ask`,
   and the client then makes two connections: a throwaway one that asks `account <name>`
   (does this world know me, so is the creation screen needed), and the real one. The real
   one waits for the join snapshot under the black loading backdrop, and only when the
   world is loaded does it send `login` (`main.cc`, "awaiting join snapshot").
2. v1.4.1 kept the world frozen until somebody had logged in (bugs/052, issue 16), and a
   frozen beat returned before the tail of `serverTick`, which is where a joiner's snapshot
   (the rebaseline) is sent. That had been fine while "frozen" meant no client connected at
   all: there was nobody to send it to.

Together: the client waits for the world, the server waits for the login. The one snapshot
a server does send without a live beat is the boot's, to the first connection it ever
accepts, and with `join.cmd` that connection is the account probe, which throws it away.

Measured on the released v1.4.1 server, started as `start-server.cmd` starts it: the probe
connection is sent 117,137 bytes, the real connection 10 (the stream preamble) in eight
seconds, and no login ever arrives. Against the v1.4.0 server the same client is sent
119,181 bytes and logs in.

## Why the release proofs did not see it
Every proof that uses the real client logged a wire bot in first as the host, so the world
was already running when the client connected. The golden gate and the wire proofs use bots
that send `login` without waiting for anything. No test joined an empty server the way a
player does. `firstjoin` below does exactly that and nothing else, and
`tools/release_proofs.py` now runs it with every other proof before a release.

## Fix
A frozen beat still serves a joiner. When a connection was accepted, `serverTick` now does
on a frozen beat what the live tail does: the netId re-walk, the blob and the baseline, and
the fight's framing if one is frozen mid-turn. It reads the world as it stands and advances
nothing, so the fight is exactly where it was left, which is what issue 16 asked for.

Two follow-ups to bugs/052 came out of testing this with a fight on:

* The gate was asked before the drain. The beat that noticed the last player leave still
  ran live with their body unbound, the combat barrier ends the turn of an unbound body at
  once, and the whole enemy side took its turns in that one beat. A player who quit on
  their own turn (where a fight nearly always sits, waiting on the human) came back a round
  behind. `serverServe` now runs the drain first and asks the gate after it, so that beat
  is already frozen and the turn is still theirs.
* A turn that is held like that has to be said again after the login. The client decides
  "is it my turn" when `TURN_START` arrives, by comparing it with its own actor, and it
  only learns which actor is its own from the roster that follows its login. The turn that
  came with the snapshot arrived before that. For slot 0 the two happen to agree; any other
  player would have sat through their own turn on the wait cursor. On a login or claim that
  binds the body whose turn it is, the server now re-arms the idle budget (the clock stood
  still while they were away, so what was left could be seconds) and sends the turn again.

## Verification
`python -u tools/client_screen_proof.py firstjoin ...` starts the server with
`start-server.cmd`'s settings (no admin port) and the real client with `join.cmd`'s, three
times: a new name on a new game through the creation screen; the same name again on the
now empty, frozen server, which must still answer the account probe; and once more after
the server was restarted from the F6 quicksave.

| build | result |
|---|---|
| v1.4.1 (`--expect-defect`, 3/3) | creation finishes, the world never arrives, no login, no frame drawn |
| fixed (7/7) | world sent and drawn all three times, account known on return, quicksave and restart work |

`python -u tools/client_screen_proof.py heldturn ...`: two players in a fight that waits on
the real client; the host leaves, the client is closed, it comes back alone and presses
Space. A wire connection that never logs in watches every announced turn.

| build | result |
|---|---|
| v1.4.1 (`--expect-defect`) | the returning game is never sent the world |
| v1.4.0 (`--expect-defect`) | it gets in, but the fight ran on without it |
| fixed (3/3) | three turn announcements while it joined, all its own; its game logged "this player's turn" before its end of turn was accepted |

`python -u tools/issue_wire_proof.py joinfreeze ...` is the same on the wire, for the host
and for a second player: the sim clock on the frames sent before the login does not move,
the one turn announced with the world is the returning player's own, it is said once more
after the login, and ending it is accepted.

| server | frames before the login | turns before the login | turns after the login |
|---|---|---|---|
| v1.4.0 (`--expect-defect`) | 38, clock running | 12 | none (the fight had moved on) |
| v1.4.1 (`--expect-defect`) | 0 | none | four enemy turns, then the host's |
| fixed (9/9) | 6, clock standing | the host's own | the host's own, once more |
