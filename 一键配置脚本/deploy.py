# -*- coding: utf-8 -*-
"""
AX3000T 校园网一键部署工具 v3.0
=================================
单文件完整脚本 — 小白友好 · 傻瓜式操作 · 智能检测

用法：
  - 双击 !START.bat      → 交互式菜单
  - python deploy.py      → 交互式菜单
  - python deploy.py lazy → 🤖 懒人一键模式（全自动，只需填密码）
  - python deploy.py wifi → 快速切换校园网
"""
import subprocess, os, sys, json, time, re, base64, shutil, io
from pathlib import Path
from datetime import datetime

# 强制 UTF-8 输出（解决 Windows GBK 编码问题）
for attr in ['stdout', 'stderr']:
    s = getattr(sys, attr)
    if s.encoding != 'utf-8':
        try: setattr(sys, attr, io.TextIOWrapper(s.buffer, encoding='utf-8', errors='replace'))
        except: pass

# ═══════════════════════════════════════════════════════════════
# 终端 UI 组件
# ═══════════════════════════════════════════════════════════════
C = {"G": "\033[92m", "R": "\033[91m", "Y": "\033[93m",
     "B": "\033[94m", "C": "\033[96m", "W": "\033[1m", "D": "\033[2m", "X": "\033[0m"}
def clr(c, t): return f"{C[c]}{t}{C['X']}"
def _ok(m):  print(f"  {clr('G','[✓]')} {m}")
def _fail(m): print(f"  {clr('R','[✗]')} {m}")
def _info(m): print(f"  {clr('B','[i]')} {m}")
def _warn(m): print(f"  {clr('Y','[!]')} {m}")
def _tip(m):  print(f"  {clr('D', m)}")
def _cls():   os.system("cls" if os.name == "nt" else "clear")

def banner(sub=None):
    _cls()
    print(clr("C", """
  ╔══════════════════════════════════════════════════════╗
  ║                                                      ║
  ║     AX3000T 校园网一键部署工具 v3.0                   ║
  ║     小白友好 · 傻瓜式操作 · 智能检测                  ║
  ║                                                      ║
  ╚══════════════════════════════════════════════════════╝
"""))
    if sub: print(f"  {clr('W', sub)}")
    print()

def step_hdr(n, total, title, desc=""):
    print(f"  {clr('C','━'*40)}")
    print(f"  {clr('W',f'Step {n}/{total}: {title}')}")
    print(f"  {clr('C','━'*40)}")
    if desc:
        print()
        for l in desc.strip().split("\n"):
            print(f"  {clr('D', l.strip())}")
    print()

def press_enter(msg="按 Enter 继续..."):
    print()
    input(f"  {clr('Y', msg)}")
    print()

def ask(prompt, default=None, required=True):
    while True:
        h = f" (默认: {default})" if default else ""
        v = input(f"  {clr('C', prompt)}{h}: ").strip()
        if not v and default:
            v = default
            _info(f"使用默认值: {v}")
        if not v and required:
            _warn("此项不能为空，请重新输入")
            continue
        return v

def ask_pwd(prompt, confirm=True, min_len=8):
    import getpass
    while True:
        p = getpass.getpass(f"  {clr('C', prompt)}: ")
        if len(p) < min_len:
            _warn(f"密码至少 {min_len} 位")
            continue
        if confirm:
            p2 = getpass.getpass(f"  {clr('C', '请再次输入确认')}: ")
            if p != p2: _fail("两次输入不一致！"); continue
        return p

def ask_yesno(prompt, default="y"):
    yn = input(f"  {clr('C', prompt)} (y/n, 默认 {default}): ").strip().lower()
    if not yn: yn = default
    return yn in ("y","yes")

def ask_choice(prompt, options, default=None):
    print()
    for k, lbl in options: print(f"    [{k}] {lbl}")
    print()
    while True:
        h = f" (默认 {default})" if default else ""
        c = input(f"  {clr('C', prompt)}{h}: ").strip()
        if not c and default: return default
        if c in [o[0] for o in options]: return c
        _warn(f"请输入 {'/'.join(o[0] for o in options)}")

def show_card(rows):
    w = max(len(r[0])+len(str(r[1])) for r in rows)+6; w = max(w,40)
    print(f"  ┌{'─'*w}┐")
    for key,val,*rest in rows:
        cl = rest[0] if rest else None
        vs = str(val) if val is not None else clr('D','(无)')
        if cl: vs = clr(cl, str(val))
        print(f"  │ {key}: {vs}" + " " * (w - len(key) - len(str(val)) - 4) + "│")
    print(f"  └{'─'*w}┘")

def err_box(title, msg):
    print(f"\n  {clr('R','╔'+'═'*50+'╗')}")
    print(f"  {clr('R','║')} {clr('W',title.ljust(48))} {clr('R','║')}")
    for l in msg.strip().split("\n"): print(f"  {clr('R','║')} {l.ljust(48)} {clr('R','║')}")
    print(f"  {clr('R','╚'+'═'*50+'╝')}\n")

def ok_box(title, msg):
    print(f"\n  {clr('G','╔'+'═'*50+'╗')}")
    print(f"  {clr('G','║')} {clr('W',title.ljust(48))} {clr('G','║')}")
    for l in msg.strip().split("\n"): print(f"  {clr('G','║')} {l.ljust(48)} {clr('G','║')}")
    print(f"  {clr('G','╚'+'═'*50+'╝')}\n")

# ═══════════════════════════════════════════════════════════════
# SSH 连接管理
# ═══════════════════════════════════════════════════════════════
ROUTER_IP = "192.168.1.1"
ROUTER_USER = "root"
SSH_OPTS = "-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"

