# -*- coding: utf-8 -*-
"""
llm_report.py — LLM 文本生成(三结合点之一二: 周报叙述 + 逐品类归因解释 + 滞销建议)

铁律: LLM 只做「数据→文本」翻译, 不碰数字计算。
- 输入 = out/decision.json 的结构化结论(数字锚定)
- 校验 = 输出文本中的数字必须能在输入数字集中找到(1% 容差), 失败则回退规则模板并记录
- 密钥只存 scripts/llm_config.json, 不写入任何交付物
输出: out/llm_texts.json
用法: python scripts/llm_report.py
"""
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")

cfg = json.load(open(os.path.join(ROOT, "scripts", "llm_config.json"), encoding="utf-8"))

SYS_PROMPT = """你是零售门店的周报撰写助手。严格遵守:
1. 只使用我提供的结构化数据, 禁止编造或推算任何数字;
2. 文本中出现的数字必须与输入完全一致(保留千分位逗号格式), 不得四舍五入、换算单位;
3. 不确定的表述用文字模糊化("接近""左右"可用), 但绝不猜测具体数字;
4. 语气: 店长能读懂的经营语言, 直接、具体、不堆砌形容词;
5. 用简体中文。"""

USER_TMPL = """基于以下 {store} ({stype}) {week} 订货周的结构化结论, 生成三类文本:

【周报】3-4 句经营叙述: 本周销售与环比原因、缺货风险最紧的品类、最重要的补货动作。
【归因解释】对每个品类一行(15-25字): 为什么建议这个订量(引用 μ/库存天数/趋势标签)。
【滞销建议】2-3 句: 滞销 TOP 品类的处理动作。

数据:
- KPI: 周销售额 {sales}, 环比 {salesD}
- 品类行(格式: 品类|上周销量|预测μ±σ|库存|在途|库存天数|建议箱数|标签):
{catlines}
- 滞销TOP: {slow}

严格按以下 JSON 输出(不要 markdown 代码块):
{{"report": "...", "reasons": {{"品类名": "一句话", ...}}, "slowAdvice": "..."}}"""


