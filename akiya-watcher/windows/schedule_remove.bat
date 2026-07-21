@echo off
rem === remove automatic runs ===
schtasks /Delete /F /TN "akiya-watcher patrol"
schtasks /Delete /F /TN "akiya-watcher digest"
echo ===== KAIJO KANRYOU =====
pause