class SSH:
    def __init__(self, host=ROUTER_IP, user=ROUTER_USER):
        self.host, self.user, self.pwd, self.key = host, user, None, None

    def find_keys(self):
        cand = [
            Path(__file__).parent.parent / ".ssh" / "ax3000t_rsa",
            Path.home() / ".ssh" / "ax3000t_rsa",
            Path.home() / ".ssh" / "id_ed25519",
            Path.home() / ".ssh" / "id_rsa",
        ]
        return [str(p) for p in cand if p.exists()]

    def _try_key(self, kp):
        r = subprocess.run(f'ssh {SSH_OPTS} -i "{kp}" {self.user}@{self.host} "echo OK"',
                          shell=True, capture_output=True, text=True, timeout=10)
        return r.returncode == 0 and "OK" in r.stdout

    def _try_empty(self):
        r = subprocess.run(f'ssh {SSH_OPTS} -o PasswordAuthentication=no {self.user}@{self.host} "echo OK"',
                          shell=True, capture_output=True, text=True, timeout=10)
        return r.returncode == 0 and "OK" in r.stdout

    def auto_connect(self):
        """返回 (success, method)"""
        for k in self.find_keys():
            if self._try_key(k):
                self.key = k; return True, f"密钥({Path(k).name})"
        if self._try_empty():
            return True, "空密码"
        return False, "需要密码"

    def connect_pwd(self, pwd):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False)
        tmp.write(f'@echo {pwd}'); tmp.close()
        env = os.environ.copy()
        env['SSH_ASKPASS'] = tmp.name; env['SSH_ASKPASS_REQUIRE'] = 'force'; env['DISPLAY'] = 'dummy'
        r = subprocess.run(f'ssh {SSH_OPTS} -o PubkeyAuthentication=no {self.user}@{self.host} "echo OK"',
                          shell=True, capture_output=True, text=True, timeout=10, env=env)
        try: os.unlink(tmp.name)
        except: pass
        if r.returncode==0 and "OK" in r.stdout:
            self.pwd = pwd; return True
        return False

    def _prefix(self):
        if self.key: return f'ssh {SSH_OPTS} -i "{self.key}" {self.user}@{self.host}'
        if self.pwd: return f'ssh {SSH_OPTS} {self.user}@{self.host}'
        return f'ssh {SSH_OPTS} -o PasswordAuthentication=no {self.user}@{self.host}'

    def run(self, cmd, timeout=30, show=False):
        import tempfile
        pf = self._prefix()
        tmp = None; env = os.environ.copy()
        if self.pwd and not self.key:
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.bat', delete=False)
            tmp.write(f'@echo {self.pwd}'); tmp.close()
            env['SSH_ASKPASS'] = tmp.name; env['SSH_ASKPASS_REQUIRE'] = 'force'; env['DISPLAY'] = 'dummy'
        try:
            r = subprocess.run(f'{pf} "{cmd}"', shell=True, capture_output=True, text=True, timeout=timeout, env=env)
            out = r.stdout + r.stderr
            if tmp:
                try: os.unlink(tmp.name)
                except: pass
            if show:
                for l in out.split("\n"):
                    l = l.strip()
                    if l and not any(s in l for s in ["Warning: Permanently","WARNING: connection","store now, decrypt","The server may","BusyBox v"]):
                        print(f"         {l}")
            return r.returncode == 0, out
        except subprocess.TimeoutExpired:
            if tmp:
                try: os.unlink(tmp.name)
                except: pass
            return False, "TIMEOUT"
        except Exception as e:
            if tmp:
                try: os.unlink(tmp.name)
                except: pass
            return False, str(e)

    def test(self):
        ok_r, out = self.run("echo OK", timeout=10)
        return ok_r and "OK" in out

    def setup_key(self, name="ax3000t_rsa"):
        kd = Path(__file__).parent.parent / ".ssh"; kd.mkdir(parents=True, exist_ok=True)
        kp = kd / name
        if not kp.exists():
            subprocess.run(f'ssh-keygen -t ed25519 -f "{kp}" -N "" -C "ax3000t"', shell=True, capture_output=True, timeout=15)
            _info(f"密钥已生成: {kp}")
        with open(str(kp)+".pub") as f: pub = f.read().strip()
        self.run(f"mkdir -p /etc/dropbear && echo '{pub}' >> /etc/dropbear/authorized_keys")
        self.key = str(kp)
        _ok("SSH 免密登录已配置")
        # 写 ~/.ssh/config
        sc = Path.home()/".ssh"/"config"
        entry = f"\nHost ax3000t\n    HostName {self.host}\n    User {self.user}\n    IdentityFile {self.key}\n    StrictHostKeyChecking no\n    UserKnownHostsFile /dev/null\n"
        if not sc.exists() or "Host ax3000t" not in sc.read_text():
            with open(sc,"a") as f: f.write(entry)
            _ok("快捷连接已配置: ssh ax3000t")

ssh = SSH()

# ═══════════════════════════════════════════════════════════════
# WiFi 管理
# ═══════════════════════════════════════════════════════════════
def wifi_scan():
    """扫描周边WiFi，返回 [{ssid,signal,security,freq,bssid}]"""
    _info("正在扫描周边 WiFi（约 10 秒）...")
    out = ""
    for dev in ["phy0-ap0","phy1-ap0"]:
        _, out = ssh.run(f"iw dev {dev} scan", timeout=20)
        if out and len(out) > 200: break
        # 也试试 iwinfo
        _, out2 = ssh.run(f"iwinfo {dev} scan", timeout=15)
        if out2 and len(out2) > len(out): out = out2
    if not out or len(out) < 80:
        _warn("无法扫描，请手动输入 SSID")
        return []
    nets, cur = [], {}
    for line in out.split("\n"):
        line = line.strip()
        if line.startswith("BSS "):
            if cur.get("ssid"): nets.append(cur)
            cur = {"bssid": line[4:21] if len(line)>20 else ""}
        elif "SSID:" in line:
            s = line.replace("SSID:","").strip()
            if s: cur["ssid"] = s
        elif "signal:" in line:
            m = re.search(r"signal:\s*(-?[\d.]+)\s*dBm", line)
            if m: cur["signal"] = float(m.group(1))
        elif "freq:" in line:
            m = re.search(r"freq:\s*(\d+)", line)
            if m: cur["freq"] = int(m.group(1))
        elif "RSN:" in line or "WPA:" in line:
            cur["security"] = "WPA2/WPA3"
        elif "WEP:" in line:
            cur["security"] = "WEP"
    if cur and cur.get("ssid"): nets.append(cur)
    # 去重排序
    seen = set(); unique = []
    for n in nets:
        s = n.get("ssid","")
        if s and s not in seen:
            seen.add(s)
            n.setdefault("security","开放"); n.setdefault("signal",-99); n.setdefault("freq",0)
            unique.append(n)
    unique.sort(key=lambda x: x.get("signal",-99), reverse=True)
    return unique

def display_scan(nets):
    if not nets: return
    print(f"  {clr('W','扫描到的 WiFi 网络')}（按信号强度排序）:")
    header = "  #    SSID                           信号      频段   加密"
    print(f"  {clr('D', header)}")
    print(f"  {clr('D','-'*58)}")
    for i, n in enumerate(nets):
        sig = n.get("signal",-99)
        sc = "G" if sig > -60 else ("Y" if sig > -75 else "R")
        b = "5G" if n.get("freq",0)>4000 else "2.4G"
        print(f"  [{i+1:<3}] {clr(sc, n.get('ssid','')[:28].ljust(30))} {clr(sc, f'{sig:.0f} dBm'.ljust(8))} {b.ljust(6)} {n.get('security','?')}")
    print()

def config_dorm_wifi(ssid, password):
    """配置宿舍WiFi — 适配全新路由器"""
    # 检测 radio0 是否存在（全新路由器可能没有）
    _, check = ssh.run("uci get wireless.radio0.path 2>/dev/null", timeout=5)
    if "18000000.wifi" not in check:
        _info("首次配置 2.4G radio...")
        ssh.run("uci set wireless.radio0=wifi-device; uci set wireless.radio0.type='mac80211'; uci set wireless.radio0.path='platform/soc/18000000.wifi'; uci set wireless.radio0.band='2g'; uci set wireless.radio0.channel='1'; uci set wireless.radio0.htmode='HE20'; uci set wireless.radio0.country='CN'; uci set wireless.radio0.disabled='0'", timeout=5)

    ssh.run(f"uci set wireless.default_radio0.ssid='{ssid}'", timeout=5)
    ssh.run(f"uci set wireless.default_radio0.encryption='psk2'", timeout=5)
    ssh.run(f"uci set wireless.default_radio0.key='{password}'", timeout=5)
    ssh.run("uci set wireless.default_radio0.mode='ap'", timeout=5)
    ssh.run("uci set wireless.default_radio0.network='lan'", timeout=5)
    # Phase 13: hostapd 调优 — 防止设备重连导致其他设备断联
    ssh.run("uci set wireless.default_radio0.disassoc_low_ack='0'", timeout=5)
    ssh.run("uci set wireless.default_radio0.skip_inactivity_poll='1'", timeout=5)
    ssh.run("uci set wireless.default_radio0.wpa_group_rekey='86400'", timeout=5)
    ssh.run("uci set wireless.default_radio0.uapsd='0'", timeout=5)
    ssh.run("uci set wireless.default_radio0.auth_cache='1'", timeout=5)
    ssh.run("uci commit wireless", timeout=5)
    return True

