#!/bin/sh
# 开机等待网络就绪后自动认证（最长等 10 分钟）
LOG_FILE="/tmp/campus_network.log"
log() { echo "[$(date +%Y-%m-%d\ %H:%M:%S)] [BootAuth] $1" >> $LOG_FILE; }

log "开机认证：等待网络就绪..."
i=0
while [ $i -lt 60 ]; do
    if ip addr show phy1-sta0 2>/dev/null | grep -q "inet " && ip route show default 2>/dev/null | grep -q phy1-sta0; then
        log "网络就绪（约$((i * 10))秒），执行认证检测..."
        /etc/campus_network/auto_login.sh
        exit 0
    fi
    sleep 10
    i=$((i + 1))
done
log "等待超时（10分钟），直接执行认证检测..."
/etc/campus_network/auto_login.sh
