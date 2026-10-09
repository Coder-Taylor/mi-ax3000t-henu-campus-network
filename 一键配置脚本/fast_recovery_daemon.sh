#!/bin/sh
# ==========================================================
#  快速恢复守护进程 v2.0
#  替代 cron 看门狗，实现秒级检测和恢复
#
#  v2.0 修复：
#  - 启动时等待网络接口就绪（避免在网络未初始化时触发认证）
#  - Level 4 必须路由存在才触发认证（修复无路由时白跑认证的 bug）
#  - 增加 30 秒启动冷却期（给网络充分的初始化时间）
# ==========================================================

LOG_FILE="/tmp/campus_network.log"
STA_IFACE="phy1-sta0"
CAMPUS_SSID="henu-student"
CAMPUS_CHANNEL=""

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [FastRecovery] $1" >> $LOG_FILE
}

check_sta_connected() {
    iw dev $STA_IFACE link 2>/dev/null | grep -q "Connected"
}

check_route() {
    ip route show default 2>/dev/null | grep -q "$STA_IFACE"
}

check_http_portal() {
    # 检测 HTTP 是否被校园网强制门户劫持（返回 0 = 被劫持，需重新认证）
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 http://www.baidu.com 2>/dev/null)
    if [ "$code" = "302" ]; then
        return 0
    fi
    return 1
}

check_network() {
    ping -c 1 -W 2 223.5.5.5 > /dev/null 2>&1
}

wait_for_ready() {
    log "⏳ 等待网络接口就绪..."
    local i=0
    while [ $i -lt 45 ]; do
        if ! check_sta_connected; then
            sleep 1
            i=$((i + 1))
            continue
        fi
        if ! ip addr show $STA_IFACE 2>/dev/null | grep -q "inet "; then
            sleep 1
            i=$((i + 1))
            continue
        fi
        if ! check_route; then
            sleep 1
            i=$((i + 1))
            continue
        fi
        log "✅ 网络接口就绪（${i}秒）"
        return 0
    done
    log "⚠️ 等待超时（${i}秒），继续运行..."
    return 1
}

fast_sta_reconnect() {
    log "🔄 快速重连 STA..."
    iw dev $STA_IFACE disconnect 2>/dev/null
    sleep 0.5
    iw dev $STA_IFACE connect "$CAMPUS_SSID" $CAMPUS_CHANNEL 2>/dev/null
    local i=1
    while [ $i -le 6 ]; do
        sleep 0.5
        if check_sta_connected; then
            log "✅ STA 重连成功（${i}个周期）"
            return 0
        fi
        i=$((i + 1))
    done
    log "❌ 快速重连失败，回退到 wifi reload..."
    wifi reload 2>/dev/null
    sleep 5
    return 1
}

dhcp_renew() {
    log "🔄 DHCP 续租..."
    killall -q -USR1 udhcpc 2>/dev/null
    sleep 1
    if ! check_route; then
        ifup wwan 2>/dev/null
        sleep 2
    fi
}

main_loop() {
    local fail_count=0
    local last_auth_time=0
    local http_check_count=0

    log "🚀 快速恢复守护进程启动 v2.0"
    log "   检测间隔: 1秒 | 信道: 自动跟随 STA"

    wait_for_ready

    local start_time=$(date +%s)

    while true; do
        if check_network; then
            http_check_count=$((http_check_count + 1))
            if [ $http_check_count -ge 60 ] && check_http_portal; then
                log "⚠️ 检测到 HTTP 被门户劫持（认证会话失效），触发重新认证..."
                last_auth_time=0
                http_check_count=0
                /etc/campus_network/auto_login.sh --force &
                sleep 3
            fi
            if [ $fail_count -gt 0 ]; then
                log "✅ 网络已恢复（失败次数: $fail_count）"
            fi
            fail_count=0
            sleep 1
            continue
        fi


        fail_count=$((fail_count + 1))

        if [ $fail_count -eq 1 ]; then
            log "⚠️ 网络不通，开始诊断..."
        fi

        if ! check_route; then
            log "⚠️ 默认路由丢失！(${fail_count}s)"
            if check_sta_connected; then
                log "    STA仍连接，执行DHCP续租..."
                dhcp_renew
                sleep 1
            else
                log "    STA已断开，执行快速重连..."
                fast_sta_reconnect
                sleep 1
                dhcp_renew
            fi
            if check_route && check_network; then
                log "✅ 路由恢复成功，网络已通"
                fail_count=0
                sleep 1
                continue
            fi
        fi

        # v2.0 修复：必须路由存在 + 启动冷却期 30 秒
        local now=$(date +%s)
        local uptime_sec=$((now - start_time))
        if [ $fail_count -ge 5 ] && check_route && [ $uptime_sec -ge 30 ] && [ $((now - last_auth_time)) -ge 60 ]; then
            log "🔐 路由存在但网络不通，触发认证..."
            last_auth_time=$now
            /etc/campus_network/auto_login.sh --force &
        fi

        # v2.1: 持续15秒未恢复且路由存在时，先尝试 DHCP 续租（比完整重置温和且有效）
        if [ $fail_count -ge 15 ] && check_route && ! check_network; then
            log "🔄 持续15秒未恢复，尝试 DHCP 续租加速恢复..."
            dhcp_renew
        fi

        if [ $fail_count -ge 30 ]; then
            log "🚨 持续失败30秒，执行完整重置..."
            wifi reload 2>/dev/null
            sleep 5
            ifup wwan 2>/dev/null
            sleep 3
            if check_route; then
                /etc/campus_network/auto_login.sh --force &
            fi
            fail_count=0
            start_time=$(date +%s)
        fi

        sleep 1
    done
}

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
