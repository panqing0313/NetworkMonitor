# 📡 Network Monitor

**实时局域网设备监测 · 网络拓扑可视化 · macOS 原生桌面应用**

![screenshot](https://img.shields.io/badge/平台-macOS%20ARM64-blue)
![version](https://img.shields.io/badge/版本-1.0.0-green)
![size](https://img.shields.io/badge/大小-33MB-lightgrey)

---

## 功能特性

### 🌐 实时网络拓扑图

- D3.js 力导向图动态展示所有局域网设备
- 中心节点 → 本机（蓝色脉冲动画）
- 内圈节点 → LAN 设备（绿色，含摄像头/路由器/手机等）
- 外圈节点 → 外网服务（橙色，Google/WeChat 等自动识别）
- 活跃连接上有发光粒子沿线条流动
- 节点可拖拽、画布可缩放平移
- 点击任意设备弹出详情窗口

### 📊 实时流量监控

| 指标 | 采样频率 |
|---|---|
| 下载速度 | 2 秒刷新 |
| 上传速度 | 2 秒刷新 |
| 累计流量 | 实时累计 |
| 活动连接数 | 3 秒刷新 |

### 📱 局域网设备发现

- ARP 协议自动发现同网段所有设备
- Ping 扫描补充静默设备（摄像头、IoT 等）
- MAC OUI 数据库识别厂商（30+ 品牌）
- 自动分类设备类型（手机/电脑/路由器/摄像头/IoT）

### 🔗 内外网连接监控

- 实时跟踪本机所有 TCP 活动连接
- 自动识别外网服务（Google/Apple/WeChat/AWS 等）
- 一键查看连接详情弹窗

### 🎯 设备详情

- IP / MAC / 厂商 / 类型
- 在线率统计（最近 N 次采样）
- 上线/离线历史时间线

---

## 快速开始

### 方式一：DMG 安装（推荐）

```
dist/Network_Monitor_v1.0.dmg  (17MB)
```

1. 双击 DMG 打开
2. 将 `Network Monitor.app` **拖入 Applications 文件夹**
3. 首次启动：系统设置 → 隐私与安全性 → **仍要打开**
4. 此后双击即可运行

> 无需安装 Python / pip / 任何依赖，开箱即用

### 方式二：命令行运行

```bash
# 安装依赖
pip install flask pyyaml pywebview

# 启动桌面应用
cd NetworkMonitor && python3 main.py

# 或快速扫描
python3 main.py --scan
```

---

## 项目结构

```
NetworkMonitor/
├── main.py                    # 主入口
├── NetworkMonitor.app/        # macOS 原生应用包
├── stop.app/                  # 停止应用
├── config.yaml                # 配置文件
├── scanner/
│   ├── arp_scanner.py        # ARP 发现 + 网关检测
│   ├── ping_scanner.py       # Ping 在线检测
│   ├── oui_db.py             # MAC 厂商数据库（30+品牌）
│   ├── network_stats.py      # 实时流量监控
│   └── connections.py        # 内外网连接追踪
├── tracker/
│   ├── device_db.py          # SQLite 持久化
│   └── models.py             # 数据模型
├── gui/
│   ├── app.py                # Flask API 服务
│   ├── templates/
│   │   └── index.html        # 仪表盘 UI（含 D3.js 图）
│   └── static/
│       ├── style.css         # 暗色主题样式
│       └── d3.min.js         # D3.js v7
└── dist/
    └── Network_Monitor_v1.0.dmg  # 📦 分发安装包
```

---

## 技术栈

| 组件 | 技术 |
|---|---|
| 桌面窗口 | pywebview (macOS WebKit) |
| 后端 API | Flask |
| 前端渲染 | HTML/CSS/JS + D3.js v7 |
| 数据库 | SQLite |
| 网络扫描 | ARP + 并发 Ping |
| 流量监控 | netstat |
| 打包分发 | PyInstaller → DMG |

---

## 构建指南

```bash
# 构建独立 .app
pip install pyinstaller
cd NetworkMonitor
python3 -m PyInstaller \
  --name "Network Monitor" \
  --windowed --onedir \
  --add-data "gui/templates:templates" \
  --add-data "gui/static:static" \
  --add-data "config.yaml:." \
  --hidden-import "scanner.*" \
  --hidden-import "tracker.*" \
  --hidden-import "gui.app" \
  --osx-bundle-identifier "com.local.network-monitor" \
  main.py

# 打包 DMG
hdiutil create -volname "Network Monitor" \
  -srcfolder dist/Network\\ Monitor.app \
  -ov -format UDZO \
  dist/Network_Monitor_v1.0.dmg
```

---

## 已知问题

- 首次运行若报"未验证的开发者"，在系统设置中允许即可
- 摄像头等静默设备需点击"扫描"按钮做完整 Ping 扫网段才能发现
- 外网服务识别基于 IP 前缀匹配，部分服务可能显示 Unknown
