#!/bin/sh
# ============================================================
#  握手探针 v1.0
#
#  背景：偶发"第一次连不上，重试就好"（原神首包探测、视频首帧、
#        表情包加载）。这类故障只发生在连接建立阶段，事后查不到。
#
#  与 probe_stall.sh 的分工：
#    probe_stall.sh  —— 测"下载快不快"（TTFB、带宽）
#    本脚本          —— 测"连得上连不上"（DNS/建连/TLS 三段握手）
#
#  核心思路：把一次连接拆成三段分别计时。
#    握手失败时，哪一段是 0 或超时，就能直接指认故障环节。
#
#  部署：cron 每分钟
#    * * * * * /root/probe_handshake.sh >/dev/null 2>&1
# ============================================================

LOG=/overlay/handshake.log
MAXLOG=300000          # 超过 300KB 截断到后 1000 行
FAILLOG=/tmp/hs_streak
HEARTBEAT=1800         # 正常时每 30 分钟留一行

# 被测目标：覆盖你实际会卡的三类场景
#   mihoyo    —— 原神启动/资源校验
#   hdslb     —— B 站视频首帧
#   qpic      —— 微信表情包
#   gstatic   —— 通用公网基线（判断是不是全网都慢）
TARGETS="
https://sdk-static.mihoyo.com/
https://autopatchcn.yuanshen.com/
https://i0.hdslb.com/
https://mmbiz.qpic.cn/
https://www.gstatic.com/generate_204
"

NOW=$(date "+%Y-%m-%d %H:%M:%S")

# --- 数值格式化：busybox 无 bc，用 awk ---
fmt() {
    awk -v v="${1:-0}" 'BEGIN{printf "%.3f", v}'
}

probe_one() {
    url="$1"
    # 关键：只取三段计时，不要 body（--max-time 保护）
    # busybox curl 支持 time_namelookup / time_connect / time_appconnect
    out=$(curl -s -o /dev/null --connect-timeout 3 --max-time 8 \
        -w "%{http_code} %{time_namelookup} %{time_connect} %{time_appconnect} %{time_starttransfer}" \
        "$url" 2>/dev/null)
    rc=$?

    if [ $rc -ne 0 ] || [ -z "$out" ]; then
        # curl 失败：区分错误类型
        case $rc in
            6)  err="DNS失败" ;;
            7)  err="TCP拒绝" ;;
            28) err="超时" ;;
            35|60) err="TLS失败" ;;
            *)  err="rc=$rc" ;;
        esac
        echo "FAIL|${url#https://}|${err}"
        return 1
    fi

    code=$(echo "$out" | awk '{print $1}')
    dns=$(echo "$out" | awk '{print $2}')
    tcp=$(echo "$out" | awk '{print $3}')
    tls=$(echo "$out" | awk '{print $4}')
    ttfb=$(echo "$out" | awk '{print $5}')

    # 判定：哪一段异常
    bad=""
    # DNS > 1 秒 = 解析慢（上游丢包特征）
    awk -v v="$dns" 'BEGIN{exit !(v>1.0)}' && bad="${bad} DNS=$dns"
    # 建连 > 1 秒 = TCP 握手慢（空口/链路问题）
    awk -v v="$tcp" 'BEGIN{exit !(v>1.0)}' && bad="${bad} TCP建连=$tcp"
    # TLS > 2 秒 = 证书握手慢（对端或中间设备）
    awk -v v="$tls" 'BEGIN{exit !(v>2.0)}' && bad="${bad} TLS=$tls"
    # code 000 = 请求根本没发出去
    [ "$code" = "000" ] && bad="${bad} code=000"

    if [ -n "$bad" ]; then
        echo "SLOW|${url#https://}|${bad# }|dns=$dns tcp=$tcp tls=$tls ttfb=$ttfb"
        return 1
    fi

    echo "OK|${url#https://}|dns=$dns tcp=$tcp tls=$tls ttfb=$ttfb"
    return 0
}

