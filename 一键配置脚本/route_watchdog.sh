#!/bin/sh
# ==========================================================
#  路由看门狗 — 每30秒检测默认路由是否丢失
#  如果路由丢失，立即尝试恢复（不等到cron触发）
# ==========================================================

LOG_FILE="/tmp/campus_network.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Watchdog] $1" >> $LOG_FILE
}

# 检测默认路由
check_route() {
    ip route show default 2>/dev/null | grep -q "phy1-sta0"
}

# 检测 STA 是否连接
check_sta() {
    iw dev phy1-sta0 link 2>/dev/null | grep -q "Connected"
}

main() {
    if check_route; then
        # 路由正常，什么都不做
        exit 0
    fi
    
    log "⚠️ 默认路由丢失！"
    
    if check_sta; then
        log "STA 仍连接，执行 DHCP 续租..."
        ifup wwan 2>/dev/null
        sleep 3
    else
        log "STA 已断开，重新连接 WiFi..."
        wifi reload 2>/dev/null
        sleep 5
        ifup wwan 2>/dev/null
        sleep 3
    fi
    
    if check_route; then
        log "✅ 路由看门狗恢复成功"
        # 检查网络是否需要重新认证
        if ! ping -c 2 -W 3 223.5.5.5 > /dev/null 2>&1; then
            log "网络不通，触发认证脚本..."
            /etc/campus_network/auto_login.sh &
        fi
    else
        log "❌ 看门狗恢复失败"
    fi
}

main
