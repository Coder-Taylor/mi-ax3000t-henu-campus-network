# 项目规则（给 AI 助手看）

小米 AX3000T + ImmortalWrt 24.10.5，让路由器无线连河南大学 `henu-student` 并自动完成
Portal 认证，给宿舍发 WiFi。

**面向人的文档在 `README.md` 和 `文档/` 下。本文件只写"干活时需要知道的"。**

---

## 一、硬规则

1. **每次改文件后必须提交并推送**：`git add -A && git commit -m "..." && git push`
2. **凭据永不入库**。`credentials.txt` 已在 `.gitignore`。提交信息和文档里不写具体学号/密码/SSID。
3. **force push 必须先获得用户明确授权。**
4. **改开机链路（init.d / crontab / 启动脚本）必须真实重启验证**，不能只看 `ps`。

---

## 二、仓库结构

```
├── README.md                      入口，按读者分流
├── CLAUDE.md                      本文件（AI 用）
├── AGENTS.md                      指向 CLAUDE.md
├── credentials.txt                敏感，gitignored
│
├── 文档/
│   ├── 刷机指南.md                 原厂 → ImmortalWrt
│   ├── 日常使用.md                 改 WiFi / 换账号 / 看流量
│   ├── 排障手册.md                 按症状查
│   ├── 原理详解.md                 为什么这么配
│   ├── Linux入门.md                命令行 / vi / 文件系统
│   ├── 拓展玩法.md                 能装什么、装不了什么
│   ├── 路由器当前状态.md            两台机器的配置快照 ⭐改配置后要更新
│   ├── 脚本使用教程.md              所有脚本的参数和用法
│   ├── 开发日志.md                  完整开发过程（历史存档，3778 行）
│   ├── 开发日志_按日期.md            按日期的维护记录
│   ├── Mi-AX3000T路由器开发总结.md   简历友好版总结
│   └── convert_to_html.py          开发日志 → HTML
│
├── 一键配置脚本/                    ⭐权威脚本版本
│   ├── deploy.py                   电脑端一键部署 v3.0
│   ├── auto_config.sh              路由器端一键配置（内嵌副本可能滞后）
│   ├── auto_login.sh.template      认证脚本模板（占位符，权威）
│   ├── fast_recovery_daemon.sh     守护进程 v2.2（权威）
│   ├── boot_auth.sh                开机等网络就绪再认证
│   ├── route_watchdog.sh           开机早期加速 STA 重连
│   ├── campus_auth.init            开机认证服务
│   ├── crontab.root                crontab 模板
│   ├── dns_fix.sh                  DNS 五层修复 v2.3
│   └── !START.bat / !PUSH_ALL.bat  Windows 双击入口
│
├── 监控工具/
│   ├── probe_stall.sh              卡顿探针（路由器上跑，cron 每分钟）
│   ├── probe_handshake.sh          握手探针（DNS/TCP/TLS 三段计时，cron 每分钟）
│   ├── kick_weak.sh                弱终端剔除（cron 每 2 分钟）
│   ├── repro_download.sh           主动压测，复现资源下载场景（手动）
│   ├── monitor.py                  电脑端实时监控/压测/对比
│   └── gen_stress_image.py         压测图表
│
├── 小米AX3000T刷机教程openwrt大分区版-干净原生.rar
│                                   刷机工具包，152MB，走 Git LFS
└── 小米AX3000T刷机教程openwrt大分区版/ 和 -old/   本地解压，gitignored
```

---

## 三、两台机器

| | 自用机 | 待售机 |
|---|---|---|
| IP | `192.168.1.1` / `ssh ax3000t` | `192.168.1.2` / `ssh ax3000t2` |
| NAND | ESMT | Winbond |
| 组件 | 全套（VPN/adblock/监控/CAKE） | 只有认证 + DNS + Argon |

改配置前先确认连的是哪台。详见 `文档/路由器当前状态.md`。

---

## 四、关键路径

