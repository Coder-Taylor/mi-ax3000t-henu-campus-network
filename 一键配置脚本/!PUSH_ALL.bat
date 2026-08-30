@echo off
title Push Tool - Gitee + GitHub
setlocal enabledelayedexpansion

echo ========================================
echo   Push Tool - Gitee + GitHub
echo ========================================
echo.

cd /d "%~dp0.."
echo Repo dir: %CD%
echo.

echo [1/2] Push to Gitee + GitHub (via origin multi-URL)...
git push origin --all
if %errorlevel% equ 0 (
    echo [OK] push succeeded
    set PUSH_OK=1
) else (
    echo [FAIL] push failed (network / auth / handshake)
    set PUSH_OK=0
)

echo.
echo [2/2] Retry push (some remotes may succeed on retry)...
git push origin --all
if %errorlevel% equ 0 (
    echo [OK] retry succeeded
    set PUSH_OK=1
) else (
    echo [FAIL] retry also failed
)

echo.
echo ========================================
if !PUSH_OK! equ 1 (
    echo [OK] All pushes completed.
) else (
    echo [FAIL] Push failed. Check network and authentication.
    echo.
    echo Manual options:
    echo   1) gh repo sync Coder-Taylor/mi-ax3000t-henu-campus-network
    echo   2) git push github --all   (after setting SSH key)
    echo   3) Check git remote -v for stored tokens
)
echo ========================================
pause
