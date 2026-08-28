# -*- coding: utf-8 -*-
"""
非油选品/智能补货 POC —— 模拟数据生成
口径详见: 06_POC_非油选品/01_数据需求清单.md
所有数据均为模拟数据, 严禁用于真实业务决策。
"""
import numpy as np
import pandas as pd
from pathlib import Path

rng = np.random.default_rng(20260827)

OUT = Path(r"D:\OneDrive\AICoding\AI转型\06_POC_非油选品\sim_data")
OUT.mkdir(parents=True, exist_ok=True)

N_WEEKS = 52          # 历史周数
WEEK_START = pd.Timestamp("2025-09-01")  # 周一

# ---------------- D1 门店主数据 ----------------
# 分型比例: 高速 33% / 城区 54% / 乡村 13% (24家: 8/13/3)
store_types = ["高速"] * 8 + ["城区"] * 13 + ["乡村"] * 3
provinces = ["北京", "天津", "河北", "内蒙古", "甘肃", "陕西"]
type_config = {
    "高速": dict(area=(60, 90), shelf=(4, 7), base_scale=1.35, name_prefix="高速",
                 mix={"饮料": 0.30, "方便速食": 0.28, "食品": 0.18, "烟酒": 0.10, "日用品": 0.08, "汽服用品": 0.06},
                 lead_time=3),
    "城区": dict(area=(80, 150), shelf=(6, 12), base_scale=1.0, name_prefix="城区",
                 mix={"食品": 0.26, "饮料": 0.24, "方便速食": 0.16, "日用品": 0.14, "烟酒": 0.12, "汽服用品": 0.08},
                 lead_time=5),
    "乡村": dict(area=(50, 70), shelf=(3, 6), base_scale=0.55, name_prefix="乡村",
                 mix={"汽服用品": 0.20, "日用品": 0.22, "食品": 0.20, "饮料": 0.16, "烟酒": 0.16, "方便速食": 0.06},
                 lead_time=7),
}
stores = []
for i, st in enumerate(store_types, 1):
    cfg = type_config[st]
    stores.append(dict(
        store_id=f"S{i:03d}",
        store_name=f"{cfg['name_prefix']}·{rng.choice(['朝阳','永定','雁栖','麒麟','雁塔','金城','天河','望北','青羊','安宁','东湖','白云'])}店",
        store_type=st,
        province=rng.choice(provinces),
        area_m2=round(rng.uniform(*cfg["area"]), 1),
        shelf_count=int(rng.integers(*cfg["shelf"])),
        traffic_level="车流" if st == "高速" else ("人流" if st == "城区" else "油卡客户"),
        base_scale=cfg["base_scale"] * rng.uniform(0.75, 1.25),
        lead_time_days=cfg["lead_time"],
    ))
df_store = pd.DataFrame(stores)

