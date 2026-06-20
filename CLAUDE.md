# AX3000T 校园网自动认证项目

## 🎉 状态：已完成！

> **⚠️ 仓库规则**：每次对项目文件做任何修改后，必须 `git add -A && git commit -m "<描述>"` 并自动 push 到 Gitee。
> 远程仓库：https://gitee.com/taylorchengitee/mi-ax3000t-henu-campus-network
>
> **📝 开发流程**：每次对话/修改后，按需更新以下文件：
> 1. `CLAUDE.md` — 如果步骤进度、运行状态、关键信息、文件导航有变化
> 2. `开发日志.md` — 如果做了新的技术工作（新 Phase），含命令+原理
> 3. `开发日志_按日期.md` — 按日期追加当日工作摘要
> 4. `路由器当前状态.md` — 如果路由器配置有变化（IP/信道/SSID 等）
> 5. `README.md` — 如果项目简介、快速开始、技术栈有变化
> 6. `! re-generate HTML` — 修改 `开发日志.md` 后运行 `python 文档/convert_to_html.py`
> 7. `git add -A && git commit -m "<描述>"` — 最后提交并推送

```
步骤0: ✅ 刷写 ImmortalWrt 大分区固件（XMiR-Patcher 解锁SSH → 备份Factory → sysupgrade）
步骤1: ✅ 系统固化（重启不丢失，overlay 78MB可用）
步骤2: ✅ 安全加固（密码 + SSH密钥 + WiFi加密）
步骤3: ✅ WiFi WAN 配置（5G STA连接henu-student）
步骤4: ✅ 认证脚本部署（三步认证全通过）
步骤5: ✅ 分层网络恢复（守护进程秒级恢复路由 + cron 5分钟兜底认证）
步骤6: ✅ CAKE 智能流控（110Mbps 动态分配）
步骤7: ✅ Argon 主题美化（可换壁纸）
步骤8: ✅ 设备重连断网修复（频宽对齐 + 路由看门狗 + 启动加速）
步骤9: ✅ 校园网内部网站 DNS 修复（henu.edu.cn → 114.114.114.114）
步骤10: ✅ 设备重连断网修复 v2（快速恢复守护进程替代cron看门狗）
步骤11: ✅ 广告拦截 adblock（DNS 层面，185,435 域名，全设备生效）
步骤12: ✅ WireGuard VPN 客户端 + NTP 时间同步 + 流量监控(nlbwmon) + 网络质量监控(collectd)
Phase12: ✅ 修复启动后认证循环失败（v2.0守护进程 + v3.0认证脚本，恢复时间 8min→3min）
步骤13: ✅ 设备重连断联修复 v3（2.4G/5G hostapd 配置对齐 + DHCP租约168h + UAPSD关闭 + PMKSA缓存开启）
```

## 当前运行状态
- **WAN**: phy1-sta0 (5G) → henu-student → IP 10.36.4.137 → 已认证
- **LAN**: br-lan (192.168.1.1), DHCP 分配宿舍设备
- **AP 2.4G**: phy0-ap0, SSID `<见 credentials.txt>`, WPA2加密, ch1/20MHz
- **AP 5G**: phy1-ap0, SSID `<见 credentials.txt>-5G`, WPA2加密, ch52/40MHz
- **信道**: 5GHz 已锁定 ch52（避免 ACS 触发 radio reset）
- **守护进程**: fast_recovery_daemon 每秒检测，秒级恢复（替代 cron 20秒轮询）
- **认证检测**: cron 每5分钟自动检测/重连（守护进程每秒检测路由，秒级恢复）
- **VPN**: WireGuard wg0 → 10.66.66.2/24, Peer 47.94.146.53:51820, keepalive 25s
- **NTP**: sysntpd → ntp.tencent.com + ntp1.aliyun.com + ntp.ntsc.ac.cn + cn.ntp.org.cn
- **流量监控**: nlbwmon（30s刷新, 24h提交, LuCI Bandwidth Monitor）
- **性能监控**: collectd + RRDtool（CPU/接口/负载/内存/WiFi/Ping, LuCI Statistics）

