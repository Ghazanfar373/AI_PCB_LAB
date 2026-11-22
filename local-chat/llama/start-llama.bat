@echo off
setlocal
cd /d "%~dp0"
for /f "delims=" %%F in ('dir /s /b llama-server.exe 2^>nul') do set "SERVER=%%F"
if not defined SERVER (
  echo llama-server.exe was not found. The CUDA build may still be extracting.
  pause
  exit /b 1
)
set "MODEL=%USERPROFILE%\.ollama\models\blobs\sha256-1194192cf2a187eb02722edcc3f77b11d21f537048ce04b67ccf8ba78863006a"
echo.
echo llama-server: http://127.0.0.1:8080/v1
echo Model: qwen3-coder
echo Leave this window open. Closing it stops the model.
echo.
"%SERVER%" -m "%MODEL%" --alias qwen3-coder -c 8192 --fit on --fit-ctx 8192 --host 127.0.0.1 --port 8080
pause
