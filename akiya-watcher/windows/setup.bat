@echo off
rem === akiya-watcher first-time setup ===
cd /d "%~dp0.."
where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python ga mitsukarimasen. SETUP.md no Step1 wo mite kudasai.
  pause
  exit /b 1
)
py -m venv .venv
call .venv\Scripts\python -m pip install --upgrade pip
call .venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Install ni shippai shimashita. Internet setsuzoku wo kakunin.
  pause
  exit /b 1
)
echo.
echo ===== SETUP KANRYOU (setup complete) =====
pause
