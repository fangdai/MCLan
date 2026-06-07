@echo off
REM mclan - pull-and-run LAN Minecraft server (zero install on Windows).
REM Double-click this file to start the friendly setup, or pass options:
REM   start.bat                         (beginner wizard - just answer the questions)
REM   start.bat up --version 1.20.4     (advanced)
setlocal
cd /d "%~dp0"

REM Preferred path: native PowerShell edition. Ships with every modern Windows,
REM so there is NOTHING to install (other than Java, which Minecraft needs).
where powershell >nul 2>nul
if %ERRORLEVEL%==0 (
  if "%~1"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0mclan.ps1" play
  ) else (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0mclan.ps1" %*
  )
  goto :done
)

REM Fallback: Python edition (identical features) if PowerShell is unavailable.
set "PYCMD="
where py >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
  where python >nul 2>nul && set "PYCMD=python"
)
if defined PYCMD (
  if "%~1"=="" ( %PYCMD% -m mclan play ) else ( %PYCMD% -m mclan %* )
  goto :done
)

echo.
echo mclan could not find PowerShell or Python on this system.
echo PowerShell ships with Windows, so this is unusual - try running from a normal
echo Command Prompt, or install Python from https://python.org/downloads
echo.

:done
echo.
echo (The server has stopped. You can close this window.)
pause
