@echo off
REM mclan - pull-and-run LAN Minecraft server.
REM Double-click this file to start the friendly setup, or pass options:
REM   start.bat                         (beginner wizard - just answer the questions)
REM   start.bat up --version 1.20.4     (advanced: skip the wizard)
setlocal
cd /d "%~dp0"

REM Find a Python launcher.
set "PYCMD="
where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
  where python >nul 2>nul && set "PYCMD=python"
)

if not defined PYCMD (
  echo.
  echo mclan needs Python 3.8 or newer, and it's not installed yet.
  echo Get it free from https://python.org/downloads
  echo IMPORTANT: during install, tick "Add Python to PATH".
  echo Then double-click this file again.
  echo.
  pause
  exit /b 1
)

REM No arguments -> beginner wizard. Arguments -> pass straight through.
if "%~1"=="" (
  %PYCMD% -m mclan play
) else (
  %PYCMD% -m mclan %*
)

echo.
echo (The server has stopped. You can close this window.)
pause
