@echo off
rem Гасит окна ComfyUI и gen_worker, запущенные start_gen.bat.

taskkill /FI "WINDOWTITLE eq gen_worker*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq ComfyUI*" /T /F >nul 2>&1

echo Остановлено (если было запущено).
pause