def config_5g_ap(ssid_2g, password):
    """配置5G AP — 在 radio1 上创建第二个 WiFi 热点（复用2.4G的SSID+密码，加-5G后缀）

    适配场景：
    - 全新路由器：创建 wifinet0 接口
    - 已有5G AP：仅更新 Phase 13 调优参数（幂等安全）
    """
    ssid_5g = ssid_2g + "-5G"

    # 检查 wifinet0 是否已存在
    _, check = ssh.run("uci get wireless.wifinet0.ssid 2>/dev/null", timeout=5)
    is_new = "wifinet0" not in check

    if is_new:
        _info("首次配置 5G AP（wifinet0）...")
        # 锁定5G信道（ch52），避免 ACS 触发 radio reset
        ssh.run("uci set wireless.radio1.channel='52'", timeout=5)
        ssh.run("uci set wireless.radio1.htmode='HE40'", timeout=5)
        # 创建 wifinet0 AP 接口
        ssh.run("uci set wireless.wifinet0=wifi-iface", timeout=5)
        ssh.run("uci set wireless.wifinet0.device='radio1'", timeout=5)
        ssh.run("uci set wireless.wifinet0.mode='ap'", timeout=5)
        ssh.run(f"uci set wireless.wifinet0.ssid='{ssid_5g}'", timeout=5)
        ssh.run("uci set wireless.wifinet0.encryption='psk2'", timeout=5)
        ssh.run(f"uci set wireless.wifinet0.key='{password}'", timeout=5)
        ssh.run("uci set wireless.wifinet0.network='lan'", timeout=5)
    else:
        cur_ssid = check.strip() if check else "?"
        _info(f"5G AP 已存在 (SSID: {cur_ssid})，更新 Phase 13 调优...")

    # Phase 13: hostapd 调优（无论新建还是已有，都确保参数正确）
    ssh.run("uci set wireless.wifinet0.disassoc_low_ack='0'", timeout=5)
    ssh.run("uci set wireless.wifinet0.skip_inactivity_poll='1'", timeout=5)
    ssh.run("uci set wireless.wifinet0.wpa_group_rekey='86400'", timeout=5)
    ssh.run("uci set wireless.wifinet0.uapsd='0'", timeout=5)
    ssh.run("uci set wireless.wifinet0.auth_cache='1'", timeout=5)
    ssh.run("uci commit wireless", timeout=5)

    if is_new:
        _ok(f"5G WiFi 已创建: {ssid_5g} (ch52/HE40)")
    else:
        _ok(f"5G WiFi Phase 13 调优已更新")
    return True

def config_campus_sta(ssid, password=None, security="none"):
    """配置校园网STA连接 — 适配全新/已配置路由器"""
    # 备份（可能不存在，忽略错误）
    ssh.run("cp /etc/config/wireless /etc/config/wireless.bak 2>/dev/null; cp /etc/config/network /etc/config/network.bak 2>/dev/null", timeout=5)

    # 检测 radio1 是否存在，不存在则创建
    _, check = ssh.run("uci get wireless.radio1.path 2>/dev/null", timeout=5)
    if "18000000.wifi" not in check:
        _info("首次配置 5G radio...")
        ssh.run("uci set wireless.radio1=wifi-device; uci set wireless.radio1.type='mac80211'; uci set wireless.radio1.path='platform/soc/18000000.wifi+1'; uci set wireless.radio1.band='5g'; uci set wireless.radio1.country='CN'", timeout=5)

    # 检测 default_radio1 是否存在
    _, check = ssh.run("uci get wireless.default_radio1.ssid 2>/dev/null", timeout=5)

    cmds = f"""
uci set wireless.default_radio1.mode='sta'
uci set wireless.default_radio1.ssid='{ssid}'
uci set wireless.default_radio1.encryption='{security}'
uci set wireless.default_radio1.network='wwan'
uci set wireless.radio1.channel='auto'
uci set wireless.radio1.htmode='HE40'
"""
    if password and security != "none":
        cmds += f"uci set wireless.default_radio1.key='{password}'\n"
    else:
        cmds += "uci delete wireless.default_radio1.key 2>/dev/null || true\n"

    cmds += """uci commit wireless

# 创建 wwan（如果不存在）
if ! uci get network.wwan 2>/dev/null; then
    uci set network.wwan='interface'
    uci set network.wwan.proto='dhcp'
    uci commit network
fi

# 防火墙：将 wwan 加入 WAN zone
if uci get firewall.@zone[1].network 2>/dev/null | grep -q wwan; then
    echo "WWAN_IN_ZONE"
else
    uci add_list firewall.@zone[1].network='wwan' 2>/dev/null || true
    uci commit firewall
fi

uci set firewall.@defaults[0].fullcone='0' 2>/dev/null
uci set firewall.@defaults[0].fullcone6='0' 2>/dev/null
uci commit firewall 2>/dev/null
echo ALL_OK
"""
    ok_r, out = ssh.run(cmds)
    return ok_r and "ALL_OK" in out

def switch_campus(ssid, password=None, security="none"):
    cmds = f"""
uci set wireless.default_radio1.ssid='{ssid}'
uci set wireless.default_radio1.encryption='{security}'
"""
    if password and security != "none": cmds += f"uci set wireless.default_radio1.key='{password}'\n"
    else: cmds += "uci delete wireless.default_radio1.key 2>/dev/null || true\n"
    cmds += "uci commit wireless\necho SWITCHED\n"
    ok_r, out = ssh.run(cmds)
    return ok_r and "SWITCHED" in out

def apply_wifi():
    _info("正在应用 WiFi 配置...")
    ssh.run("wifi reload 2>&1", timeout=15)
    for i in range(6):
        time.sleep(2)
        ok_s, out = ssh.run("iw dev phy1-sta0 link 2>/dev/null | grep -q Connected && echo Y", timeout=5)
        if ok_s and "Y" in out: break
        sys.stdout.write(f"\r  {clr('C',f'等待 STA 连接... ({i+1}/6)')}")
        sys.stdout.flush()
    print()
    ok_s, out = ssh.run("iw dev phy1-sta0 link 2>/dev/null | head -5", timeout=5)
    if ok_s and "Connected" in out:
        _ok("5G STA 已连接校园网")
        ssh.run("ifup wwan 2>/dev/null; sleep 2; fw4 restart 2>/dev/null", timeout=10)
        ok_i, ip_out = ssh.run("ip addr show dev phy1-sta0 2>/dev/null | grep 'inet '", timeout=5)
        if ok_i and ip_out:
            m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", ip_out)
            if m: _info(f"校园网 IP: {clr('G', m.group(1))}")
        return True
    else:
        _warn("STA 连接未成功，请确认校园网 WiFi 在范围内")
        return False

# ═══════════════════════════════════════════════════════════════
# 认证脚本部署
# ═══════════════════════════════════════════════════════════════

