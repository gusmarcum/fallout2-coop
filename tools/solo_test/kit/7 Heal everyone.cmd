@echo off
rem Solo co-op test: pass an hour and heal both characters, for another round.
cd /d "%~dp0"
call "%~dp0test-settings.cmd"
title SOLO TEST - heal everyone
echo.
python "%~dp0tools\test_tool.py" heal --admin %TEST_ADMIN%
echo.
pause
