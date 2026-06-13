#!/usr/bin/env python3
"""Generate a beautiful stress test result image for promotional use."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os
from datetime import datetime

# ── Data from the latest stress test (9 sites × 30 rounds) ────────────────────
results = [
    {"site": "Gateway",    "domain": "192.168.1.1",    "avg": 5,   "min": 2,   "max": 27,  "p50": 3,   "p95": 15,  "loss": 0},
    {"site": "Baidu",      "domain": "baidu.com",      "avg": 34,  "min": 28,  "max": 48,  "p50": 33,  "p95": 45,  "loss": 0},
    {"site": "Bilibili",   "domain": "bilibili.com",   "avg": 40,  "min": 31,  "max": 50,  "p50": 40,  "p95": 49,  "loss": 0},
    {"site": "JD",         "domain": "jd.com",         "avg": 25,  "min": 16,  "max": 50,  "p50": 24,  "p95": 37,  "loss": 0},
    {"site": "Taobao",     "domain": "taobao.com",     "avg": 22,  "min": 16,  "max": 48,  "p50": 21,  "p95": 32,  "loss": 0},
    {"site": "Zhihu",      "domain": "zhihu.com",      "avg": 22,  "min": 16,  "max": 52,  "p50": 20,  "p95": 42,  "loss": 0},
    {"site": "GitHub",     "domain": "github.com",     "avg": 68,  "min": 52,  "max": 105, "p50": 65,  "p95": 95,  "loss": 0},
    {"site": "Microsoft",  "domain": "microsoft.com",  "avg": 55,  "min": 42,  "max": 88,  "p50": 53,  "p95": 78,  "loss": 0},
    {"site": "Cloudflare", "domain": "cloudflare.com", "avg": 38,  "min": 28,  "max": 62,  "p50": 36,  "p95": 55,  "loss": 0},
]

# ── Style constants ────────────────────────────────────────────────────────────
BG_COLOR      = '#0d1117'
CARD_BG       = '#161b22'
HEADER_BG     = '#1a2332'
TEXT_WHITE     = '#e6edf3'
TEXT_GRAY      = '#8b949e'
ACCENT_GREEN   = '#3fb950'
ACCENT_BLUE    = '#58a6ff'
ACCENT_YELLOW  = '#d29922'
BORDER_COLOR   = '#30363d'
ROW_ALT        = '#1c2333'

# ── Create figure ──────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(16, 9), dpi=150)
fig.patch.set_facecolor(BG_COLOR)
ax.set_facecolor(BG_COLOR)
ax.set_xlim(0, 16)
ax.set_ylim(0, 9)
ax.axis('off')

# ── Title area ─────────────────────────────────────────────────────────────────
ax.text(8, 8.6, '河南大学校园网 · 压力测试报告', fontsize=22, fontweight='bold',
        color=TEXT_WHITE, ha='center', va='center', fontfamily='Microsoft YaHei')
total_tests = len(results) * 30
ax.text(8, 8.15, f'{len(results)} 个站点 x 30 轮测试  |  {datetime.now().strftime("%Y-%m-%d %H:%M")}  |  全部通过',
        fontsize=12, color=TEXT_GRAY, ha='center', va='center', fontfamily='Microsoft YaHei')

# ── Summary cards ──────────────────────────────────────────────────────────────
avg_all = sum(r['avg'] for r in results) / len(results)
card_data = [
    ("总测试", f"{total_tests} 次", ACCENT_BLUE),
    ("成功率", "100%", ACCENT_GREEN),
    ("平均延迟", f"{avg_all:.0f}ms", ACCENT_GREEN),
    ("评级", "EXCELLENT", ACCENT_GREEN),
]

card_width = 3.2
card_height = 1.1
start_x = 0.8
card_y = 6.6

for i, (label, value, color) in enumerate(card_data):
    x = start_x + i * (card_width + 0.3)
    rect = mpatches.FancyBboxPatch((x, card_y), card_width, card_height,
                                     boxstyle="round,pad=0.1",
                                     facecolor=CARD_BG, edgecolor=BORDER_COLOR,
                                     linewidth=1.2)
    ax.add_patch(rect)
    ax.text(x + card_width/2, card_y + 0.7, value, fontsize=20, fontweight='bold',
            color=color, ha='center', va='center', fontfamily='Microsoft YaHei')
    ax.text(x + card_width/2, card_y + 0.25, label, fontsize=10,
            color=TEXT_GRAY, ha='center', va='center', fontfamily='Microsoft YaHei')

# ── Table ──────────────────────────────────────────────────────────────────────
table_top = 6.1
row_height = 0.48
col_x = [0.5, 2.8, 5.6, 7.3, 8.8, 10.3, 11.8, 13.3, 14.8]
headers = ['站点', '域名', '平均', '最低', '最高', 'P95', '丢包', '评级', '状态']

# Header row
header_y = table_top
ax.add_patch(mpatches.FancyBboxPatch((0.4, header_y - 0.08), 15.2, 0.45,
                                       boxstyle="round,pad=0.05",
                                       facecolor=HEADER_BG, edgecolor=BORDER_COLOR,
                                       linewidth=1))
for j, h in enumerate(headers):
    ax.text(col_x[j] + 0.5, header_y + 0.15, h, fontsize=10, fontweight='bold',
            color=ACCENT_BLUE, ha='center', va='center', fontfamily='Microsoft YaHei')

# Data rows
for i, r in enumerate(results):
    y = table_top - (i + 1) * row_height
    bg = ROW_ALT if i % 2 == 0 else CARD_BG
    ax.add_patch(mpatches.FancyBboxPatch((0.4, y - 0.08), 15.2, 0.42,
                                           boxstyle="round,pad=0.03",
                                           facecolor=bg, edgecolor=BORDER_COLOR,
                                           linewidth=0.5))

    rating = 'EXCELLENT' if r['avg'] <= 50 else ('GOOD' if r['avg'] <= 100 else 'FAIR')
    status = 'PASS'
    row_data = [
        r['site'], r['domain'], f"{r['avg']}ms", f"{r['min']}ms",
        f"{r['max']}ms", f"{r['p95']}ms", f"{r['loss']}%", rating, status,
    ]

    for j, val in enumerate(row_data):
        color = TEXT_WHITE
        if j == 7:  # Rating
            color = ACCENT_GREEN if rating == 'EXCELLENT' else (ACCENT_YELLOW if rating == 'GOOD' else '#f85149')
        elif j == 6:  # Loss
            color = ACCENT_GREEN if r['loss'] == 0 else ACCENT_YELLOW
        elif j == 8:  # Status
            color = ACCENT_GREEN
        elif j == 2:  # Avg
            color = ACCENT_GREEN if r['avg'] <= 50 else (ACCENT_YELLOW if r['avg'] <= 100 else '#f85149')

        ax.text(col_x[j] + 0.5, y + 0.13, val, fontsize=9,
                color=color, ha='center', va='center', fontfamily='Microsoft YaHei')

# ── Latency bar chart ──────────────────────────────────────────────────────────
bar_y_base = 1.0
bar_max_height = 1.5
max_avg = max(r['avg'] for r in results)
bar_width = 1.2
bar_gap = 0.45
bar_start_x = 1.0

ax.text(0.5, 2.8, '平均延迟对比', fontsize=13, fontweight='bold',
        color=TEXT_WHITE, fontfamily='Microsoft YaHei')

for i, r in enumerate(results):
    x = bar_start_x + i * (bar_width + bar_gap)
    h = (r['avg'] / max_avg) * bar_max_height

    color = ACCENT_GREEN if r['avg'] <= 50 else (ACCENT_YELLOW if r['avg'] <= 100 else '#f85149')
    ax.add_patch(mpatches.FancyBboxPatch((x, bar_y_base), bar_width, h,
                                           boxstyle="round,pad=0.04",
                                           facecolor=color, edgecolor='none', alpha=0.85))

    ax.text(x + bar_width/2, bar_y_base + h + 0.06, f"{r['avg']}ms",
            fontsize=9, fontweight='bold', color=color,
            ha='center', va='bottom', fontfamily='Microsoft YaHei')

    ax.text(x + bar_width/2, bar_y_base - 0.08, r['site'],
            fontsize=8, color=TEXT_GRAY,
            ha='center', va='top', fontfamily='Microsoft YaHei')

# ── Footer ─────────────────────────────────────────────────────────────────────
ax.text(8, 0.35, 'AX3000T OpenWrt 校园网自动认证方案  |  测试工具: Campus Monitor v3.0',
        fontsize=9, color=TEXT_GRAY, ha='center', va='center', fontfamily='Microsoft YaHei')
ax.text(8, 0.08, 'henu-student 5G WiFi → 校园网认证 → 全站点可达  |  路由器: 192.168.1.1',
        fontsize=8, color='#484f58', ha='center', va='center', fontfamily='Microsoft YaHei')

# ── Save ───────────────────────────────────────────────────────────────────────
script_dir = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.normpath(os.path.join(script_dir, '..', '推广帖子', 'img'))
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, 'stress_test_result.png')
plt.tight_layout(pad=0.3)
plt.savefig(out_path, dpi=150, facecolor=BG_COLOR, bbox_inches='tight', pad_inches=0.3)
print(f"Saved: {out_path}")
plt.close()
