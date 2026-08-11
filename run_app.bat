@echo off
title DailyCheckApp Server
chcp 65001 >nul
cls
echo ============================================================
echo           🚀 جاري تشغيل تطبيق DailyCheckApp...
echo ============================================================
echo.
echo 📍 المسار الحالي: %~dp0
echo 🌐 سيتم فتح الصفحة تلقائياً في المتصفح على: http://127.0.0.1:5000
echo.

cd /d "%~dp0"

REM فتح المتصفح بعد 2 ثانية لضمان بدء خادم Flask
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" app.py
) else (
    python app.py
)

pause
