@echo off
REM ==========================================================
REM  PULSO IA - descarga las noticias y abre la web
REM  Doble clic en este archivo.
REM ==========================================================
title Pulso IA - Actualizar
cd /d "%~dp0"

echo.
echo  Descargando noticias de IA desde 24 fuentes...
echo.
python fetch_news.py
if errorlevel 1 (
  echo.
  echo  [Aviso] No se pudo usar 'python'. Probando con 'py'...
  py fetch_news.py
)
if errorlevel 1 (
  echo.
  echo  [ERROR] Ninguna variante de Python funciono.
  echo  Instala Python desde https://www.python.org/downloads/
  echo  recuerda marcar "Add Python to PATH" durante la instalacion.
  echo.
  pause
  exit /b 1
)

echo.
echo  Listo. Abriendo Pulso IA...
start "" "index.html"
exit /b 0
