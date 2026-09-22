"""快速测试：把线性读出换成非线性读出，能否修复"极值被压缩"。

问题
----
实验 03 实测：所有线性读出的**极值捕捉比只有 0.55~0.67**
（真实值最高 1% 的样本，预报均值只有真实的 55~67%）。
后果：62% 业务阈值够不到，**用绝对阈值判级的三级决策失效**。

根因：线性 MSE 读出把极值拉向均值。

本测试：Koopman 特征不变，只把**读出层**从岭回归换成梯度提升树（HistGradientBoosting），
看极值捕捉与事件指标是否改善。

⚠️ 若非线性读出明显更好，则说明"物理代理"价值在**特征**而非线性读出本身——
这是一个需要在报告中如实说明的架构结论。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operator.transport import KoopmanTransport, TransportConfig, build_features  # noqa: E402
from src.physics.cave_model import CaveModel, CaveParams                              # noqa: E402

TRAIN_END, VAL_END = "2019-12-31", "2020-12-31"
HORIZONS = (24, 48, 72)
THRESHOLDS = {"62%": 62.0, "67%": 67.0, "75%": 75.0}


def peak_ratio(y, p, q=0.99):
    ok = np.isfinite(y) & np.isfinite(p)
    yt, pp = y[ok], p[ok]
    m = yt >= np.quantile(yt, q)
    return round(float(pp[m].mean() / yt[m].mean()), 4) if m.sum() else np.nan


def auc_f1(y, p, thr, cut):
    from sklearn.metrics import roc_auc_score
    a, b = y >= thr, p >= cut
    tp = int((a & b).sum()); fp = int((~a & b).sum()); fn = int((a & ~b).sum())
    pr = tp / (tp + fp) if tp + fp else 0.0
    rc = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * pr * rc / (pr + rc) if pr + rc else 0.0
    try:
        auc = float(roc_auc_score(a.astype(int), p)) if a.any() and (~a).any() else np.nan
    except Exception:  # noqa: BLE001
        auc = np.nan
    return round(auc, 4), round(f1, 4)


def main() -> None:
    from sklearn.ensemble import HistGradientBoostingRegressor

    od = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                     index_col=0, parse_dates=True).sort_index()
    od = od[~od.index.duplicated(keep="first")]
    y = CaveModel(CaveParams()).simulate(od)["RH_in"].to_numpy(float)

    tr = np.asarray(od.index <= pd.Timestamp(TRAIN_END, tz="UTC"))
    va = np.asarray((od.index > pd.Timestamp(TRAIN_END, tz="UTC")) &
                    (od.index <= pd.Timestamp(VAL_END, tz="UTC")))
    te = np.asarray(od.index > pd.Timestamp(VAL_END, tz="UTC"))

    kt = KoopmanTransport(TransportConfig(ridge_beta=1.0)).fit(od[tr], y[tr],
                                                               fit_koopman=False)
    Psi = build_features(od, kt.cfg).astype(np.float32)
    print(f"特征维度 p = {Psi.shape[1]}")

    rows = []
    for h in HORIZONS:
        y_h = np.full_like(y, np.nan)
        y_h[:-h] = y[h:]
        ok = np.isfinite(y_h)

        # ---- 线性（状态式，与主力实验同口径）----
        w_lin = kt.fit_direct(od[tr], y[tr], h)
        p_lin = kt.predict_direct(od[te], w_lin)[: int(te.sum()) - h]

        # ---- 非线性：GBDT 直接在同一批 Koopman 特征上做多步回归 ----
        m_tr = ok & tr
        m_va = ok & va
        m_te = ok & te
        gb = HistGradientBoostingRegressor(
            max_iter=300, learning_rate=0.08, max_depth=6,
            early_stopping=True, validation_fraction=0.1, random_state=0)
        gb.fit(Psi[m_tr], y_h[m_tr])
        p_gb = gb.predict(Psi[te][: int(te.sum()) - h])

        yt = y[te][h:]
        y_va_h = y[va][h:]
        p_lin_va = kt.predict_direct(od[va], w_lin)[: len(y_va_h)]
        p_gb_va = gb.predict(Psi[va][: len(y_va_h)])

        for name, p, pv in (("线性岭回归", p_lin, p_lin_va),
                            ("GBDT 非线性", p_gb, p_gb_va)):
            r = p - yt
            row = {"h": h, "readout": name,
                   "RMSE": round(float(np.sqrt((r ** 2).mean())), 3),
                   "peak_ratio": peak_ratio(yt, p)}
            for tn, thr in THRESHOLDS.items():
                base = float((y_va_h >= thr).mean())
                cut = float(np.quantile(pv, 1 - base)) if base > 0 else thr
                a, f = auc_f1(yt, p, thr, cut)
                row[f"AUC_{tn}"] = a
                row[f"F1_{tn}"] = f
            rows.append(row)

    df = pd.DataFrame(rows)
    print(df.to_string(index=False))
    df.to_csv(ROOT / "results" / "derisk03_readout_compare.csv", index=False)
    print("\n已写入 results/derisk03_readout_compare.csv")

    print("\n极值捕捉比（越接近 1 越好）：")
    print(df.pivot_table(index="readout", columns="h", values="peak_ratio").round(3).to_string())
    print("\n事件 AUC @62%：")
    print(df.pivot_table(index="readout", columns="h", values="AUC_62%").round(3).to_string())
    print("\n事件 F1 @62%：")
    print(df.pivot_table(index="readout", columns="h", values="F1_62%").round(3).to_string())


if __name__ == "__main__":
    main()
