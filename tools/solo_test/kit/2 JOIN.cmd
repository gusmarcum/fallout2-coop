@echo off
setlocal EnableExtensions
rem ===========================================================================
rem  Solo co-op test, step 2: join the test server as your own character.
rem  Run "1 START TEST.cmd" first and leave its window open.
rem
rem  The game runs in a window so the stand-in's window stays readable next to
rem  it. Remove the F2_WINDOWED line below to play the test full screen.
rem ===========================================================================
cd /d "%~dp0"
call "%~dp0test-settings.cmd"
title Fallout 2 - %HOST_NAME% (SOLO TEST)

set "F2_CLIENT_CONNECT=127.0.0.1:%TEST_NET%"
set "F2_PLAYER_NAME=%HOST_NAME%"
set "F2_PLAYER_CREATE=ask"
set "F2_WINDOWED=1"

"%~dp0fallout2-ce.exe"
if errorlevel 1 goto :trouble
endlocal
exit /b 0

:trouble
echo.
echo The game closed with an error. The usual causes:
echo  - Another copy of Fallout 2 is running on this PC. Close it and try again.
echo  - The test server is not running. Run "1 START TEST.cmd" first.
echo.
pause
endlocal
exit /b 1
