#!/bin/bash
# ============================================================
#  AX3000T 校园网自动配置脚本
#  适用：刚刷完 ImmortalWrt 大分区版的小米 AX3000T
#  功能：一键完成 WiFi 配置 + 校园网认证 + CAKE 智能流控
#  使用：在路由器 SSH 中运行此脚本
#        sh /path/to/auto_config.sh
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

banner() {
    clear 2>/dev/null || true
    echo -e "${CYAN}"
    echo "  ╔══════════════════════════════════════════════╗"
    echo "  ║                                              ║"
    echo "  ║     AX3000T 校园网自动配置工具 v1.0           ║"
    echo "  ║     ImmortalWrt 24.10 专用                   ║"
    echo "  ║                                              ║"
    echo "  ╚══════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
}

step_ok() { echo -e "  ${GREEN}[✓]${NC} $1"; }
step_fail() { echo -e "  ${RED}[✗]${NC} $1"; }
step_info() { echo -e "  ${BLUE}[i]${NC} $1"; }
step_warn() { echo -e "  ${YELLOW}[!]${NC} $1"; }
step_input() { echo -ne "  ${CYAN}[?]${NC} $1: "; }

press_enter() {
    echo ""
    echo -ne "  ${YELLOW}按 Enter 继续...${NC}"
    read -r dummy
    echo ""
}

# ============================================================
# Step 0：检查环境
# ============================================================
step0_check() {
    banner
    echo -e "${BOLD}欢迎使用 AX3000T 校园网自动配置工具！${NC}"
    echo ""
    echo "  本脚本将帮助你完成以下配置："
    echo "    1. 设置 root 密码"
    echo "    2. 配置宿舍 WiFi 热点（名称 + 密码）"
    echo "    3. 配置无线 WAN（让路由器连校园网）"
    echo "    4. 部署校园网自动认证脚本"
    echo "    5. 设置定时重连（断线自动恢复）"
    echo "    6. 安装 CAKE 智能流控（防一人占满带宽）"
    echo "    7. 美化 LuCI 管理界面（Argon 主题）"
    echo ""
    echo -e "${YELLOW}  请确保：${NC}"
    echo "    - 路由器已刷入 ImmortalWrt 24.10"
    echo "    - 路由器已通电，电脑通过网线或 WiFi 连接到路由器"
    echo "    - 能访问 http://192.168.1.1"
    echo "    - 路由器当前未连接任何 WAN 口"
    echo ""
    echo -ne "  ${CYAN}确认以上条件都满足？(y/n)${NC}: "
    read -r confirm
    case "$confirm" in
        y|Y|yes|YES)
            echo ""
            step_ok "环境检查通过"
            ;;
        *)
            echo ""
            step_warn "请先满足条件后再运行本脚本"
            exit 0
            ;;
    esac

    # 检查是否在路由器上运行
    if [ ! -f "/etc/config/wireless" ]; then
        step_fail "未检测到 OpenWrt 系统，请在路由器 SSH 中运行本脚本"
        exit 1
    fi
    step_ok "检测到 OpenWrt 系统"

    # 检查 overlay 空间
    AVAIL=$(df -m /overlay 2>/dev/null | tail -1 | awk '{print $4}')
    step_info "overlay 可用空间: ${AVAIL}MB"

    # 检查外网
    if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
        step_ok "外网连接正常"
    else
        step_warn "外网不通——稍后配置好校园网认证后才能上网"
    fi

    press_enter
}

# ============================================================
# Step 1：设置 root 密码
# ============================================================
step1_password() {
    banner
    echo -e "${BOLD}Step 1/7：设置 root 密码${NC}"
    echo ""
    echo "  root 是路由器的管理员账户。设置密码保护 SSH 和 Web 管理界面。"
    echo "  建议：至少 8 位，包含字母、数字、特殊符号"
    echo ""

    while true; do
        step_input "请输入 root 密码（输入时不显示）"
        stty -echo 2>/dev/null || true
        read -r PASS1
        stty echo 2>/dev/null || true
        echo ""

        step_input "请再次输入密码确认"
        stty -echo 2>/dev/null || true
        read -r PASS2
        stty echo 2>/dev/null || true
        echo ""

        if [ "$PASS1" = "$PASS2" ] && [ -n "$PASS1" ]; then
            ROOT_PASSWORD="$PASS1"
            break
        else
            step_warn "两次输入不一致或为空，请重试"
            echo ""
        fi
    done

    printf '%s\n%s\n' "$ROOT_PASSWORD" "$ROOT_PASSWORD" | passwd root >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        step_ok "root 密码已设置成功"
    else
        step_fail "密码设置失败，请手动执行 passwd"
        exit 1
    fi

    press_enter
}

