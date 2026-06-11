@echo off
REM Windows Build Script for Network Monitor
REM 直接双击运行即可打包

echo ====================================
echo  📡 Network Monitor - Windows 打包
echo ====================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未找到 Python，请先安装 Python 3.9+
    echo    下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Install deps
echo 📦 安装依赖...
python -m pip install --upgrade pip
python -m pip install pyinstaller flask pywebview pyyaml

if %errorlevel% neq 0 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)

REM Build
echo 🔨 打包中...
python scripts\build_app.py

if %errorlevel% neq 0 (
    echo ❌ 打包失败
    pause
    exit /b 1
)

REM Create ZIP
echo 📀 压缩为 ZIP...
powershell Compress-Archive -Path "dist\Network Monitor\*" -DestinationPath "dist\Network_Monitor_v1.0_win.zip" -Force

echo.
echo ✅ 打包完成！
echo    产物: dist\Network Monitor.exe
echo    ZIP: dist\Network_Monitor_v1.0_win.zip
echo.

pause
