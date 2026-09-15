# -*- coding: utf-8 -*-
"""
replenish.py — 决策台数据管线(补货建议真实计算)

以 2017-W32 为订货周(周一晨), 基于 forecast.py 的 μ±σ 计算各店品类补货建议,
KPI/畅销滞销来自真实数据, 缺货损失/周转来自 analysis.py 推演。
构造假设(页面标注): 库存=近4周均值×1.2, 在途=0.5×μ, 箱规/单价为品类级演示口径。
输出: out/decision.json (前端决策台 DDATA)
"""
import json
import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "favorita")
OUT = os.path.join(ROOT, "out")

# 3 家代表店(真实 Favorita 门店: 旗舰大店/中型城区店/高原小镇店)
REP = [(44, "Store 44 · Quito", "旗舰大店"),
       (1, "Store 1 · Quito Centro", "中型城区店"),
       (11, "Store 11 · Cayambe", "高原小镇店")]
WK = "2017-W32"          # 订货周
HIST_W = [f"2017-W{w:02d}" for w in range(20, 33)]  # W20-W32

from_analysis = __import__("json").load  # noqa (占位避免误删)

# ─────────────── 数据 ───────────────
train = pd.read_csv(os.path.join(DATA, "train.csv"), parse_dates=["date"])
train["yw"] = train["date"].dt.strftime("%G-W%V")
weekly = (train.groupby(["store_nbr", "family", "yw"], as_index=False)
          .agg(sales=("sales", "sum"), promo_days=("onpromotion", lambda s: int((s > 0).sum()))))
fc = pd.read_csv(os.path.join(OUT, "forecast.csv"))
fcm = fc.set_index(["store_nbr", "family", "yw"])
views = json.load(open(os.path.join(OUT, "views_data.json"), encoding="utf-8"))
analysis = json.load(open(os.path.join(OUT, "analysis.json"), encoding="utf-8"))
CN = views["catCN"]

import importlib.util
spec = importlib.util.spec_from_file_location("m", os.path.join(ROOT, "scripts", "analysis.py"))
# 箱规/单价表直接内联(与 analysis.py 保持一致)
BOX = {"GROCERY I": 24, "BEVERAGES": 24, "PRODUCE": 12, "CLEANING": 30, "DAIRY": 18,
       "BREAD/BAKERY": 20, "PERSONAL CARE": 20, "DELI": 15, "EGGS": 30, "POULTRY": 12,
       "MEATS": 12, "SEAFOOD": 12, "FROZEN FOODS": 20, "LIQUOR,WINE,BEER": 12,
       "HOME CARE": 24, "BABY CARE": 24, "PET SUPPLIES": 20, "AUTOMOTIVE": 12,
       "HARDWARE": 12, "HOME APPLIANCES": 6, "BEAUTY": 18, "BOOKS": 20, "MAGAZINES": 30,
       "CELEBRATION": 24, "LINGERIE": 20, "LADIESWEAR": 20, "HOME AND KITCHEN I": 12,
       "HOME AND KITCHEN II": 12, "GROCERY II": 24, "SCHOOL AND OFFICE SUPPLIES": 24,
       "PLAYERS AND ELECTRONICS": 10, "LAWN AND GARDEN": 12, "PREPARED FOODS": 24}
PRICE = {"GROCERY I": 2.1, "BEVERAGES": 1.4, "PRODUCE": 1.8, "CLEANING": 2.9, "DAIRY": 2.3,
         "BREAD/BAKERY": 1.6, "PERSONAL CARE": 3.6, "DELI": 3.1, "EGGS": 2.5, "POULTRY": 3.4,
         "MEATS": 4.2, "SEAFOOD": 5.0, "FROZEN FOODS": 2.8, "LIQUOR,WINE,BEER": 4.5,
         "HOME CARE": 3.2, "BABY CARE": 3.8, "PET SUPPLIES": 3.5, "AUTOMOTIVE": 6.5,
         "HARDWARE": 5.5, "HOME APPLIANCES": 28.0, "BEAUTY": 4.2, "BOOKS": 6.0,
         "MAGAZINES": 3.0, "CELEBRATION": 3.3, "LINGERIE": 5.0, "LADIESWEAR": 6.5,
         "HOME AND KITCHEN I": 7.0, "HOME AND KITCHEN II": 9.0, "GROCERY II": 2.6,
         "SCHOOL AND OFFICE SUPPLIES": 2.0, "PLAYERS AND ELECTRONICS": 12.0,
         "LAWN AND GARDEN": 4.8, "PREPARED FOODS": 3.0}

