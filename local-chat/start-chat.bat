@echo off
cd /d "%~dp0"
echo.
echo Local chat: http://127.0.0.1:8765/
echo From your phone on Tailscale: http://100.75.227.123:8765/
echo Leave this window open. Closing it stops the page.
echo Chat, Picture, and Animate are on that same page. Do not port-forward it to the internet.
echo.
start "" cmd /c "timeout /t 1 /nobreak >nul & start http://127.0.0.1:8765/"
python serve.py
if errorlevel 1 py -3 serve.py
pause
