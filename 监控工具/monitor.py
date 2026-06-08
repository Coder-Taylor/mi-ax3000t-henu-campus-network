# -*- coding: utf-8 -*-
"""AX3000T Campus Network Monitor v3.0 — Real-time | Throughput | Charts | Capacity | Compare"""
import subprocess, os, sys, json, time, re, io, math, argparse
from pathlib import Path
from datetime import datetime
import concurrent.futures

# --- UTF-8 ---
for attr in ['stdout', 'stderr']:
    s = getattr(sys, attr)
    if s.encoding != 'utf-8':
        try: setattr(sys, attr, io.TextIOWrapper(s.buffer, encoding='utf-8', errors='replace'))
        except: pass

# --- Colours ---
G, R, Y, B, C, W, D, X = "\033[92m", "\033[91m", "\033[93m", "\033[94m", "\033[96m", "\033[1m", "\033[2m", "\033[0m"
def clr(c, t): return c + t + X
def _cls():
    # ANSI cursor home — no flicker vs cls()
    sys.stdout.write("[H[J")
    sys.stdout.flush()

# --- Sites ---
SITES = [
    ("Gateway",    "192.168.1.1",     "http://192.168.1.1",         True),
    ("Baidu",      "baidu.com",       "https://www.baidu.com",      False),
    ("Bilibili",   "bilibili.com",    "https://www.bilibili.com",   False),
    ("JD",         "jd.com",          "https://www.jd.com",         False),
    ("Taobao",     "taobao.com",      "https://www.taobao.com",     False),
    ("Zhihu",      "zhihu.com",       "https://www.zhihu.com",      False),
    ("GitHub",     "github.com",      "https://github.com",         False),
    ("Microsoft",  "microsoft.com",   "https://www.microsoft.com",  False),
    ("Cloudflare", "cloudflare.com",  "https://www.cloudflare.com", False),
]
SAVE_DIR = Path(__file__).parent / "test_results"
HIST_MAX = 120

# ================================================================
# Network Throughput (Windows Get-NetAdapterStatistics)
# ================================================================
def get_net_bytes():
    try:
        ps = (
            'powershell -NoProfile -Command '
            '"$a=Get-NetAdapterStatistics|?{$_.Name -notmatch'
            ' \\\'Loopback|isatap|Teredo\\\'}|'
            'Sort @{E={[long]$_.ReceivedBytes+[long]$_.SentBytes}} -Desc|'
            'Select -First 1;if($a){Write-Host $a.ReceivedBytes $a.SentBytes $a.Name}"'
        )
        r = subprocess.run(ps, shell=True, capture_output=True, text=True, timeout=5)
        if r.stdout.strip():
            p = r.stdout.strip().split()
            if len(p) >= 2: return int(p[0]), int(p[1]), ' '.join(p[2:])
    except: pass
    return 0, 0, "N/A"

# ================================================================
# Latency Measurement
# ================================================================
def measure_latency(url, timeout=2):
    cmd = 'curl -s -m {} -w "%{{time_connect}}" -o NUL "{}"'.format(timeout, url)
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout + 2)
        v = r.stdout.strip()
        if v and v.replace('.', '').isdigit(): return round(float(v) * 1000, 1)
    except: pass
    return -1

def measure_batch(sites, timeout=2):
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(sites)) as ex:
        futures = {ex.submit(measure_latency, s[2], timeout): s for s in sites}
        for f in concurrent.futures.as_completed(futures):
            s = futures[f]
            try: results[s[0]] = f.result()
            except: results[s[0]] = -1
    return results

# ================================================================
# Bandwidth Capacity Test
# ================================================================
CAP_URLS = [
    "https://speed.cloudflare.com/__down?bytes=10000000",
    "https://mirrors.aliyun.com/centos/8/isos/x86_64/CentOS-8-x86_64-1905-boot.iso",
    "https://mirrors.cloud.tencent.com/centos/8/isos/x86_64/CentOS-8-x86_64-1905-boot.iso",
]

