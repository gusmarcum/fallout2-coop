@echo off
rem Solo co-op test: show both characters' level and experience.
cd /d "%~dp0"
call "%~dp0test-settings.cmd"
title SOLO TEST - character sheets
echo.
python "%~dp0tools\test_tool.py" sheets --admin %TEST_ADMIN%
echo.
pause
