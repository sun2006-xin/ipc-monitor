@echo off
REM ========================================================
REM IPC-Monitor · Windows 源码双击启动 run.bat
REM   作用：
REM     1) 强制 stdout/stderr UTF-8 （避免中文打印 GBK 崩溃）
REM     2) 使用系统 python3.11 / python 启动 main.py
REM     3) 崩了不直接关闭窗口，停住显示 ExitCode 方便拍错误信息
REM ========================================================
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d %~dp0

where python >nul 2>nul
if ERRORLEVEL 1 (
    echo [ERROR] 没找到 Python。去 https://www.python.org/downloads/release/python-3119/ 安装并勾选 "Add Python to PATH"。
    echo.
    pause
    exit /b 1
)

echo [IPC-Monitor] 使用 Python 解释器：
python --version
echo.
echo [IPC-Monitor] 正在启动 main.py...
python main.py
set EXITCODE=%ERRORLEVEL%
echo.
echo ===========================================
echo 程序已退出 ExitCode=%EXITCODE%
echo   (如果 0 正常关闭；否则请保存上方错误信息用于排查)
echo ===========================================
pause
endlocal
