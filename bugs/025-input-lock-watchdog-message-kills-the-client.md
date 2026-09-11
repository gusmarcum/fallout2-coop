# 025: Long scripted cutscenes freeze the mouse for 15 s, then the client closes

**Status**: FIXED (2026-09-10), not yet confirmed in live play.
**Files**: `src/display_monitor.cc` (`displayMonitorAddMessageStyled`), `src/main.cc`
(the input-lock watchdog's notice).

## Symptom
During a long scripted scene, the mouse and all controls die ("like a disable ui
thing"), nothing responds for 15 seconds, and then the game window closes. Reported
from live play on 2026-09-10 at Valerie's shop in Vault City: the Vic-Valerie reunion
scene fired, the player froze, and the client exited. Rejoining reproduced it exactly:
the scene's progress lives in temp script variables that reset on map load, and the
relationship LVAR that retires the scene is only set at its final stage, so the player
was stuck in a freeze-crash loop at the shop. Windows logged both exits as 0xc0000005
in fallout2-ce.exe, same fault offset. The server survives throughout.

## Two layers

**The freeze is vanilla by design.** vcmainwk.ssl (Valerie) runs the reunion as a real
cutscene: `game_ui_disable` at stage 0, then 38 timer-driven float stages at 3 to 6
game seconds each, over two minutes, with `game_ui_enable` only at stage 38. Vanilla
players sit through it watching the floats. The co-op viewer has a 15 s input-lock
watchdog (added for bugs/016, the Navarro CIMine leak) that frees the controls when no
release arrives, so a legit long cutscene ALWAYS trips it. Firing is normal, and the
outcome is right for co-op (the other player keeps playing; the floats stream anyway).

**The crash is ours.** The watchdog announced itself with
`displayMonitorAddMessage("Controls released (the script never gave them back).")`,
a string literal in read-only .rdata. The display monitor's word-wrap splits long
messages IN PLACE: it strrchr's the last fitting space and writes '\0' there
(restoring the ' ' after), which requires writable input. Every vanilla caller passes
a buffer; the literal is wider than the 167 px monitor, so the very first watchdog
fire wrote into .rdata and the client died on an access violation. addr2line places
the crash offset (0x1023ba) exactly on that store inside
`displayMonitorAddMessageStyled`, and the client log ends with the watchdog line
followed by the monitor beep that the same function plays two lines earlier. In other
words: every single watchdog activation since it was added has killed the client, and
it presented as "random crash after my mouse died".

The same trap sat latent at other co-op call sites: the loot-highlight ON/OFF
literals (short enough not to wrap, today), `ClientPresenter::consoleMessage`'s
const_cast (any long streamed message in read-only or shared memory), and the
`.c_str()` casts in client_net/client_trade (writable in practice, but mutating a
std::string through `c_str()` is undefined behavior).

## Fix
One choke point: `displayMonitorAddMessageStyled` copies the text into a local
buffer before the wrap machinery runs, so caller memory is never written. Behavior
is unchanged by construction: the function always restored the input before
returning, so no caller could observe the mutation; the SFALL console-file log still
receives the original untruncated pointer. This retires the whole defect class,
including the c_str() undefined behavior.

The watchdog's notice is reworded to "Controls released (a scripted scene held them
past the cap)." on the system channel, since firing usually means a long vanilla
cutscene now, not a script bug. The 15 s bound stays: the server never gates control
verbs on the scripted lock, the scene's floats keep streaming, its timers keep
advancing server-side, and its closing game_ui_enable simply arrives as a no-op, so
an early release costs nothing and returns the player to the game.

## Verification
Golden gates (the client binary runs them) must stay identical: the copy changes no
wrap output. Live check: replay the Vic-Valerie scene. Expect controls back after
15 s with the new system-channel notice, the floats playing on to the end, no crash,
and the scene never re-firing after it completes once (LVAR_Vic_Relationship set at
stage 38).