| 内容 | 路径 |
|---|---|
| 认证脚本 | `/etc/campus_network/auto_login.sh` |
| 守护进程 | `/etc/campus_network/fast_recovery_daemon.sh` |
| 开机服务 | `/etc/init.d/campus_auth`（S99）、`/etc/init.d/fast_recovery`（S98） |
| 认证日志 | `/tmp/campus_network.log`（`/tmp` 重启清空） |
| 卡顿探针日志 | `/overlay/probe.log` |
| 握手探针日志 | `/overlay/handshake.log` |
| 弱终端剔除日志 | `/overlay/kick.log` |
| 崩溃现场 | `/sys/fs/pstore/`（只 4 块，满了显示 ENOSPC） |
| crontab | `/etc/crontabs/root` |

---

## 五、必须知道的坑

改代码前先扫一遍这里，都是真实踩过的。

### 网络检测不能用 8.8.8.8

校园网屏蔽 `8.8.8.8` 和 `114.114.114.114` 的 ICMP，100% 丢包。
用它判断"网络是否通"会永远误判 → 反复触发认证 → 小包卡顿。
**统一用 `223.5.5.5`。**

### crontab 严禁 `@` 关键字

本机 busybox crond 没编译 `@reboot` / `@daily`。写了会秒退并进入 crash loop，
连 `*/5` 也一起失效。开机任务交给 `/etc/init.d/`。

### init.d 的 `boot()`

`/etc/rc.common` 默认 `boot() { start "$@"; }`。自定义 `boot()` 不调 `start` 就不会注册实例
（表现为服务显示 enabled 但开机不跑）。

### 不要用 `procd respawn 0`

procd 把 `threshold=0` 当"永远重启"，不是"不重启"。一次性任务不要用 procd，
写普通启动脚本 + `&` 后台跑。

### 不要用 `wifi reload`

满流量时会触发 mtk_eth 驱动空指针崩溃，整机重启。pstore 里的栈：

```
mtk_stop → mtk_dma_free → mtk_rx_clean → dma_unmap_page_attrs → dcache_inval_poc
```

**改用**：

```sh
ubus call network.interface.wwan down; sleep 2; ubus call network.interface.wwan up
```

只动 wwan 单接口，不碰 WiFi 热点、LAN、DMA。脚本里已经全部改过了，手动操作也要避开。

### dnsmasq 的 rebind 豁免必须走 uci

写在 `/etc/dnsmasq.conf` 会被 uci 生成的运行配置覆盖，不生效。
**改用** `uci add_list dhcp.@dnsmasq[0].rebind_domain='...'`。
验证：`grep rebind /var/etc/dnsmasq.conf.cfg*`。

### 局域网不能发没有出口的 IPv6

odhcpd 会一直发 `fddd:ec86:845a::/60` 的 ULA 地址，但路由器没有 IPv6 默认路由。
设备拿到地址后优先试 IPv6，等到超时才回退 IPv4，App 首包/握手就卡在那一两秒。

日志线索：`logread | grep odhcpd` 反复报
`No default route present, setting ra_lifetime to 0!`

必须是：

```sh
uci get dhcp.lan.ra                    # disabled
uci show network.lan | grep ip6assign  # 无输出
ip -6 addr show br-lan | grep fddd     # 无输出
/etc/init.d/odhcpd status              # 未运行
```

改完**必须让设备重新拿地址**（手机飞行模式一次），旧 ULA 有效期约 1 小时。

### 弱终端会拖慢整个空口

-96/-97 dBm 的终端用 6 Mbit/s 最低速率反复重传，每帧占满一个空口时隙，
其它设备首包排队。**看不出来**，因为它自己已经没在传数据了。

用 `/root/kick_weak.sh` 清理，**四个条件同时满足**才动作：

| 条件 | 阈值 |
|---|---|
| 不在白名单 | `WHITELIST` |
| 信号 | ≤ -92 dBm |
| 空闲 | ≥ 600 秒 |
| 失败率 | ≥ 15% |
| **连续命中** | **≥ 5 次（10 分钟）** |

**白名单里的设备永不踢**（手机/电脑/Pad 四台，见脚本顶部）。

**`STREAK` 连续判定不能去掉**。v1 没有它，用户手机信号瞬间掉到 -99 dBm
持续几十秒就被误踢，手机随即自动连去隔壁 WiFi，表现为"连着 WiFi 但加载不出图"。
先 `DRY_RUN=1` 预演。

