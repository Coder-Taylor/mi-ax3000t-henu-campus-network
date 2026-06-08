@echo off
cd /d "%~dp0"
title AX3000T Deploy

:loop
cls
echo.
echo   ======================================
echo     AX3000T Deploy Tool v3.0
echo   ======================================
echo.
echo   [1] Lazy One-Click (recommended)
echo   [2] Interactive Menu
echo   [0] Exit
echo.
set "c="
set /p c="  Select: "

if "%c%"=="1" goto :lazy
if "%c%"=="2" goto :menu
if "%c%"=="0" goto :end
goto :loop

:lazy
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python deploy.py lazy
    goto :loop
)
where python3 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python3 deploy.py lazy
    goto :loop
)
echo Python not found!
pause
goto :loop

:menu
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python deploy.py
    goto :loop
)
where python3 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    python3 deploy.py
    goto :loop
)
echo Python not found!
pause
goto :loop

:end
