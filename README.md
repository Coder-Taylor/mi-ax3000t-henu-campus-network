# 校园网自动认证路由器系统 · 小米 AX3000T

> 基于 ImmortalWrt 的校园网自动认证方案，实现宿舍路由器无线接入 henu-student、Portal 全自动三步认证、断网秒级恢复与智能流控。
>
> **说明**：本项目参考了 Jerry 的 HENU_autologin 方案（路由器刷机与校园网连接思路），在 AI（Claude Code）协作下独立完成适配与开发。核心 Shell 认证脚本、守护进程、CAKE 流控配置等均为自主编写。

[![状态](https://img.shields.io/badge/状态-已完成-brightgreen)](https://gitee.com/taylorchengitee/mi-ax3000t-henu-campus-network)
[![平台](https://img.shields.io/badge/平台-MT7981B%20(AX3000T)-blue)]()
[![AI](https://img.shields.io/badge/AI-Claude%20Code-9cf)]()

---

## 项目背景

宿舍校园网 `henu-student` 采用 Portal 认证方式，每台设备需要手动登录，且认证有时效限制（不定期过期）。本项目让路由器做"中间人"——路由器连接校园网并自动认证，宿舍所有设备通过路由器共享网络，无需各自登录。

---

## 实现的功能

| 功能 | 说明 |
|------|------|
| ✅ **无线 WAN** | 路由器通过 5G WiFi（STA 模式）连接校园网，无需网线 |
| ✅ **Portal 自动认证** | 三步认证全自动（获取参数→验证身份→门户登录），过期自动重连 |
| ✅ **断网秒级恢复** | 守护进程每秒检测，网络中断 1-3 秒内自动恢复 |
| ✅ **多设备共享** | LAN + 2.4G AP + 5G AP 同时在线，宿舍设备即连即用 |
| ✅ **CAKE 智能流控** | 110Mbps 带宽动态分配，多人下载/打游戏互不干扰 |
| ✅ **DNS 修复** | 校园网内部网站（教务/学工/图书馆）全部可访问 |
| ✅ **WiFi 断联修复 v3** | DHCP 租期 168h + hostapd 配置对齐，解决设备重连导致的全屋断网 |
| ✅ **流量监控** | nlbwmon 显示每台设备的实时流量与协议分布 |
| ✅ **性能图表** | collectd + RRDtool 记录 CPU、内存、网络、延迟长周期数据 |
| ✅ **VPN 远程访问** | WireGuard 客户端，外网可远程管理宿舍网络 |
| ✅ **广告拦截** | dnsmasq 后端 adblock，185K+ 域名，全设备生效 |

---

## 技术栈

| 领域 | 技术 |
|------|------|
| 路由器系统 | ImmortalWrt 24.10.5（Linux 6.6，OpenWrt 衍生版） |
| 配置管理 | UCI（统一配置接口） |
| 网络协议 | WiFi STA+AP 双模 / DHCP / NAT (MASQUERADE+FULLCONENAT) / nftables |
| 流控 | CAKE qdisc（Common Applications Kept Enhanced） |
| 自动化 | Shell 脚本 + procd 守护进程 + cron 定时 |
| 监控 | nlbwmon（流量） + collectd（系统性能） |
| VPN | WireGuard（内核级，UDP NAT 穿透） |
| DNS | dnsmasq + UCI 域名转发 + rebind 豁免 + 多层策 |
| 开发工具 | **AI 协作（Claude Code）** / Shell / Python / PowerShell |

---

## 项目结构

```
/
├── 文档/
│   ├── 从零开始教程.md            ← 完整小白教程（面向完全零基础）
│   ├── 开发日志.md                ← 完整开发过程（按阶段，教学级，3500+行）
│   ├── 开发日志_按日期.md          ← 按日期记录的项目经历
│   ├── 学习笔记 (MD/HTML)          ← 技术博客风格的完整总结
│   └── 脚本使用教程.md            ← 各脚本和监控工具的使用说明
│
├── 一键配置脚本/
│   ├── deploy.py                  ← 一键部署工具（免手动配置）
│   ├── auto_config.sh             ← 路由器一键配置脚本
│   ├── fast_recovery_daemon.sh    ← 秒级断网恢复守护进程（核心组件）
│   └── dns_fix.sh                 ← 校园内部网站 DNS 修复脚本
│
├── 监控工具/
│   ├── monitor.py                 ← 实时监控 + 压力测试 + 对比分析（Python 三合一）
│   └── test_results/              ← 压力测试数据存档
│
└── 小米AX3000T刷机教程openwrt大分区版/
    └── step1解锁ssh/              ← XMiR-Patcher 刷机工具
```

---

## 部署方式

```bash
# 方式一：一键部署（推荐）
# Windows 下双击 一键配置脚本\!START.bat

# 方式二：SSH 手动部署
ssh root@192.168.1.1
# 路由器上执行一键配置
sh /etc/campus_network/auto_config.sh

# 方式三：分步部署（详细教程见文档/从零开始教程.md）
```

详细的部署步骤和故障排查请参阅 [从零开始教程](./文档/从零开始教程.md)。

---

## 开发过程记录

本项目全流程记录于 [开发日志.md](./文档/开发日志.md)（3500+行，教学级文档），内容涵盖：

| 阶段 | 内容 |
|------|------|
| 步骤 0 | 路由器刷机（XMiR-Patcher 解锁 SSH → 备份 Factory → 刷入 ImmortalWrt）|
| Phase 0 | 前置基础概念（SSH/OverlayFS/UCI/NAT/WiFi 模式/守护进程等）|
| Phase 1-5 | 安全加固 → WiFi WAN → 认证脚本 → 定时重连 + NAT 修复 |
| Phase 6-7 | CAKE 流控 + Argon 主题美化 |
| Phase 8-10 | 设备重连断网修复（v1 频宽对齐 → v2 守护进程 → v3 终极方案）|
| Phase 11 | WireGuard VPN + NTP + nlbwmon + collectd 全栈监控 |
| Phase 12-13 | 启动循环修复 + DHCP/hostapd 深度调优 |

---

## 开发方式说明

本项目使用 **Claude Code（AI 代码助手）作为主要协作工具**完成开发。具体协作方式：

- **需求转化为实现**：描述需求场景（如"检测网络断开后自动恢复"），由 AI 生成初始代码，人工审核后部署测试
- **故障排查**：路由器运行时出现异常（如认证失败、WiFi 断连），将日志反馈给 AI 分析根因，获得修复方案
- **文档编写**：所有文档（开发日志、教程、学习笔记）均由 AI 在人工指导下撰写，确保技术准确性
- **迭代优化**：修复方案部署后观察效果，持续反馈给 AI 进行改进（如断网恢复从 cron 20秒 → 守护进程 1秒）

这种协作方式**大幅降低了嵌入式 Linux 开发的入门门槛**，使大一学生能够独立完成从刷机到生产级部署的全流程。

---

## 相关链接

- [GitHub](https://github.com/Coder-Taylor/mi-ax3000t-henu-campus-network)
- [Gitee](https://gitee.com/taylorchengitee/mi-ax3000t-henu-campus-network)
- [完整学习笔记（Markdown）](./文档/AX3000T校园网项目_完整学习笔记.md)
- [完整学习笔记（HTML）](./文档/AX3000T校园网项目_完整学习笔记.html)

---

## 许可证

[MIT License](./LICENSE)
