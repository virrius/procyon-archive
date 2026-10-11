@echo off
rem Поднимает ComfyUI + gen_worker каждый в своём окне. Запускать двойным кликом
rem или из терминала:
rem   start_gen.bat                            -> адрес Archive из ..\.env
rem   start_gen.bat http://localhost:8000      -> разово в другой Archive

set ENVFILE=%~dp0..\.env
set PA_WORKER_TOKEN=
set PA_SERVER_URL=

for /f "tokens=1,* delims==" %%a in ('findstr /b "PA_WORKER_TOKEN=" "%ENVFILE%"') do set PA_WORKER_TOKEN=%%b
for /f "tokens=1,* delims==" %%a in ('findstr /b "PA_SERVER_URL=" "%ENVFILE%"') do set PA_SERVER_URL=%%b

if not "%~1"=="" set "PA_SERVER_URL=%~1"

if "%PA_WORKER_TOKEN%"=="" (
  echo Не нашёл PA_WORKER_TOKEN в %ENVFILE%
  pause
  exit /b 1
)

if "%PA_SERVER_URL%"=="" (
  echo Не нашёл PA_SERVER_URL в %ENVFILE%
  pause
  exit /b 1
)

echo Запускаю ComfyUI...
start "ComfyUI" cmd /k "cd /d F:\comfyui && venv\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188"

echo Жду, пока ComfyUI поднимется...
:waitloop
timeout /t 3 /nobreak >nul
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8188/system_stats > "%TEMP%\comfy_check.txt" 2>nul
set /p CODE=<"%TEMP%\comfy_check.txt"
if not "%CODE%"=="200" goto waitloop

echo ComfyUI готов. Запускаю воркер на %PA_SERVER_URL%...
start "gen_worker" cmd /k "cd /d %~dp0 && set "PA_SERVER_URL=%PA_SERVER_URL%" && set "PA_WORKER_TOKEN=%PA_WORKER_TOKEN%" && F:\comfyui\venv\Scripts\python.exe gen_worker.py"

echo Готово. Открыты два окна: ComfyUI и gen_worker.
echo Гасить — stop_gen.bat или Ctrl+C в этих окнах.
