# Network Monitor

实时局域网设备监测 · 网络拓扑可视化 · macOS / Windows 桌面应用

[![GitHub release](https://img.shields.io/github/v/release/panqing0313/NetworkMonitor)](https://github.com/panqing0313/NetworkMonitor/releases)
[![Build](https://github.com/panqing0313/NetworkMonitor/actions/workflows/build.yml/badge.svg)](https://github.com/panqing0313/NetworkMonitor/actions)
![platform](https://img.shields.io/badge/platform-macOS%20|%20Windows-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## 功能

**实时网络拓扑** — D3.js 力导向图展示所有设备，中心本机脉冲发光、LAN 节点可拖拽、WAN 服务自动分类，活跃连接有粒子动画

**流量监控** — 实时下载/上传速度、累计流量、活动连接数，每 2 秒刷新

**设备发现** — ARP 协议+ Ping 扫描，自动识别厂商（30+品牌）和类型（手机/电脑/路由器/摄像头/IoT）

**连接追踪** — 内外网 TCP 连接实时显示，自动识别 Google/Apple/WeChat/AWS 等服务

**设备详情** — 点击任意节点查看 IP/MAC/厂商/在线率/历史记录

---

## 快速安装

### macOS

从 [Releases](https://github.com/panqing0313/NetworkMonitor/releases) 下载 `Network_Monitor_v1.0.dmg`

```
1. 双击 DMG 打开
2. 将 Network Monitor.app 拖入 Applications
3. 首次启动: 系统设置 → 隐私与安全性 → 仍要打开
```

> 无需安装 Python，开箱即用

### Windows

从 [Releases](https://github.com/panqing0313/NetworkMonitor/releases) 下载 `Network_Monitor_v1.0_win.zip`

```
1. 解压 ZIP
2. 运行 Network Monitor.exe
```

> 无需安装 Python，开箱即用

### 命令行运行（开发用）

```bash
pip install flask pywebview pyyaml pyinstaller
cd NetworkMonitor

# 启动桌面应用
python main.py

# 快速扫描
python main.py --scan
```

---

## 界面布局

```
┌──── 设备列表 ────┬────── 拓扑图 + 流量 ──────┬──── 活动记录 ────┐
│                  │  [在线设备数] [总设备]     │                  │
│  🟢 xiaoqiang    │  ┌──────────────────┐     │  🟢上线 10:23   │
│  🟢 panqingdemini│  │  D3.js 网络拓扑图 │     │  🔴离线 10:15   │
│  🟢 mac          │  │  可拖拽 / 缩放    │     │  🟢上线 10:08   │
│  🟢 chuangmi_cam │  └──────────────────┘     │  🟢上线 09:55   │
│  🔴 panqingdeiph │  ⬇️ 1.2 Mbps  ⬆️ 0.3 Mbps │                  │
└──────────────────┴───────────────────────────┴──────────────────┘
```

---

## 项目结构

```
NetworkMonitor/
├── main.py                    # 主入口（跨平台）
├── config.yaml                # 配置文件
├── build_windows.bat          # Windows 一键打包
├── scanner/
│   ├── platform_utils.py     # 跨平台命令适配层
│   ├── arp_scanner.py        # ARP 发现 + 网关检测
│   ├── ping_scanner.py       # Ping 在线检测
│   ├── oui_db.py             # MAC 厂商数据库
│   ├── network_stats.py      # 实时流量监控
│   └── connections.py        # 内外网连接追踪
├── tracker/
│   ├── device_db.py          # SQLite 持久化
│   └── models.py             # 数据模型
├── gui/
│   ├── app.py                # Flask API 服务
│   ├── templates/index.html  # 仪表盘 (含 D3.js 图)
│   └── static/
│       ├── style.css         # 暗色主题
│       └── d3.min.js         # D3.js v7
├── scripts/
│   └── build_app.py          # 统一构建脚本
└── .github/workflows/
    └── build.yml             # GitHub Actions 自动打包
```

---

## 技术栈

| 组件 | 技术 |
|---|---|
| 桌面窗口 | pywebview (macOS WebKit / Windows MSHTML) |
| 后端 API | Flask |
| 前端渲染 | HTML/CSS/JS + D3.js v7 |
| 数据库 | SQLite |
| 网络扫描 | ARP + 并发 Ping |
| 流量监控 | netstat (macOS `-b` / Windows `-e`) |
| 打包分发 | PyInstaller → DMG / ZIP |

---

## GitHub Actions 自动构建

每次推送 tag `v*` 时自动打包：

```bash
git tag v1.0
git push origin v1.0
```

Actions 会在两个 runner 上并行构建:

- `macos-latest` → `Network_Monitor_v1.0.dmg`
- `windows-latest` → `Network_Monitor_v1.0_win.zip`

产物自动上传到 GitHub Release。

### 本地构建

```bash
python scripts/build_app.py
```

脚本自动检测当前平台并构建对应格式。

---

## 已知问题

- macOS 首次运行若提示"未验证的开发者"，在系统设置中允许即可
- 摄像头等静默设备需点击"扫描"按钮做完整 Ping 扫网段才能发现
- 外网服务识别基于 IP 前缀匹配，部分服务可能显示 Unknown
- Windows 构建需要 Windows 环境（GitHub Actions 自动处理）
