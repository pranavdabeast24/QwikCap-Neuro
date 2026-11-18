@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" goto setup
if not exist "desktop.py" goto incomplete
".venv\Scripts\python.exe" -c "import tkinter, PIL, pypdfium2, reportlab, pypdf, openpyxl, defusedxml" >nul 2>&1
if errorlevel 1 goto setup
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0desktop.py"
exit /b 0

:setup
echo QuickCap (CV) needs a local Python environment with Tk and the application requirements.
echo In this folder, run these commands yourself:
echo   py -3.12 -m venv .venv
echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
echo Then run start-desktop-windows.bat again.
pause
exit /b 1

:incomplete
echo desktop.py is missing. Restore the complete QuickCap (CV) source folder.
pause
exit /b 1