# ---------------- D2 SKU主数据 ----------------
cat_config = {
    # 类别: (毛利率范围, 季节型, 保质期, 毛利率高的促销弹性)
    "饮料":   dict(margin=(0.25, 0.40), season="summer", shelf_life=270, promo_elastic=(1.6, 2.2)),
    "食品":   dict(margin=(0.20, 0.35), season="flat",    shelf_life=180, promo_elastic=(1.4, 1.9)),
    "方便速食": dict(margin=(0.25, 0.38), season="winter",  shelf_life=120, promo_elastic=(1.5, 2.0)),
    "日用品":  dict(margin=(0.18, 0.30), season="flat",    shelf_life=540, promo_elastic=(1.1, 1.3)),
    "烟酒":   dict(margin=(0.12, 0.20), season="holiday", shelf_life=720, promo_elastic=(1.2, 1.5)),
    "汽服用品": dict(margin=(0.30, 0.45), season="flat",   shelf_life=720, promo_elastic=(1.1, 1.3)),
}
cat_items = {
    "饮料": [("500ml瓶装水", 1.5), ("350ml碳酸饮料", 2.5), ("500ml即饮茶", 3.5), ("450ml果汁", 4.0),
             ("250ml功能饮料", 5.5), ("330ml咖啡饮", 6.0), ("1.25L碳酸家庭装", 5.5), ("电解质水", 6.5),
             ("无糖气泡水", 4.5), ("常温酸奶饮", 3.0)],
    "食品": [("沙琪玛", 3.0), ("蛋黄派", 4.0), ("薯片70g", 4.5), ("巧克力棒", 5.0), ("混合坚果", 12.0),
             ("饼干", 3.5), ("牛肉干", 18.0), ("口香糖", 6.0), ("蛋糕", 5.5), ("山楂条", 2.5)],
    "方便速食": [("桶装方便面", 4.5), ("自热米饭", 15.0), ("火腿肠", 2.0), ("卤蛋", 2.5), ("饭团", 6.0),
               ("关东煮串", 4.0), ("速食汤", 5.0), ("拌面", 5.5), ("烧饼", 3.0), ("热狗肠", 3.5)],
    "日用品": [("抽纸 mini", 3.0), ("湿巾", 4.0), ("玻璃水", 12.0), ("香薰", 15.0), ("毛巾", 10.0),
             ("雨伞", 25.0), ("充电线", 20.0), ("口罩", 5.0), ("洗衣液便携", 8.0), ("创可贴", 4.0)],
    "烟酒": [("卷烟A", 18.0), ("卷烟B", 25.0), ("卷烟C", 32.0), ("听装啤酒", 5.0), ("小瓶白酒", 30.0),
            ("红酒小支", 40.0)],
    "汽服用品": [("机油小瓶", 45.0), ("玻璃水2L", 15.0), ("车载香水", 25.0), ("胎压计", 40.0), ("应急启动电源", 120.0),
              ("坐垫", 60.0), ("拖车绳", 35.0), ("车载手机支架", 18.0)],
}
prefix_map = {"饮料": "B", "食品": "S", "方便速食": "K", "日用品": "R", "烟酒": "Y", "汽服用品": "A"}

skus = []
sku_counter = {}
for cat, items in cat_items.items():
    sku_counter.setdefault(cat, 0)
    for name, price in items:
        sku_counter[cat] += 1
        cfg = cat_config[cat]
        margin = rng.uniform(*cfg["margin"])
        cost = price / (1 + margin)
        # 每个品类再衍生2个规格变体 -> 共约 (10+10+10+10+6+8)*?  控制总数
        skus.append(dict(
            sku_id=f"{prefix_map[cat]}{sku_counter[cat]:03d}",
            sku_name=name, category=cat, sub_category=name[:2],
            cost=round(cost, 2), price=price,
            margin_pct=round(margin, 3),             shelf_life_days=cfg["shelf_life"],
            box_size=6 if price > 30 else int(rng.choice([6, 12, 24])),  # 贵重品小箱规
            moq=1,
            supplier=rng.choice(["昆仑统一配送", "昆仑统一配送", "本地供应商"]),
            season_type=cfg["season"],
            promo_elastic=round(rng.uniform(*cfg["promo_elastic"]), 2),
        ))
# 生成规格衍生变体, 总数到 ~180
extra_names = ["(新包装)", "(家庭装)", "(联名款)", "(迷你装)", "(大容量)"]
base_skus = list(skus)
for k, s in enumerate(base_skus):
    if len(skus) >= 180:
        break
    for v in range(3):  # 每个基础SKU最多衍生3个变体
        if len(skus) >= 180:
            break
        s2 = dict(s)
        s2["sku_id"] = s["sku_id"] + f"V{v+1}"
        s2["sku_name"] = s["sku_name"] + extra_names[(k + v) % len(extra_names)]
        s2["price"] = round(s["price"] * rng.uniform(0.8, 1.3), 1)
        s2["cost"] = round(s2["price"] / (1 + s["margin_pct"]), 2)
        skus.append(s2)
