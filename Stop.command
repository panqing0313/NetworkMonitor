#!/bin/bash
# 停止 Network Monitor
# 双击此文件关闭正在运行的监测服务

cd "$(dirname "$0")"
echo "🛑 正在停止 Network Monitor..."

# Stop by PID file
PID_FILE="/tmp/NetworkMonitor.pid"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    kill "$PID" 2>/dev/null
    for i in 1 2 3; do
        if ! kill -0 "$PID" 2>/dev/null; then break; fi
        sleep 1
    done
    kill -9 "$PID" 2>/dev/null
    rm -f "$PID_FILE"
fi

# Also clean port
lsof -ti "tcp:5206" 2>/dev/null | xargs kill -9 2>/dev/null

echo "✅ Network Monitor 已停止"
echo ""
echo "按 Enter 关闭此窗口..."
read
