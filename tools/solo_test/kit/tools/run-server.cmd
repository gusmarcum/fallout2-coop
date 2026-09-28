@echo off
rem Started by "1 START TEST.cmd" in its own minimized window. The server's settings
rem arrive in the environment; everything it prints goes to server-console.log, which
rem the stand-in reads the awards from.
rem
rem Every path is spelled out. A bare "f2_server.exe" relies on cmd searching the current
rem folder, and that search is switched off on some setups
rem (NoDefaultCurrentDirectoryInExePath), where the server then never starts.
cd /d "%~dp0.."
"%~dp0..\f2_server.exe" > "%~dp0..\server-console.log" 2>&1
