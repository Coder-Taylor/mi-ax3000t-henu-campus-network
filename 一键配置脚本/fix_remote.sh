#!/bin/sh
# ============================================================
#  fix_remote.sh — 校园网认证一键修复
#
#  由 !FIX.bat 通过 ssh 送进路由器执行，不需要手动上传。
#  做四件事：
#    1. 诊断：无线是否连着校园网、有没有 IP、有没有默认路由
#    2. 检查连接校园网的那个无线接口有没有被误设密码
#    3. 按故障类型修复（能轻则轻，不动整块无线）
#    4. 验证并给出下一步
#
#  注意：故意不用 wifi reload。满流量时它会让内核崩溃，
#        只在"无线配置确实错了且当前断开"时才用一次。
# ============================================================

PATH=/usr/sbin:/usr/bin:/sbin:/bin
STA="phy1-sta0"
AUTOLOGIN="/etc/campus_network/auto_login.sh"

echo ""
echo "=============================================="
echo "  校园网认证修复"
echo "=============================================="

# ---------- 第 0 步：找连接校园网的那个无线接口 ----------
STASEC=$(uci show wireless 2>/dev/null | grep "\.mode='sta'" | sed "s/^wireless\.//; s/\.mode=.*//" | head -1)
if [ -z "$STASEC" ]; then
    echo ""
    echo "[X] 找不到 STA 模式的无线接口。"
    echo "    这台路由器可能还没配置无线 WAN，或者配置被清空了。"
    echo "    请联系给你配置的人。"
    exit 1
fi
echo ""
echo "连接校园网的接口配置名：$STASEC"

MODE=$(uci -q get wireless."$STASEC".mode)
SSID=$(uci -q get wireless."$STASEC".ssid)
ENC=$(uci -q get wireless."$STASEC".encryption)
KEY=$(uci -q get wireless."$STASEC".key)
NET=$(uci -q get wireless."$STASEC".network)

echo "  mode       = $MODE"
echo "  ssid       = $SSID"
echo "  encryption = $ENC"
echo "  network    = $NET"

NEED_WIFI_FIX=0

# ---------- 第 1 步：无线链路 ----------
echo ""
echo "[1/5] 检查无线链路..."
LINK=$(iw dev "$STA" link 2>/dev/null | head -1)
echo "  $LINK"

if echo "$LINK" | grep -q "Not connected"; then
    LINK_OK=0
else
    LINK_OK=1
fi

# ---------- 第 2 步：配置校验 ----------
echo ""
echo "[2/5] 检查接口配置..."

if [ -n "$SSID" ] && [ "$SSID" != "henu-student" ]; then
    echo "  [!] SSID 不是 henu-student，当前是「$SSID」"
    echo "      正在改回 henu-student"
    uci set wireless."$STASEC".ssid='henu-student'
    NEED_WIFI_FIX=1
fi

if [ -n "$ENC" ] && [ "$ENC" != "none" ]; then
    echo "  [!] 这个接口被设了加密方式「$ENC」"
    echo "      校园网是开放网络，这里必须改成 none"
    uci set wireless."$STASEC".encryption='none'
    NEED_WIFI_FIX=1
fi

if [ -n "$KEY" ]; then
    echo "  [!] 这个接口被设了 WiFi 密码 —— 这就是上不了网的原因"
    echo "      正在删除这个密码"
    uci delete wireless."$STASEC".key
    NEED_WIFI_FIX=1
fi

if [ -z "$NET" ]; then
    echo "  [!] 没有绑定 network，补上 wwan"
    uci set wireless."$STASEC".network='wwan'
    NEED_WIFI_FIX=1
fi

if [ "$NEED_WIFI_FIX" = "1" ]; then
    uci commit wireless
    echo "  配置已改好（已 commit）"
else
    echo "  OK，配置没问题"
fi

# ---------- 第 3 步：按情况修复 ----------
echo ""
echo "[3/5] 修复..."

