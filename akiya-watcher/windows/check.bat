@echo off
rem === settings health check ===
cd /d "%~dp0.."
.venv\Scripts\python -m akiya_watcher.main --config config.yaml --check
pause
