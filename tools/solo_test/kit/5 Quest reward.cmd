@echo off
rem Solo co-op test: pay a 500 point award the way play pays one.
cd /d "%~dp0"
call "%~dp0test-settings.cmd"
title SOLO TEST - quest reward
echo.
python "%~dp0tools\test_tool.py" reward 500 --admin %TEST_ADMIN%
echo.
pause
