@echo off
rem === run patrol once and open the report ===
cd /d "%~dp0.."
.venv\Scripts\python -m akiya_watcher.main --config config.yaml --report data\report.html
if exist data\report.html start "" data\report.html
pause