def run_capacity_test():
    best = 0
    for url in CAP_URLS:
        try:
            cmd = 'curl -s -m 8 -w "%{{size_download}} %{{time_total}}" -o NUL "{}"'.format(url)
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=12)
            parts = r.stdout.strip().split()
            if len(parts) >= 2:
                b, s = float(parts[0]), float(parts[1])
                if s > 0.5 and b > 500000: best = max(best, round(b / s * 8 / 1048576, 1))
        except: pass
        if best > 0: break
    return best

# ================================================================
# Statistics
# ================================================================
def compute_stats(data):
    valid = [v for v in data if v > 0]
    if not valid: return dict(avg=0, min=0, max=0, p50=0, p95=0, p99=0, loss_pct=100, samples=0)
    n = len(valid); vs = sorted(valid)
    return dict(
        avg=round(sum(vs) / n, 1), min=round(vs[0], 1), max=round(vs[-1], 1),
        p50=round(vs[n // 2], 1),
        p95=round(vs[int(n * 0.95)], 1) if int(n * 0.95) < n else round(vs[-1], 1),
        p99=round(vs[int(n * 0.99)], 1) if int(n * 0.99) < n else round(vs[-1], 1),
        loss_pct=round((len(data) - n) / len(data) * 100, 1) if data else 0,
        samples=n
    )

# ================================================================
# Site Selection
# ================================================================
def select_sites():
    print("\n  " + clr(C, "=" * 50))
    print("  " + clr(W, "Campus Monitor - Select Sites"))
    print("  " + clr(C, "=" * 50) + "\n")
    for i, s in enumerate(SITES):
        tag = "(gateway)" if s[3] else ""
        print("  " + clr(D, "[{:2}] {:<12} {:<22} {}".format(i + 1, s[0], s[1], tag)))
    hint = 'Input: 1,3,5  or  1-5  or  "all" (default=all)'
    print("\n  " + clr(D, hint))
    inp = input("  " + clr(C, "Sites") + ": ").strip()
    if not inp or inp.lower() == "all": return SITES
    if re.match(r'^\d+-\d+$', inp):
        a, b = map(int, inp.split('-'))
        return [s for i, s in enumerate(SITES) if a <= i + 1 <= b]
    ids = set()
    for x in re.split(r'[,\s]+', inp):
        if x.isdigit(): ids.add(int(x))
    return [s for i, s in enumerate(SITES) if i + 1 in ids] if ids else SITES

# ================================================================
# Charts
# ================================================================
def draw_speed_chart(history):
    CH, CW = 6, 60
    recent = history[-CW:]
    gmax = max(recent) if recent else 1
    if gmax <= 0: return
    rng = max(gmax, 1)
    grid = [[' '] * CW for _ in range(CH)]
    sc = CW - len(recent)
    for i, v in enumerate(recent):
        col = sc + i
        if col < 0 or col >= CW: continue
        row = (CH - 1) - int(max(0, min(1, v / rng)) * (CH - 1))
        row = max(0, min(CH - 1, row))
        grid[row][col] = '#'
        for fy in range(row + 1, CH):
            if grid[fy][col] == ' ': grid[fy][col] = '.'
    print("  " + clr(C, "Real-time throughput (Mbps):"))
    bar = '-' * CW
    print("  " + clr(D, "+-------+{}+".format(bar)))
    for y in range(CH):
        val = gmax - (y / (CH - 1)) * rng
        lbl = "{:5.0f}".format(val)
        lc = G if val > rng * 0.7 else (Y if val > rng * 0.3 else R)
        print("  " + clr(lc, "|{}   |{}|".format(lbl, ''.join(grid[y]))))
    print("  " + clr(D, "+-------+{}+".format(bar)))

def draw_latency_chart(chart_sites, history):
    CH, CW = 12, 60
    chars = ['#', '*', '+', '@']; colors = [W, Y, C, G]
    all_vals = []
    for s in chart_sites:
        all_vals.extend([v for v in history[s[0]][-CW:] if v > 0])
    if len(all_vals) < 2: return
    sv = sorted(all_vals)
    p5 = sv[max(0, int(len(sv) * 0.05))]
    p95 = sv[min(len(sv) - 1, int(len(sv) * 0.95))]
    gmin, gmax = p5, p95
    rng = gmax - gmin
    if rng < 30: mid = (gmax + gmin) / 2; gmin, gmax = max(0, mid - 15), mid + 15; rng = gmax - gmin

    grid = [[' '] * CW for _ in range(CH)]
    for si, s in enumerate(chart_sites):
        recent_vals = [v for v in history[s[0]][-CW:] if v > 0]
        if len(recent_vals) < 2: continue
        ch = chars[si]; sc = CW - len(recent_vals)
        for i, v in enumerate(recent_vals):
            col = sc + i
            if col < 0 or col >= CW: continue
            norm = max(0, min(1, (v - gmin) / rng)) if rng > 0 else 0.5
            row = (CH - 1) - int(norm * (CH - 1)); row = max(0, min(CH - 1, row))
            grid[row][col] = ch
            for fy in range(row + 1, CH):
                if grid[fy][col] == ' ': grid[fy][col] = '.'

    bar = '-' * CW
    print("  " + clr(D, "+-------+{}+".format(bar)))
    for y in range(CH):
        val = gmax - (y / (CH - 1)) * rng
        lbl = "{:5.0f}ms".format(val)
        lc = R if val > gmax - rng * 0.25 else (Y if val > gmax - rng * 0.5 else G)
        print("  " + clr(lc, "|{}|{}|".format(lbl, ''.join(grid[y]))))
    print("  " + clr(D, "+-------+{}+".format(bar)))
    leg = '          '
    for i, s in enumerate(chart_sites):
        leg += '{}={}  '.format(chars[i], clr(colors[i], s[0]))
    print(leg)

# ================================================================
# LIVE MONITOR
# ================================================================
def live_monitor():
    sites = select_sites()
    if not sites: return

    history = {s[0]: [] for s in sites}
    losses = {s[0]: 0 for s in sites}
    rounds_done = {s[0]: 0 for s in sites}

    start_in, start_out, adapter = 0, 0, "N/A"
    prev_in, prev_out = 0, 0
    spd_dn, spd_up = 0.0, 0.0
    prev_dn, prev_up = 0.0, 0.0
    spd_hist = []; prev_time = None

    cap_dn = 0.0; last_cap = 0; cap_future = None
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    rnd = 0

    init = get_net_bytes()
    if init[0] > 0:
        prev_in, prev_out = init[0], init[1]; start_in, start_out = init[0], init[1]
        adapter = init[2]; prev_time = time.time()

    try:
        while True:
            rnd += 1; t0 = time.time()

            batch = measure_batch(sites, timeout=2)
            for s in sites:
                rounds_done[s[0]] += 1
                v = batch.get(s[0], -1); history[s[0]].append(v)
                if len(history[s[0]]) > HIST_MAX: history[s[0]] = history[s[0]][-HIST_MAX:]
                if v < 0: losses[s[0]] += 1

            bdata = get_net_bytes()
            if bdata[0] > 0 and prev_time:
                now = time.time(); dt = now - prev_time
                if dt >= 0.3:
                    bi, bo = bdata[0], bdata[1]; adapter = bdata[2]
                    di = bi - prev_in; do_ = bo - prev_out
                    if di < 0: di = bi
                    if do_ < 0: do_ = bo
                    prev_dn, prev_up = spd_dn, spd_up
                    spd_dn = round(di / dt * 8 / 1048576, 1)
                    spd_up = round(do_ / dt * 8 / 1048576, 1)
                    prev_in, prev_out = bi, bo; prev_time = now
                    spd_hist.append(spd_dn)
                    if len(spd_hist) > 120: spd_hist = spd_hist[-120:]

            if rnd == 1 or time.time() - last_cap > 30:
                if cap_future is None or cap_future.done():
                    cap_future = ex.submit(run_capacity_test); last_cap = time.time()
            if cap_future and cap_future.done():
                try:
                    v = cap_future.result()
                    if v > 0: cap_dn = v
                except: pass
                cap_future = None

            # --- RENDER ---
            _cls()
            total_loss = sum(losses.values())
            now_str = datetime.now().strftime('%H:%M:%S')
            print("\n  " + clr(W, "+" + "=" * 54 + "+"))
            print("  " + clr(W, "|  CAMPUS MONITOR   {}   Round {:<5}  Loss: {:<4}  |".format(now_str, rnd, total_loss)))
            print("  " + clr(W, "+" + "=" * 54 + "+") + "\n")

            print("  " + clr(D, "Adapter: " + adapter))
            if cap_dn > 0:
                print("  " + clr(Y, "Capacity: DL {:.1f}Mbps / UL {:.1f}Mbps".format(cap_dn, 0.0)))
            else:
                print("  " + clr(Y, "Capacity: testing..."))

            if spd_dn > 0 or spd_up > 0:
                da = '^' if spd_dn > prev_dn + 2 else ('v' if spd_dn < prev_dn - 2 else '-')
                sc = G if spd_dn > 50 else (Y if spd_dn > 10 else R)
                print("  " + clr(sc, "Now: DL {:.1f}Mbps {}   UL {:.1f}Mbps {}".format(spd_dn, da, spd_up, '-')))
            else:
                print("  " + clr(D, "Now: idle"))

            cb = get_net_bytes()
            if cb[0] > 0:
                dm = round((cb[0] - start_in) / 1048576, 1); um = round((cb[1] - start_out) / 1048576, 1)
                tc = G if dm < 100 else (Y if dm < 1000 else C)
                print("  " + clr(tc, "Total: DL {:.1f}MB / UL {:.1f}MB since start".format(dm, um)))

            if len(spd_hist) >= 2: print(); draw_speed_chart(spd_hist)

            chart_sites = [s for s in sites if not s[3]][:4]
            if chart_sites: print(); draw_latency_chart(chart_sites, history)

            print()
            f = "{:<10} {:<16} {:>8} {:>8} {:>8} {:>8} {:>8}"
            print("  " + clr(W, f.format('Site', 'Domain', 'Now', 'Avg', 'Min', 'Max', 'Loss')))
            print("  " + clr(D, f.format('-' * 10, '-' * 16, '-' * 8, '-' * 8, '-' * 8, '-' * 8, '-' * 8)))

            for s in sites:
                name = s[0]; vals = history[name]; st = compute_stats(vals)
                cur = vals[-1] if vals else -1
                cs = "{:.0f}ms".format(cur) if cur > 0 else "FAIL"
                ls = "{}/{}".format(losses[name], rounds_done[name])
                color = G if 0 < st["avg"] < 50 else (Y if st["avg"] < 150 else R)
                a_s = "{:.0f}ms".format(st["avg"]) if st["avg"] > 0 else "-"
                n_s = "{:.0f}ms".format(st["min"]) if st["min"] > 0 else "-"
                x_s = "{:.0f}ms".format(st["max"]) if st["max"] > 0 else "-"
                print("  " + clr(color, f.format(name, s[1], cs, a_s, n_s, x_s, ls)))

            print("\n  " + clr(D, "Ctrl+C to stop and save"))
            time.sleep(max(0.05, 0.5 - (time.time() - t0)))

    except KeyboardInterrupt:
        print("\n\n  " + clr(W, "=" * 54))
        print("  " + clr(C, "Final Summary"))
        print("  " + clr(W, "=" * 54))
        print("  " + clr(D, "Rounds: {}  Sites: {}  Samples: {}".format(rnd, len(sites), rnd * len(sites))))
        print("  " + clr(G, "Download: {:.1f}Mbps  Upload: {:.1f}Mbps".format(spd_dn, spd_up)) + "\n")
        f2 = "{:<12} {:<16} {:>8} {:>8} {:>8} {:>6}"
        print("  " + clr(W, f2.format('Site', 'Domain', 'Avg', 'Min', 'Max', 'Loss')))
        print("  " + clr(D, "-" * 60))
        for s in sites:
            st = compute_stats(history[s[0]])
            color = G if 0 < st["avg"] < 50 else (Y if st["avg"] < 150 else R)
            a_s = "{:.0f}ms".format(st["avg"]) if st["avg"] > 0 else "-"
            n_s = "{:.0f}ms".format(st["min"]) if st["min"] > 0 else "-"
            x_s = "{:.0f}ms".format(st["max"]) if st["max"] > 0 else "-"
            print("  " + clr(color, f2.format(s[0], s[1], a_s, n_s, x_s, str(losses[s[0]]))))
        _save(sites, history, losses, rounds_done, rnd, spd_dn, spd_up)
    finally:
        ex.shutdown(wait=False)

def _save(sites, history, losses, rounds_done, rnd, spd_dn, spd_up):
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fp = SAVE_DIR / "Monitor_{}.json".format(ts)
    data = {"time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "rounds": rnd,
            "download_mbps": spd_dn, "upload_mbps": spd_up, "sites": []}
    for s in sites:
        st = compute_stats(history[s[0]])
        data["sites"].append({"name": s[0], "domain": s[1], "avg": st["avg"], "min": st["min"],
            "max": st["max"], "p50": st["p50"], "p95": st["p95"], "p99": st["p99"],
            "loss": losses[s[0]], "rounds": rounds_done[s[0]], "loss_pct": st["loss_pct"]})
    with open(fp, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
    print("\n  " + clr(G, "Saved: {}".format(fp.name)) + "\n")

# ================================================================
# STRESS TEST
# ================================================================
def stress_test():
    sites = select_sites()
    if not sites: return
    print("\n  [1] 10  [2] 30  [3] 60  [4] 100")
    c = input("  " + clr(C, "Rounds (default=2)") + ": ").strip()
    rounds = {1: 10, 2: 30, 3: 60, 4: 100}.get(int(c) if c.isdigit() else 0, 30)

    ts = datetime.now().strftime('%H:%M:%S')
    print("\n  " + clr(C, "Stress Test: {} sites x {} rounds".format(len(sites), rounds)))
    print("  " + clr(D, "Start: " + ts) + "\n")

    history = {s[0]: [] for s in sites}
    for r in range(rounds):
        batch = measure_batch(sites, timeout=3)
        for s in sites: history[s[0]].append(batch.get(s[0], -1))
        pct = (r + 1) / rounds * 100; bw = 30; f = int(bw * (r + 1) / rounds)
        sys.stdout.write("\r  [{}] {:.0f}%  ({}/{})".format("#" * f + "-" * (bw - f), pct, r + 1, rounds))
        sys.stdout.flush()

    print("\n\n  " + clr(W, "Results:\n"))
    ff = "{:<12} {:<16} {:>7} {:>7} {:>7} {:>7} {:>7} {:>6} {}"
    print("  " + clr(W, ff.format('Site', 'Domain', 'Avg', 'Min', 'Max', 'P50', 'P95', 'Loss', 'Rating')))
    print("  " + clr(D, "-" * 78))

    report = []
    for s in sites:
        st = compute_stats(history[s[0]])
        if st["avg"] < 50 and st["loss_pct"] < 5: rating, color = "EXCELLENT", G
        elif st["avg"] < 100 and st["loss_pct"] < 10: rating, color = "GOOD", G
        elif st["avg"] < 200 and st["loss_pct"] < 20: rating, color = "FAIR", Y
        else: rating, color = "POOR", R
        rw = ff.format(s[0][:12], s[1][:16],
            "{:.0f}ms".format(st["avg"]) if st["avg"] > 0 else "-",
            "{:.0f}ms".format(st["min"]) if st["min"] > 0 else "-",
            "{:.0f}ms".format(st["max"]) if st["max"] > 0 else "-",
            "{:.0f}ms".format(st["p50"]) if st["p50"] > 0 else "-",
            "{:.0f}ms".format(st["p95"]) if st["p95"] > 0 else "-",
            "{:.0f}%".format(st["loss_pct"]), clr(color, rating))
        print("  " + rw)
        report.append({"name": s[0], "domain": s[1], **st})

    print("\n  " + clr(W, "Avg Latency:"))
    max_avg = max((r["avg"] for r in report if r["avg"] > 0), default=1)
    for r in report:
        if r["avg"] <= 0: print("  " + clr(R, r["name"].ljust(12) + " ALL FAILED")); continue
        bw = max(1, int(r["avg"] / max_avg * 40))
        color = G if r["avg"] < 50 else (Y if r["avg"] < 150 else R)
        print("  {:<12} {} {:.0f}ms".format(r["name"], clr(color, "#" * bw), r["avg"]))

    ib, cap = get_net_bytes(), run_capacity_test()
    if ib[0] > 0:
        print("\n  " + clr(W, "Network:") + "\n  Adapter: " + ib[2])
        if cap > 0: print("  Capacity: " + clr(G, "{:.1f} Mbps".format(cap)))
        else: print("  Capacity: N/A")

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fp = SAVE_DIR / "Stress_{}.json".format(ts)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump({"time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                   "rounds": rounds, "capacity_mbps": cap, "sites": report}, f, ensure_ascii=False, indent=2)
    print("\n  " + clr(G, "Saved: {}".format(fp.name)))
    input("\n  " + clr(Y, "Press Enter..."))

# ================================================================
# COMPARE
# ================================================================
def compare_results():
    if not SAVE_DIR.exists():
        print("  " + clr(R, "No saved results yet.")); input("  " + clr(Y, "Press Enter...")); return
    files = sorted(SAVE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(files) < 2:
        print("  " + clr(R, "Need at least 2 results (found {})".format(len(files))))
        input("  " + clr(Y, "Press Enter...")); return

    print("\n  " + clr(W, "Available Results:\n"))
    for i, fp in enumerate(files[:20]):
        try:
            d = json.loads(fp.read_text())
            print("  [{}] {} | {} | {}r | {}s".format(i+1, fp.name, d.get('time','?'), d.get('rounds','?'), len(d.get('sites',[]))))
        except: pass

    try:
        a = int(input("\n  " + clr(C, "Select 1st") + ": ")) - 1
        b = int(input("  " + clr(C, "Select 2nd") + ": ")) - 1
    except: return
    if a < 0 or a >= len(files) or b < 0 or b >= len(files): return

    d1, d2 = json.loads(files[a].read_text()), json.loads(files[b].read_text())
    print("\n  " + clr(W, "Comparison:"))
    print("  Baseline: {} ({}r)".format(d1.get('time','?'), d1.get('rounds','?')))
    print("  Current:  {} ({}r)\n".format(d2.get('time','?'), d2.get('rounds','?')))
    print("  " + clr(W, "{:<12} {:>8} {:>8} {:>8} {}".format('Site', 'Before', 'After', 'Diff', 'Trend')))
    print("  " + clr(D, "-" * 50))

    for s1 in d1.get("sites", []):
        name = s1["name"]
        s2m = [s for s in d2.get("sites", []) if s["name"] == name]
        if not s2m: print("  " + clr(R, name.ljust(12) + " (gone)")); continue
        s2 = s2m[0]; a1, a2 = s1.get("avg", 0), s2.get("avg", 0)
        if a1 > 0 and a2 > 0:
            diff = a2 - a1
            trend = clr(G, "FASTER") if diff < -10 else (clr(R, "SLOWER") if diff > 10 else clr(Y, "SAME"))
            print("  {:<12} {:>7}ms {:>7}ms {:>+7}ms {}".format(name, "{:.0f}".format(a1), "{:.0f}".format(a2), diff, trend))
        else: print("  " + clr(R, name.ljust(12) + " N/A"))
    input("\n  " + clr(Y, "Press Enter..."))

# ================================================================
# MAIN
# ================================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", default="menu", choices=["menu", "live", "stress", "compare"])
    args = parser.parse_args()
    if args.mode == "live": live_monitor()
    elif args.mode == "stress": stress_test()
    elif args.mode == "compare": compare_results()
    else:
        _cls()
        print("\n  " + clr(W, "AX3000T Network Monitor v3.0"))
        print("  " + clr(D, "Real-time | Throughput | XY Charts | Capacity | Compare\n"))
        print("  [1] Live Monitor")
        print("  [2] Stress Test")
        print("  [3] Compare Results")
        print("  [0] Exit\n")
        c = input("  " + clr(C, "Select") + ": ").strip()
        if c == "1": live_monitor()
        elif c == "2": stress_test()
        elif c == "3": compare_results()

_monitor_state = None
if __name__ == "__main__":
    _running = True
    try:
        main()
    except KeyboardInterrupt:
        print()
        print('  ' + clr(Y, 'Interrupted'))
        print()
    except Exception as e:
        print()
        print('  ' + clr(R, 'Error: ' + str(e)))
        import traceback
        traceback.print_exc()
        input('  Press Enter...')