AUTH_SCRIPT = '''#!/bin/sh
USERNAME="{username}"
PASSWORD="{password}"
OPERATOR_SUFFIX="{operator}"
CAMPUS_CODE="{campus_code}"
LOG_FILE="/tmp/campus_network.log"
log() {{ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE; }}
get_auth_params() {{
    WAN_IP=$(ip route get 8.8.8.8 2>/dev/null | awk '{{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}}')
    TIMESTAMP=$(($(date +%s) * 1000))
    UUID=$(cat /proc/sys/kernel/random/uuid 2>/dev/null)
    echo "$WAN_IP $TIMESTAMP $UUID"
}}
check_route() {{ ip route show default 2>/dev/null | grep -q "phy1-sta0"; }}
recover_route() {{
    log "路由丢失，尝试恢复..."
    if iw dev phy1-sta0 link 2>/dev/null | grep -q "Connected"; then
        ifup wwan 2>/dev/null; sleep 3
    else wifi reload 2>/dev/null; sleep 5; ifup wwan 2>/dev/null; sleep 3; fi
    check_route && log "路由已恢复" && return 0; return 1
}}
first_auth() {{
    log "第一步认证..."
    R=$(wget -q -O - --post-data="campusCode=${{CAMPUS_CODE}}&username=${{USERNAME}}&password=${{PASSWORD}}&operatorSuffix=${{OPERATOR_SUFFIX}}" --header="Content-Type: application/x-www-form-urlencoded" --header="Referer: http://172.29.35.36:6060/" "http://172.29.35.27:8088/aaa-auth/api/v1/auth" 2>&1)
    log "第一步响应: $R"; echo "$R" | grep -q '"code":1'
}}
second_auth() {{
    log "第二步认证..."
    R=$(wget -q -O - --post-data="username=${{USERNAME}}&password=${{PASSWORD}}&operatorSuffix=${{OPERATOR_SUFFIX}}" --header="Content-Type: application/x-www-form-urlencoded" --header="Referer: http://172.29.35.36:6060/" "http://172.29.35.27:8882/user/check-only" 2>&1)
    log "第二步响应: $R"; echo "$R" | grep -q '"code":1'
}}
portal_auth() {{
    log "第三步门户认证..."
    P=$(get_auth_params); IP=$(echo "$P" | cut -d" " -f1); TS=$(echo "$P" | cut -d" " -f2); UD=$(echo "$P" | cut -d" " -f3)
    [ -z "$IP" ] && log "无法获取WAN IP" && return 1
    log "参数: IP=$IP, TS=$TS, UUID=$UD"
    R=$(wget -q -O - --header="Referer: http://172.29.35.36:6060/" --header="Cookie: macAuth=; ABMS=362ee66b-fa1f-4ef9-a651-bfd9d61d194a" -T 10 "http://172.29.35.36:6060/quickauth.do?userid=${{USERNAME}}%40henuyd&passwd=${{PASSWORD}}&wlanuserip=${{IP}}&wlanacname=HD-SuShe-ME60&wlanacIp=172.22.254.253&timestamp=${{TS}}&uuid=${{UD}}" 2>&1)
    log "第三步响应: $R"; echo "$R" | grep -q '"message":"认证成功"'
}}
check_network() {{ ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; }}
full_auth() {{
    log "开始完整认证流程..."
    if first_auth; then sleep 2; if second_auth; then sleep 2; if portal_auth; then log "所有步骤完成"; return 0; fi; fi; fi
    return 1
}}
main() {{
    log "=== 认证检测 ==="
    if check_network; then log "已连通"; return 0; fi
    if ! check_route; then log "路由丢失，尝试恢复..."; recover_route; check_network && log "恢复后网络已通" && return 0; fi
    log "开始认证..."
    if full_auth; then sleep 5; check_network && log "认证成功！" || log "认证完成但检测失败"
    else log "认证失败"; fi
}}
main'''

WATCHDOG = '''#!/bin/sh
LOG_FILE="/tmp/campus_network.log"
log() {{ echo "[$(date '+%Y-%m-%d %H:%M:%S')] [Watchdog] $1" >> $LOG_FILE; }}
check_route() {{ ip route show default 2>/dev/null | grep -q "phy1-sta0"; }}
check_sta() {{ iw dev phy1-sta0 link 2>/dev/null | grep -q "Connected"; }}
if check_route; then exit 0; fi
log "路由丢失！"
if check_sta; then ifup wwan 2>/dev/null; sleep 3
else wifi reload 2>/dev/null; sleep 5; ifup wwan 2>/dev/null; sleep 3; fi
check_route && log "看门狗恢复成功"
if ! ping -c 2 -W 3 8.8.8.8 > /dev/null 2>&1; then /etc/campus_network/auto_login.sh & fi'''

INITD = '''#!/bin/sh /etc/rc.common
START=99
boot() {{
    for i in $(seq 1 12); do iw dev phy1-sta0 link 2>/dev/null | grep -q Connected && break; sleep 5; done
    for i in $(seq 1 6); do ip addr show dev phy1-sta0 2>/dev/null | grep -q 'inet ' && break; sleep 5; done
    /etc/campus_network/auto_login.sh &
}}'''

FAST_RECOVERY_DAEMON = '''#!/bin/sh
# 快速恢复守护进程 — 秒级检测和恢复
LOG_FILE="/tmp/campus_network.log"
STA_IFACE="phy1-sta0"
CAMPUS_SSID="henu-student"
CAMPUS_CHANNEL="5260"
log() {{ echo "[$(date '+%Y-%m-%d %H:%M:%S')] [FastRecovery] $1" >> $LOG_FILE; }}
check_sta_connected() {{ iw dev $STA_IFACE link 2>/dev/null | grep -q "Connected"; }}
check_route() {{ ip route show default 2>/dev/null | grep -q "$STA_IFACE"; }}
check_network() {{ ping -c 1 -W 2 8.8.8.8 > /dev/null 2>&1; }}
fast_sta_reconnect() {{
    log "快速重连 STA..."
    iw dev $STA_IFACE disconnect 2>/dev/null; sleep 0.5
    iw dev $STA_IFACE connect "$CAMPUS_SSID" $CAMPUS_CHANNEL 2>/dev/null
    for i in $(seq 1 6); do sleep 0.5; check_sta_connected && log "STA 重连成功(${i}周期)" && return 0; done
    log "快速重连失败，回退到 wifi reload..."; wifi reload 2>/dev/null; sleep 5; return 1
}}
dhcp_renew() {{
    log "DHCP 续租..."; killall -q -USR1 udhcpc 2>/dev/null; sleep 1
    if ! check_route; then ifup wwan 2>/dev/null; sleep 2; fi
}}
PIDFILE="/var/run/fast_recovery_daemon.pid"
if [ -f "$PIDFILE" ]; then
    OLDPID=$(cat "$PIDFILE"); kill -0 "$OLDPID" 2>/dev/null && exit 0
fi
echo $$ > "$PIDFILE"
log "快速恢复守护进程启动 (间隔1秒, 信道锁定: $CAMPUS_CHANNEL MHz)"
local fail_count=0; local last_auth_time=0
while true; do
    if check_network; then fail_count=0; sleep 1; continue; fi
    fail_count=$((fail_count + 1))
    [ $fail_count -eq 1 ] && log "网络不通，开始诊断..."
    if ! check_route; then
        log "默认路由丢失! (${fail_count}s)"
        if check_sta_connected; then dhcp_renew
        else fast_sta_reconnect; sleep 1; dhcp_renew; fi
        if check_route && check_network; then log "路由恢复成功，网络已通"; fail_count=0; sleep 1; continue; fi
    fi
    local now=$(date +%s)
    if [ $fail_count -ge 3 ] && [ $((now - last_auth_time)) -ge 60 ]; then
        log "路由存在但网络不通，触发认证..."; last_auth_time=$now
        /etc/campus_network/auto_login.sh &
    fi
    if [ $fail_count -ge 30 ]; then
        log "持续失败30秒，完整重置..."; wifi reload 2>/dev/null; sleep 5
        ifup wwan 2>/dev/null; sleep 3; /etc/campus_network/auto_login.sh &; fail_count=0
    fi
    sleep 1
done'''

INITD_FAST_RECOVERY = '''#!/bin/sh /etc/rc.common
START=98
USE_PROCD=1
start_service() {{
    procd_open_instance
    procd_set_param command /bin/sh /etc/campus_network/fast_recovery_daemon.sh
    procd_set_param respawn 3600
    procd_set_param stdout 1
    procd_set_param stderr 1
    procd_close_instance
}}
stop_service() {{
    pidof fast_recovery_daemon.sh | xargs kill 2>/dev/null
    rm -f /var/run/fast_recovery_daemon.pid
}}'''

def deploy_auth_script(username, password, operator="@henuyd", campus_code="07cdfd23373b17c6b337251c22b7ea57"):
    s = AUTH_SCRIPT.format(username=username, password=password, operator=operator, campus_code=campus_code)
    enc = base64.b64encode(s.encode()).decode()
    ssh.run("mkdir -p /etc/campus_network", timeout=5)
    ok_r, _ = ssh.run(f"echo '{enc}' | base64 -d > /etc/campus_network/auto_login.sh && chmod +x /etc/campus_network/auto_login.sh && echo DEPLOYED")
    return ok_r and "DEPLOYED" in _

def deploy_watchdog():
    enc = base64.b64encode(WATCHDOG.encode()).decode()
    ok_r, _ = ssh.run(f"echo '{enc}' | base64 -d > /etc/campus_network/route_watchdog.sh && chmod +x /etc/campus_network/route_watchdog.sh && echo DEPLOYED")
    return ok_r and "DEPLOYED" in _

