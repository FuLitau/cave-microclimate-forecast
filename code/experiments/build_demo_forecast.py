"""为前端看板预生成演示用预报序列。

为什么要预生成
--------------
前端要展示的是"未来 24/48/72 h 的窟内风险预报"，这需要把**输运算子的多步读出**
跑一遍并落盘，前端只做展示、不做计算。这样前端启动快、且结果可复现、可审计。

做法
----
1. 用 2001–2020 拟合输运算子（与实验口径一致，模拟真实部署：只用历史数据训练）；
2. 在 2021 年之后挑若干"有代表性"的起点（含高湿事件、含平稳期）；
3. 每个起点输出 72 h 的窟内 RH 预报 + 实况（物理合成标签）+ 三级决策；
4. 同时输出一条连续的历史序列，供"离线回放"模式使用。

⚠️ 预报对象是 **physics-derived synthetic** 窟内 RH，不是实测。前端与文档均须标注。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operator.transport import KoopmanTransport, TransportConfig  # noqa: E402
from src.physics.cave_model import CaveModel, CaveParams              # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

TRAIN_END = "2020-12-31"
HORIZONS = (24, 48, 72)

#: 三级阈值（逐级独立出处，见 docs/02_数据集方案.md §3.5）
RH_WARN, RH_CRIT, RH_CLOSE = 62.0, 67.0, 75.0


def decision(rh: float) -> tuple[int, str]:
    """窟内 RH -> (等级, 建议)。用上分位数思路，这里对单点预报直接判级。"""
    if rh >= RH_CLOSE:
        return 2, "关闭高危洞窟"
    if rh >= RH_WARN:
        return 1, "限流（控制人数与停留时长）"
    return 0, "正常开放"


def main() -> None:
    outdoor = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                          index_col=0, parse_dates=True).sort_index()
    outdoor = outdoor[~outdoor.index.duplicated(keep="first")]

    print("[1] 生成窟内物理合成标签 ...")
    cave = CaveModel(CaveParams()).simulate(outdoor)

    tr = outdoor.index <= pd.Timestamp(TRAIN_END, tz="UTC")
    print(f"[2] 拟合输运算子（训练段 {tr.sum():,} h）...")
    kt = KoopmanTransport(TransportConfig(ridge_beta=1.0)).fit(
        outdoor[tr], cave["RH_in"].to_numpy()[tr], fit_koopman=False)

    rh_true = cave["RH_in"].to_numpy(dtype=float)
    idx = outdoor.index

    # 直接多步读出权重：每个时效只拟合一次（否则内层循环会重复拟合数百次）
    print("[3] 逐时效拟合直接多步读出 ...")
    w_direct = {h: kt.fit_direct(outdoor[tr], rh_true[tr], h) for h in range(73)}
    print("    完成 0-72 h")

    # ---------- 挑演示起点：按**未来 72 h 内**的窟内 RH 挑，而不是按起点时刻挑 ----------
    # 预警系统要展示的是"提前量"，因此起点必须选在**事件发生之前**。
    # 早期版本按起点时刻的 RH 分位数选，结果三个场景的 72 h 预报全落在阈值以下，
    # 完全演示不出预警能力。
    te_pos = np.where(~tr)[0]
    te_pos = te_pos[(te_pos > 168) & (te_pos < len(idx) - 200)]
    fut_max = np.array([rh_true[p:p + 73].max() for p in te_pos])
    picks = []
    for q, label in ((0.9999, "高湿事件"), (0.98, "偏高湿"), (0.50, "平稳期")):
        target = np.quantile(fut_max, q)
        j = int(np.argmin(np.abs(fut_max - target)))
        picks.append((int(te_pos[j]), label, q))
    print("[3] 演示起点（按未来 72 h 内最大窟内 RH 选，确保起点在事件之前）：")
    for p, l, _ in picks:
        print(f"      {l:<6} 起点 {idx[p]}   未来 72h 内最大窟内 RH = "
              f"{rh_true[p:p + 73].max():.1f}%")

    # ---------- 逐起点生成 72 h 预报 ----------
    rows = []
    for pos, label, q in picks:
        # 严格因果：只用截止到 pos 的外场观测构造特征
        hist = outdoor.iloc[: pos + 1]
        for h in range(0, 73):
            tgt = pos + h
            if tgt >= len(idx):
                break
            pred = kt.predict_direct(hist, w_direct[h])[-1]
            truth = float(rh_true[tgt])
            lvl, advice = decision(float(pred))
            rows.append({
                "origin": str(idx[pos]),
                "scenario": label,
                "step_h": h,
                "time": str(idx[tgt]),
                "RH_pred": round(float(pred), 3),
                "RH_true": round(truth, 3),
                "level": lvl,
                "advice": advice,
                "T_out": round(float(outdoor["T2M"].iloc[tgt]), 2),
                "RH_out": round(float(outdoor["RH2M"].iloc[tgt]), 2),
                "Q_m3h": round(float(cave["Q_m3h"].iloc[tgt]), 1),
            })

    df_fc = pd.DataFrame(rows)
    df_fc.to_csv(RESULTS / "demo_forecast.csv", index=False)
    print(f"    写出 demo_forecast.csv  {df_fc.shape}")

    # ---------- 历史序列（离线回放用）：2021 年起，逐时 ----------
    hist_df = pd.DataFrame({
        "time": idx[~tr].astype(str),
        "T_out": outdoor["T2M"][~tr].round(2).to_numpy(),
        "RH_out": outdoor["RH2M"][~tr].round(2).to_numpy(),
        "T_in": cave["T_in"][~tr].round(2).to_numpy(),
        "RH_in": cave["RH_in"][~tr].round(2).to_numpy(),
        "Q_m3h": cave["Q_m3h"][~tr].round(1).to_numpy(),
    })
    hist_df.to_csv(RESULTS / "demo_history.csv", index=False)
    print(f"    写出 demo_history.csv  {hist_df.shape}")

    # ---------- 风险统计（供仪表盘） ----------
    r = hist_df["RH_in"].to_numpy()
    stats = {
        "RH_in_mean": round(float(np.mean(r)), 2),
        "RH_in_min": round(float(np.min(r)), 2),
        "RH_in_max": round(float(np.max(r)), 2),
        "frac_gt62": round(float((r > RH_WARN).mean() * 100), 3),
        "frac_gt67": round(float((r > RH_CRIT).mean() * 100), 3),
        "frac_gt75": round(float((r > RH_CLOSE).mean() * 100), 3),
        "n_hours": int(len(r)),
        "period": f"{idx[~tr].min()} ~ {idx[~tr].max()}",
    }
    pd.Series(stats).to_json(RESULTS / "demo_stats.json", force_ascii=False, indent=2)
    print(f"    写出 demo_stats.json  {stats}")


if __name__ == "__main__":
    main()