## 关键信息
- 路由器: `192.168.1.1` / `ssh ax3000t`（免密）
- Web管理: `http://192.168.1.1`（root / `<见 credentials.txt>`）
- WiFi: `<见 credentials.txt>` / `<见 credentials.txt>`
- 校园网: `<见 credentials.txt>` / `<见 credentials.txt>` / `@<见 credentials.txt>`
- 认证脚本: `/etc/campus_network/auto_login.sh` (v3.0，含 preflight_check + 重试机制)
- 快速恢复守护进程: `/etc/campus_network/fast_recovery_daemon.sh` (v2.0，每秒检测，启动等待+冷却期)
- 路由看门狗: `/etc/campus_network/route_watchdog.sh` (已被快速恢复守护进程替代)
- 启动脚本: `/etc/init.d/campus_auth` / `/etc/init.d/fast_recovery` (开机启动)
- 认证日志: `/tmp/campus_network.log`
- DNS 修复脚本: `/etc/campus_network/dns_fix.sh`（一键修复校园内部网站访问）
- 广告拦截: LuCI → Services → Adblock（185K 域名，dnsmasq 后端，全设备生效）
- WireGuard 配置: `/etc/wireguard/`（私钥 + 公钥），UCI: `network.wg0`
- WireGuard 管理: LuCI → Network → Interfaces → wg0 或 `wg show`
- 流量监控: LuCI → Services → Bandwidth Monitor（nlbwmon，每设备/协议统计）
- 性能图表: Statistics → Graphs（collectd，CPU/内存/流量/延迟/WiFi）
- 凭据文件: `credentials.txt`（本地，勿上传）
- 概念参考: 教程"基础知识速成" + 开发日志 Phase 0（所有术语内联解释）

## DNS 说明
校园网 DHCP 提供两个 DNS 服务器，各有问题：
- `111.6.174.198`（河南移动DNS，通过 DHCP 下发）
- `114.114.114.114`（公共 DNS）

| 域名 | 111.6.174.198 | 114.114.114.114 | 解决方案 |
|------|:---:|:---:|------|
| zwyy.henu.edu.cn | 125.219.33.206 ❌ | 202.196.96.29 ✅ | → hosts 写死 202.196.96.29 |
| software.henu.edu.cn | 解析为空 ❌ | 58.212.123.41 ✅ | → hosts 写死 58.212.123.41 |
| net.henu.edu.cn | 172.31.7.4 ✅ | 58.212.123.41 ⚠️ | → hosts 写死 172.31.7.4（内网） |
| jwgl.henu.edu.cn | 172.31.7.4 ✅ | 211.142.109.84 ❌ | → 111 + rebind豁免 |
| xg.henu.edu.cn | 172.31.0.6 ❌ | 58.212.123.41 ✅ | → 114 |
| lib.henu.edu.cn | 202.196.96.29 ✅ | 202.196.96.29 ✅ | 均可 |
| superhuazai.me | 间歇解析异常 | 104.21.18.208 ✅ | → hosts 写死 104.21.18.208 (Cloudflare) |

修复包含四层：
1. **/etc/hosts**: 静态写死 zwyy→202.196.96.29, software→58.212.123.41, net→172.31.7.4, superhuazai→104.21.18.208（最可靠）
2. **UCI**: 精确域名 DNS 转发 (xg→114, jwgl→111)
3. **/etc/dnsmasq.conf**: `rebind-domain-ok=/henu.edu.cn/ /ntp.org.cn/` 允许校园内部 RFC1918 IP + 抑制 NTP DNS rebind 告警
4. **filter_aaaa=1**: 过滤 IPv6 解析（路由器无 IPv6 路由）