def deploy_initd():
    enc = base64.b64encode(INITD.encode()).decode()
    ok_r, _ = ssh.run(f"echo '{enc}' | base64 -d > /etc/init.d/campus_auth && chmod +x /etc/init.d/campus_auth && /etc/init.d/campus_auth enable 2>/dev/null && echo DEPLOYED")
    return ok_r and "DEPLOYED" in _

def deploy_cron():
    cron = """*/5 * * * * /etc/campus_network/auto_login.sh
@reboot sleep 30; /etc/campus_network/auto_login.sh
0 4 * * 1,4 /sbin/reboot
"""
    enc = base64.b64encode(cron.encode()).decode()
    ok_r, _ = ssh.run(f"echo '{enc}' | base64 -d > /tmp/crontab_new && crontab /tmp/crontab_new && /etc/init.d/cron restart && echo CRON_SET")
    return ok_r and "CRON_SET" in _

def deploy_fast_recovery():
    """部署快速恢复守护进程（替代cron看门狗）"""
    enc_d = base64.b64encode(FAST_RECOVERY_DAEMON.encode()).decode()
    enc_i = base64.b64encode(INITD_FAST_RECOVERY.encode()).decode()
    cmds = f"""
mkdir -p /etc/campus_network
echo '{enc_d}' | base64 -d > /etc/campus_network/fast_recovery_daemon.sh
chmod +x /etc/campus_network/fast_recovery_daemon.sh
echo '{enc_i}' | base64 -d > /etc/init.d/fast_recovery
chmod +x /etc/init.d/fast_recovery
/etc/init.d/fast_recovery enable 2>/dev/null
# 停止旧的cron看门狗（如果还在运行）
pkill -f route_watchdog.sh 2>/dev/null || true
# 启动守护进程
/etc/init.d/fast_recovery start 2>/dev/null
sleep 2
# 验证
ps | grep fast_recovery | grep -v grep | grep -q daemon && echo FAST_RECOVERY_OK
"""
    ok_r, out = ssh.run(cmds, timeout=20)
    return ok_r and "FAST_RECOVERY_OK" in out

def deploy_all_auto():
    """部署所有自动化脚本（快速恢复守护进程+init.d+cron）"""
    return deploy_fast_recovery() and deploy_initd() and deploy_cron()

def deploy_dns_fix():
    """
    DNS 修复：解决校园内部网站 DNS 解析问题 (v2.0)

    问题1: 校园 DHCP DNS (111.6.174.198) 对某些域名返回不可达IP
           zwyy.henu.edu.cn → 125.219.33.206 (不可达)  → hosts写死 + 114 DNS
           software.henu.edu.cn → 解析为空    (不可达)  → hosts写死
           net.henu.edu.cn  → 58.212.123.41 (公网不可达) → hosts写死 172.31.7.4(内网)
           xg.henu.edu.cn   → 172.31.0.6     (不可达)  → 114 DNS
           jwgl.henu.edu.cn → 211.142.109.84 (不可达)  → campus DNS

    问题2: dnsmasq rebind 保护丢弃 RFC1918 私有IP
           jwgl → 172.31.7.4 被丢弃   → rebind-domain-ok=/henu.edu.cn/

    问题3: DNS同时返回IPv6地址, 但路由器无IPv6路由
           手机优先尝试IPv6 → 超时   → filter_aaaa=1 全局过滤
    """
    _info("配置校园网 DNS 修复...")

    ok = True

    # Fix 1: /etc/hosts 静态解析 (最可靠, 不依赖DNS)
    for domain, ip in [("zwyy.henu.edu.cn", "202.196.96.29"),
                        ("software.henu.edu.cn", "58.212.123.41"),
                        ("net.henu.edu.cn", "172.31.7.4")]:
        ok_r, out = ssh.run(
            f"grep -q '{domain}' /etc/hosts && echo EXISTS", timeout=5)
        if not (ok_r and "EXISTS" in out):
            ok_r, out = ssh.run(
                f"echo '{ip} {domain}' >> /etc/hosts && echo ADDED",
                timeout=5)
            if ok_r and "ADDED" in out:
                _ok(f"  /etc/hosts: {domain} → {ip}")
            else:
                _warn(f"  hosts 添加失败: {domain}")
                ok = False

    # Fix 2: Per-domain DNS forwarding (hosts之外的域名)
    for domain, dns in [("xg.henu.edu.cn", "114.114.114.114"),
                         ("jwgl.henu.edu.cn", "111.6.174.198")]:
        ok_r, out = ssh.run(
            f"uci show dhcp 2>/dev/null | grep -q 'server.*{domain}.*{dns}' && echo EXISTS",
            timeout=5)
        if ok_r and "EXISTS" in out:
            continue
        ok_r, out = ssh.run(
            f"uci add_list dhcp.@dnsmasq[0].server='/{domain}/{dns}' && echo ADDED",
            timeout=5)
        if ok_r and "ADDED" in out:
            _ok(f"  UCI: {domain} → {dns}")
        else:
            _warn(f"  添加规则失败: {domain}")
            ok = False

    # Fix 3: 过滤 AAAA (IPv6) 记录 (路由器无IPv6, 避免手机优先尝试IPv6超时)
    ok_r, out = ssh.run(
        "uci get dhcp.@dnsmasq[0].filter_aaaa 2>/dev/null", timeout=5)
    if ok_r and out.strip() == "1":
        pass  # already set
    else:
        ssh.run("uci set dhcp.@dnsmasq[0].filter_aaaa='1'", timeout=5)
        _ok("  UCI: filter_aaaa=1 (过滤IPv6, 路由器无IPv6路由)")

    # Fix 4: 允许 henu.edu.cn 返回 RFC1918 私有IP
    ok_r, out = ssh.run(
        "grep -q 'rebind-domain-ok=/henu.edu.cn/' /etc/dnsmasq.conf && echo EXISTS",
        timeout=5)
    if not (ok_r and "EXISTS" in out):
        ssh.run(
            "echo 'rebind-domain-ok=/henu.edu.cn/' >> /etc/dnsmasq.conf",
            timeout=5)
        _ok("  dnsmasq.conf: rebind-domain-ok=/henu.edu.cn/ (放行校园内部IP)")

    # Fix 5: 确保 log-facility 不丢弃日志
    ssh.run(
        "sed -i 's/^log-facility=\\/dev\\/null/#log-facility=\\/dev\\/null/' /etc/dnsmasq.conf",
        timeout=5)

    # Phase 13: 延长 DHCP 租约 — 防止设备重连触发连锁断联
    cur_lease = ssh.run("uci get dhcp.lan.leasetime 2>/dev/null", timeout=5)[1].strip()
    if cur_lease and cur_lease != "168h":
        ssh.run("uci set dhcp.lan.leasetime='168h'", timeout=5)
        _ok(f"DHCP 租约: {cur_lease} → 168h (7天)")
    elif not cur_lease:
        ssh.run("uci set dhcp.lan.leasetime='168h'", timeout=5)
        _ok("DHCP 租约: 168h (7天)")

    # Commit and restart
    ssh.run("uci commit dhcp", timeout=5)
    ssh.run("/etc/init.d/dnsmasq restart", timeout=10)

    if ok:
        _ok("DNS 修复完成 (hosts + filter_aaaa + rebind豁免 + 域名转发 + DHCP 168h)")
    else:
        _warn("DNS 修复部分失败")
    return ok

def install_packages():
    """首次安装包前更新 opkg 源（全新路由器必需）"""
    _info("更新软件源...")
    ssh.run("opkg update 2>/dev/null | tail -3", timeout=45)

