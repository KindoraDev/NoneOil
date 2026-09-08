# -*- coding: utf-8 -*-
"""
aggregate_views.py — 数据查看页聚合(Favorita 真实数据 → out/views_data.json)
为原型页面的 4 个数据查看页(门店总览/品类深钻/事件日历/油价关联)产出真实聚合数据。
用法: python scripts/aggregate_views.py  (在项目根目录执行)
"""
import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "favorita")
OUT = os.path.join(ROOT, "out")
os.makedirs(OUT, exist_ok=True)

# ─────────────────────────── 读取 ───────────────────────────
train = pd.read_csv(os.path.join(DATA, "train.csv"), parse_dates=["date"])
stores = pd.read_csv(os.path.join(DATA, "stores.csv"))
trans = pd.read_csv(os.path.join(DATA, "transactions.csv"), parse_dates=["date"])
holidays = pd.read_csv(os.path.join(DATA, "holidays_events.csv"), parse_dates=["date"])
oil = pd.read_csv(os.path.join(DATA, "oil.csv"), parse_dates=["date"])

train["week"] = train["date"].dt.isocalendar().week.astype(int)
train["year"] = train["date"].dt.year
train["dow"] = train["date"].dt.dayofweek

views = {}

# ─────────────────────────── ① 门店总览(近52周) ───────────────────────────
cutoff = train["date"].max() - pd.Timedelta(weeks=52)
t52 = train[train["date"] > cutoff]
g = t52.groupby("store_nbr").agg(
    sales=("sales", "sum"), promo_rows=("onpromotion", lambda s: int((s > 0).sum())),
    rows=("sales", "size"))
g["promo_pct"] = (g["promo_rows"] / g["rows"] * 100).round(1)
# 周均销售额
weeks_n = t52["date"].dt.to_period("W").nunique()
g["weekly_sales"] = (g["sales"] / weeks_n).round(0)
# 客流: 近52周日均
tr52 = trans[trans["date"] > cutoff]
tg = tr52.groupby("store_nbr")["transactions"].mean().round(0)
# 品类数
cg = t52.groupby("store_nbr")["family"].nunique()

store_rows = []
for _, s in stores.iterrows():
    sn = int(s["store_nbr"])
    if sn not in g.index:
        continue
    store_rows.append({
        "store": sn, "city": s["city"], "state": s["state"],
        "type": s["type"], "cluster": int(s["cluster"]),
        "weeklySales": int(g.loc[sn, "weekly_sales"]),
        "dailyTrans": int(tg.get(sn, 0)),
        "cats": int(cg.get(sn, 0)),
        "promoPct": float(g.loc[sn, "promo_pct"]),
    })
store_rows.sort(key=lambda r: -r["weeklySales"])
views["stores"] = store_rows

# ─────────────────────────── ② 品类深钻 ───────────────────────────
# 2a. 周序列(近104周, 全公司, 33品类) — 用 (year, week) 字符串
cutoff104 = train["date"].max() - pd.Timedelta(weeks=104)
t104 = train[train["date"] > cutoff104].copy()
t104["yw"] = t104["date"].dt.strftime("%G-W%V")  # ISO 年-周
wk = (t104.groupby(["family", "yw"])["sales"].sum().round(0)
      .reset_index())
views["catWeeks"] = {}
for fam, sub in wk.groupby("family"):
    views["catWeeks"][fam] = [[r["yw"], int(r["sales"])] for _, r in sub.iterrows()]

# 2b. 店×品类 销售额(近52周, 用于54店分布)
sf = t52.groupby(["family", "store_nbr"])["sales"].sum().round(0)
views["catByStore"] = {fam: [int(v) for _, v in sub.droplevel(0).items()]
                       for fam, sub in sf.groupby(level=0)}

# 2c. 促销 lift(品类): 店内对比(每店 促销日均/非促销日均), 再跨店取中位数 — 排除门店规模混杂
sd = t52.groupby(["family", "store_nbr", "date"]).agg(
    sales=("sales", "sum"), promo=("onpromotion", "max")).reset_index()
lift_by_fam = {}
for fam, sub in sd.groupby("family"):
    ratios = []
    for _, ss in sub.groupby("store_nbr"):
        p = ss[ss["promo"] > 0]["sales"].mean()
        b = ss[ss["promo"] == 0]["sales"].mean()
        if pd.notna(p) and pd.notna(b) and b > 0:
            ratios.append(p / b)
    if ratios:
        lift_by_fam[fam] = round(float(pd.Series(ratios).median()), 2)
views["lift"] = lift_by_fam

