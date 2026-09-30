@echo off
REM ==========================================================
REM  PULSO IA - actualizacion silenciosa para Tarea Programada
REM  No abre nada. Deja registro en auto_update.log
REM ==========================================================
cd /d "%~dp0"
python fetch_news.py >> auto_update.log 2>&1
if errorlevel 1 (
  py fetch_news.py >> auto_update.log 2>&1
)
exit /b 0