def install_cake():
    _info("正在安装 CAKE 智能流控...")
    install_packages()
    ssh.run("opkg install sqm-scripts luci-app-sqm 2>/dev/null | tail -3", timeout=30)
    ok_r, out = ssh.run("""
uci set sqm.eth1='queue'; uci set sqm.eth1.enabled='1'
uci set sqm.eth1.interface='phy1-sta0'
uci set sqm.eth1.download='110000'; uci set sqm.eth1.upload='110000'
uci set sqm.eth1.qdisc='cake'; uci set sqm.eth1.script='piece_of_cake.qos'
uci set sqm.eth1.linklayer='ethernet'; uci set sqm.eth1.overhead='44'
uci set sqm.eth1.qdisc_advanced='1'
uci set sqm.eth1.iqdisc_opts='nat dual-srchost triple-isolate wash ack-filter'
uci set sqm.eth1.eqdisc_opts='nat dual-srchost triple-isolate wash ack-filter'
uci set sqm.eth1.ingress_ecn='ECN'; uci set sqm.eth1.egress_ecn='ECN'
uci commit sqm; /etc/init.d/sqm enable 2>/dev/null; /etc/init.d/sqm start 2>/dev/null
sleep 3; tc -s qdisc show dev phy1-sta0 2>/dev/null | grep -q cake && echo CAKE_RUNNING
""", timeout=45)
    return ok_r and "CAKE_RUNNING" in out

def install_argon():
    _info("正在安装 Argon 主题...")
    install_packages()
    ssh.run("opkg install luci-theme-argon luci-app-argon-config 2>/dev/null | tail -3", timeout=30)
    ok_r, out = ssh.run("uci set luci.main.mediaurlbase='/luci-static/argon' 2>/dev/null; uci commit luci 2>/dev/null; echo ARGON_OK", timeout=15)
    return ok_r and "ARGON_OK" in out

def preflight_check():
    """
    路由器预检 — 适配全新/reset路由器
    Returns: (reachable: bool, message: str)
    """
    # 1. HTTP 检测（最快判断路由器是否在线）
    import urllib.request
    try:
        req = urllib.request.Request(f"http://{ROUTER_IP}", method='HEAD')
        urllib.request.urlopen(req, timeout=5)
        _ok(f"路由器 Web 界面可访问: http://{ROUTER_IP}")
    except:
        # 尝试其他常见 IP
        for alt_ip in ["192.168.31.1", "192.168.2.1"]:
            try:
                req = urllib.request.Request(f"http://{alt_ip}", method='HEAD')
                urllib.request.urlopen(req, timeout=3)
                _warn(f"路由器 IP 可能是 {alt_ip} 而非 {ROUTER_IP}")
                new_ip = ask(f"请输入正确的路由器 IP", default=alt_ip)
                ssh.host = new_ip
                break
            except:
                continue
        else:
            _warn("无法通过 HTTP 访问路由器")
            tip("请确认：路由器通电、网线插在 LAN 口、电脑 IP 为自动获取")
            new_ip = ask("请输入路由器 IP", default=ROUTER_IP)
            ssh.host = new_ip

    # 2. SSH 检测
    _info("检测 SSH 连接...")
    ok_conn, method = ssh.auto_connect()
    if not ok_conn:
        _warn("SSH 自动连接失败")
        print(f"  {clr('D','新刷的 ImmortalWrt 默认 root 无密码，直接回车即可')}")
        pwd = ask_pwd("请输入 root 密码（空密码直接回车）", confirm=False, min_len=0)
        if pwd:
            if not ssh.connect_pwd(pwd):
                return False, "密码连接失败"
        else:
            if not ssh._try_empty():
                return False, "空密码连接失败（SSH 服务可能未启动）"
        method = "密码" if pwd else "空密码"

    _ok(f"SSH 已连接 (方式: {method})")

    # 3. 验证系统
    ok_s, out = ssh.run("cat /etc/os-release 2>/dev/null | grep -E 'PRETTY|OPENWRT'", timeout=5)
    if ok_s and ("OpenWrt" in out or "ImmortalWrt" in out):
        m = re.search(r'"(.+)"', out)
        sys_name = m.group(1) if m else "OpenWrt"
        _ok(f"系统: {clr('G', sys_name)}")

        # 检查是否为 initramfs（临时系统）
        ok_m, mount = ssh.run("mount 2>/dev/null | grep '/overlay'", timeout=5)
        if ok_m and "ubifs" in mount:
            _ok("系统已固化 ✅ 重启不丢失配置")
        else:
            _warn("注意：系统可能未固化（initramfs），重启后配置会丢失！")
            _warn("请先刷入正式固件，再运行本工具")
    else:
        _warn("未检测到 OpenWrt/ImmortalWrt 系统")
        if not ask_yesno("系统可能不是 ImmortalWrt，是否继续？", "n"):
            return False, "非 OpenWrt 系统"

    # 4. 磁盘空间
    ok_d, disk = ssh.run("df -m /overlay 2>/dev/null | tail -1 | awk '{print $4}'", timeout=5)
    if ok_d:
        try:
            avail = int(disk.strip())
            if avail < 10:
                _warn(f"可用空间不足: {avail}MB（建议 >10MB）")
            else:
                _info(f"可用空间: {avail}MB")
        except: pass

    return True, "路由器就绪"


def find_router():
    """自动探测路由器 IP"""
    # 尝试从路由表推断
    import subprocess as sp
    try:
        r = sp.run("ipconfig", shell=True, capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if "Default Gateway" in line:
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                if m and m.group(1) != "0.0.0.0":
                    gw = m.group(1)
                    _info(f"检测到网关 IP: {clr('G', gw)}")
                    return gw
    except: pass
    return ROUTER_IP

def test_internet():
    """检测外网连通性"""
    ok_r, out = ssh.run("ping -c 1 -W 3 8.8.8.8", timeout=5)
    return ok_r and ("1 received" in out or "1 packets received" in out or "min/avg/max" in out)

# ═══════════════════════════════════════════════════════════════
# 状态管理
# ═══════════════════════════════════════════════════════════════
STATE_FILE = "/tmp/auto_config_state.json"

def state_load():
    ok_r, out = ssh.run(f"cat {STATE_FILE} 2>/dev/null || echo '{{}}'")
    try: data = json.loads(out.strip().split("\n")[-1] if out else "{}")
    except: data = {}
    for k in ["step1_password","step2_wifi","step3_wwan","step4_auth","step5_cron","step6_cake","step7_argon"]:
        if k not in data: data[k] = False
    return data

def state_save(s):
    ssh.run(f"echo '{json.dumps(s)}' > {STATE_FILE}", timeout=5)

def show_status():
    banner("当前状态")
    s = state_load()
    print(f"  {clr('W','部署进度')}")
    print(f"  ┌{'─'*38}┐")
    for k, name in [("step1_password","root 密码"),("step2_wifi","宿舍 WiFi"),("step3_wwan","校园网连接"),
                     ("step4_auth","Portal 认证"),("step5_cron","定时重连"),("step6_cake","CAKE 流控"),("step7_argon","Argon 主题")]:
        mark = clr('G','[✓ 已完成]') if s.get(k) else clr('Y','[⬜ 未完成]')
        print(f"  {mark} {name}")
    print(f"  └{'─'*38}┘\n")

    _info("实时运行状态...")
    ok_r, out = ssh.run("cat /etc/os-release 2>/dev/null | grep PRETTY", timeout=5)
    sys_info = re.search(r'"(.+)"', out).group(1) if ok_r and out else "?"
    ok_r, out = ssh.run("ip addr show dev phy1-sta0 2>/dev/null | grep 'inet '", timeout=5)
    wan_ip = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out).group(1) if ok_r and out else "无"
    ok_r, out = ssh.run("iw dev phy1-sta0 link 2>/dev/null | grep SSID", timeout=5)
    sta_ssid = out.replace("SSID:","").strip() if ok_r and out else "未连接"
    net_ok = test_internet()
    ok_r, out = ssh.run("tc -s qdisc show dev phy1-sta0 2>/dev/null | grep -q cake && echo Y", timeout=5)
    cake_ok = ok_r and "Y" in out

    show_card([
        ("系统", sys_info),
        ("校园网 IP", wan_ip, "G"),
        ("SSID", sta_ssid),
        ("外网", "已连通 ✅" if net_ok else "未连通 ❌", "G" if net_ok else "R"),
        ("CAKE", "运行中" if cake_ok else "未启动", "G" if cake_ok else "Y"),
    ])
    press_enter()

