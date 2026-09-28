@echo off
rem Solo co-op test: stop the test server. Nothing from the test is saved.
cd /d "%~dp0"
call "%~dp0test-settings.cmd"
title SOLO TEST - stop
echo.
python "%~dp0tools\test_tool.py" stop --admin %TEST_ADMIN%
echo.
pause
