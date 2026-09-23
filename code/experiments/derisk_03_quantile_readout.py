"""解风险实验 03：读出层的极值压缩问题，与分位数读出修复。

背景（一个必须写进报告的诊断）
------------------------------
实验 02 与前端演示暴露出一个严重问题：**MSE 拟合的线性读出层会把极值系统性拉向均值**。

实测证据（2024-04-16 起 72 h 的一个"高湿事件"场景，真实窟内 RH 升到 89.0%）：

============================  =========================
方法                           h=72 预报（落盘出处）
============================  =========================
状态式 MSE 读出（旧）          34.6%（demo_forecast.csv 终点值）
轨迹式 MSE 读出（完美外场）     55.0%（derisk03_peak.csv 整体口径）
真值                           89.0%（demo_stats.json RH_in_max）
============================  =========================

.. note::
   上表的 34.6% 是**该场景 72 h 窗口终点的单点预报值**（step_h=72）；
   同一场景 0–72 h 窗口内的**最大**预报值是 38.4%（step_h=66），
   答辩 PPT 与演示面板引用的是后者（"最高只报出 38.4%"）。
   两个数都对，但指向不同统计量，不可混用。

**后果**：62% 的业务阈值在极值场景下够不到 → **用绝对阈值判级的三级决策完全失效**。
根因是回归到均值：在均方误差意义下，把尾部压平几乎不损失什么。

一个重要的架构澄清
------------------
"轨迹式读出"（把 t→t+h 的外场轨迹喂进算子）**与时效 h 无关**——
要预报 s 时刻的窟内值，就用 s 时刻的外场特征，这正是**同时刻（nowcast）读出**。
所以：

* ``L1 室外预报`` 的作用是提供 s 时刻的外场值；
* ``L2 算子`` 就是那个**与时效无关的 nowcast 读出**，在每个未来时刻各应用一次。

三种读出
--------
1. ``state-MSE``：只用 t 时刻及之前的外场，一次性预报 t+h（**旧口径**）
2. ``traj-MSE``：在 t+h 处用真实外场做 nowcast = **完美气象预报上界**
3. ``traj-Quantile(τ=0.9)``：同上，但读出层改为**分位数（pinball）回归** ← 本作品修复

``state`` → ``traj`` 的差距 = **L1 室外预报的价值**（不给未来外场就抓不到快变过程）；
``traj-MSE`` → ``traj-Quantile`` 的差距 = **风险对齐读出的价值**（条件均值 → 条件分位数）。

⚠️ ``traj-*`` 用真实未来外场，是**上界**而非可部署性能；部署时未来外场来自 L1 预报。
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

RESULTS = ROOT / "results"
TRAIN_END = "2019-12-31"
VAL_END = "2020-12-31"
HORIZONS = (24, 48, 72)
RH_WARN, RH_CRIT, RH_CLOSE = 62.0, 67.0, 75.0
THRESHOLDS = {"62%(业务预警)": RH_WARN, "67%(潮解起始)": RH_CRIT,
              "75%(吸湿突变)": RH_CLOSE}
TAU_UP = 0.9
BETA = 1.0


def reg(y, p) -> dict:
    ok = np.isfinite(y) & np.isfinite(p)
    yt, pp = y[ok], p[ok]
    r = pp - yt
    ss = float(((yt - yt.mean()) ** 2).sum())
    return {"RMSE": round(float(np.sqrt((r ** 2).mean())), 3),
            "R2": round(1 - float((r ** 2).sum()) / ss, 4) if ss > 0 else np.nan,
            "bias": round(float(r.mean()), 3),
            "p95_pred": round(float(np.percentile(pp, 95)), 2),
            "max_true": round(float(yt.max()), 2)}


def events(y, p, thr, cut) -> dict:
    from sklearn.metrics import roc_auc_score
    ok = np.isfinite(y) & np.isfinite(p)
    yt, pp = y[ok], p[ok]
    a = yt >= thr
    b = pp >= cut
    tp = int((a & b).sum()); fp = int((~a & b).sum()); fn = int((a & ~b).sum())
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
    try:
        auc = float(roc_auc_score(a.astype(int), pp)) if a.any() and (~a).any() else np.nan
    except Exception:  # noqa: BLE001
        auc = np.nan
    return {"base_rate": round(float(a.mean()), 4),
            "alarm_rate": round(float(b.mean()), 4),
            "precision": round(pr, 4), "recall": round(rc, 4),
            "F1": round(f1, 4),
            "AUC": round(auc, 4) if np.isfinite(auc) else np.nan}


def peak_capture(y, p, q: float = 0.99) -> dict:
    """**极值捕捉能力**：真实值最高的 1% 样本上，预报均值 / 真实均值。

    这是"预警能不能用"的直接度量——点精度指标（R²/RMSE）对它是盲的。
    """
    ok = np.isfinite(y) & np.isfinite(p)
    yt, pp = y[ok], p[ok]
    if len(yt) == 0:
        return {}
    m = yt >= np.quantile(yt, q)
    if m.sum() == 0:
        return {}
    return {"peak_n": int(m.sum()),
            "peak_true_mean": round(float(yt[m].mean()), 3),
            "peak_pred_mean": round(float(pp[m].mean()), 3),
            "peak_ratio": round(float(pp[m].mean() / yt[m].mean()), 4)}


def main() -> None:
    t0 = time.time()
    print("=" * 88)
    print("解风险实验 03：读出层的极值压缩与分位数读出修复")
    print("=" * 88)

    od = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                     index_col=0, parse_dates=True).sort_index()
    od = od[~od.index.duplicated(keep="first")]
    cave = CaveModel(CaveParams()).simulate(od)
    y = cave["RH_in"].to_numpy(dtype=float)

    tr = np.asarray(od.index <= pd.Timestamp(TRAIN_END, tz="UTC"))
    va = np.asarray((od.index > pd.Timestamp(TRAIN_END, tz="UTC")) &
                    (od.index <= pd.Timestamp(VAL_END, tz="UTC")))
    te = np.asarray(od.index > pd.Timestamp(VAL_END, tz="UTC"))
    print(f"\n切分  训练 {tr.sum():,} / 验证 {va.sum():,} / 测试 {te.sum():,}")

    print("\n[1] 闭式拟合算子（训练段）...")
    kt = KoopmanTransport(TransportConfig(ridge_beta=BETA)).fit(
        od[tr], y[tr], fit_koopman=False)
    print(f"    特征维度 p = {kt.n_features_in_}")

    print("[2] 构建全序列特征（一次，轨迹式读出直接取 t+h 行）...")
    Psi = build_features(od, kt.cfg)
    Zall = kt._add_intercept(kt.transform(Psi))

    # --- 轨迹式读出 = nowcast 读出，与时效无关 ---
    w_traj = kt.w_                                   # MSE（条件均值）
    print("[3] IRLS 拟合分位数 nowcast 读出 tau=%.2f ..." % TAU_UP)
    w_qtl = kt.fit_direct_quantile(od[tr], y[tr], 0, tau=TAU_UP)

    # --- 状态式读出（旧口径）：每个时效单独拟合 ---
    print("[4] 拟合状态式 MSE 读出（每个时效一个）...")
    w_state = {h: kt.fit_direct(od[tr], y[tr], h) for h in HORIZONS}

    rows, ev_rows, pk_rows = [], [], []
    for h in HORIZONS:
        n = int(te.sum()) - h
        yt = y[te][h:]
        preds = {
            "state-MSE（旧口径）": kt.predict_direct(od[te], w_state[h])[:n],
            "traj-MSE（完美外场）": Zall[te] @ w_traj,
            f"traj-Quantile(tau={TAU_UP})": Zall[te] @ w_qtl,
        }
        preds = {k: v[:n] for k, v in preds.items()}

        # 验证段标定决策阈值（无信息泄露）
        Zva = kt._add_intercept(kt.transform(build_features(od[va], kt.cfg)))
        vpreds = {
            "state-MSE（旧口径）": kt.predict_direct(od[va], w_state[h]),
            "traj-MSE（完美外场）": Zva @ w_traj,
            f"traj-Quantile(tau={TAU_UP})": Zva @ w_qtl,
        }
        y_va = y[va]
        cuts = {}
        for tn, thr in THRESHOLDS.items():
            base = float((y_va[h:] >= thr).mean())
            for name, vp in vpreds.items():
                vv = vp[: len(y_va) - h]
                cuts[f"{tn}|{name}"] = (float(np.quantile(vv, 1 - base))
                                        if base > 0 else thr)

        print(f"\n{'=' * 88}\n时效 h = {h} h\n{'=' * 88}")
        print(pd.DataFrame([{"model": k, **reg(yt, v)} for k, v in preds.items()]
                           ).to_string(index=False))
        for k, v in preds.items():
            rows.append({"horizon_h": h, "model": k, **reg(yt, v)})
            pk = peak_capture(yt, v)
            if pk:
                pk_rows.append({"horizon_h": h, "model": k, **pk})
            for tn, thr in THRESHOLDS.items():
                ev_rows.append({"horizon_h": h, "threshold": tn, "model": k,
                                **events(yt, v, thr, cuts[f"{tn}|{k}"])})

    pd.DataFrame(rows).to_csv(RESULTS / "derisk03_accuracy.csv", index=False)
    pd.DataFrame(ev_rows).to_csv(RESULTS / "derisk03_events.csv", index=False)
    pd.DataFrame(pk_rows).to_csv(RESULTS / "derisk03_peak.csv", index=False)

    print(f"\n{'=' * 88}\n极值捕捉比（真实值最高 1% 的样本：预报均值 / 真实均值）\n{'=' * 88}")
    print(pd.DataFrame(pk_rows).pivot_table(index="model", columns="horizon_h",
                                            values="peak_ratio").round(3).to_string())

    df_ev = pd.DataFrame(ev_rows)
    for metric in ("F1", "AUC"):
        print(f"\n{'=' * 88}\n事件检测 {metric}（62% 阈值，决策阈值验证段标定）\n{'=' * 88}")
        print(df_ev[df_ev.threshold.str.startswith("62")]
              .pivot_table(index="model", columns="horizon_h", values=metric)
              .round(3).to_string())

    print(f"\n总用时 {time.time() - t0:.1f}s  结果写入 results/derisk03_*.csv")


if __name__ == "__main__":
    main()
