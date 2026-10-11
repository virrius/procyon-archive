@echo off
rem Только воркер (ComfyUI уже должен быть поднят и слушать 8188).
rem Запускать двойным кликом или из терминала.
rem   start_worker_only.bat                            -> адрес из ..\.env
rem   start_worker_only.bat http://localhost:8000      -> разово в другой Archive

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

cd /d %~dp0
echo Archive: %PA_SERVER_URL%
F:\comfyui\venv\Scripts\python.exe gen_worker.py
