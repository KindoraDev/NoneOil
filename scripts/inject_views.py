# -*- coding: utf-8 -*-
"""
inject_views.py — 把 out/views_data.json 注入原型 HTML 的 /*VDATA_START*/.../*VDATA_END*/ 标记之间。
幂等: 重复运行会覆盖旧数据。用法: python scripts/inject_views.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "原型_前端功能总览_v0.2.html")
DATA = os.path.join(ROOT, "out", "views_data.json")

with open(DATA, encoding="utf-8") as f:
    data = json.load(f)
with open(HTML, encoding="utf-8") as f:
    html = f.read()

payload = "/*VDATA_START*/" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "/*VDATA_END*/"
new_html, n = re.subn(r"/\*VDATA_START\*/[\s\S]*?/\*VDATA_END\*/", lambda m: payload, html, count=1)
if n == 0:
    raise SystemExit("未找到 VDATA 标记, 请检查 HTML 模板")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(new_html)
print(f"OK 注入 {os.path.getsize(DATA)/1024:.0f} KB -> {os.path.basename(HTML)} (总 {os.path.getsize(HTML)/1024:.0f} KB)")
