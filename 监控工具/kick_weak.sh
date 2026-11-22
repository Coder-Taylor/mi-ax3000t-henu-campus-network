#!/bin/sh
# ============================================================
#  弱终端剔除看门狗 v1.0
#
#  背景：2026-11-22 实测发现 phy1-ap0 上挂着 -97 dBm 的终端，
#        tx 失败率 8%（11393/142155），另有 -96 dBm 的失败率 45%。
#        这类终端用 6 Mbit/s 最低速率反复重传，占满空口时隙，
#        拖慢全宿舍其他设备的首包 —— 表现为"偶发卡一下、握手失败"。
#
#  策略：三个条件同时满足才剔除，缺一不可。
#    1. 信号 ≤ RSSI_MIN（默认 -85 dBm）
#    2. 无流量 ≥ IDLE_MIN 秒（默认 300 秒，避免误踢正在下载的）
#    3. 发送失败率 ≥ FAIL_RATE（默认 5%，避免误踢信号差但能用的）
#
#  剔除后终端会自动重连（如果它还在范围内且信号变好）。
#  如果它信号一直很差，会反复重连失败，这本身就是要的结果：
#  不让它长期占着空口。
#
#  为什么不用 disassoc_low_ack=1：
#    那个是 hostapd 内部的连续失败计数，一次性触发，不可控且会连锁
#    断掉正常设备（文档里 2026-10 就因为这个把它设成 0）。
#    这里条件明确、可调、可回滚。
#
#  部署：cron 每 2 分钟
#    */2 * * * * /root/kick_weak.sh >/dev/null 2>&1
# ============================================================

IFACE=${IFACE:-phy1-ap0}
RSSI_MIN=${RSSI_MIN:--85}      # 信号门槛，低于此值才算弱
IDLE_MIN=${IDLE_MIN:-300}      # 空闲秒数门槛
FAIL_RATE=${FAIL_RATE:-5}      # 发送失败率门槛（百分比）
LOG=/overlay/kick.log
MAXLOG=100000
DRY_RUN=${DRY_RUN:-0}

NOW=$(date "+%Y-%m-%d %H:%M:%S")

# --- 解析 iw station dump ---
# 输出格式：每台终端一段
#   Station xx:xx:... (on phy1-ap0)
#       inactive time:  <ms>
#       tx packets:     N
#       tx failed:      N
#       signal:         -97 [-100, -100] dBm
iw dev "$IFACE" station dump 2>/dev/null | awk '
    /^Station/ {
        if (mac) print mac, sig, idle, tp, tf
        mac=$2; sig=""; idle=""; tp=""; tf=""
    }
    /inactive time:/ {idle=$3}          # 毫秒
    /^[ \t]tx packets:/ {tp=$3}
    /^[ \t]tx failed:/ {tf=$3}
    /signal:/ && $2 ~ /^-/ {sig=$2}     # 只取主值，忽略方括号
    END {if (mac) print mac, sig, idle, tp, tf}
' | while read -r mac sig idle tp tf; do
    [ -z "$mac" ] && continue
    [ -z "$sig" ] && continue

    # idle 是毫秒，转秒
    idle_s=$(( idle / 1000 ))

    # 失败率（整数百分比，避免浮点）
    if [ "${tp:-0}" -gt 0 ]; then
        fail_pct=$(( tf * 100 / tp ))
    else
        fail_pct=0
    fi

    # 条件判定：信号弱 + 空闲久 + 失败率高
    weak=0; idle_ok=0; fail_ok=0
    [ "$sig" -le "$RSSI_MIN" ] && weak=1
    [ "$idle_s" -ge "$IDLE_MIN" ] && idle_ok=1
    [ "$fail_pct" -ge "$FAIL_RATE" ] && fail_ok=1

    if [ "$weak" = "1" ] && [ "$idle_ok" = "1" ] && [ "$fail_ok" = "1" ]; then
        if [ "$DRY_RUN" = "1" ]; then
            echo "[$NOW] [DRY] would kick $mac sig=${sig}dBm idle=${idle_s}s fail=${fail_pct}% (${tf}/${tp})"
        else
            iw dev "$IFACE" station del "$mac" 2>/dev/null
            echo "[$NOW] KICK $mac sig=${sig}dBm idle=${idle_s}s fail=${fail_pct}% (${tf}/${tp})"
        fi
    fi
done >> "$LOG" 2>&1

# --- 日志轮转 ---
if [ -f "$LOG" ]; then
    SIZE=$(wc -c < "$LOG")
    if [ "$SIZE" -gt "$MAXLOG" ]; then
        tail -200 "$LOG" > /tmp/kick.tmp && mv /tmp/kick.tmp "$LOG"
    fi
fi