# ============================================================
# Step 2：配置宿舍 WiFi
# ============================================================
step2_wifi() {
    banner
    echo -e "${BOLD}Step 2/7：配置宿舍 WiFi 热点${NC}"
    echo ""
    echo "  这是你宿舍设备连的 WiFi（2.4G 频段，穿墙好）。"
    echo "  另一个 5G 频段将被用作连接校园网的出口。"
    echo ""

    step_input "WiFi 名称（SSID，支持中文）"
    read -r WIFI_SSID
    [ -z "$WIFI_SSID" ] && WIFI_SSID="AX3000T-Dorm"

    echo ""
    step_input "WiFi 密码（至少 8 位）"
    stty -echo 2>/dev/null || true
    read -r WIFI_PASS
    stty echo 2>/dev/null || true
    echo ""
    [ -z "$WIFI_PASS" ] && WIFI_PASS="change.me.2026"

    echo ""
    echo -e "  WiFi 名称: ${GREEN}${WIFI_SSID}${NC}"
    echo -e "  WiFi 密码: ${GREEN}${WIFI_PASS}${NC}"
    echo ""
    echo -ne "  ${CYAN}确认？(y/n)${NC}: "
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ] && [ "$confirm" != "yes" ]; then
        step_warn "已取消，将使用默认值"
        WIFI_SSID="AX3000T-Dorm"
        WIFI_PASS="change.me.2026"
    fi

    # 配置 2.4G AP
    uci set wireless.default_radio0.ssid="$WIFI_SSID"
    uci set wireless.default_radio0.encryption='psk2'
    uci set wireless.default_radio0.key="$WIFI_PASS"
    # Phase 13: hostapd 调优 — 防止设备重连导致其他设备断联
    uci set wireless.default_radio0.disassoc_low_ack='0'
    uci set wireless.default_radio0.skip_inactivity_poll='1'
    uci set wireless.default_radio0.wpa_group_rekey='86400'
    uci set wireless.default_radio0.uapsd='0'
    uci set wireless.default_radio0.auth_cache='1'
    uci commit wireless

    step_ok "2.4G 宿舍 WiFi 配置完成（含 Phase 13 hostapd 调优）"

    # ── 5G AP：在 radio1 上创建第二个热点（复用2.4G的SSID+密码，加-5G后缀）──
    echo ""
    echo -e "  ${BLUE}[i]${NC} 正在配置 5G 宿舍 WiFi（wifinet0）..."
    WIFI_5G_SSID="${WIFI_SSID}-5G"

    # 锁定5G信道（ch52），避免 ACS 触发 radio reset
    uci set wireless.radio1.channel='52'
    uci set wireless.radio1.htmode='HE40'

    # 创建 wifinet0（如果已存在则更新）
    if ! uci get wireless.wifinet0 >/dev/null 2>&1; then
        uci set wireless.wifinet0='wifi-iface'
        uci set wireless.wifinet0.device='radio1'
        uci set wireless.wifinet0.mode='ap'
        step_info "创建 wifinet0 5G AP 接口"
    fi
    uci set wireless.wifinet0.ssid="$WIFI_5G_SSID"
    uci set wireless.wifinet0.encryption='psk2'
    uci set wireless.wifinet0.key="$WIFI_PASS"
    uci set wireless.wifinet0.network='lan'
    # Phase 13: hostapd 调优
    uci set wireless.wifinet0.disassoc_low_ack='0'
    uci set wireless.wifinet0.skip_inactivity_poll='1'
    uci set wireless.wifinet0.wpa_group_rekey='86400'
    uci set wireless.wifinet0.uapsd='0'
    uci set wireless.wifinet0.auth_cache='1'
    uci commit wireless

    step_ok "5G 宿舍 WiFi 配置完成: ${WIFI_5G_SSID} (ch52/HE40, 含 Phase 13 调优)"

    press_enter
}

