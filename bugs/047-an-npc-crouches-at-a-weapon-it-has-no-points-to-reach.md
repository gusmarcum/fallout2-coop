# 047: An NPC crouches, over and over, at a weapon it has no action points left to reach

**Status**: FIXED (2026-09-30), proven on a sandbox against the AI; not yet confirmed in
live play.
**Files**: `src/actions.cc` (`actionPickUp`'s record branch), `tools/issue_wire_proof.py`
(`retry`), `tools/client_screen_proof.py` (`npcloot`, the same count).

## Symptom
GitHub issue 13, the follow-up to v1.4.0: "when a turn comes where an NPC actually could pick
it up, they still try to do so sometimes. It seems the game doesn't let them, so they get
stuck in a weird pickup animation loop for like 20 iterations. After that, they usually
finish turn and manage to pick it up on the next turn."

## Root cause
bugs/042 made the pickup wait for the walk and judged the reach after it, as vanilla does.
What it did not change is what happens when the critter has NO action points left: the
AI's attack loop (`_ai_try_attack`, up to ten attempts a turn) keeps asking for the weapon
after a hunt that fell short, and vanilla answers each ask by abandoning the sequence
before it starts (`animationRegisterMoveToObject` with no AP runs `_anim_cleanup`, and
`actionPickUp` returns -1): nothing is shown, nothing is taken.

The recorder's move leaf refuses a walk with no AP WITHOUT poisoning the sequence (a
record-purity rule, server_anim.cc), so the rest of the sequence was still recorded: the
crouch (`ANIM_MAGIC_HANDS_GROUND`) and its sound were shipped to every viewer as a
presentation sequence, from wherever the critter stood, while the reach check judged at
registration dropped the pickup itself. One crouch per ask, with the spear still on the
ground; the viewers played them back in a row. The next turn the critter had points again,
walked up and took it.

## Fix
`actionPickUp`'s record branch answers a critter with no action points as vanilla does,
before anything is recorded: -1, nothing shipped. Traced as `[cpickup] critter=N
item_net=M NOT attempted: no action points left`. The branch also ships its recording only
for a sequence that stood (rc 0): a sequence a leaf abandoned (a mover with no walk art)
shows nothing in vanilla either.

## Verification
The AI produces the ask only in some turns (a raider that threw the spear and hunts it
again, seen once in a 75 s run against v1.4.0 and not at all in two runs against the fix),
so the proof has the host ask, through the same `actionPickUp`. With the Bonus Move perk
the host's two free moves keep its turn alive at 0 AP (vanilla's H-12 rule ends a turn at 0
AP and no free moves). `python -u tools/issue_wire_proof.py retry <f2_server.exe> <sandbox>
<port> <cmd port> [--expect-defect]`: three spears at the host's feet, taken at 3 AP each
(9 AP to 0), a fourth three hexes off, a raider fourteen hexes past the host keeping the
fight on; then the host asks for the fourth. Read off the server log: "[anim-cb] skipped:
the sequence's reach check already failed" followed by a shipped sequence is v1.4.0's
crouch; "NOT attempted: no action points left" is the refusal.

| server | the ask with no AP left | shipped for the host | the fourth spear |
|---|---|---|---|
| v1.4.0 (`--expect-defect`, 5/5) | reach check "already failed" at registration | 1 sequence (the crouch) | still on the ground |
| fixed (4/4) | refused before anything is recorded | nothing | still on the ground |

The real client's `npcloot` proof (bugs/048) counts the same lines in a fight the AI drives,
and reports them when the AI happens to produce the ask.