# ═══════════════════════════════════════════════════════════════
# 🤖 懒人一键模式 — 核心
# ═══════════════════════════════════════════════════════════════
def lazy_mode():
    """懒人一键部署：自动检测 + 只需填关键信息"""
    banner("[懒人] 懒人一键部署模式")
    print(f"  {clr('W','欢迎！这个模式只需要你填几个必要信息，其余全部自动完成。')}")
    print(f"  {clr('D','预计耗时 3-5 分钟。支持全新路由器（reset后首次使用）和已有配置的路由器。')}")
    print()

    # 1. 连接 & 预检（适配全新路由器）
    step_hdr(1, 5, "路由器检测 & 连接",
        "自动检测路由器IP → SSH连接 → 系统验证\n"
        "适用场景：全新刷机、reset重置、已有配置")
    print(f"  {clr('D','正在探测路由器...')}")

    # 自动探测 IP
    detected_ip = find_router()
    if detected_ip != ROUTER_IP:
        ssh.host = detected_ip
        _info(f"路由器 IP: {clr('G', detected_ip)}")

    # 预检
    ok_pre, msg = preflight_check()
    if not ok_pre:
        err_box("路由器未就绪", f"预检失败: {msg}\n请确认路由器已通电、网线插在LAN口、\n浏览器能打开 http://{ssh.host}")
        return
    press_enter()

    # 检查是否已部署过
    s_existing = state_load()
    if s_existing.get("step1_password") and s_existing.get("step2_wifi"):
        print(f"  {clr('Y','检测到路由器已有配置！')}")
        if ask_yesno("是否重新配置全部？(选n则仅更新校园网)", "n"):
            _info("将覆盖现有配置")
        else:
            _info("将保留现有配置，仅更新校园网连接")
            # 快速模式：只问校园网
            _warn("快速更新模式暂未实现，请使用主菜单 [2] 切换校园网")
            press_enter()
            return

    # 2. 填信息（一步搞定！）
    step_hdr(2, 5, "填写信息", "一次性填完所有必要信息，然后自动执行。")
    print(f"  {clr('D','━━━ 路由器安全 ━━━')}")
    root_pwd = ask_pwd("设置 root 管理员密码", confirm=True, min_len=8)
    print()
    print(f"  {clr('D','━━━ 宿舍 WiFi ━━━')}")
    dorm_ssid = ask("WiFi 名称（支持中文/emoji）", default="可以和我在一起吗")
    dorm_pwd = ask_pwd("WiFi 密码", confirm=True, min_len=8)
    print()
    print(f"  {clr('D','━━━ 校园网连接 ━━━')}")
    net_type = ask_choice("校园网类型", [("A","开放WiFi+Portal认证 (如henu-student)"),("B","加密WiFi (输密码即连)")], default="A")
    if ask_yesno("扫描周边WiFi选校园网？", "y"):
        nets = wifi_scan()
        display_scan(nets)
        if nets and ask_yesno("从列表选择？", "y"):
            n = ask("输入编号", default="1")
            try:
                idx = int(n)-1
                if 0 <= idx < len(nets):
                    campus_ssid = nets[idx]["ssid"]
                    _info(f"已选: {clr('G',campus_ssid)}")
            except: campus_ssid = ask("校园网 WiFi 名称", default="henu-student")
        else: campus_ssid = ask("校园网 WiFi 名称", default="henu-student")
    else: campus_ssid = ask("校园网 WiFi 名称", default="henu-student")

    campus_pwd = None; campus_sec = "none"
    if net_type == "B":
        campus_sec = "psk2"
        campus_pwd = ask_pwd("校园网 WiFi 密码", confirm=True, min_len=8)
    else:
        if ask_yesno("校园网 WiFi 有密码吗？", "n"):
            campus_sec = "psk2"
            campus_pwd = ask_pwd("校园网 WiFi 密码", confirm=True, min_len=8)

    auth_user = auth_pass = operator = None
    if net_type == "A":
        print()
        print(f"  {clr('D','━━━ Portal 认证信息 ━━━')}")
        auth_user = ask("学号")
        auth_pass = ask_pwd("校园网密码（上网认证用的）", confirm=True, min_len=1)
        op = ask_choice("运营商", [("1","@henuyd 移动"),("2","@henult 联通"),("3","@henudx 电信")], default="1")
        operator = {"1":"@henuyd","2":"@henult","3":"@henudx"}.get(op,"@henuyd")

    print()
    show_card([
        ("root密码","***"),
        ("宿舍WiFi", dorm_ssid),
        ("WiFi密码","***"),
        ("校园网", campus_ssid),
        ("类型", "Portal认证" if net_type=="A" else "WPA2密码"),
    ])
    if auth_user: show_card([("学号",auth_user),("运营商",operator)])

    if not ask_yesno("\n确认开始自动部署？", "y"):
        _info("已取消"); return
    press_enter()

    # 3. 自动执行
    step_hdr(3, 5, "⚡ 自动部署中", "正在配置路由器，请勿断开...")

    # root密码
    ssh.run(f"printf '%s\\n%s\\n' '{root_pwd}' '{root_pwd}' | passwd root")
    ssh.pwd = root_pwd
    s = state_load(); s["step1_password"] = True; state_save(s)
    _ok("root 密码已设置")

    # 宿舍WiFi (2.4G)
    config_dorm_wifi(dorm_ssid, dorm_pwd)
    s["step2_wifi"] = True; state_save(s)
    _ok("2.4G WiFi 已配置")

    # 5G AP (复用2.4G的SSID+密码，自动加-5G后缀)
    config_5g_ap(dorm_ssid, dorm_pwd)
    _ok("5G WiFi 已配置")

    # 校园网
    config_campus_sta(campus_ssid, campus_pwd, campus_sec)
    s["step3_wwan"] = True; state_save(s)
    _ok("校园网连接已配置")

    apply_wifi()

    # 认证
    if net_type == "A" and auth_user:
        deploy_auth_script(auth_user, auth_pass, operator)
        s["step4_auth"] = True; state_save(s)
        _ok("认证脚本已部署")
        print()
        _info("测试认证...")
        ssh.run("/etc/campus_network/auto_login.sh", timeout=30, show=True)
        time.sleep(2)

    # DNS 修复（校园网内部域名）
    deploy_dns_fix()

    # 自动化
    deploy_all_auto()
    s["step5_cron"] = True; state_save(s)
    _ok("路由看门狗 + 定时认证 + 开机启动 已部署")

    # 可选增强
    step_hdr(4, 5, "🎨 可选增强", "推荐安装，但可以跳过。")
    do_cake = ask_yesno("安装 CAKE 流控（防一个人下载全宿舍卡）？", "y")
    do_argon = ask_yesno("安装 Argon 美化主题？", "y")

    if do_cake:
        if install_cake(): s["step6_cake"] = True; state_save(s); _ok("CAKE 已启动")
    if do_argon:
        if install_argon(): s["step7_argon"] = True; state_save(s); _ok("Argon 已安装")

    # 4. SSH密钥
    step_hdr(5, 5, "🔑 SSH 免密登录", "设置后只需 ssh ax3000t 就能连路由器。")
    if ask_yesno("配置 SSH 免密登录？(推荐)", "y"):
        ssh.setup_key("ax3000t_rsa")
    else:
        _info("跳过，可以之后在主菜单 [4] 中设置")

    # 5. 完成！
    banner()
    ok_box("🎉 部署完成！",
        "拔掉网线，只留电源线即可独立工作。\n"
        f"手机连 {dorm_ssid} 即可上网。\n\n"
        "Web 管理: http://192.168.1.1\n"
        "SSH: ssh ax3000t\n\n"
        "故障排查:\n"
        "  看日志 → cat /tmp/campus_network.log\n"
        "  手动认证 → /etc/campus_network/auto_login.sh\n"
        "  重启WiFi → wifi reload")
    press_enter()

