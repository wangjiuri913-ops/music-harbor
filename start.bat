@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if not exist ".venv\Scripts\python.exe" goto create

:check
".venv\Scripts\python.exe" -c "import flask, requests" >nul 2>nul
if errorlevel 1 goto install
goto run

:create
echo [*] Creating virtual environment...
python -m venv .venv
if errorlevel 1 goto failed
goto check

:install
echo [*] Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

:run
echo [*] Starting MusicHarbor at http://127.0.0.1:8000
".venv\Scripts\python.exe" app.py
exit /b 0

:failed
echo [!] Setup failed. Install Python 3.10+ and make sure "python" is on PATH.
pause
exit /b 1
