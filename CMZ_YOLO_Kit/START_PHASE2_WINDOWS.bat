@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3.12 phase2_launch.py
) else (
  python phase2_launch.py
)
pause