# ============================================================
# Step 3：配置 WiFi WAN（连接校园网）
# ============================================================
step3_wwan() {
    banner
    echo -e "${BOLD}Step 3/7：配置无线 WAN——让路由器连校园网${NC}"
    echo ""
    echo "  路由器将通过 5G radio 无线连接到校园网 WiFi。"
    echo "  校园网 WiFi 通常是开放网络（无密码），需要 Portal 认证。"
    echo ""
    echo "  请确保你能看到校园网 WiFi 信号。"
    echo ""

    step_input "校园网 WiFi 名称（SSID）"
    read -r CAMPUS_SSID
    [ -z "$CAMPUS_SSID" ] && CAMPUS_SSID="henu-student"

    echo ""
    step_input "校园网 WiFi 是否需要密码？(y/n)"
    read -r has_enc
    CAMPUS_ENC="none"
    CAMPUS_WIFIKEY=""
    if [ "$has_enc" = "y" ] || [ "$has_enc" = "Y" ]; then
        step_input "请输入校园网 WiFi 密码"
        stty -echo 2>/dev/null || true
        read -r CAMPUS_WIFIKEY
        stty echo 2>/dev/null || true
        echo ""
        CAMPUS_ENC="psk2"
    fi

    echo ""
    echo -e "  校园网 SSID: ${GREEN}${CAMPUS_SSID}${NC}"
    echo -e "  校园网加密: ${GREEN}${CAMPUS_ENC}${NC}"
    echo ""
    echo -ne "  ${CYAN}确认？(y/n)${NC}: "
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        step_warn "已取消，将使用 henu-student（开放网络）"
        CAMPUS_SSID="henu-student"
        CAMPUS_ENC="none"
    fi

    # 备份
    cp /etc/config/wireless /etc/config/wireless.bak 2>/dev/null
    cp /etc/config/network /etc/config/network.bak 2>/dev/null
    cp /etc/config/firewall /etc/config/firewall.bak 2>/dev/null
    step_ok "已备份当前配置"

    # radio1 改为 STA 模式
    uci set wireless.default_radio1.mode='sta'
    uci set wireless.default_radio1.ssid="$CAMPUS_SSID"
    uci set wireless.default_radio1.encryption="$CAMPUS_ENC"
    [ -n "$CAMPUS_WIFIKEY" ] && uci set wireless.default_radio1.key="$CAMPUS_WIFIKEY" || uci delete wireless.default_radio1.key 2>/dev/null || true
    uci set wireless.default_radio1.network='wwan'
    uci set wireless.radio1.channel='auto'
    uci commit wireless
    step_ok "radio1 (5G) 已改为 STA 客户端模式"

    # 创建 wwan 接口
    uci set network.wwan='interface'
    uci set network.wwan.proto='dhcp'
    uci commit network
    step_ok "wwan 网络接口已创建（DHCP）"

    # 防火墙
    uci add_list firewall.@zone[1].network='wwan' 2>/dev/null || true
    uci commit firewall
    step_ok "防火墙：wwan 已加入 WAN 区域"

    # 关闭 fullcone（避免 NAT bug）
    uci set firewall.@defaults[0].fullcone='0'
    uci set firewall.@defaults[0].fullcone6='0'
    uci commit firewall
    step_ok "防火墙：fullcone 已关闭，使用标准 NAT"

    # 应用
    echo ""
    step_info "正在应用 WiFi 配置..."
    wifi reload 2>&1 | while IFS= read -r line; do echo "         $line"; done
    sleep 3

    # 验证
    echo ""
    if iw dev phy1-sta0 link 2>/dev/null | grep -q "Connected"; then
        step_ok "5G STA 已成功连接 $CAMPUS_SSID"

        ifup wwan 2>/dev/null
        sleep 3

        WAN_IP=$(ip addr show dev phy1-sta0 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1)
        if [ -n "$WAN_IP" ]; then
            step_ok "已获取校园网 IP: $WAN_IP"
        else
            step_warn "暂未获取 IP，稍后认证脚本会自动处理"
        fi
    else
        step_warn "STA 连接可能未成功，请检查校园网 WiFi 是否在范围内"
        echo "         可以稍后手动运行: wifi reload"
    fi

    # 重启防火墙
    fw4 restart 2>&1 | while IFS= read -r line; do echo "         $line"; done
    step_ok "防火墙已重启"

    press_enter
}

