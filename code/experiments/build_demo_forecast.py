"""为前端看板预生成演示用预报序列。

为什么要预生成
--------------
前端要展示的是"未来 24/48/72 h 的窟内风险预报"，这需要把**输运算子的多步读出**
跑一遍并落盘，前端只做展示、不做计算。这样前端启动快、且结果可复现、可审计。

读出层的选择（本轮修订）
------------------------
早期版本用**状态式线性 MSE 读出**（``fit_direct`` + ``predict_direct``）。实测三个
演示场景的决策级全为 0：真实峰值 89.0% 的高湿事件只报出 **38.4%**，连 62% 的一级
预警都够不到。``code/results/derisk03_peak.csv`` 已量化根因——MSE 线性读出把极值
**系统性拉向均值**，真实值最高 1% 的样本上只复现真值的 **55.9–59.2%**；换上
**分位数（pinball）读出**后捕捉比提到 **62.0–67.4%**（``derisk03_readout_compare.csv``）。

故本脚本改用**风险对齐的分位数读出**（这正是本作品 L3 层的算法贡献），同时保留
线性 MSE 列作为对照，好让看板如实展示"换读出层带来了多少改善"。

决策阈值（关键口径）
--------------------
窟内 RH 的三级阈值 62 / 67 / 75% 是**物理量**（盐害潮解起始 / 吸湿突变）。
但预报值系统性偏保守，**直接拿预报值去比 62% 永远不会触发**。业务上正确的做法是
把物理阈值**换算成预报值上的判定门限**：

    cut_thr = Quantile(pred_cal, 1 - P(true >= thr))

在**独立标定段**上按基准率标定——本项目所有实验（``derisk02``、``derisk03``）都
是这个口径。本脚本用 **2021 年**作标定段（算子只用 ≤2020 拟合），演示场景取自
2024 / 2025，两者不重叠，**不构成信息泄露**。

同时输出 ``level_raw``（不做标定、直接拿 62/67/75 去比预报值的天真口径）以便对照：
它在本作品上**恒为 0 级**，这个差距本身就是要如实展示的结论，不得隐去。

⚠️ 预报对象是 **physics-derived synthetic** 窟内 RH，不是实测。前端与文档均须标注。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operator.transport import (                        # noqa: E402
    KoopmanTransport, TransportConfig, build_features,
)
from src.physics.cave_model import CaveModel, CaveParams    # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

TRAIN_END = "2020-12-31"          # 算子拟合段（含）
CALIB_YEAR = 2021                 # 决策门限标定段（与演示场景不重叠）
N_HORIZON = 73                    # 0..72 h
HORIZONS = (24, 48, 72)

#: 三级阈值（逐级独立出处，见 docs/02_数据集方案.md §3.5）——物理量，单位 % RH
RH_WARN, RH_CRIT, RH_CLOSE = 62.0, 67.0, 75.0
THRESHOLDS = (("62%(业务预警)", RH_WARN), ("67%(潮解起始)", RH_CRIT),
              ("75%(吸湿突变)", RH_CLOSE))

#: 候选分位数读出；在标定段上按 F1 选，**不用演示场景选**
TAU_GRID = (0.90, 0.95)


def raw_decision(rh: float) -> tuple[int, str]:
    """天真口径：直接拿物理阈值比预报值。"""
    if rh >= RH_CLOSE:
        return 2, "关闭高危洞窟"
    if rh >= RH_CRIT:
        return 1, "限流（控制人数与停留时长）"
    if rh >= RH_WARN:
        return 1, "限流（控制人数与停留时长）"
    return 0, "正常开放"


def cal_decision(v62: float, v67: float, v75: float,
                 cut62: float, cut67: float, cut75: float) -> tuple[int, str]:
    """标定口径：预报值超过在标定段上按基准率定出的门限才报警。"""
    if v75 >= cut75:
        return 2, "关闭高危洞窟"
    if v67 >= cut67:
        return 1, "限流（控制人数与停留时长）"
    if v62 >= cut62:
        return 1, "限流（控制人数与停留时长）"
    return 0, "正常开放"


def main() -> None:
    t0 = time.time()
    outdoor = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                          index_col=0, parse_dates=True).sort_index()
    outdoor = outdoor[~outdoor.index.duplicated(keep="first")]
    idx = outdoor.index

    print("[1] 生成窟内物理合成标签 ...")
    cave = CaveModel(CaveParams()).simulate(outdoor)
    rh_true = cave["RH_in"].to_numpy(dtype=float)

    ts = lambda s: pd.Timestamp(s, tz="UTC")                      # noqa: E731
    tr = np.asarray(outdoor.index <= ts(TRAIN_END))
    ca = np.asarray((outdoor.index > ts(TRAIN_END)) &
                    (outdoor.index <= ts(f"{CALIB_YEAR}-12-31")))

    print(f"[2] 拟合输运算子（训练段 {tr.sum():,} h, ≤{TRAIN_END}）...")
    kt = KoopmanTransport(TransportConfig(ridge_beta=1.0)).fit(
        outdoor[tr], rh_true[tr], fit_koopman=False)

    print("[3] 全序列构造特征（严格因果，供切片使用）...")
    Psi = build_features(outdoor, kt.cfg)
    print(f"    特征维度 p = {Psi.shape[1]}")

    # ---------- 逐时效拟合读出（线性 MSE 对照 + 候选分位数） ----------
    print(f"[4] 逐时效拟合 {N_HORIZON} 个读出权重 ...")
    t1 = time.time()
    w_mse = {h: kt.fit_direct(outdoor[tr], rh_true[tr], h, Psi=Psi[tr])
             for h in range(N_HORIZON)}
    print(f"    线性 MSE       {time.time() - t1:6.1f}s")
    w_q: dict[float, dict[int, np.ndarray]] = {}
    for tau in TAU_GRID:
        t1 = time.time()
        w_q[tau] = {h: kt.fit_direct_quantile(outdoor[tr], rh_true[tr], h, tau=tau,
                                              Psi=Psi[tr])
                    for h in range(N_HORIZON)}
        print(f"    分位数 τ={tau}   {time.time() - t1:6.1f}s")

    # ---------- 在标定段上选 τ，并按基准率标定门限 ----------
    def pred_series(weights: dict[int, np.ndarray], mask: np.ndarray) -> dict[int, np.ndarray]:
        """返回 {h: 在 mask 起点上的预报值}。注意 h 步后的真值窗口可能越出 mask。"""
        Z = kt._add_intercept(kt.transform(Psi[mask]))
        return {h: (Z @ weights[h]).reshape(-1) for h in range(N_HORIZON)}

    pm_ca = pred_series(w_mse, ca)
    pq_ca = {tau: pred_series(w_q[tau], ca) for tau in TAU_GRID}

    def f1_at(pred: dict[int, np.ndarray], cuts: dict[int, float]) -> float:
        """标定段上的 F1（62% 档，各时效合并）。"""
        tp = fp = fn = 0
        for h in HORIZONS:
            true_h = rh_true[ca][h:]
            n = len(true_h)
            a = true_h >= RH_WARN
            b = pred[h][:n] >= cuts[h]
            tp += int((a & b).sum()); fp += int((~a & b).sum()); fn += int((a & ~b).sum())
        pr = tp / (tp + fp) if tp + fp else 0.0
        rc = tp / (tp + fn) if tp + fn else 0.0
        return 2 * pr * rc / (pr + rc) if pr + rc else 0.0

    print(f"[5] 在标定段 {CALIB_YEAR} 上选分位数 τ（判据 = 62% 档 F1，各时效合并，"
          f"门限按基准率标定）...")
    cands = {"线性 MSE（对照）": pm_ca, **{f"分位数 τ={t}": pq_ca[t] for t in TAU_GRID}}
    cuts_by_cand: dict[str, dict[int, float]] = {}
    for name, pred in cands.items():
        cuts_by_cand[name] = {}
        for h in HORIZONS:
            true_h = rh_true[ca][h:]
            base = float((true_h >= RH_WARN).mean())
            cuts_by_cand[name][h] = (float(np.quantile(pred[h][:len(true_h)], 1 - base))
                                     if base > 0 else RH_WARN)
    f1s = {name: f1_at(pred, cuts_by_cand[name]) for name, pred in cands.items()}
    for name, v in sorted(f1s.items(), key=lambda kv: -kv[1]):
        print(f"      {name:<18} 标定段 F1@62% = {v:.4f}")
    best = max(f1s, key=lambda k: f1s[k])
    print(f"    → 选用 **{best}**（若并列取第一个）。注意：τ 的选择只用标定段，"
          f"未看演示场景。")

    # 最终读出的逐时效门限：三个阈值各一套
    final_pred_ca = cands[best]
    cuts: dict[str, dict[int, float]] = {}
    for tname, thr in THRESHOLDS:
        cuts[tname] = {}
        for h in range(N_HORIZON):
            true_h = rh_true[ca][h:]
            base = float((true_h >= thr).mean())
            v = final_pred_ca[h][:len(true_h)]
            cuts[tname][h] = float(np.quantile(v, 1 - base)) if base > 0 else thr
    for tname, thr in THRESHOLDS:
        print(f"      门限 {tname}: h=24 → {cuts[tname][24]:.2f}, "
              f"h=48 → {cuts[tname][48]:.2f}, h=72 → {cuts[tname][72]:.2f}")

    pd.DataFrame([{"threshold": tn, "horizon_h": h, "cut_on_pred": round(cuts[tn][h], 4)}
                  for tn, _ in THRESHOLDS for h in range(N_HORIZON)]
                 ).to_csv(RESULTS / "demo_calibration.csv", index=False)

    # ---------- 挑演示起点：按**未来 72 h 内**的窟内 RH 挑，而不是按起点时刻挑 ----------
    te_pos = np.where(~tr & ~ca)[0]
    te_pos = te_pos[(te_pos > 168) & (te_pos < len(idx) - 200)]
    fut_max = np.array([rh_true[p:p + N_HORIZON].max() for p in te_pos])
    picks = []
    for q, label in ((0.9999, "高湿事件"), (0.98, "偏高湿"), (0.50, "平稳期")):
        target = np.quantile(fut_max, q)
        j = int(np.argmin(np.abs(fut_max - target)))
        picks.append((int(te_pos[j]), label, q))
    print("\n[6] 演示起点（选在事件之前，按未来 72 h 内最大窟内 RH 的分位数挑）：")
    for p, lab, _ in picks:
        print(f"      {lab:<6} 起点 {idx[p]}   未来 72 h 真实峰值 "
              f"{rh_true[p:p + N_HORIZON].max():.2f}%")

    # ---------- 逐起点生成 72 h 预报 ----------
    rows = []
    for pos, label, _ in picks:
        z1 = kt._add_intercept(kt.transform(Psi[pos:pos + 1]))
        z1m = None
        for h in range(N_HORIZON):
            tgt = pos + h
            if tgt >= len(idx):
                break
            pred = float(np.asarray(z1 @ w_q[TAU_GRID[0]][h]).reshape(-1)[0])
            pred_best = float(np.asarray(z1 @ (
                w_q[float(best.split("=")[1])] if "分位数" in best else w_mse
            )[h]).reshape(-1)[0])
            pred_mse = float(np.asarray(z1 @ w_mse[h]).reshape(-1)[0])
            truth = float(rh_true[tgt])
            lvl_raw, adv_raw = raw_decision(pred_best)
            lvl, adv = cal_decision(
                pred_best, pred_best, pred_best,
                cuts["62%(业务预警)"][h], cuts["67%(潮解起始)"][h],
                cuts["75%(吸湿突变)"][h])
            rows.append({
                "origin": str(idx[pos]),
                "scenario": label,
                "step_h": h,
                "time": str(idx[tgt]),
                "RH_pred": round(pred_best, 3),          # 主读出（风险对齐）
                "RH_pred_lin": round(pred_mse, 3),       # 线性 MSE 对照
                "RH_pred_tau90": round(pred, 3),         # τ=0.90 对照
                "RH_true": round(truth, 3),
                "level": lvl,                            # 标定口径（业务用）
                "advice": adv,
                "level_raw": lvl_raw,                    # 天真口径（对照，恒 0）
                "advice_raw": adv_raw,
                "cut_62": round(cuts["62%(业务预警)"][h], 3),
                "cut_67": round(cuts["67%(潮解起始)"][h], 3),
                "cut_75": round(cuts["75%(吸湿突变)"][h], 3),
                "T_out": round(float(outdoor["T2M"].iloc[tgt]), 2),
                "RH_out": round(float(outdoor["RH2M"].iloc[tgt]), 2),
                "Q_m3h": round(float(cave["Q_m3h"].iloc[tgt]), 1),
            })

    df_fc = pd.DataFrame(rows)
    df_fc.to_csv(RESULTS / "demo_forecast.csv", index=False)
    print(f"\n[7] 写出 demo_forecast.csv  {df_fc.shape}")

    summ = []
    for (lab, org), s in df_fc.groupby(["scenario", "origin"], sort=False):
        nz = s[s.level > 0]
        summ.append({
            "scenario": lab, "origin": org,
            "pred_peak": round(float(s.RH_pred.max()), 2),
            "pred_peak_lin": round(float(s.RH_pred_lin.max()), 2),
            "true_peak": round(float(s.RH_true.max()), 2),
            "level": int(s.level.max()), "level_raw": int(s.level_raw.max()),
            "n_warn": int(len(nz)),
            "first_warn_h": int(nz.step_h.min()) if len(nz) else -1,
        })
    print(pd.DataFrame(summ).to_string(index=False))

    # ---------- 历史序列（离线回放用）：2022 年起，逐时 ----------
    m_hist = np.asarray(outdoor.index > ts(f"{CALIB_YEAR}-12-31"))
    hist_df = pd.DataFrame({
        "time": idx[m_hist].astype(str),
        "T_out": outdoor["T2M"][m_hist].round(2).to_numpy(),
        "RH_out": outdoor["RH2M"][m_hist].round(2).to_numpy(),
        "T_in": cave["T_in"][m_hist].round(2).to_numpy(),
        "RH_in": cave["RH_in"][m_hist].round(2).to_numpy(),
        "Q_m3h": cave["Q_m3h"][m_hist].round(1).to_numpy(),
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
        "period": f"{idx[m_hist].min()} ~ {idx[m_hist].max()}",
        "readout": best,
        "calib_year": CALIB_YEAR,
        "tau_grid": list(TAU_GRID),
        "calib_f1_62": {k: round(v, 4) for k, v in f1s.items()},
    }
    pd.Series(stats).to_json(RESULTS / "demo_stats.json", force_ascii=False, indent=2)
    print(f"    写出 demo_stats.json  readout={best}  period={stats['period']}")
    print(f"\n总用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
