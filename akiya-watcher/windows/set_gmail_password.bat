@echo off
rem === save Gmail app password as environment variable ===
set /p PW=Gmail app password wo koko ni harituke shite Enter:
setx GMAIL_APP_PASSWORD "%PW%"
echo.
echo ===== HOZON SHIMASHITA (atarashii mado kara yuukou) =====
pause