**不要用 `disassoc_low_ack=1`**：那是 hostapd 连续失败计数，一次性触发、
不可控、会连锁断掉正常设备。

### 路由器自身的 TLS 慢，不代表客户端慢

MT7981 双核 A53 做非对称加密：单发 0.33s，8 并发线性增长到 1.4s。
但手机/电脑自己握手只要 0.05s，路由器只转发不参与加解密。

**排查时不要被这个误导**。测网络要从客户端测；从路由器 curl 测到的 TLS 耗时
只反映它自己的 CPU 性能。

### 上游 DNS 不能用校园下发的那两个
`111.6.174.198` 和 `114.114.114.114` 实测各约 20% 查询超时重传，单次卡 2.5s。
**症状极具迷惑性**：视频/图片一直转圈，但大文件下载速度正常（下载只解析一次域名）；
电脑也常看不出来（系统 DNS 缓存厚）。

配置（`noresolv=1` 让 dnsmasq 忽略 `/tmp/resolv.conf.d/resolv.conf.auto`）：

```sh
uci set dhcp.@dnsmasq[0].noresolv='1'
uci add_list dhcp.@dnsmasq[0].server='223.5.5.5'
uci add_list dhcp.@dnsmasq[0].server='119.29.29.29'
uci add_list dhcp.@dnsmasq[0].server='/henu.edu.cn/111.6.174.198'
```

`henu.edu.cn` 整域仍走校园 DNS（内网域名公网解析不到）。
诊断先看 `/overlay/probe.log` 里 `dns=` 和 `ttfb=` 的拆分。

### busybox 缺的工具

没有：`base64`、`od`、`diff`、`timeout` 的部分参数。
`sleep` 不支持小数，`ping` 不支持 `-i 0.2` / `-f`。
`wget` 抓 HTTPS 跨主机重定向会段错误 → 用 `curl`。
`date +%s%N` 的 `%N` 不支持，返回空 → 计时用 `/proc/uptime` 相减。

### SSH 密钥

新刷的 ImmortalWrt root 无密码，dropbear 允许 none 认证，可直连。
装公钥后需显式 `-i ~/.ssh/ax3000t_rsa`，已配 `~/.ssh/config` 别名。
传文件用 `ssh host "cat > file" < local`（没有 `base64`）。
**不要用 `ssh -n ... < file`**（`-n` 和 stdin 重定向冲突）。

### 认证判定只看第三步

三步认证中前两步（`/aaa-auth/api/v1/auth`、`/user/check-only`）是检查，
`check-only` 校验极宽松，拼错账号也可能返回成功。
**只有第三步 `quickauth.do` 返回 `"message":"认证成功"` 才算真的通过。**

### ICMP 与 HTTP 劫持不同步

会话过期时校园网**只劫持 HTTP**，ICMP 照常放行。ping 得通不代表能上网。
检测必须看 HTTP 是否被 302 到门户页。

门户特征串：`usertemp|henu-jinming|wlanacname|wlanuserip`。
**不要用 `/portal/`**——真实百度页面的工信部备案链接含这个字符串，会误判。

---

## 六、开发流程

改完东西按需更新：

1. `文档/路由器当前状态.md` —— 配置变了就更新
2. `文档/开发日志_按日期.md` —— 追加当日工作摘要
3. `文档/开发日志.md` —— 只有大的技术工作才写新 Phase
4. `CLAUDE.md` —— 文件导航、坑、关键路径变了才改
5. 改过 `开发日志.md` 后跑 `python 文档/convert_to_html.py`
6. `git add -A && git commit && git push`

**文档写的原则**：给不同读者分流（见 README），不写重复内容。
日常操作、排障、原理、刷机各自独立成文，不要混在一起。

---

## 七、推送

```bash
git push                 # origin：Gitee + GitHub 双 pushurl
git push github main     # GitHub 走 SSH，origin 卡住时用
```

`origin` 的第二个 pushurl 内嵌了一个 GitHub PAT（明文在 `.git/config`，不会被提交但也该撤销）。
Gitee 免费仓库**不支持 Git LFS**，152MB 的 rar 实际只存在 GitHub。

本机直连 github.com 超时，需走代理 `http://127.0.0.1:7897`。
