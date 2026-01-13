@echo off
chcp 65001 >nul
title 大物实验报告生成器 v2.0 启动器

echo ====================================================
echo      大物实验报告生成器 v2.0 - 一键启动脚本
echo ====================================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8 或以上版本。
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b
)

:: 检查 XeLaTeX
xelatex --version >nul 2>&1
if errorlevel 1 (
    echo [警告] 未检测到 XeLaTeX，PDF 编译功能将无法使用。
    echo 请安装 TeX Live 或 MiKTeX。
    echo.
    echo 你仍然可以继续运行，但只能生成 LaTeX 源码。
    echo.
    pause
)

:: 检查/创建虚拟环境
if not exist "venv" (
    echo [信息] 正在创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b
    )
)

:: 激活虚拟环境
call venv\Scripts\activate

:: 安装依赖
if not exist "node_modules\.installed" (
    echo [信息] 正在安装/更新依赖库...
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    if errorlevel 1 (
        echo [错误] 依赖安装失败。
        pause
        exit /b
    )
    echo. > node_modules\.installed
)

:: 启动应用
echo.
echo [成功] 环境准备就绪！
echo [信息] 正在启动服务器...
echo [提示] 如果浏览器没有自动打开，请手动访问 http://localhost:5000
echo.
echo 按 Ctrl+C 可以停止服务器
echo.

:: 自动打开浏览器
start http://localhost:5000

:: 运行 Flask
python app.py

pause
