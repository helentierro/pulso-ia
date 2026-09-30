@echo off
REM ==========================================================
REM  PULSO IA - servidor local (recomendado)
REM  Evita los bloqueos de file:// y permite recarga real.
REM  Ctrl+C para cerrar.
REM ==========================================================
title Pulso IA - servidor local
cd /d "%~dp0"
start "" "http://localhost:8765/index.html"
python -m http.server 8765
