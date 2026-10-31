@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"
title AX3000T Fix

echo.
echo ==============================================
echo   AX3000T Campus Network Auto Repair
echo ==============================================
echo.
echo   Keep fix_remote.sh in the SAME folder as this file.
echo.

if not exist "fix_remote.sh" (
    echo [X] fix_remote.sh not found in this folder.
    echo     Put both files together, then run this again.
    goto :end
)

set "ROUTER_IP=192.168.1.1"
set /p "ROUTER_IP=Router IP [press Enter for 192.168.1.1]: "
if "%ROUTER_IP%"=="" set "ROUTER_IP=192.168.1.1"

echo.
echo Target: %ROUTER_IP%
echo Password: the router admin password. Nothing shows while typing.
echo.

where ssh >nul 2>&1
if errorlevel 1 (
    echo [X] ssh not found.
    echo     Windows Settings - Apps - Optional Features - add OpenSSH Client.
    goto :end
)

echo Connecting...
echo.

ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 -o ServerAliveInterval=15 root@%ROUTER_IP% "cat > /tmp/fix_remote.sh && sh /tmp/fix_remote.sh" < fix_remote.sh

set "RC=%ERRORLEVEL%"

echo.
echo ==============================================
if "%RC%"=="0" (
    echo   DONE - network is working
) else (
    echo   NOT FIXED YET - code %RC%
    echo.
    echo   Copy everything above and send it to whoever
    echo   set up this router. It has the diagnostic info.
)
echo ==============================================
echo.

:end
echo.
pause
