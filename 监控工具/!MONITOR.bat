@echo off
cd /d "%~dp0"
title Network Monitor

:loop
cls
echo.
echo   ======================================
echo     AX3000T Network Monitor v2.0
echo   ======================================
echo.
echo   [1] Live Monitor
echo   [2] Stress Test
echo   [3] Compare Results
echo   [0] Exit
echo.
set "c="
set /p c="  Select: "

if "%c%"=="1" goto :live
if "%c%"=="2" goto :stress
if "%c%"=="3" goto :cmp
if "%c%"=="0" goto :end
goto :loop

:live
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python monitor.py live
    goto :loop
)
powershell -ExecutionPolicy Bypass -File "legacy\Monitor.ps1"
pause
goto :loop

:stress
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python monitor.py stress
    goto :loop
)
powershell -ExecutionPolicy Bypass -File "legacy\StressTest.ps1"
pause
goto :loop

:cmp
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python monitor.py compare
    goto :loop
)
powershell -ExecutionPolicy Bypass -File "legacy\Compare.ps1"
pause
goto :loop

:end