> **全量扫描结果**（2026-06-14，70+ 子域名）：`rebind-domain-ok=/henu.edu.cn/` 已覆盖所有 `*.henu.edu.cn` 子域名。
> 23 个域名返回内网 IP（172.31.x.x / 10.x.x.x），rebind 豁免全部生效。
> 3 个域名服务器不可达（paper→172.31.2.73, cloud→10.12.253.27, ir→125.219.33.231），非 DNS 问题。
> 
> **河南大学网站全量分析**（2026-06-20，250 个子域名，来源：主管主办网站.xlsx）：
> 111 DNS 为所有 `*.henu.edu.cn` 返回 172.31.7.4（校内统一门户），114 DNS 返回 58.212.123.41。
> 17 个域名 114→211.142.109.84（非标准），但实际访问时 111 DNS 优先，不影响使用。
> 结论：现有四层方案已全覆盖，无需新增 hosts。

一键修复: `sh /etc/campus_network/dns_fix.sh`

## 故障排查
- 认证失败: `cat /tmp/campus_network.log`
- 手动认证: `/etc/campus_network/auto_login.sh`
- 网络中断恢复: 守护进程自动处理，查看 `grep FastRecovery /tmp/campus_network.log`
- 启动后断网: 守护进程 v2.0 会自动等待网络就绪 + 30秒冷却期后才触发认证
- 守护进程状态: `ps | grep fast_recovery` / `/etc/init.d/fast_recovery status`
- 手动恢复路由: `/etc/campus_network/route_watchdog.sh`
- 校园内部网站打不开: 检查 DNS 配置 `uci show dhcp | grep henu`，修复 `sh /etc/campus_network/dns_fix.sh`
- DNS 解析测试: `nslookup zwyy.henu.edu.cn`
- 重启WiFi: `wifi reload`
- 查看状态: `iw dev phy1-sta0 link`
- 检查频宽: `iw dev phy1-ap0 info | grep width`
- 查看5G信道是否锁定: `uci get wireless.radio1.channel`（应为52）
- WireGuard 状态: `wg show` 或 `ip addr show wg0`
- WireGuard 握手失败: 检查 `persistent_keepalive` 是否设置，ping 服务器
- NTP 同步状态: `date` + `logread | grep ntp`
- 流量监控为空: 检查 `list local_network 'lan'` 是否在 nlbwmon 配置中
- collectd 图表: Statistics → Graphs（重启后历史丢失是正常的，/tmp 是内存盘）

## 文件导航

```
AX3000T刷机校园网/
├── CLAUDE.md                      ← 项目入口（本文件）
├── credentials.txt                ← 敏感凭据（勿上传）
│
├── 文档/                           ← 所有文档集中在这里
│   ├── 从零开始教程.md             ← 完整小白教程
│   ├── 开发日志.md                 ← 完整开发过程记录（按 Phase，教学级）
│   ├── 开发日志_按日期.md           ← 开发过程记录（按日期，快速查阅）
│   ├── 脚本使用教程.md             ← 脚本+监控工具说明
│   ├── 路由器当前状态.md           ← 路由器配置快照
│   ├── convert_to_html.py         ← 开发日志转 HTML 工具
│   └── AX3000T校园网项目_完整学习笔记.html ← 可打印的 HTML 学习笔记
│
├── 一键配置脚本/                   ← 路由器配置工具
│   ├── !START.bat                 ← 双击启动配置菜单
│   ├── deploy.py                  ← 一键部署工具 v3.0（懒人模式）
│   ├── auto_config.sh             ← 路由器一键配置脚本
│   ├── fast_recovery_daemon.sh    ← 快速恢复守护进程 v2.0（秒级断网恢复）
│   └── dns_fix.sh                 ← 校园内部网站 DNS 修复脚本
│
├── 监控工具/                       ← 网络监控工具
│   ├── !MONITOR.bat               ← 双击打开监控菜单
│   ├── monitor.py                 ← 实时监控 + 压力测试 + 对比（Python 三合一）
│   ├── gen_stress_image.py        ← 压力测试结果图表生成
│   └── test_results/              ← 自动保存的 JSON 测试数据
│
├── .ssh/                           ← SSH 配置和密钥
├── .claude/                        ← Claude Code 设置
└── 小米AX3000T刷机教程openwrt大分区版/  ← 刷机工具和固件
```
