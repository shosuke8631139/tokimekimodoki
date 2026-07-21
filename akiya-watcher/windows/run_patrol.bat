@echo off
rem === silent patrol (used by Task Scheduler) ===
cd /d "%~dp0.."
if not exist data mkdir data
.venv\Scripts\python -m akiya_watcher.main --config config.yaml --report data\report.html >> data\watch.log 2>&1