# ═══════════════════════════════════════════════════════════════
# 交互式主菜单
# ═══════════════════════════════════════════════════════════════
def menu_wifi_switch():
    banner("📡 切换校园网")
    ok_s, out = ssh.run("iw dev phy1-sta0 link 2>/dev/null | grep SSID", timeout=5)
    if ok_s: _info(f"当前: {clr('G', out.replace('SSID:','').strip())}")
    nets = wifi_scan(); display_scan(nets)
    if nets and ask_yesno("从列表选择？","y"):
        n = ask("编号"); ssid = nets[int(n)-1]["ssid"] if 0<=int(n)-1<len(nets) else ask("SSID")
    else: ssid = ask("WiFi 名称")
    sec = "none"; pwd = None
    if ask_yesno("校园网有WiFi密码？","n"):
        sec = "psk2"; pwd = ask_pwd("WiFi密码", confirm=True, min_len=8)
    if switch_campus(ssid, pwd, sec):
        _ok("已切换"); apply_wifi()
    press_enter()

def menu_dorm_wifi():
    banner("🏠 修改宿舍 WiFi")
    ok_s, out = ssh.run("uci get wireless.default_radio0.ssid 2>/dev/null", timeout=5)
    cur = out.strip() if ok_s else "?"
    _info(f"当前: {clr('G',cur)}")
    c = ask_choice("修改", [("1","改名称"),("2","改密码"),("3","都改")], default="3")
    ssid = ask("新名称", default=cur) if c in ("1","3") else None
    pwd = ask_pwd("新密码", confirm=True, min_len=8) if c in ("2","3") else None
    if ssid: ssh.run(f"uci set wireless.default_radio0.ssid='{ssid}'")
    if pwd: ssh.run(f"uci set wireless.default_radio0.key='{pwd}'")
    ssh.run("uci commit wireless && wifi reload", timeout=15)
    _ok("已更新"); press_enter()

def menu_ssh():
    banner("🔑 SSH 管理")
    if ssh.key: _info(f"密钥: {clr('G',ssh.key)}")
    elif ssh.pwd: _info("密码认证")
    else: _info("空密码/无认证")
    c = ask_choice("", [("1","生成密钥+免密登录"),("2","配置快捷连接 ssh ax3000t"),("3","测试连接"),("4","改密码"),("0","返回")], default="0")
    if c=="1": ssh.setup_key("ax3000t_rsa")
    elif c=="2":
        sc = Path.home()/".ssh"/"config"
        entry = f"\nHost ax3000t\n    HostName {ssh.host}\n    User {ssh.user}\n    IdentityFile {ssh.key or (Path(__file__).parent.parent/'.ssh'/'ax3000t_rsa')}\n    StrictHostKeyChecking no\n    UserKnownHostsFile /dev/null\n"
        if not sc.exists() or "Host ax3000t" not in sc.read_text():
            with open(sc,"a") as f: f.write(entry)
            _ok("已配置 ssh ax3000t")
        else: _info("已存在")
    elif c=="3":
        if ssh.test(): _ok("连接正常 ✅")
        else: _fail("连接失败 ❌")
    elif c=="4":
        p = ask_pwd("新密码", confirm=True, min_len=8)
        ssh.run(f"printf '%s\\n%s\\n' '{p}' '{p}' | passwd root"); ssh.pwd = p; _ok("已更新")
    press_enter()

def menu_tools():
    banner("🔧 高级工具")
    c = ask_choice("", [("1","查看认证日志"),("2","手动触发认证"),("3","路由状态"),("4","重启WiFi"),("0","返回")], default="0")
    if c=="1": ssh.run("tail -30 /tmp/campus_network.log", show=True); press_enter()
    elif c=="2": ssh.run("/etc/campus_network/auto_login.sh", show=True, timeout=30); press_enter()
    elif c=="3": ssh.run("ip route show; echo ---; iw dev phy1-sta0 link 2>/dev/null|head -8; echo ---; free -m|head -2", show=True); press_enter()
    elif c=="4": ssh.run("wifi reload", timeout=20); _ok("已重启"); press_enter()

def main_menu():
    # 连接
    ok_conn = False
    for _ in range(3):
        ok_conn, method = ssh.auto_connect()
        if ok_conn: break
        banner("连接路由器")
        _warn(f"无法自动连接 ({ssh.host})")
        p = ask_pwd("root 密码（新系统回车跳过）", confirm=False, min_len=0)
        if p:
            if ssh.connect_pwd(p): ok_conn = True; break
        elif ssh._try_empty(): ok_conn = True; break
    if not ok_conn:
        banner("无法连接")
        err_box("连接失败", "3次尝试均失败。\n请检查网线、电源，浏览器打开 http://192.168.1.1 确认路由器在线。")
        input(f"\n  {clr('Y','按 Enter 退出...')}")
        return

    s = state_load()
    while True:
        banner()
        print(f"  {clr('W','主菜单')}\n")
        items = [
            ("1","🤖 懒人一键部署","自动检测+只填关键信息，其余全自动 (推荐!)","step1_password"),
            ("2","📡 切换校园网 WiFi","快速更换校园网连接",None),
            ("3","🏠 修改宿舍 WiFi","改名称或密码",None),
            ("4","🔑 SSH 连接管理","设置免密登录、测试连接",None),
            ("5","📊 查看当前状态","路由器运行信息一览",None),
            ("6","🔧 高级工具","日志查看、手动认证、重启服务",None),
            ("0","退出","",None),
        ]
        for item in items:
            k, lbl, desc, sk = item[0], item[1], item[2], item[3] if len(item)>3 else None
            done = clr('G',' ✓') if sk and s.get(sk) else ""
            print(f"  [{k}] {lbl}{done}")
            if desc: print(f"      {clr('D',desc)}")
        print()
        ch = input(f"  {clr('C','请选择 (0-6)')}: ").strip()
        if ch=="0":
            banner(); print(clr('G',"  再见！\n")); break
        elif ch=="1": lazy_mode(); s = state_load()
        elif ch=="2": menu_wifi_switch()
        elif ch=="3": menu_dorm_wifi()
        elif ch=="4": menu_ssh()
        elif ch=="5": show_status()
        elif ch=="6": menu_tools()

if __name__ == "__main__":
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else ""
        if cmd in ("lazy","--lazy","-l"):
            # 命令行直接进懒人模式
            ok_conn, _ = ssh.auto_connect()
            if not ok_conn:
                pwd = input(f"{clr('C','root密码（新系统直接回车）')}: ")
                if pwd: ssh.connect_pwd(pwd)
                elif not ssh._try_empty(): print("连接失败"); sys.exit(1)
            lazy_mode()
        elif cmd == "wifi": menu_wifi_switch()
        elif cmd == "dorm": menu_dorm_wifi()
        elif cmd == "status": show_status()
        elif cmd in ("help","--help","-h"):
            print("AX3000T 校园网一键部署工具 v3.0")
            print("  python deploy.py         交互式菜单")
            print("  python deploy.py lazy    懒人一键模式")
            print("  python deploy.py wifi     快速切换校园网")
            print("  python deploy.py status   查看状态")
        else:
            main_menu()
    except KeyboardInterrupt:
        print(f"\n\n  {clr('Y','已中断')}")
    except Exception as e:
        print(f"\n  {clr('R',f'错误: {e}')}")
        import traceback; traceback.print_exc()
        input("  按 Enter 退出...")
