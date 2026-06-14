# 🎓 AX3000T 校园网自动认证

> 小米 AX3000T 路由器 + ImmortalWrt + 河南大学 henu-student 校园网全自动认证解决方案

[![状态](https://img.shields.io/badge/状态-已完成-brightgreen)](https://gitee.com/taylorchengitee/mi-ax3000t-henu-campus-network)
[![平台](https://img.shields.io/badge/平台-MT7981B%20(AX3000T)-blue)]()

---

## 📖 这是什么？

在宿舍用 AX3000T 路由器连接 `henu-student` 校园网，实现：

- ✅ **无线 WAN** — 路由器通过 5G WiFi 连接校园网（不需要网线）
- ✅ **自动认证** — Portal 认证全自动完成，过期自动重连
- ✅ **断网秒级恢复** — 守护进程每秒检测，断网 1-2 秒自动恢复
- ✅ **多设备共享** — LAN + 2.4G/5G WiFi 同时在线
- ✅ **智能流控** — CAKE qdisc 110Mbps 动态分配，打游戏不卡
- ✅ **DNS 修复** — 校园内部网站（教务/学工/图书馆）全部可访问

所有脚本和配置文件均在路由器上运行，断网无需人工干预。

---

## 🚀 快速开始

> 详细教程见 [从零开始教程](./文档/从零开始教程.md)

### 前置条件

| 项目 | 要求 |
|------|------|
| 路由器 | 小米 AX3000T（v1 版本） |
| 固件 | ImmortalWrt 大分区版 |
| 电脑 | Windows（需安装 Python 和 SSH 客户端） |
| 校园网 | henu-student（河南大学） |

### 三步部署

```bash
# 1. SSH 连接路由器
ssh root@192.168.1.1

# 2. 运行一键配置脚本
sh /etc/campus_network/auto_config.sh

# 3. 等待认证完成
cat /tmp/campus_network.log
```

### 本地监控（Windows）

```cmd
# 双击启动实时监控（0.5 秒刷新 + 折线图）
监控工具\!MONITOR.bat
```

---

## 📁 项目结构

```
AX3000T刷机校园网/
├── README.md                       ← 项目首页
├── CLAUDE.md                       ← 项目入口（面向 AI 助手的上下文）
│
├── 文档/
│   ├── 从零开始教程.md             ← 完整小白教程
│   ├── 开发日志.md                 ← 开发过程（按阶段，教学级）
│   ├── 开发日志_按日期.md           ← 开发过程（按日期，快速查阅）
│   ├── 脚本使用教程.md             ← 脚本+监控工具说明
│   ├── 路由器当前状态.md           ← 路由器配置快照
│   ├── convert_to_html.py         ← 开发日志转 HTML 工具
│   └── AX3000T校园网项目_完整学习笔记.html  ← 可打印的 HTML 学习笔记
│
├── 一键配置脚本/
│   ├── !START.bat                  ← Windows 双击启动配置菜单
│   ├── deploy.py                   ← 一键部署工具 v3.0（懒人模式）
│   ├── auto_config.sh              ← 路由器一键配置
│   ├── fast_recovery_daemon.sh     ← 快速恢复守护进程 v2.0
│   └── dns_fix.sh                  ← 校园内部网站 DNS 修复
│
├── 监控工具/
│   ├── !MONITOR.bat                ← 双击打开监控菜单
│   ├── monitor.py                  ← 实时监控 + 压力测试 + 对比（Python 三合一）
│   ├── gen_stress_image.py         ← 压力测试结果图表生成
│   └── test_results/               ← 自动保存的 JSON 测试数据
│
└── 小米AX3000T刷机教程openwrt大分区版/
    ├── step1解锁ssh/               ← 解锁 SSH 工具
    ├── step2刷入openwrt/           ← 刷机指南
    └── 恢复原厂系统/               ← 回退指南
```

---

## 🛠️ 核心技术栈

| 技术 | 用途 |
|------|------|
| OpenWrt / ImmortalWrt | 路由器操作系统 |
| UCI | 统一配置接口 |
| dnsmasq | DHCP + DNS |
| iptables / nftables | 防火墙和 NAT |
| CAKE qdisc | 智能队列管理和流控 |
| Cron | 定时任务调度 |
| Procd | 进程管理（init.d 脚本） |
| Shell Script | 所有自动化脚本 |
| PowerShell | Windows 端监控工具 |
| Python | 刷机工具 + HTML 生成 |

---

## 🔧 关键特性

### 秒级断网恢复

传统的 cron 轮询最小粒度是 1 分钟（最快也只能 20 秒用多个 cron hack），本项目使用**持续运行的守护进程**（`fast_recovery_daemon.sh`），每秒检测网络状态：

- **路由丢失** → 触发 DHCP 重获取（1-2 秒恢复）
- **WiFi 断连** → 精确重连指定信道（3-5 秒恢复，比 `wifi reload` 快 3-4 倍）
- **认证过期** → 调用认证脚本重新登录

### 智能 DNS

校园网内部网站（教务系统、学工系统、图书馆）的 DNS 解析需要特殊处理：

| 域名 | DNS 策略 |
|------|----------|
| `zwyy.henu.edu.cn` | → 114.114.114.114 |
| `software.henu.edu.cn` | → 114.114.114.114 |
| `net.henu.edu.cn` | → 172.31.7.4（内网） |
| `jwgl.henu.edu.cn` | → 111.6.174.198 |
| `xg.henu.edu.cn` | → 114.114.114.114 |
| `lib.henu.edu.cn` | 均可 |

配合 `rebind-domain-ok` 允许校园内网 RFC1918 IP。

---

## 📊 项目历程

| 日期 | 里程碑 |
|------|--------|
| 2026-06-04 | 主开发日：刷机→固化→安全→WiFi WAN→认证→流控→监控（13 小时） |
| 2026-06-06 | 设备重连断网修复 v1：频宽对齐 + 路由看门狗 |
| 2026-06-09 | 文档全面升级：新增基础知识速成+步骤0刷机全过程+启动过程/文件系统/看门狗详解 |

详见 [开发日志（按日期）](./文档/开发日志_按日期.md)

---

## ⚠️ 注意事项

- **凭据安全**：路由器密码、WiFi 密码、校园网账号等敏感信息存放在本地 `credentials.txt`，不会上传到仓库
- **固件兼容性**：仅测试过 AX3000T v1 版本（MT7981B），其他硬件需要调整
- **校园网环境**：认证流程针对河南大学 henu-student Portal，其他学校需修改认证脚本

---

## 📄 许可证

[MIT License](./LICENSE) — 自由使用、修改、分发，保留版权声明即可。
