#!/bin/sh
# ============================================================
#  下载手法复现器 v1.0
#
#  用途：复现"游戏/App 更新资源"的真实动作序列，找出偶发失败点。
#
#  原神这类应用的资源下载不是一次 curl 就完事，而是：
#    1. 请求清单 (manifest) — 小文件，几 KB，决定要下什么
#    2. 并发下载多个分片 — 每个分片前单独建连
#    3. 每片下完校验，失败了重试
#
#  故障通常发生在 1 和 2 的"建连"上，而不是传输过程。
#  所以本脚本特意把"建连"和"传输"分开计时。
#
#  与 probe_handshake.sh 的区别：
#    probe_handshake.sh — 每分钟自动跑，安静记录
#    本脚本             — 手动跑，详细输出，用来复现和定位
#
#  用法：
#    sh repro_download.sh              # 默认跑 3 轮
#    sh repro_download.sh 10           # 跑 10 轮
#    ROUNDS=5 CONC=8 sh repro_download.sh
# ============================================================

ROUNDS=${1:-3}
CONC=${CONC:-4}
# 用几个大小不同的真实文件，覆盖"小清单"和"大分片"两类
# 这些是公开的稳定测试点
SMALL_URLS="
https://sdk-static.mihoyo.com/
https://i0.hdslb.com/
https://mmbiz.qpic.cn/
"
BIG_URL="https://speed.cloudflare.com/__down?bytes=5000000"

FAIL=0
SLOW=0
TOTAL=0

hdr() {
    echo ""
    echo "=========================================="
    echo " $1"
    echo "=========================================="
}

# 单次请求，拆三段输出
one() {
    url="$1"
    label="$2"
    out=$(curl -s -o /dev/null --connect-timeout 3 --max-time 20 \
        -w "%{http_code} %{time_namelookup} %{time_connect} %{time_appconnect} %{time_starttransfer} %{time_total} %{size_download}" \
        "$url" 2>/dev/null)
    rc=$?
    TOTAL=$((TOTAL + 1))

    if [ $rc -ne 0 ] || [ -z "$out" ]; then
        case $rc in
            6)  e="DNS 解析失败" ;;
            7)  e="TCP 连接被拒" ;;
            28) e="超时" ;;
            35) e="TLS 握手失败" ;;
            *)  e="curl 错误码 $rc" ;;
        esac
        FAIL=$((FAIL + 1))
        printf "  %-12s FAIL  %s\n" "$label" "$e"
        return 1
    fi

    code=$(echo "$out" | awk '{print $1}')
    dns=$(echo "$out"  | awk '{print $2}')
    tcp=$(echo "$out"  | awk '{print $3}')
    tls=$(echo "$out"  | awk '{print $4}')
    ttfb=$(echo "$out" | awk '{print $5}')
    tot=$(echo "$out"  | awk '{print $6}')
    sz=$(echo "$out"   | awk '{print $7}')

    # 异常判定
    flag=""
    awk -v v="$dns" 'BEGIN{exit !(v>1.0)}'  && flag="${flag}[DNS慢]"
    awk -v v="$tcp" 'BEGIN{exit !(v>1.0)}'  && flag="${flag}[建连慢]"
    awk -v v="$tls" 'BEGIN{exit !(v>2.0)}'  && flag="${flag}[TLS慢]"
    [ "$code" = "000" ] && flag="${flag}[无响应]"
    [ -n "$flag" ] && SLOW=$((SLOW + 1))

    printf "  %-12s %s dns=%-6s tcp=%-6s tls=%-6s ttfb=%-6s total=%-6s %sB %s\n" \
        "$label" "$code" "$dns" "$tcp" "$tls" "$ttfb" "$tot" "$sz" "$flag"
    return 0
}

hdr "开始: $(date '+%Y-%m-%d %H:%M:%S')  共 $ROUNDS 轮, 每轮 $CONC 并发"

# ---------- 轮次 ----------
r=1
while [ "$r" -le "$ROUNDS" ]; do
    echo ""
    echo "--- 第 $r 轮 ---"

    # 1) 小文件（模拟清单请求）
    echo "  小文件（清单类）:"
    for url in $SMALL_URLS; do
        [ -z "$url" ] && continue
        n=$(echo "$url" | sed 's|https://||; s|/.*||')
        one "$url" "$n"
    done

    # 2) 并发建连（模拟同时开多个分片连接）
    echo "  并发建连 x$CONC:"
    i=1
    while [ "$i" -le "$CONC" ]; do
        ( one "$BIG_URL" "分片$i" 2>&1 ) &
        i=$((i + 1))
    done
    wait

    r=$((r + 1))
done

# ---------- 汇总 ----------
hdr "结果"
echo "  总请求: $TOTAL"
echo "  失败:   $FAIL"
echo "  慢/异常: $SLOW"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "  有失败。看上面 FAIL 行的错误类型："
    echo "    DNS 解析失败 -> 上游 DNS 问题"
    echo "    TCP 连接被拒 -> 链路或防火墙"
    echo "    超时         -> 空口/拥塞"
    echo "    TLS 握手失败 -> 对端或中间设备"
elif [ "$SLOW" -gt 0 ]; then
    echo "  没有失败，但有慢请求。看方括号里的段名定位环节。"
else
    echo "  全部正常。"
fi

echo ""
echo "结束: $(date '+%Y-%m-%d %H:%M:%S')"
