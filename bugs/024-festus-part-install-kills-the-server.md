# 024: Handing Festus the reactor part kills the server

**Status**: FIXED (2026-09-10), not yet confirmed in live play.
**Files**: `src/server_stubs.cc` (`_selectWindowID`, `_displayFile`, `_displayFileRaw`).

## Symptom
Talking Festus at the Gecko power plant into letting you install the Hydroelectric
Magnetosphere Regulator (the speech-check route: "Get out of the way and let a
professional handle this") aborts `f2_server.exe` mid-dialogue. Every player is
disconnected; the client shows a server disconnect and exits. Reported from live play on
2026-09-10 on the power plant map. The server console's last line:

    f2_server: FATAL - client symbol '_selectWindowID' called on the core-only server.

Windows logs the abort as exception 0x40000015 in f2_server.exe. The crash is 100%
reproducible: reload and take the same dialogue line and it fires again. Handing Festus
the part on the non-speech route ends in the same script node, so it crashes too.

## Root cause
A script bug Interplay shipped in 1998. `gcfestus.int` Node30a, the node that resolves
the part install (removes the part, marks the plant repaired, awards XP and rep), calls
`display(mstr(700))` where the writer meant `display_msg(mstr(700))`. `display_msg`
prints to the message log; `display` is the intlib opcode that draws an image file into
a script-created managed window, and it is handed a message string as the filename. The
original engine never noticed: during a gsay dialog no managed window exists, so
`_selectWindowID` returns false, every intlib op ignores that result, and the bogus
filename resolves to no art, so nothing draws and nothing shows. That is also why
message 700 ("You convinced Festus to help you with the power plant.") never appears in
vanilla play.

On the dedicated server the dialogue runs headless through `_gdProcess`, Node30a executes
the opcode, and `_selectWindowID` resolved to the aborting stub in `server_stubs.cc`. The
abort came before the node's `give_xp`, so nothing after the part removal ran; since no
save happens mid-script, the crash loses nothing on disk.

This is the stub file's own rule bitten in the wild: any stub a script opcode can reach
must answer headless, never abort (`serverStubHeadlessOnce` block comment). The opcode
surface was assumed to be engine-only; vanilla game data proves otherwise.

How wide is the class? A linear disassembly of all 1,443 compiled scripts shipped in
master.dat/patch000.dat (walking the bytecode from each procedure's bodyOffset; push
opcodes carry the only inline operands, so the walk is exact, and it covered every
script to end of code) finds exactly one game script using any window intlib opcode:
gcfestus.int, one `display` (0x806B). Three Fallout 1 leftovers (barstow.int, dumar.int,
surf.int) use the old `saystart`/`sayreply` family but none of them is in SCRIPTS.LST,
so they can never attach to an object. The say-family stubs therefore stay loud.

## Fix
`_selectWindowID`, `_displayFile`, and `_displayFileRaw` move from the aborting stub set
to the headless-safe set: log once via `serverStubHeadlessOnce`, then answer as the
client does when no managed window exists (false / draw nothing), which on the server is
always. The other window opcodes' drawing calls (`_windowOutput`, `_windowPlayMovie`,
and the rest) keep their loud aborts, so a genuinely unsevered UI path still names
itself instead of limping.

## Verification
The abort itself cannot fire in the headless probe: the probe runs the client binary,
which links the real windowing code and survives by the same accident vanilla does. The
dialogue route was verified in the probe instead (geckpwpl.map, `give:258`,
`dtalk:130`): the transcript's first pages match the live crash's five `dsay` picks
(241 "I have a part", 342 "ready to install it?", then the two speech gates at Node958
and Node956 that end in Node030's single option 510 into Node30a). The probe dude's
Speech cannot pass both gates, so the last hop rests on the bytecode scan plus the live
crash placing the FATAL at the fifth pick.

Live check after deploying: replay the Festus install. The server must survive the
dialogue, print `'_selectWindowID' answered headless` once in its console, award the
repair XP, and Gecko's plant state must flip to repaired for both players.
