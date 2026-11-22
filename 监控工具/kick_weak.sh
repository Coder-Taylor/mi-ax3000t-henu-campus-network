#!/bin/sh
# ============================================================
#  弱终端剔除看门狗 v2.0
#
#  v1 的问题（2026-11-22 实测）：
#    阈值 -85 dBm / 300s / 5% 太宽松。手机在宿舍走动时信号会瞬间
#    掉到 -99，持续几十秒，三个条件立刻全中，被误踢。
#    用户手机（cheng-zhi-jia-Phone）就这样被踢了 1 次，
#    之后手机自动连去隔壁 WiFi 才恢复。
#
#  v2 的改动：
#    1. 白名单 —— 自己人永不踢（WHITELIST，按 MAC 前缀匹配）
#    2. 连续命中 —— 必须连续 STREAK 次巡检都满足，才真的踢
#       默认 5 次 = 10 分钟（cron 每 2 分钟一次）
#    3. 阈值收紧 —— -85/-5% 改到 -92/15%，空闲 300s 改到 600s
#
#  真正的僵尸设备（-96 dBm 挂着几小时不走）会连续命中几十次，
#  照样被清理；而"瞬间掉信号又恢复"的正常设备一次都命不中。
#
#  部署：cron 每 2 分钟
#    */2 * * * * /root/kick_weak.sh >/dev/null 2>&1
# ============================================================

IFACE=${IFACE:-phy1-ap0}
RSSI_MIN=${RSSI_MIN:--92}      # 信号门槛（v1 是 -85，太松）
IDLE_MIN=${IDLE_MIN:-600}      # 空闲秒数门槛（v1 是 300）
FAIL_RATE=${FAIL_RATE:-15}     # 发送失败率门槛 %（v1 是 5）
STREAK=${STREAK:-5}            # 连续命中多少次才踢（v1 无此概念）

LOG=/overlay/kick.log
MAXLOG=100000
DRY_RUN=${DRY_RUN:-0}
STATE=/tmp/kick_state

# 白名单：自己人的设备，永不踢。匹配 MAC 前缀。
# 手机 cheng-zhi-jia-Phone（部分安卓会随机化 MAC，所以按前缀匹配）
WHITELIST="7e:42:d0:18:ce:ec 40:c7:3c:31:d5:67 9c:b1:50:be:14:ff 60:d4:af:05:bf:a4"

NOW=$(date "+%Y-%m-%d %H:%M:%S")

is_whitelisted() {
    m="$1"
    for w in $WHITELIST; do
        [ "$m" = "$w" ] && return 0
    done
    return 1
}

# 读上一轮的连续计数：格式 "mac=count"
get_streak() {
    m="$1"
    c=$(awk -v k="$m" '
        {split($0, a, "="); if (a[1] == k) {print a[2]; found=1; exit}}
        END {if (!found) print 0}
    ' "$STATE" 2>/dev/null)
    echo "${c:-0}"
}

# 更新计数：传入 "mac=新值" 列表
update_state() {
    printf '%s\n' "$1" > "$STATE"
}

NEWSTATE=""

# --- 解析 iw station dump ---
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
' > /tmp/kick_scan.$$

while read -r mac sig idle tp tf; do
    [ -z "$mac" ] && continue
    [ -z "$sig" ] && continue

    # 白名单直接放过
    if is_whitelisted "$mac"; then
        NEWSTATE="${NEWSTATE}${mac}=0
"
        continue
    fi

    idle_s=$(( idle / 1000 ))
    if [ "${tp:-0}" -gt 0 ]; then
        fail_pct=$(( tf * 100 / tp ))
    else
        fail_pct=0
    fi

    # 三个条件同时满足
    weak=0; idle_ok=0; fail_ok=0
    [ "$sig" -le "$RSSI_MIN" ] && weak=1
    [ "$idle_s" -ge "$IDLE_MIN" ] && idle_ok=1
    [ "$fail_pct" -ge "$FAIL_RATE" ] && fail_ok=1

    prev=$(get_streak "$mac")

    if [ "$weak" = "1" ] && [ "$idle_ok" = "1" ] && [ "$fail_ok" = "1" ]; then
        cur=$((prev + 1))
        NEWSTATE="${NEWSTATE}${mac}=${cur}
"
        if [ "$cur" -ge "$STREAK" ]; then
            if [ "$DRY_RUN" = "1" ]; then
                echo "[$NOW] [DRY] would kick $mac sig=${sig}dBm idle=${idle_s}s fail=${fail_pct}% streak=${cur}/${STREAK}"
            else
                iw dev "$IFACE" station del "$mac" 2>/dev/null
                echo "[$NOW] KICK $mac sig=${sig}dBm idle=${idle_s}s fail=${fail_pct}% (${tf}/${tp}) streak=${cur}"
            fi
            # 踢完清零，避免它重连后又立刻被踢
            NEWSTATE="${NEWSTATE}${mac}=0
"
        fi
    else
        # 不满足条件：计数清零。这就是"瞬间抖动不误伤"的关键。
        NEWSTATE="${NEWSTATE}${mac}=0
"
    fi
done < /tmp/kick_scan.$$
rm -f /tmp/kick_scan.$$

update_state "$NEWSTATE"

# --- 日志轮转 ---
if [ -f "$LOG" ]; then
    SIZE=$(wc -c < "$LOG")
    if [ "$SIZE" -gt "$MAXLOG" ]; then
        tail -200 "$LOG" > /tmp/kick.tmp && mv /tmp/kick.tmp "$LOG"
    fi
fi
