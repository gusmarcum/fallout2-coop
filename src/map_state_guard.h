#ifndef FALLOUT_MAP_STATE_GUARD_H_
#define FALLOUT_MAP_STATE_GUARD_H_

namespace fallout {

// The dedicated server's own copy of the MAPS\*.SAV working files (bugs/032).
//
// Those files are the running world's record of every map the party has visited:
// leaving a map writes one, entering a map reads one, and a save copies all of them
// into its slot. They sit in a folder the server does not own. The host plays from
// the world folder, and every Fallout 2 program erases MAPS\*.SAV when it starts
// (vanilla's clean-up before the main menu). A file erased behind the server's back
// is a map that comes back new: the dead stand up, the looted chests are full, the
// people you met greet you for the first time, and every later save carries the loss.
//
// So the server keeps the bytes of each file it wrote or restored from a slot, and
// puts a file back when it goes MISSING. Only missing: a file that exists is never
// replaced, so a write this guard did not see cannot be undone by it. The files the
// server erases itself (a new world, a load, a random encounter left behind) are
// forgotten through the same two functions that erase them.
//
// Off unless mapStateGuardEnable() was called, which only f2_server does: the client,
// the headless probe and every golden run exactly as before.

void mapStateGuardEnable();

// The server wrote (or restored from a slot) MAPS\<fileName>: keep its bytes.
// False when the file could not be read back.
bool mapStateGuardCapture(const char* fileName);

// Every MAPS\*.SAV on disk right now, after a load placed the slot's files.
void mapStateGuardCaptureAll();

// The server erased MAPS\<fileName>, or all of them, on purpose.
void mapStateGuardForget(const char* fileName);
void mapStateGuardForgetAll();

// Before the server reads the working files: put back the ones that are gone.
// Returns how many were put back.
int mapStateGuardRestoreMissing();

} // namespace fallout

#endif /* FALLOUT_MAP_STATE_GUARD_H_ */
