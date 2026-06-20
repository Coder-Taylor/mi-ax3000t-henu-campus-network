#!/bin/sh
# ============================================================
#  校园网 DNS 修复脚本 v2.2
#  修复：WiFi下无法访问校园网内部网站 + 防止设备重连断联
#
#  问题1: 校园 DHCP DNS (111.6.174.198) 返回不可达IP 或 解析为空
#     zwyy.henu.edu.cn    → 125.219.33.206   → /etc/hosts 写死: 202.196.96.29
#     software.henu.edu.cn → 解析为空          → /etc/hosts 写死: 58.212.123.41
#     net.henu.edu.cn     → 58.212.123.41(公网) → /etc/hosts 写死: 172.31.7.4(内网)
#     xg.henu.edu.cn      → 172.31.0.6       → 114.114.114.114
#     jwgl.henu.edu.cn    → 211.142.109.84   → 111.6.174.198
#     superhuazai.me      → 校园DNS间歇解析异常 → /etc/hosts 写死: 104.21.18.208 (Cloudflare)
#
#  问题2: dnsmasq rebind 丢弃 RFC1918 私有IP
#     → rebind-domain-ok=/henu.edu.cn/ /ntp.org.cn/
#
#  问题3: DNS返回IPv6, 但路由器无IPv6路由
#     → filter_aaaa=1 (全局过滤AAAA)
#
#  用法：在路由器上运行  sh dns_fix.sh
# ============================================================

echo "================================================="
echo " 校园网 DNS 修复工具 v2.2 (含 Phase 13 DHCP 调优)"
echo "================================================="
echo ""

[ ! -f /etc/config/dhcp ] && echo "❌ 请在路由器上运行！" && exit 1

cp /etc/config/dhcp /etc/config/dhcp.bak.$(date +%Y%m%d%H%M%S)
echo "✅ 已备份 /etc/config/dhcp"

# === Fix 1: /etc/hosts 静态解析（最可靠，不依赖DNS） ===
if grep -q 'zwyy.henu.edu.cn' /etc/hosts; then
    echo "  [skip] /etc/hosts: zwyy 已存在"
else
    echo '202.196.96.29 zwyy.henu.edu.cn' >> /etc/hosts
    echo "  [add]  /etc/hosts: zwyy.henu.edu.cn → 202.196.96.29"
fi

if grep -q 'software.henu.edu.cn' /etc/hosts; then
    echo "  [skip] /etc/hosts: software 已存在"
else
    echo '58.212.123.41 software.henu.edu.cn' >> /etc/hosts
    echo "  [add]  /etc/hosts: software.henu.edu.cn → 58.212.123.41"
fi

if grep -q 'superhuazai.me' /etc/hosts; then
    echo "  [skip] /etc/hosts: superhuazai 已存在"
else
    echo '104.21.18.208 superhuazai.me' >> /etc/hosts
    echo "  [add]  /etc/hosts: superhuazai.me → 104.21.18.208 (Cloudflare)"
fi

if grep -q 'net.henu.edu.cn' /etc/hosts; then
    echo "  [skip] /etc/hosts: net 已存在"
else
    echo '172.31.7.4 net.henu.edu.cn' >> /etc/hosts
    echo "  [add]  /etc/hosts: net.henu.edu.cn → 172.31.7.4"
fi

# === Fix 2: 精确域名 DNS 转发 ===
for item in "xg.henu.edu.cn:114.114.114.114" "jwgl.henu.edu.cn:111.6.174.198"; do
    domain=${item%%:*}
    dns=${item##*:}
    if uci show dhcp 2>/dev/null | grep -q "server.*${domain}.*${dns}"; then
        echo "  [skip] ${domain} -> ${dns} (已存在)"
    else
        uci add_list dhcp.@dnsmasq[0].server="/${domain}/${dns}"
        echo "  [add]  ${domain} -> ${dns}"
    fi
done

# === Fix 3: 过滤 AAAA 记录（路由器无IPv6，避免手机优先尝试IPv6超时） ===
uci set dhcp.@dnsmasq[0].filter_aaaa='1'
echo "  [set]  filter_aaaa=1 (过滤IPv6)"

# === Fix 4: 允许 henu.edu.cn/ntp.org.cn 返回 RFC1918 私有IP ===
if grep -q 'rebind-domain-ok=/henu.edu.cn/ /ntp.org.cn/' /etc/dnsmasq.conf; then
    echo "  [skip] rebind-domain-ok=/henu.edu.cn/ /ntp.org.cn/ (已存在)"
elif grep -q 'rebind-domain-ok=/henu.edu.cn/' /etc/dnsmasq.conf; then
    # 升级旧版：添加 ntp.org.cn 豁免
    sed -i 's|rebind-domain-ok=/henu.edu.cn/|rebind-domain-ok=/henu.edu.cn/ /ntp.org.cn/|' /etc/dnsmasq.conf
    echo "  [upd]  rebind-domain-ok: 新增 /ntp.org.cn/ (抑制NTP DNS rebind告警)"
else
    echo 'rebind-domain-ok=/henu.edu.cn/ /ntp.org.cn/' >> /etc/dnsmasq.conf
    echo "  [add]  rebind-domain-ok=/henu.edu.cn/ /ntp.org.cn/"
fi

# === Fix 5: 确保日志不被丢弃 ===
sed -i 's/^log-facility=\/dev\/null/#log-facility=\/dev\/null/' /etc/dnsmasq.conf 2>/dev/null

# === Fix 6: Phase 13 — 延长 DHCP 租约，防止设备重连触发连锁断联 ===
CUR_LEASE=$(uci get dhcp.lan.leasetime 2>/dev/null)
if [ "$CUR_LEASE" != "168h" ]; then
    uci set dhcp.lan.leasetime='168h'
    echo "  [set]  DHCP 租约: ${CUR_LEASE:-默认} → 168h (7天，防设备重连断联)"
else
    echo "  [skip] DHCP 租约: 168h (已是7天)"
fi

uci commit dhcp
/etc/init.d/dnsmasq restart 2>/dev/null
sleep 2

echo ""
echo "=== 验证 ==="
for d in zwyy.henu.edu.cn software.henu.edu.cn net.henu.edu.cn jwgl.henu.edu.cn xg.henu.edu.cn superhuazai.me; do
    IP=$(nslookup $d 2>&1 | grep -oE 'Address: [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | grep -v '127.0.0.1' | awk '{print $2}' | head -1)
    if [ -z "$IP" ]; then
        echo "  ⚠️  $d → 解析失败"
    elif ping -c 1 -W 1 $IP >/dev/null 2>&1; then
        echo "  ✅ $d → $IP"
    else
        echo "  ❌ $d → $IP (不可达)"
    fi
done
echo ""
echo "================================================="
echo " 修复完成！切换飞行模式清除手机DNS缓存后再试。"
echo "================================================="
