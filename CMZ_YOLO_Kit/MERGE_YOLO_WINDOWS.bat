@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First open START_SCOUT_WINDOWS.bat to prepare the scout environment.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "merge_yolo_scans.py"
pause
