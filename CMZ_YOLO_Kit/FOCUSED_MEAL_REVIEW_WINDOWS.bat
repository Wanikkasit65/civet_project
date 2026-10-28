@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run this file from the same folder as START_SCOUT_WINDOWS.bat and its prepared .venv.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "focused_meal_review.py"
pause
