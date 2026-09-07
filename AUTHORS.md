# Authors and provenance

This project stands on two pieces of other people's work. This file records exactly which
part is whose, measured from the repository rather than from memory, so that anyone reading
the code knows what they are looking at.

Figures below were taken with `git blame` and `git shortlog` against `main` and will drift as
the project moves. Regenerate them rather than trusting them if the difference matters to you.

## The engine

[Fallout 2 Community Edition](https://github.com/alexbatalov/fallout2-ce) by **Alexander
Batalov** and contributors: a reimplementation of the Fallout 2 engine, and the overwhelming
majority of the code in this repository. Roughly 795 commits of the history are Batalov's,
with further contributions from Jan Šimek, Vasilii Rogin, k3tamina, Wipe, sonilyan, Vlad,
Edgar Miró, Martin Janiczek, c6, Alexander Arkhipov, Alexander V. Nikolaev, Austin Hurst,
Condratiy Lenovin, Eir Nym, Graham Gower, Jiří Malák, Jo, JordanCpp, Nikola Đurinec, Ryan
Deering, TomArnaez, Walter Agazzi, drjfaust, yabisiktir and λP.(P izzy).

Fallout 2 itself is the work of Black Isle Studios and Interplay. No game assets are included
in this repository or in any release of it.

## The co-op layer

[Cahb/fallout2-ce-coop](https://github.com/Cahb/fallout2-ce-coop) by **Oleksandr Mazur**: the
dedicated server, the network client and the wire protocol, delivered as five commits tagged
v0.1 through v0.4. This is the architecture the whole project sits inside. Making a
single-player engine server-authoritative, splitting the presenter from the client and the
server, and designing the wire format are his decisions, and every change in this repository
is made within them.

Around 38 source files arrived with that work. Of the lines still standing in those files
today, roughly 23,974 are his and 2,213 are this project's.

## This project

**GusMarcum**, from v0.4 onward: 60 commits, about 4,804 inserted and 159 deleted lines
across 70 files under `src/`. The work falls into three parts.

Bug fixes traced to their cause in the engine, with the reasoning kept in the commit messages
and in [`bugs/`](bugs). Fourteen of those reports carry a symptom, a root cause, the files
involved and the fix.

Features that did not exist before: player-to-player trading, the teammate revive and
party-wipe rules, quicksave and quickload, and companion combat orders reachable over the
wire. The trading subsystem is four files written from scratch,
[`src/server_trade.cc`](src/server_trade.cc), [`src/client_trade.cc`](src/client_trade.cc)
and their headers, 1,035 lines with no inherited code in them.

A test harness that runs on Windows: the engine's 41 golden scenarios made headless,
deterministic and blessed against a Windows result set, so every commit here is gated, plus
the per-feature sandbox proof scripts under [`tools/`](tools).

## Contributors

**[@adainstarks](https://github.com/adainstarks)** (William Starks), for help with this
project.

Worth stating plainly alongside the commit counts above: this project is fixed by being
played. Almost every entry in [`bugs/`](bugs) began as a symptom someone reported from a
live two-player session, not as something spotted by reading the code. The commit history
records who wrote the patch; it does not record who found the fault, and those are not
always the same person.

## Licence

[Sustainable Use License](LICENSE.md), inherited from Fallout 2 Community Edition and
unchanged. It is non-commercial, it requires that these terms travel with any copy, and it
requires a modified copy to say that it has been modified. This is a modified copy: see
[`CHANGELOG.md`](CHANGELOG.md) for what changed and when.