# 2d. 节假日效应(品类): 国家级假日日均 / 平日日均
nat_dates = set(holidays[(holidays["locale"] == "National")
                         & (holidays["type"].isin(["Holiday", "Additional", "Transfer"]))]["date"])
fam_day = t52.groupby(["family", "date"])["sales"].sum().reset_index()
fam_day["isHol"] = fam_day["date"].isin(nat_dates)
hol = fam_day[fam_day["isHol"]].groupby("family")["sales"].mean()
nh = fam_day[~fam_day["isHol"]].groupby("family")["sales"].mean()
views["holiday"] = {f: round(float(hol[f] / nh[f]), 2) for f in hol.index if nh.get(f, 0) > 0}

# 品类中文名映射(常见品类)
CN = {"BEVERAGES": "饮料", "GROCERY I": "食品杂货I", "PRODUCE": "生鲜果蔬", "CLEANING": "清洁用品",
      "DAIRY": "乳制品", "BREAD/BAKERY": "烘焙面包", "PERSONAL CARE": "个护", "DELI": "熟食",
      "EGGS": "蛋类", "POULTRY": "禽肉", "MEATS": "肉类", "SEAFOOD": "海鲜", "FROZEN FOODS": "冷冻食品",
      "LIQUOR,WINE,BEER": "酒类", "HOME CARE": "家居护理", "BABY CARE": "母婴", "PET SUPPLIES": "宠物",
      "AUTOMOTIVE": "汽配", "HARDWARE": "五金", "HOME APPLIANCES": "家电", "BEAUTY": "美妆",
      "BOOKS": "图书", "MAGAZINES": "杂志", "CELEBRATION": "节庆用品", "LINGERIE": "内衣",
      "LADIESWEAR": "女装", "HOME AND KITCHEN I": "厨具I", "HOME AND KITCHEN II": "厨具II",
      "GROCERY II": "食品杂货II", "SCHOOL AND OFFICE SUPPLIES": "文具办公", "PLAYERS AND ELECTRONICS": "电子",
      "LAWN AND GARDEN": "园艺", "PREPARED FOODS": "预制食品"}
views["catCN"] = CN
views["storeOrder"] = [int(s) for s in stores["store_nbr"]]

# ─────────────────────────── ③ 事件日历 ───────────────────────────
# 全公司日销售额 + 每个事件日 vs 前后7天基线
day_sales = train.groupby("date")["sales"].sum().round(0)
ds = day_sales.rolling(15, center=True, min_periods=7).mean()

events = []
for _, h in holidays.iterrows():
    d = h["date"]
    if d not in day_sales.index:
        continue
    base = ds.get(d)
    if pd.isna(base) or base == 0:
        continue
    events.append({
        "date": d.strftime("%Y-%m-%d"), "name": h["description"][:28],
        "type": h["type"], "locale": h["locale"], "localeName": h["locale_name"],
        "impact": round(float(day_sales[d] / base - 1) * 100, 1),  # 相对15日滚动基线%
    })
views["events"] = events
views["daySales"] = [[d.strftime("%Y-%m-%d"), int(v)] for d, v in day_sales.items()]

# ─────────────────────────── ④ 油价关联 ───────────────────────────
oil_sales = oil.merge(day_sales.rename("sales"), left_on="date", right_index=True, how="inner").dropna()
oil_sales["dcoilwtico"] = oil_sales["dcoilwtico"].ffill()
corr_all = float(oil_sales["dcoilwtico"].corr(oil_sales["sales"]))
corr_by_year = {int(y): round(float(sub["dcoilwtico"].corr(sub["sales"])), 3)
                for y, sub in oil_sales.groupby(oil_sales["date"].dt.year)}
views["oil"] = {
    "series": [[d.strftime("%Y-%m-%d"), float(p), int(s)]
               for (d, p, s) in zip(oil_sales["date"], oil_sales["dcoilwtico"], oil_sales["sales"])],
    "corr": round(corr_all, 3), "corrByYear": corr_by_year,
}

# ─────────────────────────── 输出 ───────────────────────────
out_path = os.path.join(OUT, "views_data.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(views, f, ensure_ascii=False, separators=(",", ":"))
print(f"OK -> {out_path} ({os.path.getsize(out_path)/1024:.0f} KB)")
print(f"  门店: {len(views['stores'])}  品类: {len(views['catWeeks'])}  事件: {len(views['events'])}")
print(f"  油价相关系数(全期): {views['oil']['corr']}  分年: {views['oil']['corrByYear']}")
print(f"  示例 lift: BEVERAGES {views['lift'].get('BEVERAGES')}  GROCERY I {views['lift'].get('GROCERY I')}")
