#!/usr/bin/env python3
"""
将开发日志.md 转换为精美的独立 HTML 文件
在浏览器中打开后 Ctrl+P → 另存为 PDF 即可
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import markdown
import re
from pathlib import Path

SRC = Path(r"D:\Document\学习\大学\大学项目组与代码\Projects\AX3000T刷机校园网\文档\开发日志.md")
DST = Path(r"D:\Document\学习\大学\大学项目组与代码\Projects\AX3000T刷机校园网\文档\AX3000T校园网项目_完整学习笔记.html")

# 读取 Markdown
md_text = SRC.read_text(encoding='utf-8')

# ---- 预处理：修复 Markdown 中影响渲染的问题 ----
# 把 ``` 代码块内部的 $VAR 保护起来（不在 HTML 中转义）
# 把 Bash 变量引用中的 \$ 处理好

# ---- HTML 模板 ----
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AX3000T 校园网自动认证 · 完整学习笔记</title>
<style>
  /* ====== 打印样式 ====== */
  @page {{
    size: A4;
    margin: 2cm 2.2cm;
    @bottom-center {{
      content: "第 " counter(page) " 页";
      font-size: 9pt;
      color: #888;
      font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
    }}
  }}

  /* ====== 基础样式 ====== */
  :root {{
    --bg: #ffffff;
    --fg: #1a1a1a;
    --accent: #2563eb;
    --code-bg: #f1f5f9;
    --border: #e2e8f0;
    --dim: #64748b;
    --green: #16a34a;
    --red: #dc2626;
    --yellow: #ca8a04;
    --blockquote-bg: #f8fafc;
    --blockquote-border: #3b82f6;
  }}

  * {{ box-sizing: border-box; }}

  body {{
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", "Segoe UI", system-ui, sans-serif;
    font-size: 12pt;
    line-height: 1.75;
    color: var(--fg);
    background: var(--bg);
    max-width: 820px;
    margin: 0 auto;
    padding: 1cm 0;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  /* ====== 标题层级 ====== */
  h1 {{
    font-size: 2em;
    text-align: center;
    margin: 1.5em 0 0.6em;
    padding-bottom: 0.3em;
    border-bottom: 3px double var(--accent);
    color: #0f172a;
    page-break-before: always;
  }}
  h1:first-of-type {{ page-break-before: avoid; }}
  h2 {{
    font-size: 1.5em;
    margin: 1.8em 0 0.6em;
    padding: 0.3em 0;
    border-bottom: 2px solid var(--border);
    color: #1e3a5f;
  }}
  h3 {{
    font-size: 1.2em;
    margin: 1.2em 0 0.4em;
    color: #334155;
  }}
  h4 {{
    font-size: 1.05em;
    margin: 1em 0 0.3em;
    color: #475569;
  }}

  /* ====== 段落和行内元素 ====== */
  p {{ margin: 0.6em 0; text-align: justify; }}
  strong {{ color: #0f172a; }}
  em {{ color: #475569; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  /* ====== 代码 ====== */
  code {{
    font-family: "Cascadia Code", "Fira Code", "JetBrains Mono", "Consolas", "Courier New", monospace;
    font-size: 0.9em;
    background: var(--code-bg);
    padding: 2px 5px;
    border-radius: 3px;
    border: 1px solid var(--border);
    word-break: break-all;
  }}
  pre {{
    background: #1e293b;
    color: #e2e8f0;
    padding: 1em 1.2em;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 0.85em;
    line-height: 1.55;
    margin: 0.8em 0;
    white-space: pre-wrap;
    word-break: break-all;
  }}
  pre code {{
    background: transparent;
    border: none;
    padding: 0;
    font-size: inherit;
    color: inherit;
  }}

  /* ====== 引用块 ====== */
  blockquote {{
    margin: 1em 0;
    padding: 0.6em 1em;
    border-left: 4px solid var(--blockquote-border);
    background: var(--blockquote-bg);
    border-radius: 0 4px 4px 0;
    color: #475569;
  }}
  blockquote p {{ margin: 0.3em 0; }}

  /* ====== 表格 ====== */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 1em 0;
    font-size: 0.95em;
  }}
  th {{
    background: #1e3a5f;
    color: white;
    padding: 8px 12px;
    text-align: left;
    font-weight: 600;
  }}
  td {{
    padding: 7px 12px;
    border-bottom: 1px solid var(--border);
  }}
  tr:nth-child(even) td {{ background: #f8fafc; }}
  tr:hover td {{ background: #e8f0fe; }}

  /* ====== 水平线 ====== */
  hr {{
    border: none;
    border-top: 2px dashed var(--border);
    margin: 2em 0;
  }}

  /* ====== 列表 ====== */
  ul, ol {{ padding-left: 1.8em; margin: 0.6em 0; }}
  li {{ margin: 0.3em 0; }}

  /* ====== 特殊标记 ====== */
  .emoji {{ font-style: normal; }}

  /* ====== 封面信息 ====== */
  .cover-info {{
    text-align: center;
    color: var(--dim);
    font-size: 0.95em;
    margin: 1em 0 2em;
  }}

  /* ====== 打印优化 ====== */
  @media print {{
    body {{ font-size: 10.5pt; line-height: 1.65; }}
    h1 {{ page-break-before: always; }}
    h1:first-of-type {{ page-break-before: avoid; }}
    h2 {{ page-break-after: avoid; }}
    h3, h4 {{ page-break-after: avoid; }}
    pre, blockquote, table {{ page-break-inside: avoid; }}
    a {{ color: inherit; }}
  }}

  /* ====== 目录样式 ====== */
  .toc {{ background: #f8fafc; padding: 1em 1.5em; border-radius: 8px; margin: 1.5em 0; }}
  .toc a {{ display: block; padding: 2px 0; }}
</style>
</head>
<body>

{body}

<div style="text-align:center;color:#94a3b8;font-size:0.85em;margin-top:3em;padding-top:1em;border-top:1px solid #e2e8f0;">
  <p>📖 AX3000T 校园网自动认证项目 · 完整学习笔记</p>
  <p>涵盖从路由器硬件原理到 OpenWrt 高级配置的全部知识点</p>
  <p>最后更新: 2026-06-08</p>
</div>

</body>
</html>"""

# ---- 转换 Markdown → HTML ----
md_extensions = [
    'tables',
    'fenced_code',
    'codehilite',
    'toc',
    'nl2br',
    'sane_lists',
]

# 使用 Python markdown 库转换
html_body = markdown.markdown(md_text, extensions=md_extensions)

# ---- 后处理：美化 ----
# 添加代码语言标签
html_body = re.sub(r'<pre><code>', '<pre><code>', html_body)

# 合并多余的 br
html_body = re.sub(r'<br\s*/?>\s*<br\s*/?>', '<br>', html_body)

# 写入
final_html = HTML_TEMPLATE.format(body=html_body)
DST.write_text(final_html, encoding='utf-8')

print(f"✅ HTML 已生成: {DST}")
print(f"📏 文件大小: {len(final_html):,} 字符")
print(f"🖨️  在浏览器中打开后按 Ctrl+P → 另存为 PDF 即可")
