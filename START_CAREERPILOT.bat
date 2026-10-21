@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo        CareerPilot AI - Launcher
echo ========================================
if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 goto error
)
call ".venv\Scripts\activate.bat"
echo Installing/checking required packages...
python -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Starting CareerPilot AI...
echo Open http://127.0.0.1:5000 in your browser.
echo Keep this window open while using the app.
python app.py
if errorlevel 1 goto error
pause
exit /b 0
:error
echo.
echo Something went wrong. Read the error message above.
pause
exit /b 1
