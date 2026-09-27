@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem ===========================================================================
rem  Fallout 2 Co-op: start the server
rem
rem  Put this file, f2_server.exe and fallout2-ce.exe in a COPY of your
rem  Fallout 2 folder, next to master.dat, and double-click it. That folder is
rem  the co-op world; its saves live in data\SAVEGAME.
rem ===========================================================================

rem Ignore server settings left over in the environment.
for %%v in (F2_SERVER_MAP F2_SERVER_LOAD F2_SERVER_CMD F2_SERVER_HOST) do set "%%v="

rem ---- Settings you can change ----------------------------------------------
rem  Game port that players join. join.cmd assumes 9300 unless the address
rem  it is given ends in :port.
if not defined F2_COOP_PORT set "F2_COOP_PORT=9300"
rem  Name shown to players when they connect.
set "SERVER_NAME=Fallout 2 Co-op"
rem  Admin console: off. It has no password and listens on every network, so
rem  anyone who can reach its port controls the world. To use it yourself,
rem  remove "rem" from the next line, and never forward that port.
rem set "F2_SERVER_CMD=9301"
rem ---------------------------------------------------------------------------

cd /d "%~dp0"
title Fallout 2 Co-op server

if not exist "%~dp0f2_server.exe" (
    echo f2_server.exe is not in this folder.
    echo Extract the whole release zip into your Fallout 2 folder copy, then run
    echo start-server.cmd again.
    goto :fail
)
if not exist "%~dp0master.dat" (
    echo There is no master.dat here, so this is not a Fallout 2 folder.
    echo Copy your Fallout 2 folder somewhere new, extract the release zip into
    echo that copy, and run start-server.cmd from there.
    goto :fail
)

set "HAVE_PS=1"
where powershell >nul 2>&1 || set "HAVE_PS="

rem The newest co-op save: slots 11-15 are autosaves, 16 is the F6 quicksave.
set "NEWEST="
if defined HAVE_PS for /f "usebackq delims=" %%s in (`powershell -NoProfile -NonInteractive -Command "$f = Get-ChildItem -Path 'data\SAVEGAME\SLOT1[1-6]\SAVE.DAT' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1; if ($f -and $f.Directory.Name -match '^SLOT(\d+)$') { [int]$Matches[1] }"`) do set "NEWEST=%%s"

echo.
echo Saves in this world:
if defined HAVE_PS (
    powershell -NoProfile -NonInteractive -Command "$l = @(Get-ChildItem -Path 'data\SAVEGAME\SLOT*\SAVE.DAT' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending); if ($l.Count -eq 0) { '  none yet' }; foreach ($f in $l) { if ($f.Directory.Name -match '^SLOT(\d+)$') { $n = [int]$Matches[1]; $k = 'save'; if ($n -ge 11) { $k = 'autosave' }; if ($n -eq 16) { $k = 'quicksave (F6)' }; '  slot {0,2}   {1:yyyy-MM-dd HH:mm}   {2}' -f $n, $f.LastWriteTime, $k } }"
) else (
    dir /b "data\SAVEGAME" 2>nul
)

set "TRIES=0"
:ask
set /a TRIES+=1
if %TRIES% gtr 10 goto :no_answer
echo.
if defined NEWEST (
    echo Press Enter to continue the newest co-op save, slot %NEWEST%.
    echo Or type a slot number from the list, or NEW for a new game.
) else if defined HAVE_PS (
    echo Press Enter to start a new game at the Temple of Trials,
    echo or type a slot number from the list to load it.
) else (
    echo Type NEW for a new game, or a slot number to load it.
)
set "CHOICE="
set /p "CHOICE=> "
if not defined CHOICE goto :choice_empty
set "CHOICE=%CHOICE:"=%"
if not defined CHOICE goto :choice_empty
if /i "%CHOICE%"=="new" goto :confirm_new
set "LOAD="
for /l %%i in (1,1,16) do if "%CHOICE%"=="%%i" set "LOAD=%%i"
if not defined LOAD (
    echo "%CHOICE%" is not a slot number from 1 to 16, or NEW.
    goto :ask
)
set "PAD=0%LOAD%"
if not exist "data\SAVEGAME\SLOT%PAD:~-2%\SAVE.DAT" (
    echo Slot %LOAD% is empty.
    goto :ask
)
goto :load

:choice_empty
if defined NEWEST (
    set "LOAD=%NEWEST%"
    goto :load
)
if defined HAVE_PS goto :new
goto :ask

:confirm_new
if not defined NEWEST goto :new
echo.
echo A new game starts over at the Temple of Trials, and its autosaves and
echo quicksave then replace this world's slots 11 to 16 as you play. To keep
echo this world, close this window and make a separate copy of the folder first.
set "SURE="
set /p "SURE=Start a new game anyway? (y/n) "
if not defined SURE goto :ask
set "SURE=%SURE:"=%"
if /i "%SURE%"=="y" goto :new
goto :ask

:load
set "F2_SERVER_LOAD=%LOAD%"
set "WHAT=loading slot %LOAD%"
goto :start

:new
set "F2_SERVER_MAP=artemple.map"
set "WHAT=new game"

:start
set "F2_SERVER_NET=%F2_COOP_PORT%"
set "F2_SERVER_PACE_MS=100"
set "F2_AUTOSAVE_SECS=300"
set "F2_SERVER_KEEPALIVE=1"
set "F2_SERVER_NAME=%SERVER_NAME%"
title Fallout 2 Co-op server - port %F2_COOP_PORT%
echo.
echo ============================================================================
echo  Fallout 2 Co-op server: %WHAT%, port %F2_COOP_PORT%
echo.
echo  Everyone joins with join.cmd. On this PC, leave the address empty.
echo  Friends use this PC's ZeroTier address. Never forward the port to the
echo  internet: it has no password.
echo  Autosaves every 5 minutes into slots 11-15. F6 in game quicksaves to 16.
echo.
echo  Don't click inside this window: Windows pauses the server while text in
echo  it is selected. If the game freezes, click here and press Esc.
echo  To stop the server, press F6 in game, then close this window.
echo ============================================================================
echo.
"%~dp0f2_server.exe"
echo.
echo The server has stopped.
goto :fail

:no_answer
echo.
echo No usable answer was typed. Double-click start-server.cmd to try again.

:fail
echo.
pause
endlocal
