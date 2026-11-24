@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (set "inventory_python=python") else (set "inventory_python=py -3")
%inventory_python% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
    echo Install Python 3.11 or newer and reopen this launcher.
    pause
    exit /b 1
)
%inventory_python% app.py --menu
pause
