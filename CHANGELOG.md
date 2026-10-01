# Changelog

Binaries for every version are on the
[releases page](https://github.com/gusmarcum/fallout2-coop/releases). The server and every
client must run the same version.

## v1.4.1 (2026-10-01)

Fixes for the follow-ups on three v1.4.0 reports and eight new player reports. Three of
them change behaviour you will notice (see Changed). Saves from every earlier version load
unchanged.

### Changed

- **A fight closing the character sheet is a Cancel
  ([issue #12](https://github.com/gusmarcum/fallout2-coop/issues/12), follow-up).** In
  v1.4.0 a sheet the game closed itself (a fight starting under it, a map change) kept what
  the visit had spent. It now takes it back, as Cancel does: Done is the only way to keep
  changes. Quitting the game with the sheet open still keeps what was spent.
- **A line printed by one player's action shows who did it
  ([issue #25](https://github.com/gusmarcum/fallout2-coop/issues/25)).** "You failed to
  pick the lock" from a door's script, "That door is locked" from the game, and the like
  used to reach every player as their own. The player who acted still reads the line as
  written; everyone else reads it under that player's name, "Player2: You failed to pick
  the lock."
- **The world waits for a player to log in
  ([issue #16](https://github.com/gusmarcum/fallout2-coop/issues/16)).** A server with
  nobody playing froze its world only while nobody was connected, and a game that had
  connected but not yet logged in (the account query, the creation screen, the load) set it
  running with every character unattended. A player who had left next to hostiles came back
  to find the fight had gone on without them. The world now stays frozen until a player has
  logged in, and then that player's turn waits for them as it always did.

### Fixed

- **The pipboy's Hit Points line follows a rest
  ([issue #10](https://github.com/gusmarcum/fallout2-coop/issues/10), follow-up).** The
  line above the rest options only redrew when an option was clicked, so a heal showed one
  rest late. It redraws whenever your hit points change while the pipboy is open.
- **No more crouching at a weapon out of reach
  ([issue #13](https://github.com/gusmarcum/fallout2-coop/issues/13), follow-up).** When an
  enemy's walk toward a weapon on the ground used up its action points, its AI kept asking
  to pick the weapon up, and each ask played the crouch for everyone while nothing was
  taken. As in the original game, an ask with no points left now does nothing at all.
- **A weapon an enemy picks up in a fight is seen, and stays in its body
  ([issue #13](https://github.com/gusmarcum/fallout2-coop/issues/13), follow-up).** Each
  game's copy of an enemy's inventory only updated items it already knew about, so a spear
  picked up mid-fight never reached it: the enemy looked bare-handed while using the spear,
  and its body had no spear to loot although the server had it there. The copy now takes
  in new items.
- **The level-up sound plays for your own level
  ([issue #21](https://github.com/gusmarcum/fallout2-coop/issues/21)).** The server played
  it for the host's levels only, as a broadcast, so the host's level-ups sounded on every
  screen and nobody else's ever did. Each game now plays it when its own level rises.
- **Dialog options open with one bullet for observers
  ([issue #23](https://github.com/gusmarcum/fallout2-coop/issues/23)).** Observers' games
  added a second bullet in front of the one the server already sends.
- **No "Music could not be restarted" line on joining
  ([issue #18](https://github.com/gusmarcum/fallout2-coop/issues/18)).** The music restarts
  by itself a few seconds later; the line pointed at a debug.log the release does not write.
- **Combat Control offers "Use your best weapon" and "Wear your best armor"
  ([issue #22](https://github.com/gusmarcum/fallout2-coop/issues/22)).** The text version
  of the Combat Control menu lacked the two buttons of the original window. They do what
  the buttons did.
- **Observers can scroll a trade
  ([issue #26](https://github.com/gusmarcum/fallout2-coop/issues/26)).** The scroll buttons
  were switched off for everyone but the trading player. Each observer scrolls their own
  copy of the four lists.
- **Another player's worn armor and held weapons stay out of the item list
  ([issue #27](https://github.com/gusmarcum/fallout2-coop/issues/27)).** During a steal,
  every game rebuilds its copy of the thief's inventory from scratch each time an item
  moves, and the rebuild forgot which items were worn or held, so afterwards that player's
  equipped gear showed as loose items on everyone else's screen, in that steal and in any
  trade after it.

Not in this release: [issue #20](https://github.com/gusmarcum/fallout2-coop/issues/20)
(a player or companion arriving far from the party on some maps) could not be reproduced;
see `bugs/054` for what was found.

## v1.4.0 (2026-09-30)

Fixes for eleven player reports. One of them changes how the character sheet behaves: Esc
and C now cancel, as they do in the original game (see Changed). Saves from every earlier
version load unchanged.

### Changed

- **Cancel on the character sheet takes back what the visit spent
  ([issue #12](https://github.com/gusmarcum/fallout2-coop/issues/12)).** Every skill point
  and perk goes to the server the moment it is clicked, so Cancel had nothing left to undo
  and kept everything. The server now remembers what was spent since the sheet opened, and
  Cancel walks it back: skill points, perks (the pick comes back to be made again), Tag!'s
  fourth skill, Mutate!'s trait, Educated's points and Lifegiver's hit points. Done keeps
  everything. As in the original game, **Esc and C are Cancel too: to keep what you spent,
  close the sheet with Done.** Here and Now cannot be taken back, since it pays out a whole
  level, and the game says so. A sheet the game closes itself (a fight starting, a map
  change) keeps what was spent.

### Fixed

- **Screens opened during a fight stay open
  ([issue #11](https://github.com/gusmarcum/fallout2-coop/issues/11), and the follow-up on
  [issue #3](https://github.com/gusmarcum/fallout2-coop/issues/3)).** The character sheet,
  Options and the skilldex closed a couple of frames after they opened in combat: the rule
  that a fight closes open screens was checked on every frame of the fight, not when it
  starts. A fight that starts while one of them is open still closes it.
- **A created character keeps the sex and age picked on the creation screen
  ([issue #14](https://github.com/gusmarcum/fallout2-coop/issues/14)).** The creation
  screen never sent them, so every character arrived male and 25. A female character now
  arrives female, in the female body. The joining player's client and the server both need
  this version for it; an older client still joins as before.
- **An enemy only picks up a weapon it has walked to
  ([issue #13](https://github.com/gusmarcum/fallout2-coop/issues/13)).** An unarmed enemy
  took a thrown spear from twenty hexes away, before it had taken a step: the server handed
  it the item as soon as the pickup was queued. It now walks first and takes the item only
  if it arrives; if it cannot get there this turn, it keeps walking on its next one, as in
  the original game.
- **The Temple of Trials says what it paid
  ([issue #6](https://github.com/gusmarcum/fallout2-coop/issues/6)).** Lines a map prints as
  the party arrives, such as Arroyo's "You passed the trials of Arroyo." and the experience
  line, were dropped with everything else the server holds back while it loads a map. They
  now reach every player once the map has loaded.
- **Only the player who arms a charge reads "You set the timer"
  ([issue #5](https://github.com/gusmarcum/fallout2-coop/issues/5)).** The others read
  "\<name> sets the timer." instead.
- **Healing in the inventory shows at once
  ([issue #9](https://github.com/gusmarcum/fallout2-coop/issues/9)).** The hit point
  counter and the inventory's own hit point line only changed once the inventory closed.
  Both now count while it is open.
- **Resting shows and heals
  ([issue #10](https://github.com/gusmarcum/fallout2-coop/issues/10)).** The hit point
  counter and the pipboy's date and clock now update while the pipboy is open. Rest heals
  once for every 180 minutes, counted in rounded-down steps, so a single three hour rest
  counts 169. The original game carries that count over to the next rest; the server
  started it again for every rest, so rests of three hours or less never healed. The count
  now carries over, and from the second three hour rest on, resting heals.
- **Swapping between empty hands is instant
  ([issue #7](https://github.com/gusmarcum/fallout2-coop/issues/7)).** Punch to kick
  waited a second for an animation that never plays. The wait now only happens when a
  weapon is drawn or put away.
- **The idle head scratch no longer blocks input
  ([issue #15](https://github.com/gusmarcum/fallout2-coop/issues/15)).** It counted as an
  action, so the wait cursor showed and clicks were ignored until it finished. A click now
  cancels it, as in the original game.

### Added

- **Proofs for these fixes.** [`tools/issue_wire_proof.py`](tools/issue_wire_proof.py)
  checks the server side of issues 5, 6, 10, 12, 13 and 14 with scripted players, and
  [`tools/client_screen_proof.py`](tools/client_screen_proof.py) gains checks for issues 3,
  7, 9, 10, 11, 12, 14 and 15 that run the real game client with a recorded keyboard. Each
  can show its defect on an older build.

## v1.3.2 (2026-09-28)

Three fixes, all from player reports. The first one matters to every world: maps the party
had already visited went back to new. Saves from every earlier version load unchanged.

### Fixed

- **Visited maps stay visited
  ([issue #4](https://github.com/gusmarcum/fallout2-coop/issues/4)).** The dead stood up
  again, emptied chests were full, and people greeted the party as strangers, on every map
  except the one the party was standing on; after a server restart a save seemed to keep
  only the area it was made in. The state of each visited map is a file in the world
  folder, and the game client erased those files every time it started, as the original
  game does before its main menu. The host plays from the world folder, so each time the
  host joined, the running world lost its record of every earlier map. A client started to
  join a server now leaves those files alone. The server also keeps its own copy of each
  one and puts back any that go missing, and says so on its console, which covers an older
  client or the original game started in that folder. A map that was lost before this
  update loads as new one more time, then stays the way the party leaves it. Quests,
  experience, karma, the characters and the world map were never affected.
- **A player who joins sees their own hit points
  ([issue #2](https://github.com/gusmarcum/fallout2-coop/issues/2)).** The counter of a
  joining player showed the host's hit points until that player was next hurt or healed, or
  the party changed map. The server had the right number throughout; only the screen was
  wrong.
- **Chat works during a fight
  ([issue #3](https://github.com/gusmarcum/fallout2-coop/issues/3)).** `T` opened the chat
  box in combat and the next frame closed it, and the Enter meant for the message asked to
  end combat instead. The box now stays until the line is sent (Enter) or cancelled (Esc).
  While it is open it takes every key, so the End Turn and End Combat buttons type into it:
  send or cancel first.

### Added

- **Proofs that use the real game client.**
  [`tools/map_state_proof.py`](tools/map_state_proof.py) kills two critters, leaves the
  map, starts a real game client in the server's folder, walks back, saves, restarts and
  walks back again, and checks the world at each step.
  [`tools/client_screen_proof.py`](tools/client_screen_proof.py) checks the hit point
  counter and the chat box the same way, from the client's own screenshots and a recorded
  keyboard. Both need Python and a sandbox copy of a game folder.

## v1.3.1 (2026-09-27)

One change to how the game is played together, asked for in
[issue #1](https://github.com/gusmarcum/fallout2-coop/issues/1): experience is shared. An
award used to go to whoever earned it, so the player who landed the last hit or finished
the quest levelled and the player next to them did not. Every award now pays every
connected player in full. Saves from every earlier version load unchanged.

### Added

- **The party levels together.** Every experience award pays every connected player, in
  full and exactly once, the earner included: quest and dialogue rewards, kills (a fight's
  kills are one purse, paid when the fight ends), skill use, stealing, and spotting an
  encounter on the world map. Nothing is split, so two players level at the pace one
  player would alone. Each share goes through that player's own sheet, so Swift Learner,
  level-ups, skill points and perk picks stay individual. A player who is down is paid
  with the rest as long as one teammate is standing; a player who is not connected is not
  paid. The perk Here and Now still levels only the character who takes it.
  `F2_PARTY_XP=0` on the server returns to individual awards.
- **Every award on the server console.** One line per award names its source, who earned
  it and what each player was paid, for example
  `[xp] kills 150 by the party -> Host +150 (xp 207082, level 20), Friend +150 (xp 98435, level 14)`.
- **Operator verbs.** `partyxp <slot> <amount>` pays an award the way play does.
  `xp <slot> <amount>` still pays one seat only, which makes it the way to close a gap
  between two characters that already exists. `spawn <pid> [n] near` places a critter on
  the first free hex beside the host.
- **A way to test co-op alone.** One PC runs one game client, so one person cannot fill a
  second seat with a real game. [`tools/solo_test`](tools/solo_test) fills it with a
  script that stays connected as the second character, hands its combat turns straight
  back, and reports what that player's screen is sent and what every award paid. It needs
  Python and a save with two characters.

### Changed

- **A level-up does not heal a player who is down.** They keep the higher maximum, and the
  revive sets their hit points as before.
- **`spawn` is documented as it behaves.** The README said tile `-1` places the critter
  beside the host. It places it at a random reachable spot within 30 hexes of a player;
  `near` is the placement the old text promised.

## v1.3.0 (2026-09-11)

Ten fixes, every one of them from live play. Three could end a session on the spot: a
vanilla script line that killed the server, a status message that killed the client, and a
solo world that forgot which character was yours. The rest came out of one long afternoon
in Navarro and San Francisco: elevator panels going quiet, screens closing the moment they
opened, a car that vanished on load, and planted explosives going off in the wrong place.
Saves from every earlier version load unchanged.

### Added

- **Launchers in the zip (re-issued 2026-09-27).** `start-server.cmd` lists the world's saves
  and continues the newest co-op save on Enter, or starts a new game the first time;
  `join.cmd` asks for a character name and the host's address once and remembers them. Both
  live in `dist/windows`. The exes are unchanged.
- **Two diagnostics for operators.** `F2_TRACE_PARTY=1` prints one roster line per party
  member every 25 seconds (script id, tile, elevation, distance to the leader), which tells
  a member with no script apart from a slow follow loop. Every detonation now prints two
  console lines naming the charge, who was holding it, the tile it went off on, the damage
  range, and the critter at the center.

### Fixed

- **A trade started from a dialogue line opens the trade screen.** Picking the option that
  begins bartering sent the dialogue page first and the trade second, so the player was left
  looking at an empty page. A pending trade is served before the page now.
- **No stray red box during a trade.** Objects that had no place on the map yet were drawn
  as a red question mark in the corner of the screen. Unplaced objects are skipped.
- **Installing the part in the Gecko power plant no longer takes the server down.** Festus's
  script calls a window opcode through an Interplay typo (`display` where `display_msg` was
  meant), and the server's stub for that opcode aborted the process. The window opcodes
  answer headless and draw nothing now. A bytecode walk of all 1,443 shipped scripts
  confirms Festus is the only reachable caller.
- **The controls-released notice no longer crashes the client.** A scripted scene that holds
  the interface for more than 15 seconds trips the input-lock watchdog, and the watchdog's
  message was a constant that the display monitor word-wrapped in place. The monitor wraps a
  copy now. The Vic and Valerie reunion in Vault City was an endless crash loop before this.
- **A solo world keeps your character and your name.** A world with one player never wrote
  the block that records which account owns which body, so every restart reopened character
  creation, and finishing it applied a fresh roll to the campaign character: level 1, no XP,
  no perks. Solo saves carry the account table now, a body with a level or any XP refuses a
  creation roll outright, and the greetings say what actually happened.
- **Companions keep up.** The server pumps the background script tick once per beat where
  vanilla pumps it every frame, so on a busy map a companion re-checked its follow about
  every four seconds and kept stopping where its leader used to be. Party members now get
  their own follow heartbeat twice a second, under the same dialog, combat and movie gates.
- **An elevator panel keeps working after you pick the floor you are already on.** That
  answer skips the panel's gauge animation, so it reached the server while the animation
  that opened the panel still counted the player as busy, and the busy gate threw it away
  without releasing the pending offer. The panel then stayed silent for the rest of the
  session. The answer is never dropped now, and every answer ends the offer.
- **Screens stop closing the moment they open after an elevator ride.** The elevator panel
  turned scripts back on when it closed, which on a client means it runs NPC scripts the
  server already runs. An NPC asking to start a conversation then left the client in a state
  where the inventory, loot and other screens close on their first frame until it restarted.
  The panel restores the state it found, and a client ignores local conversation requests.
- **The car survives a cancelled world map trip.** Driving off clears the marker that says
  where the car is parked, and arriving somewhere sets it again. Backing out of the world
  map with Escape never did, so a save made after that lost the car on load: the car's own
  script deletes it when the marker is not its tile, and the town script that would put it
  back does nothing while a save is loading. A cancelled trip re-points the marker at the
  car standing on the map.
- **A planted or dropped charge goes off where it actually is.** A save records each bomb
  timer against its object id, and object ids are only unique within one map, so after a load
  the timer could attach to a piece of local scenery that shares the id: the blast landed on
  that scenery for no damage, destroyed it, and the real charge sat inert in the victim's
  pocket. The loader now prefers the object that actually carries a timer.

## v1.2.0 (2026-09-10)

Cutscenes come back, and a few things the game only shows two players. Most of this came
out of one long night of proving what the server actually does with a save, which is how
three save bugs older than any of our releases turned up. Saves from every earlier version
load unchanged.

One thing to know: a save made before the account system (before player names) asks for a
character once on the first join, and applies the roll to the host body. To keep that old
character, join once with the `F2_PLAYER_CREATE=ask` line removed from the join file.

### Added

- **One suit per player.** The game places exactly one Advanced Power Armor in Navarro and
  one Mk II in the oil rig's trap room. The first time the server loads one of those maps
  it tops the locker up to one suit per seat in the save, so a second player is not sent
  through Navarro without a disguise because the first one took the only suit. Nothing is
  removed, a revisit changes nothing, and the rule table in `src/server_seat_items.cc` is
  the place to add more.

### Changed

- **Cutscenes always play.** `F2_MOVIES=0` used to switch scripted movies off on the
  server, and the launch files this project shipped set it, so no cutscene ever reached
  the players: not the tanker leaving for the oil rig, not the rig going up. The switch
  was adopted for a client that crashed on the Temple of Trials cutscene, and that crash
  was the client's own mods, not the movie. The switch is retired; a launch file that
  still sets it gets one notice at boot and is otherwise ignored. Clients must run
  unmodified game data.
- **A cutscene can no longer park the server.** The movie barrier releases on the first
  player to finish or skip, as before, and now also on its own after three minutes if no
  player ever reports back, with a line on the console. The operator can release it by
  typing `movdone` on the command channel.

### Fixed

- **A server started on a fresh map can save.** The slot writer copies the automap
  database into the slot and gave up when the file did not exist. Only a client creates
  that file, so a dedicated server hosting a new world from its own folder failed every
  save with "error 0" until a client happened to run beside it. The server now writes
  the same empty database the client would have.
- **A new world starts from the shipped maps.** Starting the server on a fresh map in a
  folder that had hosted another world kept that world's map state files, and the loader
  prefers those, so places the old world had visited came up already looted and cleared.
  The server now clears them, like the game's own new game does.
- **A failed save no longer damages the slot.** The save backup covered the save file,
  the maps and the automap but not the companion protos, which are written before the
  step that can fail. A failed save restored everything else and left protos from the
  world that failed to save, and loading that slot crashed the game. The protos are now
  backed up and restored with the rest, and a recycled autosave slot is emptied of them
  too. `F2_SERVER_DEBUG_LOG=1` makes the server name the failing step in
  `f2_server-debug.log`.
- **The character creation screen opens once, not on every launch.** With
  `F2_PLAYER_CREATE=ask` the client opened the creation screen before connecting, because
  it could not know whether the server already had the name, and the server then threw the
  roll away for a returning player. The client now asks the server first and opens the
  screen only for a name the world does not know. A fresh world still asks everyone once.
- **Leaving the worldmap no longer flashes the map you just left.** Picking a destination
  (or being pulled into an encounter) closed the worldmap screen a second or two before
  the new map arrived, and in that gap you were shown the map you had left, with whatever
  its fight still had queued playing at full speed. The screen now holds on black until
  the new map is applied, the way the original game loads the new map underneath the
  worldmap. Escaping the worldmap still returns you to the old map at once.
- **The world trace no longer reports a correct saved-state load as a reset.** With
  `F2_TRACE_WORLD=1`, re-entering a visited map logged "fresh .MAP (no saved state)" for
  the inner load of the saved file, which made every revisit read like the very bug the
  line exists to expose. It now says "loading the saved state file".

## v1.1.0 (2026-09-08)

A bug-fix release with three changes you will notice. Everything here came out of one
long play session on the oil rig.

### Fixed

- **The Navarro minefield no longer takes your controls away.** Stepping on a mine left
  the player unable to open a menu, pan the screen or use the mouse, with clicks only
  half registering, until they restarted the game. The mine's script disables the
  interface and never re-enables it; in the original game the explosion's own code hands
  the controls back, because the flag is shared between the scripts and the engine on one
  machine. Co-op had split that flag across the wire and only reconnected the script half,
  so the release never reached the player. Six of the game's scripts leak a lock this way,
  including two in Modoc and one in New Reno, and this fixes all of them. The client also
  now releases any input lock held longer than fifteen seconds and says so, so no script
  can cost a session again.
- **A save made after Frank Horrigan dies is playable.** Loading one booted the world,
  served a single beat and kicked everybody out, which looked exactly like the client
  crashing on that map. The oil rig's entry script signals the game's ending on every
  entry once Horrigan is dead, and the serve loop honoured it. A keepalive server now
  logs that once and keeps running; stopping it on purpose is still `quit` on the command
  channel.
- **The nine-door puzzle in the Enclave works.** One of the terminals opens two doors and
  then closes those same two a few lines later. The original game's doors slide on a
  deferred animation, so the second instruction quietly does nothing and the doors stay
  open; the server applies the slide immediately, so it undid the first instruction and
  that terminal could never open anything. The doors also appeared open on screen while
  the server still blocked the way through them.
- **Power armour cannot be taken off twice.** Rarely, a suit's bonuses were removed twice
  over, dropping Advanced Power Armor's wearer from 9 Strength to 1 rather than 5, and it
  stuck. Armour class and every damage resistance were being double-subtracted the same
  way, unnoticed. The bonuses can now only be taken off the body they are actually on.

### Changed

- **Autosaves rotate through their five slots in order** — 11, 12, 13, 14, 15, then back
  to 11 — instead of always recycling whichever save was furthest behind in in-game time.
  The old rule kept the most-progressed saves longest, which sounds right and degenerates:
  load an earlier save and play on, and every autosave lands on the same slot forever. The
  trade is real and worth stating: after going back to an older save, the rotation will
  overwrite the newer, further-along ones within one lap. Manual slots are where a save
  worth keeping belongs.
- **The ending no longer asks whether you want to keep playing.** In a shared world the
  answer is always yes, and one player's dialog box would sit on their screen while
  everyone else played on. The slides and the credits still play in full first. Single
  player still asks.

## v1.0.0 (2026-09-07)

**Fallout 2 has been played from start to finish in co-op.** That is what the version
number is for. It is not a claim that nothing is left to fix; it means two people can
begin at the Temple of Trials, play the whole game together, and beat Frank Horrigan,
which is the bar this project was built to clear.

### New

- **The server owns the ending.** Winning already showed the slides, because a viewer
  runs map scripts locally and each client played the sequence off its own script
  execution. That worked, and play continued afterwards, but nothing coordinated it: the
  dedicated server drops the request, so it depended on each client happening to run a
  script the server had discarded. It is a wire event now, announced by the server, with
  the slides still chosen from the globals that world earned. No reload and no shutdown
  follows, and the closing "keep playing?" prompt cannot quit anyone out of a live
  session.
- **`ending`** on the operator console replays it on demand.
- **`stat <slot> [stat] [value]`** reads or repairs a seat's base SPECIAL. It prints base
  and current side by side, so an armour or drug bonus shows as the difference. Nothing
  could reach the seven base stats before, which made repairing a character a SAVE.DAT
  edit with the server down.

### Fixed

- **NCR shot the second player for a weapon he had already put away.** Holstering in
  vanilla means switching to your empty hand, not dropping anything, and a script reads
  the hand you are holding up. On a dedicated server the opcode asked a stub pinned to
  the left hand, so swapping was invisible, and the filter was applied only to the
  anchored player, so everyone else reported both hands unconditionally. The second
  player could never comply. Now every script-facing hand reader resolves the real
  active hand, for every player.
- **A client closed itself on the oil rig, instantly, every load.** Post-Horrigan the
  map's entry script signals the end of the game, and a viewer runs map scripts locally
  while loading a map to render it. The dedicated server was guarded against that; the
  client never was, so it set the terminal quit and exited. The map appeared for a
  fraction of a second and the window shut, with no crash dump because it was a clean
  exit. A viewer never self-quits from a script now.
- **Winning the game shut the server down.** `op_endgame_movie` bypasses the script
  request queue and calls straight into the headless branch that sets the terminal quit,
  so the world would have stopped mid-ending, moments after the players started watching.
- **A silent server death now names itself.** The terminal quit ended the serve loop with
  no log line, indistinguishable from a clean shutdown, so the clients being dropped a
  second later looked like the broken half. All five sources report themselves and the
  loop prints the tick it saw one on.

## v0.6.0 (2026-09-06)

### New

- **Trading between players.** Talk to another player to propose a trade; on yes both open
  the vanilla trade screen with each other while the world keeps running. Offer locks a
  table, two locked tables raise an accept box on both sides, two yeses swap. Stealing from
  a player is refused.
- **Death is a team matter.** No self-revive. A teammate revives a dead player by using the
  body, a healing item, First Aid or Doctor: free out of combat, 4 AP on their turn in a
  fight. A revived player gets their turns back. When nobody is left standing every client
  plays the death screen and the server reloads the most recently written save.
- **Quicksave and quickload.** `F6` writes server slot 16, `F7` reloads it in place for
  everyone, in combat and while dead. Admin `load <n>` works while a world runs.
- **Combat orders presets.** The companion orders menu has a Disposition line that cycles
  Custom, Coward, Defensive, Aggressive and Berserk.
- **Companions step aside** when they are the only thing blocking a walk or an approach,
  and the walk is retried.
- **Console**: `kill <slot>`, `spawn` takes a scripts.lst number so the NPC talks,
  `despawnall`; the server window reports a client that stops draining its stream.
- **Viewer `audit`** dumps the windows, the floating objects and every player-art critter
  into `debug.log`.

### Fixed

- Sliding doors and elevator doors drifted upward with every open-and-close cycle and the
  drift was saved; frames now step with the animation's art offsets and every door is put
  back in place at map load (bugs/010).
- Elevators asked for the floor twice (bugs/009). `Esc` on the panel cancels the ride.
- The San Francisco Brotherhood door opened and closed in the same beat (bugs/011).
- Power armor's +3 Strength and radiation resistance applied only to the host (bugs/012).
- A player being stolen from saw their worn gear vanish from their own screen (bugs/013).
- The action-point bar could open a turn showing last turn's leftover (bugs/014).
- An offline teammate's parked body was drawn at the top-left corner of the screen.
- A player's sprite followed whichever hand held a weapon instead of the active hand.
- Crash on death: two new messages were string literals the message log writes into.
- The death screen garbled the rest of a large screen.
- Music stayed silent after a change between two maps that share a track.
- Two client heap-corruption crashes: merged inventory stacks freed twice. Wire stacks are
  mirrored as their own slots, the engine reports every free to the mirror, and a live-object
  registry turns a stale pointer into a logged skip.
- The whole world froze while any client loaded a map: server sends were blocking. Sends
  are non-blocking with a per-client queue (20 s freeze before, 0.2 s after).
- Companions were lost on the first map change after a load; `party` and `partyadd <pid>`
  repair worlds already hit.
- Out-of-combat input could stay blocked behind a stuck animation; capped at 3 s and logged.
- The inventory screen logs why it closed, for the "I does nothing" report.
- `tools/repair_vault_city_gate.py` removes the stacked blocking hex that walls off the
  Vault City gate in an affected save (bugs/008).

### Under the hood

- CI builds the two shipped binaries with MSYS2 mingw-w64 and the shipping flags, plus a
  Linux x64 build and cppcheck; the dead phone, Mac and 32-bit matrix is gone.
- Sandbox proof scripts under `tools/`: trade and death (51 checks), quicksave (26), armor
  perks, the parked body (14), inventory.
- Bug notes 008 to 014 under `bugs/`.

### Upgrading from v0.5.0

- Update the server and every client together: the wire gained events and verbs.
- Saves carry over. Slot 16 is now reserved for the quicksave.
- `R` no longer revives you; a teammate does.
- Power armor worn before the update: take it off and put it back on once.
- Doors that drifted in an existing save are put back in place on the first load.

## v0.5.0 (2026-09-04)

First release as its own project.

- Reconnecting keeps the world: the whole worldmap city table and quest-variable table ride
  every join; dead players stay down.
- Terminals and computers open their conversations; the conversation is attributed to the
  player who clicked.
- Companions follow whoever recruited them.
- Companion combat orders as a dialogue menu served by the server.
- A failed audio device is detected and reported; music that dies is restarted by a watchdog.
- Dialogue: no stale options over new ones, long replies page, the Review button works,
  chat on `T` also in combat.
- Two-handed weapons use one slot; arming one explosive arms one; TAB opens the automap;
  Push works on companions; a stuck wait cursor clears itself; operator `save` refuses
  when it would fail; `gvar` console command.
- Windows test harness: the 41 golden scenarios run headless and deterministic on Windows.

## v0.4

The base: [Cahb/fallout2-ce-coop](https://github.com/Cahb/fallout2-ce-coop) v0.4.
