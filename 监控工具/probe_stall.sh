#!/bin/sh
# probe_stall.sh — 网络间歇性卡顿探针（v1.0，2026-10-28）
#
# 背景：偶发"视频/表情包转圈很久，但大流量下载正常"，现场抓不到证据。
#        本脚本每分钟在路由器上测 4 个视频/图片站点，正常时不吭声，
#        一旦某站 TLS/首字节超过 2 秒或请求失败，立刻记一份现场快照：
#        RTT、WiFi 速率/信号、CAKE 计数、负载、内存。
#        正常时每 30 分钟留一行心跳，用来确认探针没死。
#
# 部署：ssh ax3000t "cat > /root/probe_stall.sh" < probe_stall.sh
#      crontab 加一行（严禁 @reboot，本机 crond 不支持）：
#      * * * * * /root/probe_stall.sh >/dev/null 2>&1
# 查看：tail -50 /overlay/probe.log
# 判读：日志里带 "卡顿:" 的行 = 那一刻确实慢，看同一行的 wifi/cake/rtt 判断是
#        无线链路、限速队列，还是上游校园网的问题。

LOG=/overlay/probe.log
HB=/tmp/probe_hb
TARGETS="https://i0.hdslb.com/ https://www.douyin.com/ https://mmbiz.qpic.cn/ https://www.bilibili.com/"

bad=""
for u in $TARGETS; do
    r=$(curl -s -o /dev/null --max-time 12 -w '%{http_code} %{time_namelookup} %{time_starttransfer} %{time_total}' "$u" 2>/dev/null)
    set -- $r
    code=$1
    dns=$2
    ttfb=$3
    total=$4
    slow=$(awk -v v="${ttfb:-0}" 'BEGIN{print (v>2)?1:0}')
    if [ "$code" = "000" ] || [ -z "$code" ] || [ "$slow" = "1" ]; then
        bad="$bad ${u#https://}(code=$code dns=$dns ttfb=$ttfb total=$total)"
    fi
done

if [ -n "$bad" ]; then
    {
        echo "=== $(date '+%Y-%m-%d %H:%M:%S') 卡顿:$bad"
        echo "load:$(cut -d' ' -f1-3 /proc/loadavg) mem_free:$(free -m | awk '/Mem:/{print $4}')M"
        echo "wifi:$(iw dev phy1-sta0 link | grep -E 'signal:|tx bitrate|rx bitrate' | tr -d '\t' | tr '\n' ' ')"
        echo "egress:$(tc -s qdisc show dev phy1-sta0 | sed -n '2p;9,12p' | tr '\n' ' ')"
        echo "ifb:$(tc -s qdisc show dev ifb4phy1-sta0 | sed -n '2p;9,12p' | tr '\n' ' ')"
        echo "rtt:$(ping -c 4 -W 2 223.5.5.5 2>/dev/null | tail -1)"
    } >> "$LOG"
    # 日志超过 300KB 截断，只留后 1000 行
    if [ "$(wc -c < "$LOG" 2>/dev/null || echo 0)" -gt 300000 ]; then
        tail -1000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
    fi
else
    now=$(date +%s)
    last=$(cat "$HB" 2>/dev/null || echo 0)
    if [ $((now - last)) -ge 1800 ]; then
        echo "$now" > "$HB"
        echo "--- $(date '+%Y-%m-%d %H:%M:%S') 正常 load:$(cut -d' ' -f1 /proc/loadavg)" >> "$LOG"
    fi
fi
exit 0