# ============================================================
# Step 4：部署校园网认证脚本
# ============================================================
step4_auth() {
    banner
    echo -e "${BOLD}Step 4/7：部署校园网 Portal 认证脚本${NC}"
    echo ""
    echo "  校园网连接后需要在 Portal 页面认证才能上外网。"
    echo "  本脚本会自动完成认证，无需人工打开浏览器。"
    echo ""
    echo "  需要以下信息（河大校园网）："
    echo "    - 学号"
    echo "    - 校园网密码"
    echo "    - 运营商后缀 (@henuyd=移动, @henult=联通, @henudx=电信)"
    echo ""

    step_input "学号"
    read -r AUTH_USER
    [ -z "$AUTH_USER" ] && read -p "学号: " AUTH_USER

    echo ""
    step_input "校园网密码"
    stty -echo 2>/dev/null || true
    read -r AUTH_PASS
    stty echo 2>/dev/null || true
    echo ""
    [ -z "$AUTH_PASS" ] && read -p "校园网密码: " AUTH_PASS

    echo ""
    echo "  运营商后缀:"
    echo "    1. @henuyd  (移动)"
    echo "    2. @henult  (联通)"
    echo "    3. @henudx  (电信)"
    echo ""
    step_input "请选择 (1/2/3)"
    read -r op_choice
    case "$op_choice" in
        2) AUTH_OP="@henult" ;;
        3) AUTH_OP="@henudx" ;;
        *) AUTH_OP="@henuyd" ;;
    esac

    echo ""
    step_input "校编码（默认河大：07cdfd23373b17c6b337251c22b7ea57，直接回车使用默认）"
    read -r AUTH_CODE
    [ -z "$AUTH_CODE" ] && AUTH_CODE="07cdfd23373b17c6b337251c22b7ea57"

    echo ""
    echo -e "  学号:     ${GREEN}${AUTH_USER}${NC}"
    echo -e "  密码:     ${GREEN}${AUTH_PASS}${NC}"
    echo -e "  运营商:   ${GREEN}${AUTH_OP}${NC}"
    echo -e "  校编码:   ${GREEN}${AUTH_CODE}${NC}"
    echo ""
    echo -ne "  ${CYAN}确认？(y/n)${NC}: "
    read -r confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        step_warn "已取消，请手动修改 /etc/campus_network/auto_login.sh"
        return 1
    fi

    mkdir -p /etc/campus_network

    cat > /etc/campus_network/auto_login.sh << 'SCRIPT_EOF'
#!/bin/sh
# ==========================================================
#  校园网自动认证脚本 v3.0
#  v3.0: 增加 preflight_check（认证前检查网络就绪）
#        first_auth 增加重试机制
# ==========================================================

USERNAME="${AUTH_USER}"
PASSWORD="${AUTH_PASS}"
OPERATOR_SUFFIX="${AUTH_OP}"
CAMPUS_CODE="${AUTH_CODE}"

LOG_FILE="/tmp/campus_network.log"
STA_IFACE="phy1-sta0"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

# 新增：认证前预检查
preflight_check() {
    # 1. 检查 STA 接口有 IP
    if ! ip addr show $STA_IFACE 2>/dev/null | grep -q "inet "; then
        log "⚠️ 预检查失败: STA 接口无 IP"
        return 1
    fi

    # 2. 检查默认路由存在
    if ! ip route show default 2>/dev/null | grep -q "$STA_IFACE"; then
        log "⚠️ 预检查失败: 无默认路由"
        return 1
    fi

    # 3. 检查认证服务器可达（ping）
    if ! ping -c 1 -W 2 172.29.35.27 >/dev/null 2>&1; then
        log "⚠️ 预检查失败: 认证服务器不可达"
        return 1
    fi

    return 0
}

