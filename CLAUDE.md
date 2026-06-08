# AX3000T 校园网自动认证项目

## 🎉 状态：已完成！

```
步骤0: ✅ 刷写 ImmortalWrt 大分区固件
步骤1: ✅ 系统固化（重启不丢失）
步骤2: ✅ 安全加固（密码 + SSH密钥 + WiFi加密）
步骤3: ✅ WiFi WAN 配置（5G STA连接henu-student）
步骤4: ✅ 认证脚本部署（三步认证全通过）
步骤5: ✅ cron定时重连（每5分钟检测）
步骤6: ✅ CAKE 智能流控（110Mbps 动态分配）
步骤7: ✅ Argon 主题美化（可换壁纸）
步骤8: ✅ 旧设备断网修复（频宽对齐 + 路由看门狗 + 启动加速）
步骤9: ✅ 校园网内部网站 DNS 修复（henu.edu.cn → 114.114.114.114）
步骤10: ✅ 旧设备重连断网修复 v2（快速恢复守护进程替代cron看门狗）
```

## 当前运行状态
- **WAN**: phy1-sta0 (5G) → henu-student → IP 10.36.82.65 → 已认证
- **LAN**: br-lan (192.168.1.1), DHCP 分配宿舍设备
- **AP 2.4G**: phy0-ap0, SSID `<见 credentials.txt>`, WPA2加密, ch1/20MHz
- **AP 5G**: phy1-ap0, SSID `<见 credentials.txt>-5G`, WPA2加密, ch52/40MHz
- **信道**: 5GHz 已锁定 ch52（避免 ACS 触发 radio reset）
- **守护进程**: fast_recovery_daemon 每秒检测，秒级恢复（替代 cron 20秒轮询）
- **认证检测**: cron 每3分钟自动检测/重连

## 关键信息
- 路由器: `192.168.1.1` / `ssh ax3000t`（免密）
- Web管理: `http://192.168.1.1`（root / `<见 credentials.txt>`）
- WiFi: `<见 credentials.txt>` / `<见 credentials.txt>`
- 校园网: `<见 credentials.txt>` / `<见 credentials.txt>` / `@<见 credentials.txt>`
- 认证脚本: `/etc/campus_network/auto_login.sh` (v2.0，含路由恢复)
- 快速恢复守护进程: `/etc/campus_network/fast_recovery_daemon.sh` (每秒检测，秒级恢复)
- 路由看门狗: `/etc/campus_network/route_watchdog.sh` (已被快速恢复守护进程替代)
- 启动脚本: `/etc/init.d/campus_auth` / `/etc/init.d/fast_recovery` (开机启动)
- 认证日志: `/tmp/campus_network.log`
- DNS 修复脚本: `/etc/campus_network/dns_fix.sh`（一键修复校园内部网站访问）
- 凭据文件: `credentials.txt`（本地，勿上传）

## DNS 说明
校园网 DHCP 提供两个 DNS 服务器，各有问题：
- `111.6.174.198`（河南移动DNS，通过 DHCP 下发）
- `114.114.114.114`（公共 DNS）

| 域名 | 111.6.174.198 | 114.114.114.114 | 解决方案 |
|------|:---:|:---:|------|
| zwyy.henu.edu.cn | 125.219.33.206 ❌ | 202.196.96.29 ✅ | → 114 |
| jwgl.henu.edu.cn | 172.31.7.4 ✅ | 211.142.109.84 ❌ | → 111 + rebind豁免 |
| xg.henu.edu.cn | 172.31.0.6 ❌ | 58.212.123.41 ✅ | → 114 |
| lib.henu.edu.cn | 202.196.96.29 ✅ | 202.196.96.29 ✅ | 均可 |

修复包含两部分：
1. **UCI**: 精确域名 DNS 转发 (zwyy/xg→114, jwgl→111)
2. **/etc/dnsmasq.conf**: `rebind-domain-ok=/henu.edu.cn/` 允许校园内部 RFC1918 IP

一键修复: `sh /etc/campus_network/dns_fix.sh`

## 故障排查
- 认证失败: `cat /tmp/campus_network.log`
- 手动认证: `/etc/campus_network/auto_login.sh`
- 网络中断恢复: 守护进程自动处理，查看 `grep FastRecovery /tmp/campus_network.log`
- 守护进程状态: `ps | grep fast_recovery` / `/etc/init.d/fast_recovery status`
- 手动恢复路由: `/etc/campus_network/route_watchdog.sh`
- 校园内部网站打不开: 检查 DNS 配置 `uci show dhcp | grep henu`，修复 `sh /etc/campus_network/dns_fix.sh`
- DNS 解析测试: `nslookup zwyy.henu.edu.cn`
- 重启WiFi: `wifi reload`
- 查看状态: `iw dev phy1-sta0 link`
- 检查频宽: `iw dev phy1-ap0 info | grep width`
- 查看5G信道是否锁定: `uci get wireless.radio1.channel`（应为52）

## 文件导航

```
AX3000T刷机校园网/
├── CLAUDE.md                      ← 项目入口（本文件）
├── credentials.txt                ← 敏感凭据（勿上传）
│
├── 文档/                           ← 所有文档集中在这里
│   ├── 从零开始教程.md             ← 完整小白教程
│   ├── 脚本使用教程.md             ← 脚本+监控工具说明
│   ├── 路由器当前状态.md           ← 路由器配置快照
│   └── 开发日志.md                 ← 完整开发过程记录（教学级）
│
├── 一键配置脚本/                   ← 路由器配置工具
│   ├── !START_CONFIG.bat          ← 双击启动配置菜单
│   ├── auto_config.sh             ← 路由器一键配置脚本
│   ├── auto_config_menu.py        ← 配置菜单 Python 版
│   └── fast_recovery_daemon.sh    ← 快速恢复守护进程（秒级断网恢复）
│
├── 监控工具/                       ← 网络监控工具
│   ├── start.bat                  ← 双击打开监控菜单
│   ├── Monitor.ps1                ← 实时监控（0.5秒刷新，折线图）
│   ├── StressTest.ps1             ← 压力测试（14站点×30轮）
│   ├── Compare.ps1                ← 对比两次测试结果
│   └── 测试记录/                   ← 自动保存的测试数据
│
├── .ssh/                           ← SSH 配置和密钥
├── .claude/                        ← Claude Code 设置
└── 小米AX3000T刷机教程openwrt大分区版/  ← 刷机工具和固件
```
