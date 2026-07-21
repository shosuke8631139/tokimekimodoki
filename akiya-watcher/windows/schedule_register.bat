@echo off
rem === register automatic runs: patrol every 3 hours + digest Sunday 8:00 ===
schtasks /Create /F /SC HOURLY /MO 3 /TN "akiya-watcher patrol" /TR "\"%~dp0run_patrol.bat\""
schtasks /Create /F /SC WEEKLY /D SUN /ST 08:00 /TN "akiya-watcher digest" /TR "\"%~dp0run_digest.bat\""
echo.
echo ===== TOUROKU KANRYOU. Yameru toki wa schedule_remove.bat =====
pause
