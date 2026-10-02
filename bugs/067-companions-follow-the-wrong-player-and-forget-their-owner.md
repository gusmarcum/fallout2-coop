# 067: Companions follow the wrong player across floors, and forget who they belong to

**Status**: FIXED (2026-10-02) for the cases below, proven on a sandbox with wire bots; not
yet confirmed in live play. Issue 41's own case (small cave maps) was not reproduced; see
the end.
**Files**: `src/party_member.cc` / `.h` (`_partyMemberSyncPosition`,
`partyMemberSyncSetMover`, the owners' save and load), `src/object.cc`
(`objectSetLocation`), `src/map.cc` (`_map_place_dude_and_mouse`,
`mapHandleTransition`), `src/player_sheet.cc` (the save appendix), `src/server_admin.cc`
(`party`, `partyadd`), `src/command.cc` (`elevate`, `entermapat`),
`tools/issue_wire_proof.py` (`companions`).

## Symptom
GitHub issue 20, the Klamath Toxic Caves: "If current Companion Owner uses the ladder,
Companion refuses to go to the Next Elevation, instead it just teleports to the Owner's
coordinate on his Current Elevation and starts to follow a remaining Player. If no player
left on that elevation, NPC finally follows to the next one. Sometimes if a Player who
doesn't own the Companion uses the ladder, Companion still gets teleported and acts like he
belongs to this Player, until he meets his Owner again." Asked for: "Companion should
belong to the Player whom he originally followed." Issue 41: "Recruitable NPCs aren't
following players to some maps." And the first report under issue 20: a companion landing
some twenty hexes off after a map change.

## Root cause
Vanilla has one player, so "bring the party to the dude" (`_partyMemberSyncPosition`) is
the whole rule, run whenever the map's elevation is set. Co-op asked that one question in
situations it has to tell apart, and asked it of `partyMemberLeader`, which wants a leader
on the companion's own floor.

1. One player changes floor. The sync ran for every companion. For the mover's own
   companion the owner had just left the floor, so the "leader" was whoever stayed behind,
   and the companion was put beside them. For somebody else's companion the leader was its
   owner, and it was put beside them again: a teleport for no reason.
2. A map load placed the companions before the other players were standing on the new map,
   so a companion whose player still held a tile number from the old map was placed beside
   that number.
3. A trip that names its arrival tile moves the group there after the load, and synced the
   companions before the other players had been moved.
4. The owner was runtime state. Every companion came back from a load belonging to nobody,
   and a world that is always started from a save had no owned companion in it at all.

## Fix
* `objectSetLocation` names the mover around its `mapSetElevation` call. With a mover, only
  that player's own companions go, and they go to the mover. Somebody else's companion is
  left where it stands. A companion with no recorded owner stays while a player is still on
  its floor and goes with the mover when that would leave it alone.
* With no mover (a load, a group move) every companion is placed beside its owner, or
  beside `gDude` when it has none; `_map_place_dude_and_mouse` now does that after the
  players are placed, and `mapHandleTransition` does it once more after moving the group.
* The save appendix carries who follows whom ('PAOW', after the events section, keyed by
  the companion's object id). An older save simply ends before it; an older server stops
  reading before it.
* The operator's `party` shows each companion's floor and owner, and
  `partyadd <pid> <slot>` sets the owner, which is the repair for a world saved before this.

## Verification
`python -u tools/issue_wire_proof.py companions ...`: two players and a spawned companion
that follows the second one. `elevate <slot> <floor>` puts one player on another floor
where they stand, as a ladder's script does.

| check | the same build with the old rules | fixed (7/7) |
|---|---|---|
| its owner changes floor | stays on floor 0, beside the player who stayed | goes with them |
| the other player changes floor twice | moved each time | stays where it stood |
| no owner: stays while a player is on its floor, follows the last one off | pass | pass |
| after a map change the second player asks for | pass | beside its owner |
| after a trip that names its arrival tile | pass | with the group |
| a save and a restart keep the owner | (new) | slot 1 before and after |

## Not reproduced
Issue 41 names the Klamath rat cave entrance and random encounter caverns. The two
map-change checks pass on the old rules as well, so they do not show that report's defect.
Points 2 and 3 are real orderings that could strand a companion, and they are fixed, but
that this is what happened in those caves is an inference. The reporter's retest decides it.