def call_llm(prompt, max_retries=2):
    body = json.dumps({
        "model": cfg["llm_model"],
        "messages": [{"role": "system", "content": SYS_PROMPT},
                     {"role": "user", "content": prompt}],
        "temperature": 0.3, "max_tokens": 1500,
    }).encode()
    for i in range(max_retries + 1):
        try:
            req = urllib.request.Request(
                cfg["llm_base_url"] + "/chat/completions", data=body,
                headers={"Authorization": "Bearer " + cfg["llm_api_key"],
                         "Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, timeout=60))
            return r["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if i == max_retries:
                raise
            print(f"  重试 {i+1}: {e}")


def extract_json(text):
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("输出中无 JSON")
    t = m.group(0)
    t = re.sub(r",\s*([}\]])", r"\1", t)  # 尾逗号容错
    return json.loads(t)


def numbers_of(obj):
    """递归提取数据结构中所有数字(含字符串里的数字), 返回浮点集合"""
    out = set()

    def walk(x):
        if isinstance(x, (int, float)):
            out.add(float(x))
        elif isinstance(x, str):
            for m in re.findall(r"-?\d[\d,]*\.?\d*", x):
                try:
                    out.add(float(m.replace(",", "")))
                except ValueError:
                    pass
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return out


def check_anchor(text, ref_nums):
    """校验文本数字是否都被输入(prompt 全文)数字覆盖(1%容差, 绝对值匹配——中文'下降16.3%'丢负号是合法表述)。"""
    issues = []
    for m in re.findall(r"-?\d[\d,]*\.?\d*", text):
        try:
            v = float(m.replace(",", ""))
        except ValueError:
            continue
        if v == 2017:
            continue  # 年份白名单
        ok = any(abs(abs(v) - abs(r)) <= max(abs(r) * 0.01, 0.11) for r in ref_nums)
        if not ok:
            issues.append(m)
    return issues


def rule_fallback_report(s):
    """校验失败时的规则版回退(与前端 buildReason 同思路)"""
    worst = min(s["cats"], key=lambda c: c["days"])
    return (f"本周销售额 {s['kpi']['sales']},环比 {s['kpi']['salesD']};"
            f"库存最紧的品类是 {worst['cn']}(覆盖 {worst['days']} 天),建议优先确认其订单。")


def main():
    d = json.load(open(os.path.join(OUT, "decision.json"), encoding="utf-8"))
    result = {"week": d["week"], "model": cfg["llm_model"], "stores": {}, "check": {}}
    for sid, s in d["stores"].items():
        print(f"生成 {s['name']} ...")
        catlines = "\n".join(
            f"{c['cat']}({c['cn']})|{c['last']:,}|{c['mu']:,}±{c['sigma']:,}|{c['stock']:,}|{c['transit']:,}|{c['days']}天|{sugg_of(c)}箱|{'/'.join(t[1] for t in c['tags'])}"
            for c in s["cats"])
        prompt = USER_TMPL.format(store=s["name"], stype=s["type"], week=d["week"],
                                  sales=s["kpi"]["sales"], salesD=s["kpi"]["salesD"],
                                  catlines=catlines,
                                  slow="、".join(f"{r[0]}({r[1]})" for r in s["slow"]))
        ref = numbers_of(prompt)  # 锚定基准 = 发给 LLM 的全部数字(含建议箱数/环比)
        try:
            raw = call_llm(prompt)
            parsed = extract_json(raw)
            # 字段级数字锚定校验: 哪个字段有编造数字就回退哪个
            issues_all = []
            if check_anchor(parsed.get("report", ""), ref):
                parsed["report"] = rule_fallback_report(s)
                issues_all.append("report")
            reasons = parsed.get("reasons", {})
            bad_reasons = [k for k, v in reasons.items() if check_anchor(str(v), ref)]
            for k in bad_reasons:
                c = next((x for x in s["cats"] if x["cat"] == k), None)
                reasons[k] = (f"μ={c['mu']:,}±{c['sigma']:,},库存{c['days']}天,按公式订"
                              f"{sugg_of(c)}箱" if c else "见建议表公式")
                issues_all.append(f"reasons:{k}")
            if check_anchor(str(parsed.get("slowAdvice", "")), ref):
                parsed["slowAdvice"] = "滞销品类折价清仓释放陈列位与资金,压缩至最小陈列面观察两周后再评估退出。"
                issues_all.append("slowAdvice")
            result["stores"][sid] = parsed
            result["check"][sid] = {"pass": not issues_all, "issues": issues_all or []}
        except Exception as e:
            print(f"  ✗ 生成失败: {e} → 全量回退规则版")
            result["stores"][sid] = {
                "report": rule_fallback_report(s),
                "reasons": {c["cat"]: f"μ={c['mu']:,}±{c['sigma']:,},库存{c['days']}天" for c in s["cats"]},
                "slowAdvice": "滞销品类折价清仓释放资金,压缩陈列面观察两周。"}
            result["check"][sid] = {"pass": False, "issues": [f"API失败: {str(e)[:80]}"]}
    with open(os.path.join(OUT, "llm_texts.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    n_pass = sum(1 for c in result["check"].values() if c["pass"])
    print(f"OK -> out/llm_texts.json  (数字锚定校验: {n_pass}/{len(result['check'])} 通过)")
    for sid, txt in result["stores"].items():
        print(f"--- {d['stores'][sid]['name']} 周报 ---")
        print(" ", txt["report"][:160])


def sugg_of(c):
    import math
    return max(0, math.ceil((c["mu"] * 2 + 1.0 * c["sigma"] * 1.4142 - c["stock"] - c["transit"]) / c["box"]))


if __name__ == "__main__":
    main()
