# Linux 入门（够用版）

刷完机，你的路由器就是一台 Linux 电脑，只是没有屏幕和键盘。
这份文档只讲**接下来会用到的那一小部分**，10 分钟能扫完。

已经用过 Linux 的可以跳过。

---

## 一、命令行是什么

用**打字**控制电脑，而不是点图标。

```
图形界面：看到图标 → 鼠标点击 → 完成
命令行：  看到光标闪 → 输入文字 → 回车 → 完成
```

**在 Windows 上打开命令行**，三种方法任选：

1. `Win + R` → 输入 `cmd` → 回车
2. 右键开始菜单 → "终端" 或 "Windows PowerShell"
3. 在文件夹地址栏输入 `cmd` → 回车（当前目录 = 这个文件夹）

打开后你会看到：

```
C:\Users\你的用户名>
```

那个 `>` 是**提示符**，意思是"我在等你输入"。

> 本文档所有代码块里的内容，都是要你在命令行里**输入并按回车**的。
> 如果行首有 `$` 或 `#`，那是提示符的表示，不要输入。

---

## 二、路径

Windows 用反斜杠和盘符，Linux 用正斜杠、没有盘符：

```
Windows:  C:\Users\HONOR\Desktop\项目\
Linux:    /etc/config/network
```

路径含中文或空格时，用双引号包住：

```bash
cd "D:\Document\学习\项目"
```

> ⚠️ Linux **严格区分大小写**。`Network`、`network`、`NETWORK` 是三个不同的东西。

---

## 三、五个必须会的命令

| 命令 | 全称 | 做什么 | 例子 |
|---|---|---|---|
| `ls` | list | 列出目录内容 | `ls /etc/config/` |
| `cat` | concatenate | 显示文件内容 | `cat /etc/os-release` |
| `cd` | change directory | 切换目录 | `cd /etc/config/` |
| `cp` | copy | 复制文件 | `cp a.txt b.txt` |
| `vi` | visual editor | 编辑文件 | `vi /etc/config/network` |

### 和 Windows 命令对照

| 操作 | Windows | Linux |
|---|---|---|
| 列文件 | `dir` | `ls` |
| 看文件内容 | `type` | `cat` |
| 切目录 | `cd` | `cd`（一样）|
| 复制 | `copy` | `cp` |
| 删除 | `del` | `rm` |
| 测网络 | `ping` | `ping`（一样）|
| 看 IP | `ipconfig` | `ip addr` |
| 清屏 | `cls` | `clear` |

---

## 四、vi 编辑器生存指南

改配置经常要编辑文件。`vi` 的操作方式和记事本完全不同，因为它有**两种模式**。

```bash
vi /etc/config/network
```

进去之后：

```
刚进去 = 命令模式（按键是命令，不会打字）
按 i   = 进入编辑模式（左下角出现 -- INSERT --，可以正常输入）
改内容
按 Esc = 回到命令模式
输入 :wq 回车 = 保存并退出
输入 :q! 回车 = 不保存退出
```

**记不住就记住这两个**：`i` 进去改，`:wq` 出来存。

> 不想用 vi 的话，LuCI 后台点鼠标效果完全一样——它背后改的是同一个文件。

---

## 五、root 是什么

`root` 是 Linux 的超级管理员，能做任何事（改系统文件、删分区、装软件）。

路由器上只有这一个用户，所以 SSH 进去直接就是 root。

提示符区分：

```
root@ImmortalWrt:~#     ← # 结尾 = root
user@ImmortalWrt:~$     ← $ 结尾 = 普通用户
```

各段含义：

```
root@ImmortalWrt:~#
 │        │      │ └─ # = root 的标志
 │        │      └─── ~ = 当前在"家目录"（/root）
 │        └────────── 主机名
 └─────────────────── 当前用户
```

---

## 六、路由器的文件系统地图

