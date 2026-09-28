@echo off
rem Solo co-op test: drop two raiders beside you. They do nothing until you attack.
cd /d "%~dp0"
call "%~dp0test-settings.cmd"
title SOLO TEST - two raiders
echo.
python "%~dp0tools\test_tool.py" raiders --admin %TEST_ADMIN%
echo.
pause
