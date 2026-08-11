@echo off
title DailyCheckApp Server
chcp 65001 >nul
cls
echo ============================================================
echo           Starting DailyCheckApp Server...
echo ============================================================
echo.
echo Current Directory: %~dp0
echo Opening Browser at: http://127.0.0.1:5000
echo.

cd /d "%~dp0"

REM Open browser after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    python app.py
)

pause
