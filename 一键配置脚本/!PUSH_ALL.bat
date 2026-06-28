@echo off
title 推送到 Gitee + GitHub
chcp 65001 >nul

echo ========================================
echo  双仓库推送工具 (Gitee + GitHub)
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/2] 正在推送到 Gitee...
git push origin --all
if %errorlevel% equ 0 (
    echo ✅ Gitee 推送成功
) else (
    echo ❌ Gitee 推送失败
    echo   可能原因：网络问题或认证失效
)

echo.
echo [2/2] 正在推送到 GitHub...
git push origin --all
if %errorlevel% equ 0 (
    echo ✅ GitHub 推送成功
) else (
    echo ❌ GitHub 推送失败
    echo   可能原因：未登录 GitHub / Token 过期 / 网络问题
    echo.
    echo 请尝试手动登录后再运行本脚本：
    echo   git remote set-url --add origin https://YOUR_TOKEN@github.com/Coder-Taylor/mi-ax3000t-henu-campus-network.git
)

echo.
echo ========================================
if %errorlevel% equ 0 (echo ✅ 全部推送完成) else (echo ⚠️ 部分推送失败，请查看上方错误信息)
echo ========================================
pause
