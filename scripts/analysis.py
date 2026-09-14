# -*- coding: utf-8 -*-
"""
analysis.py — 效果对比推演(附录·省公司视角) + 畅销/滞销数据

效果对比(A 方案,霖哥 2026-09-14 确认): Favorita 无订货记录,
现状基线按行业通识四偏差模拟(惯性订货/凑箱取整/忽视在途/无安全库存+空架兜底),
算法侧用 replenish 公式(k=1.0), 同一需求序列(2017 实际销量)重演 12 周库存轨迹。
页面显著标注「基线为模拟推演」。方向正确性验证,数值不作业务承诺。
输出: out/analysis.json
"""
import json
import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "favorita")
OUT = os.path.join(ROOT, "out")

rng = np.random.default_rng(42)  # 固定种子保证可复现

# 品类级假设: 箱规 / 单价(演示口径, 页面标注)
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
K_SAFETY = 1.0  # 算法安全库存系数(与前端默认滑块一致)
WEEKS = [f"2017-W{w:02d}" for w in range(21, 33)]  # W21-W32

# ─────────────── 数据 ───────────────
train = pd.read_csv(os.path.join(DATA, "train.csv"), parse_dates=["date"])
train["yw"] = train["date"].dt.strftime("%G-W%V")
weekly = (train.groupby(["store_nbr", "family", "yw"], as_index=False)
          .agg(sales=("sales", "sum"),
               promo_days=("onpromotion", lambda s: int((s > 0).sum()))))
fc = pd.read_csv(os.path.join(OUT, "forecast.csv"))  # 含 W21-W32 的 mu/sigma
fcm = fc.set_index(["store_nbr", "family", "yw"])

# 初始库存: W21 前 4 周均值 × 1.2(拆零)
pre = weekly[weekly.yw.isin([f"2017-W{w:02d}" for w in range(17, 21)])]
init = (pre.groupby(["store_nbr", "family"])["sales"].mean() * 1.2).to_dict()

# ─────────────── 双策略重演 ───────────────
res = {"base": {"lost": 0.0, "demand": 0.0, "lostVal": 0.0, "invVal": 0.0, "soldVal": 0.0},
       "algo": {"lost": 0.0, "demand": 0.0, "lostVal": 0.0, "invVal": 0.0, "soldVal": 0.0}}
by_store = {}

for (store, fam), sub in weekly[weekly.yw.isin(WEEKS)].groupby(["store_nbr", "family"]):
    sub = sub.set_index("yw").reindex(WEEKS)
    box, price = BOX.get(fam, 24), PRICE.get(fam, 3.0)
    demands = sub["sales"].fillna(0).values
    if demands.sum() < 1:
        continue
    # 各周预测(无则退化用上期)
    mus, sgs = [], []
    for yw in WEEKS:
        try:
            r = fcm.loc[(store, fam, yw)]
            mus.append(float(r.mu)); sgs.append(float(r.sigma))
        except KeyError:
            mus.append(max(float(np.mean(demands)), 1.0)); sgs.append(max(float(np.mean(demands)) * 0.3, 1.0))
    init_stock = init.get((store, fam), float(np.mean(demands)) * 1.2)

    for side in ("base", "algo"):
        stock = init_stock          # 期末库存
        arriving = 0.0              # 本周到货
        last_demand = float(np.mean(demands[:1])) or init_stock / 1.2
        lost = demand_tot = lost_val = inv_val = sold_val = 0.0
        for t, d in enumerate(demands):
            # ── 本周订货决策(周一), 到货滞后 1 周
            if side == "base":   # 四偏差: 惯性×U(0.8,1.05) + 四舍五入凑箱 + 无安全库存 + 忽视在途
                order = last_demand * rng.uniform(0.8, 1.05)
                order = round(order / box) * box
                if stock <= 0 and rng.random() < 0.75:   # 空架兜底
                    order = max(order, box)
            else:               # 算法: 目标库存 + 安全库存, 减库存减在途
                need = mus[t] * 2 + K_SAFETY * sgs[t] * math.sqrt(2) - stock - arriving
                order = max(0, math.ceil(need / box)) * box
            arriving_next = order
            # ── 周中: 到货 + 需求满足
            avail = stock + arriving
            sold = min(d, avail)
            stock = avail - sold
            lost_d = d - sold
            # ── 累计
            lost += lost_d; demand_tot += d
            lost_val += lost_d * price; sold_val += sold * price
            inv_val += (stock + stock + sold) / 2 * price * 7  # 金额×天
            last_demand = d
            arriving = arriving_next
        r = res[side]
        r["lost"] += lost; r["demand"] += demand_tot
        r["lostVal"] += lost_val; r["invVal"] += inv_val; r["soldVal"] += sold_val
        bs = by_store.setdefault(store, {s: {"lost": 0.0, "demand": 0.0, "lostVal": 0.0,
                                             "invVal": 0.0, "soldVal": 0.0} for s in ("base", "algo")})
        b = bs[side]
        b["lost"] += lost; b["demand"] += demand_tot
        b["lostVal"] += lost_val; b["invVal"] += inv_val; b["soldVal"] += sold_val

def metrics(r):
    stockout = r["lost"] / r["demand"] * 100
    turn = r["invVal"] / r["soldVal"] if r["soldVal"] else 0  # 金额加权天数
    return round(stockout, 1), round(turn, 0), round(r["lostVal"], 0)

b_so, b_turn, b_lost = metrics(res["base"])
a_so, a_turn, a_lost = metrics(res["algo"])

stores_vs = {}
for st, d in by_store.items():
    b = metrics(d["base"]); a = metrics(d["algo"])
    stores_vs[st] = {"base": b, "algo": a}

out = {
    "note": "基线为行业通识四偏差模拟(惯性订货/凑箱/忽视在途/无安全库存), 算法侧为补货公式重演; "
            "同一 2017 实际需求序列, 到货均滞后 1 周。方向正确性验证, 数值不作业务承诺。",
    "total": {"base": {"so": b_so, "turn": b_turn, "lost": b_lost},
              "algo": {"so": a_so, "turn": a_turn, "lost": a_lost}},
    "byStore": {str(k): v for k, v in stores_vs.items()},
}
with open(os.path.join(OUT, "analysis.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

print(f"OK -> out/analysis.json  (12 周重演, 54 店 × 33 品类)")
print(f"  缺货率:   基线 {b_so}%  → 算法 {a_so}%")
print(f"  周转天数: 基线 {b_turn}  → 算法 {a_turn}")
print(f"  销售损失: 基线 ${b_lost:,.0f} → 算法 ${a_lost:,.0f}")
