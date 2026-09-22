"""解风险实验 01：输运算子能否从室外延迟坐标重建窟内微环境？

这是整个技术路线的**关键路径验证**。若本实验失败，则"算子导出的内生风险权重"
不成立，技术路线需重做。若成立，则算法主张的三层链条全部打通。

本脚本回答四个问题
------------------
Q1 **可重建性**：闭式延迟嵌入算子能否从室外气象重建窟内 RH？
Q2 **物理性**：算子谱给出的时间常数是否落在文献报导的物理区间？
Q3 **结构性**：物理动机的特征（多尺度慢变项、Magnus 耦合项）是否真的有贡献，
   还是随便加延迟项就够了？（对应消融）
Q4 **相对优势**：相比初稿所用的"文献标定一阶传递函数"与常规回归基线，
   算子是否显著更优？（这是"应用成效"分值的直接来源）

产出：``results/derisk01_*.csv`` 与终端报告。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data import power as power_mod              # noqa: E402
from src.operator.transport import (                 # noqa: E402
    KoopmanTransport,
    TransportConfig,
    build_features,
)
from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

TRAIN_END = "2020-12-31"

#: 三级湿度阈值，每一级都有独立出处（见 docs/ 与 cave_model.PARAM_SOURCES）：
#:   62% —— 敦煌研究院官方业务阈值（樊锦诗 2013 / 郭青林 2026 / 汪万福 公开表述：
#:          "空气湿度一旦超过 62%，就可能加速壁画地仗层中的盐分潮解"），
#:          配套 CO2 预警阈值 1500 ppm。这是**业务口径**，用于"限流"触发。
#:   67% —— 可溶盐潮解起始（Demas et al. 2015, Springer，经 Gong et al. 2025 转述）。
#:   75% —— 莫高窟含盐地仗吸湿与渗透性突变点（npj Heritage Science 2025,
#:          DOI 10.1038/s40494-025-01756-1），原文建议"ambient RH should be
#:          maintained below 75%"。用于"关闭"触发。
RH_WARN = 62.0
RH_CRIT = 67.0
RH_CLOSE = 75.0


# --------------------------------------------------------------------------
# 评价指标
# --------------------------------------------------------------------------


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    resid = yp - yt
    ss_res = float((resid**2).sum())
    ss_tot = float(((yt - yt.mean()) ** 2).sum())
    return {
        "RMSE": round(float(np.sqrt((resid**2).mean())), 4),
        "MAE": round(float(np.abs(resid).mean()), 4),
        "R2": round(1.0 - ss_res / ss_tot, 5),
        "bias": round(float(resid.mean()), 4),
    }


def exceedance_metrics(y_true: np.ndarray, y_pred: np.ndarray, threshold: float) -> dict:
    """超阈值事件检测指标 —— 对应"盐害风险预警"的业务评价。"""
    from sklearn.metrics import roc_auc_score

    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    a = yt >= threshold
    b = yp >= threshold

    tp = int((a & b).sum())
    fp = int((~a & b).sum())
    fn = int((a & ~b).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    try:
        auc = float(roc_auc_score(a.astype(int), yp)) if a.any() and (~a).any() else np.nan
    except Exception:  # noqa: BLE001
        auc = np.nan

    return {
        "threshold": threshold,
        "base_rate": round(float(a.mean()), 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "F1": round(f1, 4),
        "AUC": round(auc, 4) if np.isfinite(auc) else np.nan,
        "n_pos": int(a.sum()),
    }


def exceedance_duration_error(y_true: np.ndarray, y_pred: np.ndarray,
                              threshold: float, block_h: int = 24) -> dict:
    """**超阈值持续时间**的误差 —— 这是本作品真正的业务指标。

    把序列切成 ``block_h`` 小时的块，比较每块内"超阈小时数"的误差。
    MSE 最优的模型在这个指标上未必最优，这正是"目标函数错配"的量化证据。
    """
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    n = (len(yt) // block_h) * block_h
    if n == 0:
        return {}
    a = (yt[:n] >= threshold).reshape(-1, block_h).sum(axis=1)
    b = (yp[:n] >= threshold).reshape(-1, block_h).sum(axis=1)
    err = b - a
    return {
        "threshold": threshold,
        "duration_MAE_h": round(float(np.abs(err).mean()), 4),
        "duration_bias_h": round(float(err.mean()), 4),
        "duration_RMSE_h": round(float(np.sqrt((err**2).mean())), 4),
    }


# --------------------------------------------------------------------------
# 基线模型
# --------------------------------------------------------------------------


class FirstOrderTransfer:
    """初稿所用的"文献标定一阶热湿传递函数"。

    初稿原文形式是**静态查表传递**：:math:`RH_{in}(t) = a\\,RH_{out}(t-\\Delta) + b`，
    系数 a 与滞后 Δ 由文献摘录的衰减比与滞后量给出。这里把它写成同一形式、
    只把系数换成最小二乘拟合（对初稿更有利），作为"初稿路线"的对照。

    **不含自回归项是有意的**。早期版本把它写成 :math:`y_t = a y_{t-1} + b x_t + c`
    再对整段测试序列递归推演，拟合出的 a ≈ 1.0009 略大于 1，几百步后即数值
    爆炸（R² = -3.3e22）。那只说明"递归写法本身不稳定"，**不能**用来论证
    初稿的传递函数不行——那是稻草人对照。两种口径都保留：

    * :meth:`predict` —— 静态传递（初稿原文形式，**结论以它为准**）；
    * :meth:`predict_recursive` —— 旧口径，**仅作误差累积的定性说明**。
    """

    def __init__(self, lag_h: int = 3):
        self.lag_h = lag_h
        self.coef_: np.ndarray | None = None
        self.coef_rec_: np.ndarray | None = None

    @staticmethod
    def _lagged(x: np.ndarray, lag: int) -> np.ndarray:
        xl = np.roll(x, lag)
        xl[: lag] = x[: lag]
        return xl

    def fit(self, x: np.ndarray, y: np.ndarray) -> "FirstOrderTransfer":
        xl = self._lagged(x, self.lag_h)
        A = np.column_stack([xl, np.ones(len(y))])
        self.coef_, *_ = np.linalg.lstsq(A, y, rcond=None)
        Arc = np.column_stack([y[:-1], xl[1:], np.ones(len(y) - 1)])
        self.coef_rec_, *_ = np.linalg.lstsq(Arc, y[1:], rcond=None)
        return self

    @property
    def pole(self) -> float:
        """旧（递归）口径的自回归极点 a；|a| >= 1 时递归推演必然发散。"""
        return float(self.coef_rec_[0])

    def predict(self, x: np.ndarray) -> np.ndarray:
        """静态传递 :math:`a\\,x(t-\\Delta) + b`（初稿原文形式，可部署）。"""
        a, b = self.coef_
        return a * self._lagged(x, self.lag_h) + b

    def predict_recursive(self, x: np.ndarray, y0: float) -> np.ndarray:
        """旧口径 :math:`y_t = a y_{t-1} + b x_{t-\\tau} + c` 递归推演（不稳定，仅对照）。"""
        a, b, c = self.coef_rec_
        xl = self._lagged(x, self.lag_h)
        out = np.empty(len(x))
        out[0] = y0
        for t in range(1, len(x)):
            out[t] = a * out[t - 1] + b * xl[t] + c
        return out


class RidgeDirect:
    """无延迟嵌入的直接岭回归（只用当前时刻室外要素）。"""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.mu_ = self.sigma_ = self.coef_ = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "RidgeDirect":
        self.mu_ = X.mean(axis=0)
        self.sigma_ = X.std(axis=0)
        self.sigma_[self.sigma_ < 1e-12] = 1.0
        Z = (X - self.mu_) / self.sigma_
        Z = np.column_stack([Z, np.ones(len(Z))])
        p = Z.shape[1]
        self.coef_ = np.linalg.solve(Z.T @ Z + self.alpha * np.eye(p), Z.T @ y)
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        Z = (X - self.mu_) / self.sigma_
        Z = np.column_stack([Z, np.ones(len(Z))])
        return Z @ self.coef_


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def main() -> None:
    t0 = time.time()
    print("=" * 78)
    print("解风险实验 01：延迟嵌入输运算子重建窟内微环境")
    print("=" * 78)

    # ---------- 1. 载入外场数据 ----------
    interim = ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
    if not interim.exists():
        print(f"[ERROR] 未找到 {interim}，请先运行 src/data/power.py")
        sys.exit(1)

    outdoor = pd.read_csv(interim, index_col=0, parse_dates=True)
    outdoor = outdoor[~outdoor.index.duplicated(keep="first")].sort_index()
    print(f"\n[1] 外场数据 {outdoor.shape[0]:,} 行 x {outdoor.shape[1]} 要素")
    print(f"    时间范围 {outdoor.index.min()} -> {outdoor.index.max()}")

    # ---------- 2. 物理模型生成窟内合成标签 ----------
    print("\n[2] 运行窟内热湿耦合模型（文献参数化）...")
    t1 = time.time()
    params = CaveParams()
    cave = CaveModel(params).simulate(outdoor)
    print(f"    完成，用时 {time.time() - t1:.1f}s")
    print(f"    窟内 T  : mean {cave['T_in'].mean():6.2f}  std {cave['T_in'].std():5.2f}  "
          f"range [{cave['T_in'].min():6.2f}, {cave['T_in'].max():6.2f}] degC")
    print(f"    窟内 RH : mean {cave['RH_in'].mean():6.2f}  std {cave['RH_in'].std():5.2f}  "
          f"range [{cave['RH_in'].min():6.2f}, {cave['RH_in'].max():6.2f}] %")
    print(f"    窟外 T  : mean {outdoor['T2M'].mean():6.2f}  "
          f"range [{outdoor['T2M'].min():6.2f}, {outdoor['T2M'].max():6.2f}] degC")
    print(f"    窟外 RH : mean {outdoor['RH2M'].mean():6.2f}  "
          f"range [{outdoor['RH2M'].min():6.2f}, {outdoor['RH2M'].max():6.2f}] %")
    print(f"    超阈占比: RH>67% -> {(cave['RH_in'] > RH_CRIT).mean():.4f}   "
          f"RH>75% -> {(cave['RH_in'] > RH_CLOSE).mean():.4f}")

    cave.to_csv(ROOT / "data" / "interim" / "cave_synthetic_2001_2025.csv")

    # ---------- 3. 时序切分 ----------
    tr = outdoor.index <= pd.Timestamp(TRAIN_END, tz="UTC")
    te = ~tr
    print(f"\n[3] 时序切分  训练 {tr.sum():,} h / 测试 {te.sum():,} h（无重叠，模拟真实部署）")

    y = cave["RH_in"].to_numpy(dtype=float)
    y_tr, y_te = y[tr], y[te]

    results: list[dict] = []
    preds: dict[str, np.ndarray] = {}

    # ---------- 4. 基线 ----------
    print("\n[4] 基线模型")

    # 4a. 持续性预报（persistence）
    pred_persist = np.concatenate([[y_tr[-1]], y_te[:-1]])
    m = regression_metrics(y_te, pred_persist)
    results.append({"model": "Persistence", **m})
    preds["Persistence"] = pred_persist
    print(f"    Persistence            R2={m['R2']:+.4f}  RMSE={m['RMSE']:.4f}")

    # 4b. 初稿方案：文献标定一阶传递函数（以窟外 RH 为输入，滞后 3 h）
    #     这是**初稿原文形式**（静态传递，无自回归），也是对初稿最公道的实现口径。
    fot = FirstOrderTransfer(lag_h=3).fit(outdoor.loc[tr, "RH2M"].to_numpy(), y_tr)
    pred_fot = fot.predict(outdoor.loc[te, "RH2M"].to_numpy())
    m = regression_metrics(y_te, pred_fot)
    results.append({"model": "FirstOrderTransfer(初稿方案)", **m})
    preds["FirstOrderTransfer(初稿方案)"] = pred_fot
    print(f"    FirstOrderTransfer     R2={m['R2']:+.4f}  RMSE={m['RMSE']:.4f}   <- 初稿路线")

    # 4b'. 旧口径（自回归 + 单初值递归推演）仅作对照：极点 |a|>=1 时必然数值爆炸。
    pred_fot_rec = fot.predict_recursive(outdoor.loc[te, "RH2M"].to_numpy(), y_tr[-1])
    m_rec = regression_metrics(y_te, pred_fot_rec)
    results.append({"model": "FirstOrderTransfer-递归推演(旧口径)", **m_rec})
    print(f"    FOT-递归推演(旧口径)   R2={m_rec['R2']:+.4e}  "
          f"极点 a={fot.pole:.6f} > 1 -> 必发散，不作为性能对照")

    # 4c. 无延迟嵌入的直接岭回归
    drivers = [c for c in ["T2M", "RH2M", "WS10M", "PSC", "ALLSKY_SFC_SW_DWN"]
               if c in outdoor.columns]
    rd = RidgeDirect().fit(outdoor.loc[tr, drivers].to_numpy(), y_tr)
    pred_rd = rd.predict(outdoor.loc[te, drivers].to_numpy())
    m = regression_metrics(y_te, pred_rd)
    results.append({"model": "RidgeDirect(仅当前时刻)", **m})
    print(f"    RidgeDirect            R2={m['R2']:+.4f}  RMSE={m['RMSE']:.4f}")

    # ---------- 5. 输运算子 + 消融 ----------
    print("\n[5] 输运算子与消融")

    configs = {
        "Operator-Full(本作品)": TransportConfig(),
        "Ablation-无慢变项": TransportConfig(use_slow=False),
        "Ablation-无Magnus项": TransportConfig(use_magnus=False),
        "Ablation-仅快变延迟": TransportConfig(use_slow=False, use_magnus=False),
        "Ablation-短延迟(12h)": TransportConfig(n_fast_lags=12),
    }

    models: dict[str, KoopmanTransport] = {}

    for name, cfg in configs.items():
        t = time.time()
        # 特征矩阵在**全序列**上构造一次再按时间切片：慢变窗口最长 8760 h，
        # 若分别在训练段/测试段切片上构造，测试段前一年的慢变特征会在切片
        # 起点重启，训练与测试的特征分布不一致。
        Psi = build_features(outdoor, cfg)
        kt = KoopmanTransport(cfg).fit(outdoor[tr], y_tr,
                                       fit_koopman=(name.startswith("Operator-Full")),
                                       Psi=Psi[tr])
        pred = kt.predict(outdoor[te], Psi=Psi[te])
        preds[name] = pred
        models[name] = kt
        m = regression_metrics(y_te, pred)
        m["n_features"] = len(kt.feature_names_)
        m["fit_seconds"] = round(time.time() - t, 2)
        results.append({"model": name, **m})
        print(f"    {name:<26} R2={m['R2']:+.4f}  RMSE={m['RMSE']:.4f}  "
              f"p={m['n_features']:>4}  {m['fit_seconds']:.2f}s")

    # ---------- 6. 结果汇总 ----------
    df_res = pd.DataFrame(results)
    df_res.to_csv(RESULTS / "derisk01_model_comparison.csv", index=False)

    best = "Operator-Full(本作品)"
    print("\n" + "=" * 78)
    print("[6] 超阈值事件检测（业务指标）")
    print("=" * 78)
    ex_rows = []
    for thr in (RH_WARN, RH_CRIT, RH_CLOSE):
        for name in ("FirstOrderTransfer(初稿方案)", best):
            e = exceedance_metrics(y_te, preds[name], thr)
            e["model"] = name
            ex_rows.append(e)
        e = exceedance_metrics(y_te, pred_persist, thr)
        e["model"] = "Persistence"
        ex_rows.append(e)
    df_ex = pd.DataFrame(ex_rows)[
        ["model", "threshold", "base_rate", "n_pos", "precision", "recall", "F1", "AUC"]
    ]
    print(df_ex.to_string(index=False))
    df_ex.to_csv(RESULTS / "derisk01_exceedance.csv", index=False)

    print("\n" + "=" * 78)
    print("[7] 超阈值持续时间误差（核心业务指标，24 h 分块）")
    print("=" * 78)
    dur_rows = []
    for thr in (RH_WARN, RH_CRIT, RH_CLOSE):
        for name in ("FirstOrderTransfer(初稿方案)", best):
            d = exceedance_duration_error(y_te, preds[name], thr)
            d["model"] = name
            dur_rows.append(d)
    df_dur = pd.DataFrame(dur_rows)
    print(df_dur.to_string(index=False))
    df_dur.to_csv(RESULTS / "derisk01_duration.csv", index=False)

    # ---------- 8. 算子物理可解释性 ----------
    kt = models[best]
    print("\n" + "=" * 78)
    print("[8] 算子谱：提取到的物理时间常数")
    print("=" * 78)
    try:
        sp = kt.spectrum(top_k=8)
        print(sp.to_string(index=False))
        sp.to_csv(RESULTS / "derisk01_spectrum.csv", index=False)
        print("\n    文献参照：窟内外 RH 相位滞后 pi/4（日尺度约 3 h，Gong et al. 2025）；")
        print("             换气次数 1.6 /h（关门）~ 9-13 /h（开门，Zhao et al. 2026）")
    except Exception as exc:  # noqa: BLE001
        print(f"    谱分析失败: {exc}")

    print("\n" + "=" * 78)
    print("[9] 读出权重归因：模型学到了哪条物理通道？")
    print("=" * 78)
    print("\n    按特征族汇总（权重占比）:")
    print(kt.group_importance().to_string())
    print("\n    Top-15 单项特征:")
    print(kt.readout_importance(top_k=15).to_string(index=False))
    kt.readout_importance(top_k=40).to_csv(RESULTS / "derisk01_readout.csv", index=False)

    print(f"\n总用时 {time.time() - t0:.1f}s")
    print("结果已写入 results/derisk01_*.csv")


if __name__ == "__main__":
    main()
