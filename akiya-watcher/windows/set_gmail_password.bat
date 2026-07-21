@echo off
rem === save Gmail address and app password as environment variables ===
set /p USR=Gmail address wo nyuryoku shite Enter:
set /p PW=Gmail app password wo koko ni harituke shite Enter:
setx GMAIL_USERNAME "%USR%"
setx GMAIL_APP_PASSWORD "%PW%"
echo.
echo ===== HOZON SHIMASHITA (atarashii mado kara yuukou) =====
pause