df_sku = pd.DataFrame(skus)

# 人气值: Pareto幂律(α=1.15, 理论头部20%≈80%销量), 按95分位归一化并截断
pop_raw = (rng.pareto(1.15, len(df_sku)) + 1)
p95 = np.percentile(pop_raw, 95)
pop = np.clip(pop_raw / p95, 0.02, 2.0)
df_sku["popularity"] = pop.round(4)
slow_mask = rng.random(len(df_sku)) < 0.15
df_sku.loc[slow_mask, "popularity"] = (df_sku.loc[slow_mask, "popularity"] * 0.1).clip(lower=0.01)

# 动态需求系数: 使单店周均总销量 ≈ 700 件
TARGET_STORE_WEEK_QTY = 700
K_DEMAND = TARGET_STORE_WEEK_QTY / ((1 / 6) * df_sku["popularity"].sum())

# ---------------- 时间轴与外部因子 ----------------
weeks = pd.date_range(WEEK_START, periods=N_WEEKS, freq="W-SUN")  # 周日为周末, 标记为周末行 -> 用周一? 直接周编号
week_no = np.arange(1, N_WEEKS + 1)
# 季节因子: week 1 = 9月初
def season_factor(season_type, w):
    month = (8 + w) % 12 + 1  # 9月起始
    if season_type == "summer":   # 饮料: 5-8月高
        return 0.6 + 0.9 * max(0.0, np.cos((month - 6) / 6 * np.pi))
    if season_type == "winter":   # 速食: 11-2月高
        return 0.85 + 0.45 * max(0.0, np.cos((month - 12) / 6 * np.pi) if month in (11,12,1,2) else 0)
    if season_type == "holiday":  # 烟酒: 节日前后
        return 1.5 if month in (1, 2, 9, 10) else 0.95
    return 1.0

# 节假日因子(简化: 元旦/春节/五一/十一/中秋所在周 ± 相邻周)
holiday_weeks = set()
for d in ["2026-01-01", "2026-02-17", "2026-05-01", "2026-10-01", "2026-09-25"]:
    ts = pd.Timestamp(d)
    # 找到所在周的周编号(周日起算)
    wk = (ts - WEEK_START).days // 7 + 1
    if 1 <= wk <= N_WEEKS:
        holiday_weeks.update({wk - 1, wk, wk + 1} & set(range(1, N_WEEKS + 1)))

# ---------------- D6 促销日历 ----------------
promo_rows = []
# 每季度一波大促(饮料/食品为主), 门店型参与
promo_waves = [4, 15, 28, 40, 50]  # 周编号
for pw in promo_waves:
    for _, sku in df_sku.iterrows():
        if sku["category"] in ("饮料", "食品", "方便速食") and rng.random() < 0.25:
            st = rng.choice(["全国", "全国", "省", "店"])
            promo_rows.append(dict(week=pw, sku_id=sku["sku_id"],
                                   promo_type="打折", discount=round(rng.uniform(0.75, 0.9), 2),
                                   scope=st))
df_promo = pd.DataFrame(promo_rows)
promo_lookup = {(p["sku_id"], p["week"]): p for p in promo_rows}

# ---------------- 需求量生成 + 库存推演(人工经验补货) ----------------
rows = []
order_rows = []
inv_rows = []
pending_orders = []

# 预计算季节因子
sf_cache = {}
for season_type in ["summer", "winter", "holiday", "flat"]:
    sf_cache[season_type] = np.array([season_factor(season_type, w) for w in week_no])

