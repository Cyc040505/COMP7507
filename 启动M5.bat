@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import dash, pandas, pyarrow, plotly" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements-m5-lock.txt
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" launch_m5.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Could not start. Please read the error above and docs/M5_README.md.
pause
exit /b 1
