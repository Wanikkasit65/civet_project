@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Open START_SCOUT_WINDOWS.bat in this folder once to prepare its environment.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "auto_review.py"
pause
