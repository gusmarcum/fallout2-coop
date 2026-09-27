@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem ===========================================================================
rem  Fallout 2 Co-op: join a game
rem
rem  Put this file and fallout2-ce.exe in your Fallout 2 folder, next to
rem  master.dat, and double-click it. The first time, it asks for your name and
rem  the server's address and saves them in join-settings.cmd. Delete that file
rem  to change them.
rem
rem  Your name is your character: use the same one every time, and a different
rem  one from your friends. Letters, digits, - and _ only, up to 31 characters.
rem ===========================================================================

rem Game port used when the address has no :port on the end.
if not defined F2_COOP_PORT set "F2_COOP_PORT=9300"

cd /d "%~dp0"
title Fallout 2 Co-op

if not exist "%~dp0fallout2-ce.exe" (
    echo fallout2-ce.exe is not in this folder.
    echo Extract the release zip into your Fallout 2 folder, then run join.cmd again.
    goto :fail
)
if not exist "%~dp0master.dat" (
    echo There is no master.dat here, so this is not a Fallout 2 folder.
    echo Put join.cmd and fallout2-ce.exe in your Fallout 2 folder and run it there.
    goto :fail
)

set "HAVE_PS=1"
where powershell >nul 2>&1 || set "HAVE_PS="

set "PLAYER_NAME="
set "SERVER_ADDRESS="
set "ASKED="
set "TRIES=0"
if exist "%~dp0join-settings.cmd" call "%~dp0join-settings.cmd"

:ask_name
if defined PLAYER_NAME goto :check_name
set /a TRIES+=1
if %TRIES% gtr 10 goto :no_answer
echo.
echo Pick your character name. Use the same one every time, and a different
echo one from your friends. Letters, digits, - and _ only, no spaces.
set /p "PLAYER_NAME=Name: "
set "ASKED=1"
:check_name
if not defined PLAYER_NAME goto :ask_name
if not defined HAVE_PS goto :ask_address
powershell -NoProfile -NonInteractive -Command "if ($env:PLAYER_NAME -match '^[A-Za-z0-9_-]{1,31}$') { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo That name won't work. Use 1 to 31 letters, digits, - or _, with no spaces.
    set "PLAYER_NAME="
    goto :ask_name
)

:ask_address
if defined SERVER_ADDRESS goto :check_address
set /a TRIES+=1
if %TRIES% gtr 10 goto :no_answer
echo.
echo Server address: the host's ZeroTier IP, for example 10.147.17.23.
echo If the server runs on this PC, just press Enter.
set /p "SERVER_ADDRESS=Address: "
if not defined SERVER_ADDRESS set "SERVER_ADDRESS=127.0.0.1"
set "ASKED=1"
:check_address
if not defined HAVE_PS goto :save
powershell -NoProfile -NonInteractive -Command "if ($env:SERVER_ADDRESS -match '^[A-Za-z0-9.-]+(:[0-9]{1,5})?$') { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo That doesn't look like an address. Use something like 10.147.17.23
    set "SERVER_ADDRESS="
    goto :ask_address
)

:save
if defined ASKED (
    > "%~dp0join-settings.cmd" (
        echo @rem Saved by join.cmd. Delete this file to pick a new name or address.
        echo set "PLAYER_NAME=%PLAYER_NAME%"
        echo set "SERVER_ADDRESS=%SERVER_ADDRESS%"
    )
    echo Saved your name and address in join-settings.cmd.
)

set "CONNECT=%SERVER_ADDRESS%"
if "%SERVER_ADDRESS::=%"=="%SERVER_ADDRESS%" set "CONNECT=%SERVER_ADDRESS%:%F2_COOP_PORT%"

set "F2_CLIENT_CONNECT=%CONNECT%"
set "F2_PLAYER_NAME=%PLAYER_NAME%"
set "F2_PLAYER_CREATE=ask"
title Fallout 2 Co-op - %PLAYER_NAME%
echo.
echo Joining %CONNECT% as %PLAYER_NAME%.
echo The first time the server sees your name, you make your character.
"%~dp0fallout2-ce.exe"
if errorlevel 1 goto :trouble
endlocal
exit /b 0

:trouble
echo.
echo The game closed with an error. The usual causes:
echo  - Another copy of Fallout 2 is running on this PC. Close it and try again.
echo  - The server is not running yet, or the address is wrong. The address is
echo    saved in join-settings.cmd; delete that file to enter it again.
echo  - Windows Firewall on the host is blocking f2_server.exe.
goto :fail

:no_answer
echo.
echo No usable answer was typed. Double-click join.cmd to try again.

:fail
echo.
pause
endlocal
exit /b 1