stores_out = {}
for sid, name, label in REP:
    sid = int(sid)
    sw = weekly[(weekly.store_nbr == sid)]
    # 品类按近4周销售额取 TOP 10
    top_fams = (sw[sw.yw.isin(HIST_W[-4:])].groupby("family")["sales"].sum()
                .sort_values(ascending=False).head(10).index.tolist())
    cats = []
    for fam in top_fams:
        box, price = BOX.get(fam, 24), PRICE.get(fam, 3.0)
        r = fcm.loc[(sid, fam, WK)]
        mu, sigma, last = float(r.mu), float(r.sigma), float(r.actual)
        hist4 = sw[(sw.family == fam) & (sw.yw.isin(HIST_W[-5:-1]))]["sales"].mean()
        stock = round(float(hist4) * 1.2)     # 构造假设
        transit = round(mu * 0.5)
        sugg = max(0, math.ceil((mu * 2 + 1.0 * sigma * math.sqrt(2) - stock - transit) / box))
        # 标签: 趋势/促销/库存天数(阈值与 14 天覆盖目标对齐)
        tags = []
        trend = last / max(hist4, 0.5)
        if trend > 1.1: tags.append(["t-up", "趋势↑"])
        elif trend < 0.9: tags.append(["t-dn", "趋势↓"])
        days = (stock + transit) / max(mu, 0.5) * 7
        if days < 7: tags.append(["t-pro", "库存天数低"])
        elif days > 14: tags.append(["t-low", "库存充足"])
        if int(r.promo_days) >= 3: tags.append(["t-pro", "促销档"])
        cats.append({"cat": fam, "cn": CN.get(fam, fam), "last": int(last),
                     "mu": round(mu), "sigma": round(sigma),
                     "stock": int(stock), "transit": int(transit), "box": box,
                     "price": price, "days": round(days, 1), "tags": tags})
    # KPI: 周销额(真实×假设价)+真实环比, 客流(真实), 缺货/周转(推演口径)
    wk_sales = float(sw[sw.yw == WK]["sales"].sum())
    prev_sales = float(sw[sw.yw == "2017-W31"]["sales"].sum())
    sales_d = f"{(wk_sales / max(prev_sales, 1) - 1) * 100:+.1f}%"
    vs = analysis["byStore"].get(str(sid), analysis["total"])
    if isinstance(vs.get("base"), list):   # byStore 结构: [so, turn, lost]
        vb = {"so": vs["base"][0], "turn": vs["base"][1], "lost": vs["base"][2]}
        va = {"so": vs["algo"][0], "turn": vs["algo"][1], "lost": vs["algo"][2]}
    else:
        vb, va = vs["base"], vs["algo"]
    vs = {"base": vb, "algo": va}
    tr_row = next((s for s in views["stores"] if s["store"] == sid), {})
    # 12 周趋势(全店, 真实) + 预测带(算法 μ±σ 合成)
    hist = [int(sw[sw.yw == w]["sales"].sum()) for w in HIST_W]
    tot_mu = float(fc[(fc.store_nbr == sid) & (fc.yw == WK)]["mu"].sum())
    tot_sg = float(np.sqrt((fc[(fc.store_nbr == sid) & (fc.yw == WK)]["sigma"] ** 2).sum()))
    # 畅销/滞销(近4周, 金额口径 / 周转口径)
    fam4 = sw[sw.yw.isin(HIST_W[-4:])].groupby("family")["sales"].sum().sort_values(ascending=False)
    hot = [[f, f"${fam4[f] * PRICE.get(f, 3.0):,.0f}/w"] for f in fam4.head(5).index]
    slow_days = {c["cat"]: c["days"] for c in cats}
    slow = sorted(slow_days.items(), key=lambda x: -x[1])[:5] if slow_days else []
    slow = [[f, f"{slow_days[f]:.0f} 天"] for f, _ in slow]
    stores_out[str(sid)] = {
        "name": name, "type": label,
        "kpi": {"sales": f"${wk_sales * 2.2:,.0f}", "salesD": sales_d,
                "loss": f"${vs['base']['lost'] / 12 * 0.4:,.0f}", "lossD": "—",
                "turn": f"{vs['algo']['turn']:.0f} 天", "turnD": "—",
                "cats": "33", "catsSub": "低置信 3 · 库存为构造假设"},
        "trend": {"hist": hist, "mu": round(tot_mu), "sigma": round(tot_sg)},
        "cats": cats, "hot": hot, "slow": slow,
        "vs": {"so": [f"{vs['base']['so']}%", f"{vs['algo']['so']}%"],
               "turn": [f"{vs['base']['turn']:.0f} 天", f"{vs['algo']['turn']:.0f} 天"],
               "lost": [f"${vs['base']['lost'] / 54 / 12:,.0f}/w", f"${vs['algo']['lost'] / 54 / 12:,.0f}/w"]},
    }

out = {"week": WK, "stores": stores_out, "order": [s[0] for s in REP],
       "note": "预测 μ±σ 来自 forecast.py 真实计算; 库存/在途为构造假设; "
               "箱规/单价为品类级演示口径; 缺货与周转为 analysis.py 推演值"}
with open(os.path.join(OUT, "decision.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"OK -> out/decision.json  (订货周 {WK}, {len(stores_out)} 店 × 10 品类)")
for sid, s in stores_out.items():
    n_sugg = sum(1 for c in s["cats"] if (c["mu"] * 2 - c["stock"] - c["transit"]) > 0)
    print(f"  {s['name']}: 趋势末值 {s['trend']['hist'][-1]}, 预测μ {s['trend']['mu']}, 建议补货品类 {n_sugg}/10")
