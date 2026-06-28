@echo off
title 双仓库推送 (Gitee + GitHub)
chcp 65001 >nul

setlocal enabledelayedexpansion

echo ========================================
echo  双仓库推送工具
echo  Gitee + GitHub
echo ========================================
echo.

cd /d "%~dp0.."
echo 仓库目录：%CD%
echo.

echo [1/2] 推送到 Gitee...
git push origin --all
if %errorlevel% equ 0 (
    echo ✅ Gitee 推送成功
    set GITEE_OK=1
) else (
    echo ❌ Gitee 推送失败
    echo   可能原因：网络问题或认证失效
    set GITEE_OK=0
)

echo.
echo [2/2] 推送到 GitHub...
echo   当前 origin 配置了多个 pushurl，git push 会尝试所有
git push origin --all
if %errorlevel% equ 0 (
    echo ✅ GitHub 推送成功
    set GH_OK=1
) else (
    echo ❌ GitHub 推送失败
    set GH_OK=0
)

echo.
echo ========================================
if !GITEE_OK! equ 1 (
    if !GH_OK! equ 1 (
        echo ✅ 全部推送成功
    ) else (
        echo ⚠️ Gitee 成功，GitHub 失败
        echo.
        echo 如需手动推送 GitHub，请用以下方式之一：
        echo.
        echo 方式1: 使用 GitHub CLI
        echo   gh repo sync Coder-Taylor/mi-ax3000t-henu-campus-network
        echo.
        echo 方式2: 添加 Token 到远程 URL
        echo   git remote set-url --add origin https://YOUR_TOKEN@github.com/Coder-Taylor/mi-ax3000t-henu-campus-network.git
        echo   （YOUR_TOKEN 替换为 GitHub Personal Access Token）
        echo.
        echo 方式3: 设置 SSH 密钥后使用
        echo   git remote add github git@github.com:Coder-Taylor/mi-ax3000t-henu-campus-network.git
        echo   git push github --all
    )
) else (
    echo ❌ 推送失败，请检查网络连接和认证状态
)
echo ========================================
pause
