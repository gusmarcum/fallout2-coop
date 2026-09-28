@echo off
rem Solo co-op test: drop a quest monster beside you (the Klamath rat god, with his own script).
cd /d "%~dp0"
call "%~dp0test-settings.cmd"
title SOLO TEST - quest monster
echo.
python "%~dp0tools\test_tool.py" quest --admin %TEST_ADMIN%
echo.
pause
