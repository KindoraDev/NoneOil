# -*- coding: utf-8 -*-
"""
inject_views.py — 把 out/*.json 注入原型 HTML 的标记之间(幂等,重复运行覆盖旧数据)。
标记: /*VDATA_START*/.../*VDATA_END*/ ← out/views_data.json (数据查看页)
      /*BDATA_START*/.../*BDATA_END*/ ← out/backtest.json (预测复盘页)
用法: python scripts/inject_views.py [html路径, 默认 v0.3]
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "原型_前端功能总览_v0.4.html")

INJECT = [
    (r"VDATA_START", r"VDATA_END", os.path.join(ROOT, "out", "views_data.json")),
    (r"BDATA_START", r"BDATA_END", os.path.join(ROOT, "out", "backtest.json")),
    (r"DDATA_START", r"DDATA_END", os.path.join(ROOT, "out", "decision.json")),
]

with open(HTML, encoding="utf-8") as f:
    html = f.read()

for s_mark, e_mark, path in INJECT:
    if s_mark not in html:
        print(f"跳过 {s_mark}(HTML 中无标记)")
        continue
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    payload = "/*" + s_mark + "*/" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "/*" + e_mark + "*/"
    html, n = re.subn(
        r"/\*" + s_mark + r"\*/[\s\S]*?/\*" + e_mark + r"\*/",
        lambda m: payload, html, count=1)
    if n == 0:
        raise SystemExit(f"标记 {s_mark} 替换失败")
    print(f"注入 {os.path.basename(path)} ({os.path.getsize(path)/1024:.0f} KB) -> {s_mark}")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(html)
print(f"OK -> {os.path.basename(HTML)} (总 {os.path.getsize(HTML)/1024:.0f} KB)")
