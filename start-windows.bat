@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo First run: py -3 -m venv .venv
  echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8765 in your browser.
.venv\Scripts\python.exe server.py
pause
