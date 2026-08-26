@echo off
REM ========================================================
REM IPC-Monitor · Windows 单文件 EXE 打包（可选，用户说"可选可不选"）
REM   前提：
REM     1) Python 3.11 + 所有依赖 requirements.txt + torch CPU 都已装
REM     2) pyinstaller 已存在于 Scripts/pyinstaller.exe（脚本会自动 pip install）
REM   产物：
REM     dist\IPC-Monitor.exe    (~350-500 MB, 单文件一键运行)
REM   用法：
REM     1) 把 4 个权重文件（best.pt / best.onnx / models/*.dat）
REM        跟 IPC-Monitor.exe 放同一个文件夹（或同目录 data/ models/ 按 README 结构）
REM     2) 双击运行 IPC-Monitor.exe → 首次启动缺依赖会弹窗让用户装
REM ========================================================
setlocal EnableExtensions
cd /d %~dp0
chcp 65001 >nul

echo [STEP 1/4] 检查 pyinstaller 是否可用...
where pyinstaller >nul 2>nul
if ERRORLEVEL 1 (
    echo   未安装，正在用 pip 安装 pyinstaller...
    python -m pip install pyinstaller>=6.10.0
    if ERRORLEVEL 1 (
        echo [ERROR] pyinstaller 安装失败，请手动执行：python -m pip install pyinstaller
        pause
        exit /b 1
    )
)
pyinstaller --version

echo.
echo [STEP 2/4] 清理旧 build dist...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo.
echo [STEP 3/4] 打包（PyInstaller --onefile --windowed 不弹黑色命令行窗口）...
REM   --hidden-import 兜底：防止 PyInstaller 漏收 torch/dlib/cv2/ultralytics 动态模块
pyinstaller --noconfirm --clean ^
  --onefile --windowed ^
  --name IPC-Monitor ^
  --icon NUL ^
  --hidden-import=PyQt5 ^
  --hidden-import=PyQt5.QtCore --hidden-import=PyQt5.QtGui --hidden-import=PyQt5.QtWidgets ^
  --hidden-import=cv2 --hidden-import=numpy --hidden-import=dlib ^
  --hidden-import=torch --hidden-import=torchvision --hidden-import=torchaudio ^
  --hidden-import=ultralytics ^
  --collect-all=dlib --collect-all=torch --collect-all=ultralytics ^
  --add-data "resources;resources" ^
  main.py

if ERRORLEVEL 1 (
    echo.
    echo [ERROR] PyInstaller 打包失败。
    echo   常见原因：
    echo    1) 缺少 VC++ 2015-2022 x64 Redistributable -> 去微软官网下安装
    echo    2) torch ultralytics 动态 DLL 找不到 -> 确保用 python -m pip 装的 torch==2.13.0+cpu
    echo    3) 杀毒软件误杀 PyInstaller bootloader -> 把项目目录加入白名单
    pause
    exit /b 2
)

echo.
echo [STEP 4/4] 完成！查看 dist\IPC-Monitor.exe
dir dist
echo.
echo 注意：
echo   1. EXE 不自带 4 个超大权重：请把 best.pt / best.onnx / models/*.dat 放到 EXE 同目录
echo   2. data/config.json 要从 config.sample.json 复制后改自己的摄像头账号密码
echo   3. 想让别人直接下的用：把 IPC-Monitor.exe + 4 个权重 + config.sample.json + README.md 打包 zip
pause
endlocal