# --- 抓现场快照 ---
snapshot() {
    echo "load:$(cat /proc/loadavg | awk '{print $1, $2, $3}') mem_free:$(free -m | awk '/Mem:/{print $4}')M"

    # WAN 侧
    echo "wan: $(iw dev phy1-sta0 link 2>/dev/null | grep -E 'signal|bitrate' | tr '\n' ' ')"
    echo "wan_ip: $(ip -4 addr show dev phy1-sta0 2>/dev/null | grep -oE 'inet [0-9.]+' | awk '{print $2}')"

    # 每个在线终端的信号和失败率
    # iw 输出顺序：Station -> rx packets -> tx packets -> tx failed -> signal
    # 所以在"下一个 Station"或 END 时才输出上一台的完整数据
    iw dev phy1-ap0 station dump 2>/dev/null | awk '
        /^Station/ {
            if(mac) printf "sta:%s sig=%s tx_failed=%s/%s\n", mac, (sig?sig:"?"), (tf?tf:"?"), (tp?tp:"?")
            mac=$2; sig=""; tf=""; tp=""
        }
        /signal:/ && $2 ~ /^-/ {sig=$2}
        /^[ \t]tx failed:/ {tf=$3}
        /^[ \t]tx packets:/ {tp=$3}
        END {if(mac) printf "sta:%s sig=%s tx_failed=%s/%s\n", mac, (sig?sig:"?"), (tf?tf:"?"), (tp?tp:"?")}
    '

    # CAKE 计数
    tc -s qdisc show dev phy1-sta0 2>/dev/null | grep -E "Sent|dropped" | head -2
    tc -s qdisc show dev ifb4phy1-sta0 2>/dev/null | grep -E "Sent|dropped" | head -2

    # conntrack
    echo "conntrack: $(cat /proc/sys/net/netfilter/nf_conntrack_count 2>/dev/null)/$(cat /proc/sys/net/netfilter/nf_conntrack_max 2>/dev/null)"

    # TCP 重传（累计值，看两次快照的差值才有意义）
    # /proc/net/snmp 里 "Tcp:" 出现两次：第 1 行是列名，第 2 行才是数值
    awk '/^Tcp:/{line=$0} END{split(line,a," "); printf "tcp_retranssegs=%s outsegs=%s\n", a[13], a[12]}' /proc/net/snmp

    # RTT
    echo "rtt:$(ping -c 4 -W 2 223.5.5.5 2>/dev/null | tail -1)"

    # 最近 2 分钟的 WiFi 异常事件（掉线/踢出/重连风暴）
    # 这是唯一能反映"手机侧"故障的线索，路由器侧探测看不到空口
    ev=$(logread 2>/dev/null | grep -iE "deauth|disassoc|deauthenticat|4-way handshake|MIC failure|beacon loss" | tail -6)
    if [ -n "$ev" ]; then
        echo "wifi_events:"
        echo "$ev" | sed 's/^/  /'
    fi

    # 内核最近报错（驱动层问题）
    ke=$(dmesg 2>/dev/null | grep -iE "phy1|mt7981|mt76|sta.*timeout|tx.*stuck" | tail -4)
    if [ -n "$ke" ]; then
        echo "kernel:"
        echo "$ke" | sed 's/^/  /'
    fi
}

# --- 主流程 ---
ALL_OK=1
FAILED=""
DETAIL=""

for url in $TARGETS; do
    [ -z "$url" ] && continue
    res=$(probe_one "$url")
    if [ $? -ne 0 ]; then
        ALL_OK=0
        FAILED="${FAILED} ${url#https://}"
        DETAIL="${DETAIL}
$(echo "$res" | sed 's/^/    /')"
    fi
done

if [ "$ALL_OK" = "1" ]; then
    # 全正常：只留心跳
    LAST=$(cat $FAILLOG 2>/dev/null || echo 0)
    NEXT=$((LAST + 60))
    if [ $NEXT -ge $HEARTBEAT ] || [ ! -f $FAILLOG ]; then
        echo "--- $NOW 正常" >> $LOG
        echo 0 > $FAILLOG
    else
        echo $NEXT > $FAILLOG
    fi
else
    # 有失败：完整现场
    {
        echo "=== $NOW 握手异常:${FAILED}"
        echo "$DETAIL"
        snapshot | sed 's/^/  /'
    } >> $LOG
    echo 0 > $FAILLOG
fi

# --- 日志轮转 ---
if [ -f $LOG ]; then
    SIZE=$(wc -c < $LOG)
    if [ "$SIZE" -gt $MAXLOG ]; then
        tail -1000 $LOG > /tmp/hs.tmp && mv /tmp/hs.tmp $LOG
    fi
fi
