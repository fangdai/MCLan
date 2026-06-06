@echo off
REM mclan - pull-and-run LAN Minecraft server.
REM Usage: start.bat [extra args passed to `mclan up`]
REM   start.bat
REM   start.bat --version 1.20.4 --memory 4096
setlocal
cd /d "%~dp0"

REM Find a Python launcher.
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 -m mclan up %*
  goto :eof
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python -m mclan up %*
  goto :eof
)

echo mclan needs Python 3.8+ on PATH. Install from https://python.org and re-run. 1>&2
exit /b 1