```
/
├── /etc/
│   ├── config/                  ← 所有 UCI 配置（最常改的目录）
│   │   ├── network              ← 网络接口、IP
│   │   ├── wireless             ← WiFi 设置
│   │   ├── firewall             ← 防火墙规则
│   │   └── dhcp                 ← DNS / DHCP
│   ├── init.d/                  ← 开机启动服务
│   │   ├── network
│   │   ├── campus_auth          ← 本项目的认证启动脚本
│   │   └── fast_recovery        ← 本项目的守护进程
│   └── crontabs/root            ← 定时任务表
│
├── /etc/campus_network/         ← 本项目自己的脚本目录
│   ├── auto_login.sh
│   ├── fast_recovery_daemon.sh
│   ├── route_watchdog.sh
│   ├── boot_auth.sh
│   └── dns_fix.sh
│
├── /tmp/                        ← 临时文件，⚠️ 重启就清空
│   └── campus_network.log       ← 认证日志
│
├── /overlay/                    ← 你所有修改的实际存储（重启保留）
│   └── probe.log                ← 卡顿探针日志
│
├── /rom/                        ← 出厂固件，只读，不要改
├── /usr/bin/                    ← 可执行程序
├── /www/                        ← LuCI Web 界面
├── /proc/                       ← 内核信息，虚拟的，实时生成
│   └── mtd                      ← 闪存分区表
└── /sys/class/net/              ← 网络接口信息
```

### 为什么重启不会丢配置

路由器没有硬盘，用 Flash 芯片。OpenWrt 用 **overlayfs** 叠层：

```
/rom（出厂固件，只读，永远不变）
  +  /overlay（你的修改，可写，存在 Flash 上）
  =  /（你看到的完整系统）
```

恢复出厂设置 = 清空 `/overlay`。所以重启不丢配置，`firstboot` 才丢。

> **注意**：`/tmp` 在内存里，重启一定清空。认证日志放这里是有意的——避免频繁写 Flash。

---

## 七、UCI 是什么

OpenWrt 把配置统一放在 `/etc/config/` 下，用 `uci` 命令读写。

```bash
uci show wireless              # 看所有无线配置
uci get wireless.radio1.channel    # 读某一项
uci set wireless.radio1.channel='52'   # 改某一项
uci commit wireless            # 写入文件（不 commit 等于没改）
```

**关键记忆点**：`uci set` 只是改内存里的值，**必须 `uci commit` 才写进文件**。

改完通常还要重启对应服务：

```bash
uci commit wireless
wifi reload
```

### LuCI 和 UCI 的关系

```
LuCI 网页  →  uci 命令  →  /etc/config/ 文件  →  服务读取
（点鼠标）                  （实际存储）
```

两种方式效果完全一样，看你能接受哪种。

---

## 八、几个会遇到的坑

### busybox 不是完整 Linux

路由器上的命令是精简版（busybox），有些参数不支持：

| 你以为能用 | 实际 |
|---|---|
| `sleep 0.5` | ❌ 不支持小数，只能 `sleep 1` |
| `ping -i 0.2` | ❌ 不支持小数间隔 |
| `ping -f` | ❌ 没有这个参数 |
| `diff` | ❌ 没有，用 `cmp` 或 `md5sum` |
| `od` | ❌ 没有 |
| `base64` | ❌ 没有 |
| `wget` 抓 HTTPS 重定向 | ⚠️ 可能段错误，用 `curl` 代替 |

### crontab 不支持 `@`

```bash
# ✅ 可以
*/5 * * * * /path/to/script.sh

# ❌ 会让 crond 直接崩溃退出
@reboot /path/to/script.sh
```

这台路由器的 busybox crond 没编译 `@` 关键字支持。写进去 crond 就崩，
而且 procd 会反复拉起它，进入崩溃循环——连正常的定时任务也一起失效。

开机任务请交给 `/etc/init.d/` 下的服务脚本。

### `/tmp` 里的东西会消失

`/tmp/campus_network.log` 重启就没了。需要长期保留的日志放 `/overlay/`
（refs: `/overlay/probe.log`）。

但别往 `/overlay` 频繁写——Flash 有寿命。

---

## 九、出问题时看哪里

```bash
logread | tail -40              # 系统日志
tail -50 /tmp/campus_network.log   # 本项目的认证日志
tail -50 /overlay/probe.log        # 卡顿探针
dmesg | tail -20                # 内核消息
ls /sys/fs/pstore/              # 崩溃现场（有文件说明崩过）
```

`logread` 是 OpenWrt 特有的，等价于 `journalctl`，但更轻量。

---

## 十、接着读

- [刷机指南.md](刷机指南.md) —— 具体怎么刷
- [日常使用.md](日常使用.md) —— 平时怎么用
- [排障手册.md](排障手册.md) —— 出问题怎么查
