#!/bin/bash
# 启动 Network Monitor 桌面应用
# 双击此文件会在终端中启动应用

cd "$(dirname "$0")"
echo "📡 Network Monitor 启动中..."
echo "================================"

# Use Python 3.14
PYTHON="/usr/local/bin/python3"

# Kill any existing on port 5206
lsof -ti "tcp:5206" 2>/dev/null | xargs kill 2>/dev/null
sleep 1

# Start
$PYTHON main.py

echo ""
echo "按下 Ctrl+C 停止服务..."
echo "（关闭此窗口也将停止服务）"