get_auth_params() {
    WAN_IP=$(ip route get 8.8.8.8 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
    TIMESTAMP=$(($(date +%s) * 1000))
    UUID=$(cat /proc/sys/kernel/random/uuid 2>/dev/null)
    echo "$WAN_IP $TIMESTAMP $UUID"
}

first_auth() {
    log "第一步认证..."
    local retry=0
    while [ $retry -lt 3 ]; do
        RESPONSE1=$(wget -q -O - --timeout=10 \
            --post-data="campusCode=${CAMPUS_CODE}&username=${USERNAME}&password=${PASSWORD}&operatorSuffix=${OPERATOR_SUFFIX}" \
            --header="Content-Type: application/x-www-form-urlencoded" \
            --header="Referer: http://172.29.35.36:6060/" \
            "http://172.29.35.27:8088/aaa-auth/api/v1/auth" 2>&1)

        log "第一步响应: $RESPONSE1"

        # 成功
        if echo "$RESPONSE1" | grep -q '"code":1'; then
            return 0
        fi

        # 网络层错误 → 重试
        if echo "$RESPONSE1" | grep -q "Operation not permitted\|Connection refused\|timed out\|Bad address"; then
            log "⚠️ 网络层错误，等待 3 秒后重试 ($((retry+1))/3)..."
            sleep 3
            retry=$((retry + 1))
            continue
        fi

        # 其他错误（如认证参数错误）→ 不重试
        return 1
    done
    return 1
}

second_auth() {
    log "第二步认证..."
    RESPONSE2=$(wget -q -O - --timeout=10 \
        --post-data="username=${USERNAME}&password=${PASSWORD}&operatorSuffix=${OPERATOR_SUFFIX}" \
        --header="Content-Type: application/x-www-form-urlencoded" \
        --header="Referer: http://172.29.35.36:6060/" \
        "http://172.29.35.27:8882/user/check-only" 2>&1)
    log "第二步响应: $RESPONSE2"
    if echo "$RESPONSE2" | grep -q '"code":1'; then
        return 0
    else
        return 1
    fi
}

portal_auth() {
    log "第三步门户认证..."
    PARAMS=$(get_auth_params)
    WAN_IP=$(echo "$PARAMS" | cut -d' ' -f1)
    TIMESTAMP=$(echo "$PARAMS" | cut -d' ' -f2)
    UUID=$(echo "$PARAMS" | cut -d' ' -f3)

    if [ -z "$WAN_IP" ]; then
        log "⚠️ 无法获取 WAN IP"
        return 1
    fi

    log "参数: IP=$WAN_IP, TS=$TIMESTAMP, UUID=$UUID"
    RESPONSE3=$(wget -q -O - --timeout=10 \
        --header="Referer: http://172.29.35.36:6060/" \
        --header="Cookie: macAuth=; ABMS=362ee66b-fa1f-4ef9-a651-bfd9d61d194a" \
        "http://172.29.35.36:6060/quickauth.do?userid=${USERNAME}%40henuyd&passwd=${PASSWORD}&wlanuserip=${WAN_IP}&wlanacname=HD-SuShe-ME60&wlanacIp=172.22.254.253&timestamp=${TIMESTAMP}&uuid=${UUID}" 2>&1)
    log "第三步响应: $RESPONSE3"
    if echo "$RESPONSE3" | grep -q '"message":"认证成功"'; then
        log "✅ 第三步认证成功"
        return 0
    else
        log "❌ 第三步认证失败"
        return 1
    fi
}

check_network() {
    ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1
}

full_auth() {
    log "开始完整认证流程..."
    if first_auth; then
        sleep 2
        if second_auth; then
            sleep 2
            if portal_auth; then
                log "🎉 所有认证步骤成功完成"
                return 0
            else
                log "❌ 第三步认证失败"
                return 1
            fi
        else
            log "❌ 第二步认证失败"
            return 1
        fi
    else
        log "❌ 第一步认证失败"
        return 1
    fi
}

# 新增：恢复路由
recover_route() {
    log "⚠️ 检测到默认路由丢失，尝试恢复..."
    if iw dev $STA_IFACE link 2>/dev/null | grep -q "Connected"; then
        log "STA 仍连接，执行 DHCP 续租..."
        killall -q -USR1 udhcpc 2>/dev/null
        sleep 1
        ifup wwan 2>/dev/null
        sleep 3
    else
        log "STA 已断开，尝试重新连接 WiFi..."
        wifi reload 2>/dev/null
        sleep 5
        ifup wwan 2>/dev/null
        sleep 3
    fi
    if ip route show default 2>/dev/null | grep -q "$STA_IFACE"; then
        log "✅ 路由已恢复"
        return 0
    else
        log "❌ 路由恢复失败"
        return 1
    fi
}

main() {
    log "=== 校园网认证检测 ==="

    # 第一步：检查网络连通性
    if check_network; then
        log "网络已连通"
        return 0
    fi

    # 第二步：网络不通，先检查路由
    if ! ip route show default 2>/dev/null | grep -q "$STA_IFACE"; then
        log "⚠️ 默认路由丢失，尝试恢复..."
        if recover_route; then
            if check_network; then
                log "✅ 路由恢复后网络已连通"
                return 0
            fi
        fi
    else
        log "路由存在但网络不通（可能认证过期）"
    fi

    # 第三步：认证前预检查（v3.0 新增）
    if ! preflight_check; then
        log "❌ 预检查未通过，跳过本次认证（等待网络就绪）"
        return 1
    fi

    # 第四步：完整认证
    log "开始完整认证流程..."
    if full_auth; then
        sleep 5
        if check_network; then
            log "🎉 认证成功，网络已连通！"
        else
            log "⚠️ 认证完成但网络检测失败"
        fi
    else
        log "❌ 认证流程失败"
    fi
}

main
SCRIPT_EOF

    chmod +x /etc/campus_network/auto_login.sh
    step_ok "认证脚本已部署到 /etc/campus_network/auto_login.sh"

    # 手动测试
    echo ""
    step_info "正在测试认证..."
    /etc/campus_network/auto_login.sh

    echo ""
    if ping -c 2 -W 3 8.8.8.8 >/dev/null 2>&1; then
        step_ok "认证测试通过！外网已连通"
    else
        step_warn "认证可能未成功，请查看日志: cat /tmp/campus_network.log"
    fi

    press_enter
}

