@echo off
cd /d "%~dp0"
py -3.12 all_video_launch.py
if errorlevel 1 echo Copy the error above to ChatGPT. Your old project and videos were not changed.
pause
