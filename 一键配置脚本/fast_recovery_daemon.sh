#!/bin/sh
# ==========================================================
#  快速恢复守护进程 v1.0
#  替代 cron 看门狗，实现秒级检测和恢复
#
#  解决的问题：
#  - cron 每20秒检测太慢 → 本守护进程每秒检测
#  - wifi reload 太慢(8s) → 使用 iw connect 直连(2s)
#  - 重新认证太慢(15s) → 先尝试快速恢复路由
# ==========================================================

LOG_FILE="/tmp/campus_network.log"
STA_IFACE="phy1-sta0"
CAMPUS_SSID="henu-student"
CAMPUS_CHANNEL="5260"  # channel 52 frequency in MHz

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [FastRecovery] $1" >> $LOG_FILE
}

# 快速检查 STA 连接状态
check_sta_connected() {
    iw dev $STA_IFACE link 2>/dev/null | grep -q "Connected"
}

# 快速检查默认路由
check_route() {
    ip route show default 2>/dev/null | grep -q "$STA_IFACE"
}

# 快速检查网络连通性（DNS可用即网络通）
check_network() {
    ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1
}

# 【快速恢复】仅重连 STA（不用 wifi reload，快得多）
fast_sta_reconnect() {
    log "🔄 快速重连 STA..."

    # 直接连接到已知信道，跳过扫描（节省3-5秒）
    iw dev $STA_IFACE disconnect 2>/dev/null
    sleep 0.5

    # 连接到 henu-student，指定频率避免扫描
    iw dev $STA_IFACE connect "$CAMPUS_SSID" $CAMPUS_CHANNEL 2>/dev/null

    # 等待连接建立（最多3秒）
    for i in $(seq 1 6); do
        sleep 0.5
        if check_sta_connected; then
            log "✅ STA 重连成功（${i}个周期）"
            return 0
        fi
    done

    log "❌ 快速重连失败，回退到 wifi reload..."
    wifi reload 2>/dev/null
    sleep 5
    return 1
}

# DHCP 续租
dhcp_renew() {
    log "🔄 DHCP 续租..."
    # 先尝试简单续租
    killall -q -USR1 udhcpc 2>/dev/null
    sleep 1

    # 如果还是没有路由，重新 ifup
    if ! check_route; then
        ifup wwan 2>/dev/null
        sleep 2
    fi
}

# 主循环
main_loop() {
    local fail_count=0
    local last_auth_time=0

    log "🚀 快速恢复守护进程启动"
    log "   检测间隔: 1秒 | 信道锁定: $CAMPUS_CHANNEL MHz"

    while true; do
        # === 层级1: 检查网络连通性 ===
        if check_network; then
            # 网络正常，重置失败计数
            if [ $fail_count -gt 0 ]; then
                log "✅ 网络已恢复（失败次数: $fail_count）"
            fi
            fail_count=0
            sleep 1
            continue
        fi

        # === 层级2: 网络不通，诊断原因 ===
        fail_count=$((fail_count + 1))

        if [ $fail_count -eq 1 ]; then
            log "⚠️ 网络不通，开始诊断..."
        fi

        # === 层级3: 检查路由 ===
        if ! check_route; then
            log "⚠️ 默认路由丢失！(${fail_count}s)"

            if check_sta_connected; then
                # STA还在，只是路由丢了 → DHCP续租即可
                log "    STA仍连接，执行DHCP续租..."
                dhcp_renew
                sleep 1
            else
                # STA也断了 → 快速重连
                log "    STA已断开，执行快速重连..."
                fast_sta_reconnect
                sleep 1
                dhcp_renew
            fi

            # 检查路由是否恢复
            if check_route && check_network; then
                log "✅ 路由恢复成功，网络已通"
                fail_count=0
                sleep 1
                continue
            fi
        fi

        # === 层级4: 路由存在但网络不通 → 认证过期 ===
        # 避免频繁认证：至少间隔60秒
        local now=$(date +%s)
        if [ $fail_count -ge 3 ] && [ $((now - last_auth_time)) -ge 60 ]; then
            log "🔐 路由存在但网络不通，触发认证..."
            last_auth_time=$now
            /etc/campus_network/auto_login.sh &
        fi

        # === 层级5: 持续失败超过30秒 → 完整重置 ===
        if [ $fail_count -ge 30 ]; then
            log "🚨 持续失败30秒，执行完整重置..."
            wifi reload 2>/dev/null
            sleep 5
            ifup wwan 2>/dev/null
            sleep 3
            /etc/campus_network/auto_login.sh &
            fail_count=0
        fi

        sleep 1
    done
}

# 防止重复启动
PIDFILE="/var/run/fast_recovery_daemon.pid"
if [ -f "$PIDFILE" ]; then
    OLDPID=$(cat "$PIDFILE")
    if kill -0 "$OLDPID" 2>/dev/null; then
        echo "快速恢复守护进程已在运行 (PID: $OLDPID)"
        exit 0
    fi
fi
echo $$ > "$PIDFILE"

main_loop