# ============================================================
# Step 5：设置定时重连
# ============================================================
step5_cron() {
    banner
    echo -e "${BOLD}Step 5/7：设置定时重连${NC}"
    echo ""
    echo "  校园网认证有时效（通常几小时到一天）。"
    echo "  Cron 会每 5 分钟检测一次网络，断了就自动重新认证。"
    echo ""

    # 添加 cron
    if ! grep -q "auto_login.sh" /etc/crontabs/root 2>/dev/null; then
        echo "*/5 * * * * /etc/campus_network/auto_login.sh" >> /etc/crontabs/root
        step_ok "已添加 cron 任务：每5分钟检测一次"
    else
        step_info "cron 任务已存在，跳过"
    fi

    /etc/init.d/cron restart 2>/dev/null || /etc/init.d/crond restart 2>/dev/null
    step_ok "cron 服务已重启"

    echo ""
    echo "  当前 crontab 内容:"
    echo "  ─────────────────"
    cat /etc/crontabs/root 2>/dev/null | sed 's/^/  | /'
    echo "  ─────────────────"

    press_enter
}

# ============================================================
# Step 5.5：DNS 修复（校园内部网站访问）
# ============================================================
step5_dns() {
    banner
    echo -e "${BOLD}Step 5.5/7：修复校园内部网站 DNS 解析${NC}"
    echo ""
    echo "  校园 DHCP 提供的 DNS 对部分校园域名返回不可达IP，"
    echo "  且 DNS 返回的 IPv6 地址在校园网内不通，"
    echo "  导致 WiFi 下无法访问图书馆预约、教务等网站。"
    echo ""
    echo "  此修复包含："
    echo "    1. /etc/hosts 静态解析 (最可靠)"
    echo "    2. 过滤 IPv6 AAAA 记录 (避免手机优先连IPv6超时)"
    echo "    3. 允许校园内部 RFC1918 IP"
    echo "    4. 精确域名 DNS 转发"
    echo ""

    step_info "正在配置 DNS 修复..."

    # Fix 1: /etc/hosts
    if grep -q 'zwyy.henu.edu.cn' /etc/hosts; then
        step_info "/etc/hosts: zwyy 已存在"
    else
        echo '202.196.96.29 zwyy.henu.edu.cn' >> /etc/hosts
        step_ok "/etc/hosts: zwyy.henu.edu.cn → 202.196.96.29"
    fi

    if grep -q 'software.henu.edu.cn' /etc/hosts; then
        step_info "/etc/hosts: software 已存在"
    else
        echo '58.212.123.41 software.henu.edu.cn' >> /etc/hosts
        step_ok "/etc/hosts: software.henu.edu.cn → 58.212.123.41"
    fi

    if grep -q 'net.henu.edu.cn' /etc/hosts; then
        step_info "/etc/hosts: net 已存在"
    else
        echo '172.31.7.4 net.henu.edu.cn' >> /etc/hosts
        step_ok "/etc/hosts: net.henu.edu.cn → 172.31.7.4"
    fi

    # Fix 2: Per-domain DNS forwarding
    for item in "xg.henu.edu.cn:114.114.114.114" "jwgl.henu.edu.cn:111.6.174.198"; do
        domain=${item%%:*}
        dns=${item##*:}
        if uci show dhcp 2>/dev/null | grep -q "server.*${domain}.*${dns}"; then
            step_info "${domain} -> ${dns} (已存在)"
        else
            uci add_list dhcp.@dnsmasq[0].server="/${domain}/${dns}"
            step_ok "${domain} -> ${dns}"
        fi
    done

    # Fix 3: 过滤 AAAA (IPv6) — 路由器无IPv6路由
    uci set dhcp.@dnsmasq[0].filter_aaaa='1'
    step_ok "filter_aaaa=1 (过滤IPv6)"

    # Fix 4: 允许 RFC1918 私有IP
    if grep -q 'rebind-domain-ok=/henu.edu.cn/' /etc/dnsmasq.conf; then
        step_info "rebind-domain-ok 已存在"
    else
        echo 'rebind-domain-ok=/henu.edu.cn/' >> /etc/dnsmasq.conf
        step_ok "rebind-domain-ok=/henu.edu.cn/"
    fi

    # Fix 5: 确保日志不被丢弃
    sed -i 's/^log-facility=\/dev\/null/#log-facility=\/dev\/null/' /etc/dnsmasq.conf

    # Phase 13: 延长 DHCP 租约 — 防止设备重连触发连锁断联
    CUR_LEASE=$(uci get dhcp.lan.leasetime 2>/dev/null)
    if [ "$CUR_LEASE" != "168h" ]; then
        uci set dhcp.lan.leasetime='168h'
        step_ok "DHCP 租约: ${CUR_LEASE:-默认} → 168h (7天)"
    fi

    uci commit dhcp
    /etc/init.d/dnsmasq restart 2>/dev/null
    step_ok "dnsmasq 已重启，DNS 修复完成（含 Phase 13 DHCP 168h）"

    press_enter
}

# ============================================================
# Step 6：安装 CAKE 智能流控
# ============================================================
step6_cake() {
    banner
    echo -e "${BOLD}Step 6/7：安装 CAKE 智能流控${NC}"
    echo ""
    echo "  CAKE 是最先进的队列管理算法，能防止一个人占满带宽。"
    echo "  - 平时不限速（110M 上限，高于实际 100M）"
    echo "  - 拥堵时按设备公平分配（不是按连接数）"
    echo "  - 游戏/视频电话小包永远优先"
    echo "  - 空闲设备不占用份额"
    echo ""

    step_info "正在安装 sqm-scripts..."
    opkg update 2>/dev/null | tail -1
    opkg install sqm-scripts luci-app-sqm 2>/dev/null | tail -3
    step_ok "sqm-scripts 已安装"

    # 获取 WAN 设备名
    WAN_DEV="phy1-sta0"
    if ! ip link show phy1-sta0 >/dev/null 2>&1; then
        WAN_DEV="wan"
        step_warn "phy1-sta0 未找到，使用 wan 作为 WAN 设备"
    fi

    # 配置 SQM
    uci set sqm.eth1='queue'
    uci set sqm.eth1.enabled='1'
    uci set sqm.eth1.interface="$WAN_DEV"
    uci set sqm.eth1.download='110000'
    uci set sqm.eth1.upload='110000'
    uci set sqm.eth1.qdisc='cake'
    uci set sqm.eth1.script='piece_of_cake.qos'
    uci set sqm.eth1.linklayer='ethernet'
    uci set sqm.eth1.overhead='44'
    uci set sqm.eth1.qdisc_advanced='1'
    uci set sqm.eth1.iqdisc_opts='nat dual-srchost triple-isolate wash ack-filter'
    uci set sqm.eth1.eqdisc_opts='nat dual-srchost triple-isolate wash ack-filter'
    uci set sqm.eth1.ingress_ecn='ECN'
    uci set sqm.eth1.egress_ecn='ECN'
    uci commit sqm

    /etc/init.d/sqm enable 2>/dev/null
    /etc/init.d/sqm start 2>/dev/null
    sleep 2

    if tc -s qdisc show dev "$WAN_DEV" 2>/dev/null | grep -q "cake"; then
        step_ok "CAKE 已启动，带宽上限 110Mbps（高于实际，平时不限速）"
        echo ""
        echo "  CAKE 参数:"
        tc -s qdisc show dev "$WAN_DEV" 2>/dev/null | grep "bandwidth\|triple-isolate\|nat\|wash\|ack-filter" | sed 's/^/    /'
    else
        step_warn "CAKE 启动可能失败，请手动检查"
    fi

    press_enter
}

# ============================================================
# Step 7：美化 LuCI（Argon 主题）
# ============================================================
step7_argon() {
    banner
    echo -e "${BOLD}Step 7/7：美化 LuCI 管理界面${NC}"
    echo ""
    echo "  LuCI 就是 http://192.168.1.1 的管理界面。"
    echo "  Argon 是社区最流行的主题——现代风格、侧边栏、暗色模式。"
    echo ""

    step_info "正在安装 Argon 主题..."
    opkg update 2>/dev/null | tail -1
    opkg install luci-theme-argon luci-app-argon-config 2>/dev/null | tail -3
    step_ok "Argon 主题已安装"

    step_info "正在设置 Argon 为默认主题..."
    uci set luci.main.mediaurlbase='/luci-static/argon'
    uci commit luci

    echo ""
    echo "  使用方式:"
    echo "    1. 浏览器打开 http://192.168.1.1"
    echo "    2. 系统 → 系统 → 语言和界面 → 主题 → 选择 Argon"
    echo "    3. 系统 → Argon 主题设置 → 可以换壁纸、模糊效果"
    echo "       - 壁纸可以去 https://unsplash.com 下载图片"
    echo "       - 在 LuCI → Argon Config 中上传即可"

    step_ok "Argon 主题已设为默认"

    press_enter
}

# ============================================================
# 最终汇总
# ============================================================
final_summary() {
    banner
    echo -e "${BOLD}${GREEN}  🎉 配置完成！${NC}"
    echo ""
    echo "  ┌─────────────────────────────────────────────┐"
    echo "  │  最终状态汇总                               │"
    echo "  ├─────────────────────────────────────────────┤"
    echo "  │  root 密码:      ${ROOT_PASSWORD}                    │"
    echo "  │  Web 管理:       http://192.168.1.1          │"
    echo "  │  宿舍 WiFi 2.4G:  ${WIFI_SSID}                    │"
    echo "  │  宿舍 WiFi 5G:    ${WIFI_SSID}-5G (ch52/HE40)     │"
    echo "  │  WiFi 密码:      ${WIFI_PASS}                    │"
    echo "  │  校园网 SSID:    ${CAMPUS_SSID}                    │"
    echo "  │  校园网账号:     ${AUTH_USER}                    │"
    echo "  │  CAKE 流控:      110Mbps（智能动态分配）        │"
    echo "  │  LuCI 主题:      Argon（可换壁纸）               │"
    echo "  │  DHCP 租约:      168h (7天, 防断联)              │"
    echo "  │  hostapd 调优:   disassoc_low_ack=0 + PMKSA缓存 │"
    echo "  │  auto_login:     /etc/campus_network/          │"
    echo "  │  守护进程:       秒级恢复路由 + cron 5分钟兜底   │"
    echo "  ├─────────────────────────────────────────────┤"
    echo "  │  拔掉网线，只留电源线即可工作                   │"
    echo "  │  手机连 ${WIFI_SSID} 或 ${WIFI_SSID}-5G 即可上网  │"
    echo "  └─────────────────────────────────────────────┘"
    echo ""
    echo "  故障排查:"
    echo "    认证失败:  cat /tmp/campus_network.log"
    echo "    手动认证:  /etc/campus_network/auto_login.sh"
    echo "    重启WiFi:  wifi reload"
    echo "    重连校园网: iw dev phy1-sta0 link"
    echo "    CAKE状态:  tc -s qdisc show dev phy1-sta0"
    echo ""
    echo -e "  ${GREEN}路由器现在可以拔掉网线，只插电源线独立工作了！${NC}"
    echo ""
}


# ============================================================
# 主流程
# ============================================================
main() {
    # 初始化变量
    ROOT_PASSWORD=""
    WIFI_SSID=""
    WIFI_PASS=""
    CAMPUS_SSID=""
    CAMPUS_ENC="none"
    AUTH_USER=""
    AUTH_PASS=""
    AUTH_OP=""
    AUTH_CODE=""

    step0_check
    step1_password
    step2_wifi
    step3_wwan
    step4_auth
    step5_cron
    step5_dns
    step6_cake
    step7_argon
    final_summary
}

main "$@"
