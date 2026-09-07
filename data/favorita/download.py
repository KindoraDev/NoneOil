# Favorita 数据集下载脚本(内网可用)
# 来源: HuggingFace 镜像 t4tiana/store-sales-time-series-forecasting (Kaggle 官方数据的社区镜像)
# 用法: python data/favorita/download.py
import urllib.request, os, sys

BASE = "https://hf-mirror.com/datasets/t4tiana/store-sales-time-series-forecasting/resolve/main"
FILES = ["train.csv", "test.csv", "stores.csv", "transactions.csv", "holidays_events.csv", "oil.csv"]
os.chdir(os.path.dirname(os.path.abspath(__file__)))
for f in FILES:
    if os.path.exists(f) and os.path.getsize(f) > 0:
        print(f"skip {f} (已存在)")
        continue
    print(f"下载 {f} ...")
    urllib.request.urlretrieve(f"{BASE}/{f}", f)
    print(f"  完成: {os.path.getsize(f)/1e6:.1f} MB")
print("全部完成")
