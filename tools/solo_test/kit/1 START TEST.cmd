@echo off
setlocal EnableExtensions
rem ===========================================================================
rem  Solo co-op test, step 1: the test server and the stand-in for your friend.
rem
rem  One PC runs one game, so you cannot open a second client for the second
rem  player. This window holds their seat instead and tells you what their
rem  screen is being sent and what every experience award paid to whom.
rem
rem  Leave this window open, then run "2 JOIN.cmd".
rem ===========================================================================
cd /d "%~dp0"
call "%~dp0test-settings.cmd"
title SOLO TEST - stand-in for %FRIEND_NAME% (leave open)

if not exist "%~dp0f2_server.exe" (
    echo f2_server.exe is not in this folder.
    goto :fail
)
if not exist "%~dp0master.dat" (
    echo There is no master.dat here, so this is not a Fallout 2 folder.
    goto :fail
)
where python >nul 2>&1
if errorlevel 1 (
    echo Python is not installed, or not on the PATH. The stand-in is a Python script.
    goto :fail
)
if not exist "%~dp0test-save\%SAVE_DIR%\SAVE.DAT" (
    echo The test save is missing: test-save\%SAVE_DIR%
    goto :fail
)

rem A test server left over from an earlier run would hold the port.
python "%~dp0tools\test_tool.py" stop --admin %TEST_ADMIN% >nul 2>&1
ping -n 3 127.0.0.1 >nul

rem Every run starts from the same save, so a test never depends on the last one.
robocopy "%~dp0test-save\%SAVE_DIR%" "%~dp0data\SAVEGAME\%SAVE_DIR%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo Could not put the test save in place.
    goto :fail
)

set "F2_SERVER_LOAD=%SAVE_SLOT%"
set "F2_SERVER_NET=%TEST_NET%"
set "F2_SERVER_CMD=%TEST_ADMIN%"
set "F2_SERVER_PACE_MS=100"
set "F2_SERVER_HOST=%HOST_NAME%"
set "F2_SERVER_NAME=Solo test"
rem Nothing is kept: no autosaves, and the server stops when the last player leaves.
set "F2_AUTOSAVE_SECS=0"
set "F2_SERVER_KEEPALIVE=0"

del "%~dp0server-console.log" >nul 2>&1
start "SOLO TEST - server (leave open)" /min "%~dp0tools\run-server.cmd"

python "%~dp0tools\stand_in.py" --name %FRIEND_NAME% --port %TEST_NET% --admin %TEST_ADMIN% --log "%~dp0server-console.log"

rem The stand-in ended (Ctrl+C, or the server went away): take the server down with it.
python "%~dp0tools\test_tool.py" stop --admin %TEST_ADMIN% >nul 2>&1
echo.
echo The test is over. Nothing from it was saved.
pause
endlocal
exit /b 0

:fail
echo.
pause
endlocal
exit /b 1
