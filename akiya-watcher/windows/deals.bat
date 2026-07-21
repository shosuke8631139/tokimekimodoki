@echo off
rem === deal notebook (shoudan note) ===
cd /d "%~dp0.."
.venv\Scripts\python -m akiya_watcher.deals --config config.yaml
pause
