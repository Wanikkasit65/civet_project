@echo off
cd /d "%~dp0"
echo This installs YOLO in a separate environment on first use.
echo Run ONLY after boxes, background labels and splits have been reviewed.
set /p cmz_answer="Type YES to continue, or press Enter to cancel: "
if /i not "%cmz_answer%"=="YES" goto end
py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
 py -3.12 launch.py train
 goto end
)
py -3 launch.py train
:end
pause