if [ "$NEED_WIFI_FIX" = "1" ]; then
    if [ "$LINK_OK" = "0" ]; then
        # 当前断开 = 没有流量在跑，此时重启无线相对安全
        echo "  无线配置改过、且当前未连接，重启无线使配置生效..."
        echo "  （约 20 秒，期间所有设备会短暂断开）"
        wifi reload >/dev/null 2>&1
        sleep 12
    else
        echo "  无线还连着，先不重启无线，只重连 wwan 接口"
        ubus call network.interface.wwan down >/dev/null 2>&1
        sleep 2
        ubus call network.interface.wwan up >/dev/null 2>&1
        sleep 12
        echo "  注意：新配置要等下次重启才完全生效"
    fi
else
    echo "  重连 wwan 接口..."
    ubus call network.interface.wwan down >/dev/null 2>&1
    sleep 2
    ubus call network.interface.wwan up >/dev/null 2>&1
    sleep 15
fi

# ---------- 第 4 步：验证 ----------
echo ""
echo "[4/5] 验证..."

LINK=$(iw dev "$STA" link 2>/dev/null | head -1)
IPADDR=$(ip -4 addr show dev "$STA" 2>/dev/null | grep "inet " | awk '{print $2}')
DEFAULT=$(ip route 2>/dev/null | grep "^default.*$STA")

echo "  无线:   $LINK"
echo "  IP:     ${IPADDR:-（没有）}"
echo "  默认路由: ${DEFAULT:-（没有）}"

if [ -z "$IPADDR" ]; then
    echo ""
    echo "  还没拿到 IP，再等 15 秒并重新续租..."
    ifup wwan >/dev/null 2>&1
    sleep 15
    IPADDR=$(ip -4 addr show dev "$STA" 2>/dev/null | grep "inet " | awk '{print $2}')
    echo "  IP:     ${IPADDR:-（仍然没有）}"
fi

if [ -z "$IPADDR" ]; then
    echo ""
    echo "[X] 拿不到校园网 IP。"
    echo "    可能原因："
    echo "      · 路由器离校园网 AP 太远，信号不足"
    echo "      · 校园网侧拒绝分配（账号被锁 / 端口限制）"
    echo "      · 需要重新扫描并连接信号更强的 AP"
    echo ""
    echo "    请看当前信号强度："
    iw dev "$STA" link 2>/dev/null | grep -E "signal|freq|bitrate" | sed 's/^/      /'
    echo ""
    echo "    把上面的输出发给帮你配置的人。"
    exit 1
fi

# ---------- 第 5 步：认证 ----------
echo ""
echo "[5/5] 测试外网并重新认证..."

if ping -c 3 -W 3 223.5.5.5 >/dev/null 2>&1; then
    echo "  外网已通，不需要重新认证。"
    echo ""
    echo "=============================================="
    echo "  修复完成"
    echo "=============================================="
    echo "  宿舍 WiFi 现在可以正常上网了。"
    exit 0
fi

echo "  外网不通，执行强制认证..."
if [ -x "$AUTOLOGIN" ] || [ -f "$AUTOLOGIN" ]; then
    sh "$AUTOLOGIN" --force >/dev/null 2>&1
    sleep 5
else
    echo "  [!] 找不到 $AUTOLOGIN"
fi

if ping -c 3 -W 3 223.5.5.5 >/dev/null 2>&1; then
    echo ""
    echo "=============================================="
    echo "  修复完成"
    echo "=============================================="
    echo "  宿舍 WiFi 现在可以正常上网了。"
    exit 0
fi

# ---------- 失败：给出诊断信息 ----------
echo ""
echo "=============================================="
echo "  还没通，下面是诊断信息"
echo "=============================================="
echo ""
echo "--- 最近 20 行认证日志 ---"
tail -20 /tmp/campus_network.log 2>/dev/null || echo "（日志为空）"
echo ""
echo "--- 信号强度 ---"
iw dev "$STA" link 2>/dev/null | grep -E "signal|freq|bitrate" | sed 's/^/  /'
echo ""
echo "--- CAKE 队列 ---"
tc qdisc show dev "$STA" 2>/dev/null | head -2
echo ""
echo "请把这段输出原样发给帮你配置的人。"
exit 2