for _, st in df_store.iterrows():
    mix = type_config[st["store_type"]]["mix"]
    # 门店×SKU 初始铺货: 品类结构加权抽样
    sku_pool, sku_w = [], []
    for _, sk in df_sku.iterrows():
        w = mix[sk["category"]] * (0.2 + sk["popularity"])
        sku_pool.append(sk["sku_id"])
        sku_w.append(w)
    sku_w = np.array(sku_w) / np.sum(sku_w)
    carried = rng.random(len(sku_pool)) < 0.85  # 每店并非全品类铺货
    carried_ids = [sid for sid, c in zip(sku_pool, carried) if c]

    inv = {}      # sid -> 库存
    in_transit = {}  # sid -> {到货周: 数量}
    last_week_sales = {}

    # 初始铺货: 按预期周需求×1.5周, 拆零铺货(现实: 首次铺货可拆箱)
    for sid in carried_ids:
        sk = df_sku[df_sku.sku_id == sid].iloc[0]
        exp_wk = st["base_scale"] * mix[sk["category"]] * K_DEMAND * sk["popularity"]
        inv[sid] = int(np.ceil(exp_wk * 1.5))
        last_week_sales[sid] = exp_wk  # 首周订货按预期需求

    for w in week_no:
        wk_date = WEEK_START + pd.Timedelta(days=(w - 1) * 7)
        # 1) 到货入账
        for sid in list(in_transit.keys()):
            arrivals = in_transit[sid]
            for aw in list(arrivals.keys()):
                if aw <= w:
                    inv[sid] = inv.get(sid, 0) + arrivals.pop(aw)
            if not arrivals:
                in_transit.pop(sid)

        # 2) 本周需求
        week_rows = []
        for sid in carried_ids:
            sk = df_sku[df_sku.sku_id == sid].iloc[0]
            base = st["base_scale"] * mix[sk["category"]] * K_DEMAND * sk["popularity"]  # 基础周销
            sf = sf_cache[sk["season_type"]][w - 1]
            hf = 1.35 if w in holiday_weeks else 1.0
            pf = 1.0
            pr = promo_lookup.get((sid, w))
            if pr:
                pf = sk["promo_elastic"]
            demand = base * sf * hf * pf * rng.lognormal(0, 0.25)
            # 3) 缺货约束销售
            stock = inv.get(sid, 0)
            sold = min(stock, demand)
            if stock <= 0 and demand > 0.5:
                stockout = 1
            elif demand > stock > 0:
                stockout = round(1 - stock / demand, 2)  # 部分缺货
            else:
                stockout = 0
            sold_final = int(max(0, sold))
            inv[sid] = max(0, stock - sold_final)
            # 损耗
            loss = sold_final * rng.uniform(0.005, 0.015) if sk["shelf_life_days"] <= 270 else 0
            inv[sid] = max(0, inv[sid] - loss)
            price_eff = sk["price"] * (pr["discount"] if pr else 1.0)
            week_rows.append(dict(
                store_id=st["store_id"], sku_id=sid, week=w,
                week_date=wk_date.strftime("%Y-%m-%d"),
                demand=round(demand, 2), qty=sold_final,
                amount=round(sold_final * price_eff, 2),
                stockout_flag=int(stockout > 0), stockout_ratio=stockout,
                closing_stock=round(inv[sid], 1),
            ))
            last_week_sales[sid] = sold_final
        rows.extend(week_rows)

        # 4) 周末下补货单(人工经验: 节俭偏差+凑箱取整+40%忽视在途+空架补货)
        for sid in carried_ids:
            sk = df_sku[df_sku.sku_id == sid].iloc[0]
            lw = last_week_sales.get(sid, 0)
            box = sk["box_size"]
            stock_now = inv.get(sid, 0)
            if lw <= 0 and stock_now > 0:
                # 有货无销: 滞销零星试订
                order = box if rng.random() < 0.05 else 0
            elif stock_now <= 0:
                # 空架补货: 店长看到货架空了, 75%概率补一箱
                order = box if rng.random() < 0.75 else 0
            else:
                bias = rng.uniform(0.8, 1.1)  # 节俭偏差: 平均少订5%
                need = lw * bias
                if rng.random() < 0.4:  # 忽视在途 -> 重复订货
                    pass
                else:
                    tt = sum(in_transit.get(sid, {}).values())
                    need = max(0, need - tt)
                boxes = need / box
                if boxes < 1:
                    # 需求不足一箱: 35%概率整箱补, 其余不订(等清仓)
                    order = box if rng.random() < 0.35 else 0
                else:
                    order = int(round(boxes) * box)  # 四舍五入凑箱
            if order > 0:
                arrival_w = w + max(1, st["lead_time_days"] // 3)  # 周粒度折算
                if arrival_w <= N_WEEKS:
                    pending_orders.append((st["store_id"], sid, w, order, arrival_w))
                    in_transit.setdefault(sid, {})
                    in_transit[sid][arrival_w] = in_transit[sid].get(arrival_w, 0) + order
            # 记录周末快照
            inv_rows.append(dict(
                store_id=st["store_id"], sku_id=sid, week=w,
                closing_stock=round(inv.get(sid, 0), 1),
                in_transit=round(sum(in_transit.get(sid, {}).values()), 1),
            ))

df_sales = pd.DataFrame(rows)
df_orders = pd.DataFrame(pending_orders, columns=["store_id", "sku_id", "order_week", "order_qty", "arrival_week"])
df_inv = pd.DataFrame(inv_rows)

# ---------------- 汇总输出 ----------------
df_store.to_csv(OUT / "dim_store.csv", index=False, encoding="utf-8-sig")
df_sku.to_csv(OUT / "dim_sku.csv", index=False, encoding="utf-8-sig")
df_sales.to_csv(OUT / "fact_sales.csv", index=False, encoding="utf-8-sig")
df_orders.to_csv(OUT / "fact_orders.csv", index=False, encoding="utf-8-sig")
df_inv.to_csv(OUT / "fact_inventory.csv", index=False, encoding="utf-8-sig")
df_promo.to_csv(OUT / "fact_promo.csv", index=False, encoding="utf-8-sig")

# ---------------- 摘要 ----------------
total_qty = df_sales.qty.sum()
total_amt = df_sales.amount.sum()
d = df_sales[df_sales.demand >= 1.0]  # 有效需求行: 周需求≥1件的SKU-周
so_ratio = (d.stockout_flag > 0).mean()
sku_price = dict(zip(df_sku.sku_id, df_sku.price))
lost_amt = (d.demand - d.qty).mul(d.sku_id.map(sku_price)).sum()
lost_ratio = (d.demand - d.qty).sum() / d.demand.sum()
# 库存周转: 金额加权 (总库存金额 / 周均销售金额 × 7)
sku_cost = dict(zip(df_sku.sku_id, df_sku.cost))
inv_val = (df_inv.closing_stock * df_inv.sku_id.map(sku_cost)).sum() / N_WEEKS
wk_sales_val = df_sales.amount.sum() / N_WEEKS
turn_days = inv_val / wk_sales_val * 7

print("=" * 60)
print(f"门店: {len(df_store)}  SKU: {len(df_sku)}  周数: {N_WEEKS}  K_DEMAND={K_DEMAND:.1f}")
print(f"销售明细行: {len(df_sales)}   订货单: {len(df_orders)}")
print(f"总销量: {total_qty:,.0f} 件   总销售额: ¥{total_amt:,.0f}")
print(f"单店周均销量: {total_qty/len(df_store)/N_WEEKS:.0f} 件   单店周均销售额: ¥{total_amt/len(df_store)/N_WEEKS:,.0f}")
print(f"缺货率(有效需求SKU-周, 现状/人工补货): {so_ratio:.1%}")
print(f"销量损失率(现状): {lost_ratio:.1%}   未满足需求金额: ¥{lost_amt:,.0f}")
print(f"库存周转天数(现状/人工补货, 金额加权): {turn_days:.1f} 天")
print(f"畅销集中度(全网): 头部20%SKU销量占比 = "
      f"{df_sales.groupby('sku_id').qty.sum().sort_values(ascending=False).head(int(len(df_sku)*0.2)).sum() / total_qty:.1%}")
