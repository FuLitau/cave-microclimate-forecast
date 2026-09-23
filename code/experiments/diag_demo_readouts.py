"""诊断：演示看板若换用「风险对齐」的分位数读出，三级决策是否还全为 0 级。

背景
----
``code/results/demo_forecast.csv``（前端看板唯一数据源）由
``code/experiments/build_demo_forecast.py`` 生成，用的是**状态式线性 MSE 读出**
``kt.fit_direct`` + ``kt.predict_direct``。实测三个演示场景 ``max_level`` **全为 0**：
高湿事件起点 2024-04-16 的 72 h 内真实窟内 RH 峰值 **89.0%**，而预报峰值只有
**38.4%**，连 62% 的一级预警都够不到。

``code/results/derisk03_peak.csv`` 已量化根因：MSE 线性读出把极值系统性拉向均值，
真实值最高 1% 的样本上预报均值只有真值的 **55.9–59.2%**；``derisk03_readout_compare.csv``
给出两条修复路线——分位数（τ=0.9）读出把捕捉比提到 **62.0–67.4%**，GBDT 非线性读出
提到 **60.9–68.9%**。

本脚本回答一个具体问题
----------------------
**把演示看板换成分位数读出，三个场景分别报什么级？** 这决定「应用成效」是被低估
（看板只是没接上更好的读出）还是本就如此（极值压缩是该方法的内在天花板）。

⚠️ 本脚本**不修改任何落盘产物**，只打印对照表，供决定是否重建 ``demo_forecast.csv``。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operator.transport import (                       # noqa: E402
    KoopmanTransport, TransportConfig, build_features,
)
from src.physics.cave_model import CaveModel, CaveParams   # noqa: E402

TRAIN_END = "2020-12-31"          # 与 build_demo_forecast.py 一致
N_HORIZON = 73                    # 0..72 h
RH_WARN, RH_CRIT, RH_CLOSE = 62.0, 67.0, 75.0
TAUS = (0.9, 0.95)


def level(rh: float) -> int:
    if rh >= RH_CLOSE:
        return 2
    if rh >= RH_WARN:
        return 1
    return 0


def main() -> None:
    t0 = time.time()
    print("=" * 84)
    print("诊断：演示看板的读出层对照（线性 MSE vs 分位数 τ）")
    print("=" * 84)

    od = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                     index_col=0, parse_dates=True).sort_index()
    od = od[~od.index.duplicated(keep="first")]
    cave = CaveModel(CaveParams()).simulate(od)
    rh = cave["RH_in"].to_numpy(dtype=float)
    idx = od.index

    tr = np.asarray(od.index <= pd.Timestamp(TRAIN_END, tz="UTC"))

    print("\n[1] 拟合输运算子 ...")
    kt = KoopmanTransport(TransportConfig(ridge_beta=1.0)).fit(
        od[tr], rh[tr], fit_koopman=False)
    Psi = build_features(od, kt.cfg)
    print(f"    特征维度 p = {Psi.shape[1]}   训练段 {tr.sum():,} h")

    # ---------- 复现 build_demo_forecast.py 的起点选择逻辑 ----------
    te_pos = np.where(~tr)[0]
    te_pos = te_pos[(te_pos > 168) & (te_pos < len(idx) - 200)]
    fut_max = np.array([rh[p:p + N_HORIZON].max() for p in te_pos])
    picks = []
    for q, label in ((0.9999, "高湿事件"), (0.98, "偏高湿"), (0.50, "平稳期")):
        target = np.quantile(fut_max, q)
        j = int(np.argmin(np.abs(fut_max - target)))
        picks.append((int(te_pos[j]), label))
    print("\n[2] 演示起点（与 build_demo_forecast.py 同逻辑）：")
    for p, lab in picks:
        print(f"    {lab:<6} {idx[p]}   未来 72 h 真实峰值 {rh[p:p + N_HORIZON].max():6.2f}%")

    # ---------- 逐时效拟合三种读出（带磁盘缓存：分位数读出全程约 13 min） ----------
    names = ["线性 MSE", *[f"分位数 τ={tau}" for tau in TAUS]]
    cache = ROOT / "results" / "diag_demo_readouts_weights.npz"
    print(f"\n[3] 逐时效拟合读出（0–{N_HORIZON - 1} h）...")
    W = {n: {} for n in names}
    if cache.exists():
        z = np.load(cache)
        for n in names:
            for h in range(N_HORIZON):
                W[n][h] = z[f"{n}|{h}"]
        print(f"    复用缓存 {cache.name}（删除该文件可强制重算）")
    else:
        for name in names:
            t1 = time.time()
            for h in range(N_HORIZON):
                if name == "线性 MSE":
                    W[name][h] = kt.fit_direct(od[tr], rh[tr], h, Psi=Psi[tr])
                else:
                    tau = float(name.split("=")[1])
                    W[name][h] = kt.fit_direct_quantile(od[tr], rh[tr], h, tau=tau,
                                                        Psi=Psi[tr])
            print(f"    {name:<14} {time.time() - t1:6.1f}s")
        np.savez_compressed(cache, **{f"{n}|{h}": W[n][h]
                                      for n in names for h in range(N_HORIZON)})
        print(f"    权重已缓存到 results/{cache.name}")

    # ---------- 起点 -> 0..72 h 逐时预报 ----------
    rows = []
    for p, lab in picks:
        for name, w_by_h in W.items():
            i = 0
            for h in range(N_HORIZON):
                tgt = p + h
                if tgt >= len(idx):
                    break
                pred = float(np.asarray(
                    kt._add_intercept(kt.transform(Psi[p:p + 1])) @ w_by_h[h]
                ).reshape(-1)[0])
                rows.append({"scenario": lab, "readout": name, "origin": str(idx[p]),
                             "step_h": h, "RH_pred": round(pred, 3),
                             "RH_true": round(float(rh[tgt]), 3),
                             "level": level(pred)})
                i += 1
    df = pd.DataFrame(rows)

    # ---------- 汇总 ----------
    print("\n" + "=" * 84)
    print("每场景 / 每读出：72 h 内预报峰值、真实峰值、最高决策级、首次非 0 级时刻")
    print("=" * 84)
    summ = []
    for (lab, name), g in df.groupby(["scenario", "readout"], sort=False):
        nz = g[g.level > 0]
        summ.append({
            "场景": lab, "读出": name,
            "预报峰值": round(float(g.RH_pred.max()), 2),
            "真实峰值": round(float(g.RH_true.max()), 2),
            "峰值比": round(float(g.RH_pred.max() / g.RH_true.max()), 3),
            "最高级": int(g.level.max()),
            "首次非0级(h)": int(nz.step_h.min()) if len(nz) else None,
            "非0级小时数": int((g.level > 0).sum()),
        })
    sdf = pd.DataFrame(summ)
    print(sdf.to_string(index=False))

    piv = sdf.pivot_table(index="场景", columns="读出", values="最高级")
    print("\n最高决策级对照（0=正常开放 / 1=限流 / 2=关闭）：")
    print(piv.to_string())

    out = ROOT / "results" / "diag_demo_readouts.csv"
    df.to_csv(out, index=False)
    sdf.to_csv(ROOT / "results" / "diag_demo_readouts_summary.csv", index=False)
    print(f"\n明细已写入 {out.relative_to(ROOT)}（逐时），汇总写入 "
          f"results/diag_demo_readouts_summary.csv")
    print(f"总用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
