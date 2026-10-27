@echo off
cd /d "%~dp0"
py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
 py -3.12 launch.py
 goto end
)
py -3 launch.py
:end
pause
