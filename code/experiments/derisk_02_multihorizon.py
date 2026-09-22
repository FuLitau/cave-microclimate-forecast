"""解风险实验 02：24/48/72 小时多步预报 —— 可部署方法之间的正面对比。

为什么需要这个实验（实验 01 的教训）
------------------------------------
实验 01 做的是**同时刻重建（nowcast）**，即由 t 时刻外场推断 t 时刻窟内。
该设定下持续性预报（persistence）R2 高达 0.947，看起来无人能敌。但这有两个问题：

1. **持续性预报在本场景根本不可部署**——它需要**窟内实测 RH** 作为输入，
   而莫高窟窟内数据不公开、现场也没有可用的传感器链路。它是**参考上界（oracle）**，
   不是竞争方案。
2. 本赛题的真实任务是 **24/48/72 小时预报**，不是同时刻重建。
   在真实时效下，持续性预报会迅速退化，而输运算子的价值才显现出来。

因此本实验重新定义为：**只用 t 时刻及之前的外场数据，预报 t+h 时刻的窟内 RH（h=24/48/72）**。

参评方法
--------
可部署（仅用外场公开数据）
  * ``Koopman-rollout``：:math:`\\hat h_{t+h} = w^\\top K^{h}\\Psi_t` —— **本作品**，
    闭式、无自回归误差累积
  * ``Koopman-direct``：为每个时效单独拟合读出层（直接多步策略）—— 对照，
    用于回答"K 前推是否损失精度"
  * ``FirstOrderTransfer``：初稿方案，一阶衰减+滞后，递归推 72 步
  * ``RidgeDirect``：无延迟嵌入的岭回归（只用当前时刻外场）
  * ``Climatology``：训练集同季节均值

不可部署（参考上界，需窟内实测）
  * ``Persistence``：把 t 时刻窟内 RH 当作 t+h 的预报

评价指标
--------
除 RMSE/R2 外，重点报告**业务指标**：
  * 超阈值事件命中/漏报（62% / 67% / 75% 三级，各有文献出处）
  * 超阈值**持续时长**误差（损伤判据，比逐点误差更贴近业务）
  * 首次超阈的**预警提前量**
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operator.transport import (KoopmanTransport, TransportConfig,  # noqa: E402
                                    build_features)
from src.physics.cave_model import CaveModel, CaveParams              # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

TRAIN_END = "2019-12-31"
VAL_END = "2020-12-31"          # 2021-2025 为测试段
HORIZONS = (24, 48, 72)

#: 三级阈值，逐级独立出处（详见 docs/ 与 cave_model.PARAM_SOURCES）
THRESHOLDS = {
    "62%(业务预警)": 62.0,
    "67%(潮解起始)": 67.0,
    "75%(吸湿突变)": 75.0,
}


# --------------------------------------------------------------------------
# 指标
# --------------------------------------------------------------------------


def reg_metrics(y_true, y_pred) -> dict:
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    r = yp - yt
    ss_tot = float(((yt - yt.mean()) ** 2).sum())
    return {
        "RMSE": round(float(np.sqrt((r**2).mean())), 4),
        "MAE": round(float(np.abs(r).mean()), 4),
        "R2": round(1.0 - float((r**2).sum()) / ss_tot, 5) if ss_tot > 0 else np.nan,
        "bias": round(float(r.mean()), 4),
    }


def event_metrics(y_true, y_pred, thr: float, cut: float | None = None) -> dict:
    """超阈事件检测：AUC（无阈值排序能力）与 F1（需决策阈值）。

    ⚠️ 为什么必须给决策阈值 ``cut``
    ------------------------------
    直接把"点预报 >= thr"当作报警，在事件率仅约 1% 时**永远不会触发**
    （实测所有模型的 F1 恒为 0，包括 oracle），这是**指标与预报表示不匹配**，
    不是模型无能。正确做法是：把预报值当作**风险分数**，在**验证段**标定一个
    决策阈值，再在测试段评估 F1。

    本函数中 ``cut`` 由调用方在验证段标定（见 ``calibrate_cut``），
    测试段只应用、不重新标定，**无信息泄露**。
    """
    from sklearn.metrics import roc_auc_score

    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    a = yt >= thr
    b = (yp >= cut) if cut is not None else (yp >= thr)
    tp = int((a & b).sum()); fp = int((~a & b).sum()); fn = int((a & ~b).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    try:
        auc = float(roc_auc_score(a.astype(int), yp)) if a.any() and (~a).any() else np.nan
    except Exception:  # noqa: BLE001
        auc = np.nan
    return {
        "base_rate": round(float(a.mean()), 4),
        "n_event": int(a.sum()),
        "alarm_rate": round(float(b.mean()), 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "F1": round(f1, 4),
        "AUC": round(auc, 4) if np.isfinite(auc) else np.nan,
    }


def calibrate_cut(y_true, y_pred, thr: float, mode: str = "rate") -> float:
    """在**验证段**标定决策阈值。

    ``mode="rate"``：把决策阈值设为"使报警率等于基准事件率"的分位数。
    这是标准的类别不平衡处置（不依赖测试段，也不会把 F1 优化到过拟合）。
    """
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    if len(yp) == 0:
        return thr
    base = float((yt >= thr).mean())
    if base <= 0:
        return thr
    return float(np.quantile(yp, 1.0 - base))


def duration_metrics(y_true, y_pred, thr: float, block_h: int = 24,
                     cut: float | None = None) -> dict:
    """超阈**持续时长**误差 —— 采用**事件条件化**口径。

    为什么必须条件化（方法学修正）
    ------------------------------
    直接对所有 24 h 分块取 |时长误差| 的均值是**退化指标**：在事件稀少时，
    "永远不预报超阈"的策略每块时长误差都等于真实时长的 0，因而得分很漂亮。
    这正是初稿方案（FirstOrderTransfer）系统性少报（负偏差）却在此指标上
    "获胜"的原因，与"少雨城市里永远报无雨"能在 Brier 分上占便宜同构。

    正确做法是把**检出**与**条件精度**分开，并使用联合指标：

    * ``hit_window``：真实发生超阈的分块中，预报也报出的比例（检出率）；
    * ``cond_dur_MAE_h``：**只在命中分块上**的时长误差（条件精度）；
    * ``joint_dur_MAE_h``：未命中一律按整块时长计误差，再取均值。
      该项把漏报的代价显式计入，使"少报策略"无法取巧。
    * ``false_alarm_h``：真实未超阈但预报超阈的平均时长（误报代价）。
    """
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    n = (len(yt) // block_h) * block_h
    if n == 0:
        return {}
    a = (yt[:n] >= thr).reshape(-1, block_h).sum(axis=1)   # 真实超阈小时数
    b = (yp[:n] >= (cut if cut is not None else thr)
         ).reshape(-1, block_h).sum(axis=1)                # 预报超阈小时数
    has_event = a > 0
    has_alarm = b > 0

    hit = has_event & has_alarm
    miss = has_event & ~has_alarm
    fa = ~has_event & has_alarm

    # 联合误差：命中用真实误差；漏报按整块时长 a 计（等于完全没抓到）；
    # 误报按整块预报时长 b 计。
    err = np.where(hit, np.abs(b - a), 0.0)
    err = np.where(miss, a.astype(float), err)
    err = np.where(fa, b.astype(float), err)

    # **只在"有事件或有报警"的窗口上取均值**。
    # 若对所有窗口取均值，由于事件窗口占比极低，"从不报警"的模型会因为
    # 绝大多数窗口误差为 0 而拿到最低分——这正是退化指标。
    # 限定在事件∪报警窗口上，则"从不报警"必须承担全部事件的时长误差，
    # "乱报警"必须承担误报时长，两种取巧都被堵死。
    relevant = has_event | has_alarm
    joint = float(err[relevant].mean()) if relevant.any() else np.nan

    return {
        "n_window": int(len(a)),
        "n_event_window": int(has_event.sum()),
        "hit_window": round(float(hit.sum() / has_event.sum()), 4)
                      if has_event.sum() else np.nan,
        "cond_dur_MAE_h": round(float(np.abs(b[hit] - a[hit]).mean()), 4)
                          if hit.sum() else np.nan,
        "joint_dur_MAE_h": round(joint, 4) if np.isfinite(joint) else np.nan,
        "false_alarm_h": round(float(b[fa].mean()), 4) if fa.sum() else 0.0,
        "dur_bias_h": round(float((b[has_event] - a[has_event]).mean()), 4)
                      if has_event.sum() else np.nan,
    }


def lead_time_metrics(y_true, y_pred, thr: float,
                      cut: float | None = None) -> dict:
    """首次超阈的**预警提前量**：在真实事件发生前，预报提前多少小时给出预警。

    只在"真实序列由未超阈转为超阈"的跃变点统计，避免把持续超标重复计数。
    预警判据使用**验证段标定**的决策阈值 ``cut``。
    """
    c = cut if cut is not None else thr
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    a = yt >= thr
    onset = np.where(a & ~np.r_[False, a[:-1]])[0]
    leads = []
    for t0 in onset:
        if t0 < 72:
            continue
        # 在事件发生前的 72 h 窗口内，预报是否已给出超阈信号
        win = yp[t0 - 72:t0]
        hit = np.where(win >= c)[0]
        if hit.size:
            leads.append(72 - int(hit[0]))       # 距事件发生的小时数
    return {
        "n_onset": int(len(onset)),
        "n_warned": int(len(leads)),
        "detect_rate": round(len(leads) / len(onset), 4) if len(onset) else np.nan,
        "mean_lead_h": round(float(np.mean(leads)), 2) if leads else np.nan,
    }


# --------------------------------------------------------------------------
# 基线
# --------------------------------------------------------------------------


class FirstOrderTransfer:
    """初稿方案的传递函数结构 :math:`y_t = a y_{t-1} + b x_{t-\\tau} + c`。

    **同一组拟合系数，提供三种口径不同的多步推演方式**。这一点很重要：把
    "初稿方案不行"归因到 *模型形式* 还是 *推演方式*，结论完全不同，而两者
    的差别恰好藏在"怎么把一步方程变成多步预报"这一步里。

    ``forecast_direct``
        非递归直接传递 :math:`\\hat y(t+h) = a\\,y(t) + b\\,x(t+h-\\tau) + c`。
        每个预报起点用**当时可测到的窟内实测值**重新锚定，配未来外场轨迹。
        这是**可部署**口径，且与直接多步算子（``predict_direct``）严格同口径
        ——算子的特征也只用到 ``t`` 时刻为止的历史。
    ``forecast_lagged``
        初稿原文形式（**不含自回归项**）:math:`\\hat y(t+h) = a' x(t+h-\\tau) + b'`。
        连窟内实测都不需要，是最"轻"的可部署对照。
    ``forecast_recursive``
        把预测值喂回、从单一初值一路推演的写法。极点 :math:`|a|>1` 时数学上
        必然发散（实测 a≈1.0009 时 40000 步后达 -1e17，被量程截断成常数序列），
        因此它**只能作为"误差累积"的定性说明，不能当作性能对照**。
    """

    def __init__(self, lag_h: int = 3):
        self.lag_h = lag_h
        self.coef_: np.ndarray | None = None
        self.coef_lagged_: np.ndarray | None = None

    def fit(self, x, y):
        xl = np.roll(x, self.lag_h); xl[: self.lag_h] = x[: self.lag_h]
        A = np.column_stack([y[:-1], xl[1:], np.ones(len(y) - 1)])
        self.coef_, *_ = np.linalg.lstsq(A, y[1:], rcond=None)
        # 初稿原文形式：无自回归项
        A2 = np.column_stack([xl, np.ones(len(y))])
        self.coef_lagged_, *_ = np.linalg.lstsq(A2, y, rcond=None)
        return self

    @property
    def pole(self) -> float:
        """自回归极点 a。|a| >= 1 时递归推演必发散。"""
        return float(self.coef_[0])

    def _shifted(self, x_future: np.ndarray, horizon: int, n: int) -> np.ndarray:
        """取被评估样本对应的滞后外场 :math:`x(t+h-\\tau)`（长度 n）。"""
        idx = horizon + np.arange(n) - self.lag_h
        return x_future[np.clip(idx, 0, None)]

    def forecast_direct(self, x_future: np.ndarray, y_origin: np.ndarray,
                        horizon: int) -> np.ndarray:
        """可部署口径：每个起点用当前窟内实测重锚，不递归。

        ``pred[i]`` 预测 :math:`y(t_0 + h + i)`，与 ``x_future``/``y_origin``
        的下标共用同一时基。
        """
        a, b, c = self.coef_
        n = len(x_future) - horizon
        return a * y_origin[:n] + b * self._shifted(x_future, horizon, n) + c

    def forecast_lagged(self, x_future: np.ndarray, horizon: int) -> np.ndarray:
        """初稿原文形式（仅外场滞后，无自回归）：可部署、最轻的对照。"""
        a, b = self.coef_lagged_
        n = len(x_future) - horizon
        return a * self._shifted(x_future, horizon, n) + b

    def forecast_recursive(self, x_future: np.ndarray, y_last: float,
                           horizon: int) -> np.ndarray:
        """原 P0 写法：单一初值、逐小时递归、不重置。

        内部先把递归轨迹推到 ``n + h - 1`` 步，再按"第 i 个样本对应
        :math:`y(t_0+h+i)`"对齐取片段。发散与否由 :attr:`pole` 决定。
        """
        a, b, c = self.coef_
        n = len(x_future) - horizon
        steps = n + horizon - 1
        traj = np.empty(steps)
        prev = y_last
        for t in range(steps):
            src = x_future[t - self.lag_h] if t >= self.lag_h else x_future[0]
            prev = a * prev + b * src + c
            traj[t] = prev
        return traj[horizon - 1: horizon - 1 + n]


class RidgeDirect:
    """无延迟嵌入的岭回归（只用当前时刻外场要素）。"""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.mu_ = self.sigma_ = self.coef_ = None

    def fit(self, X, y):
        self.mu_ = X.mean(axis=0); self.sigma_ = X.std(axis=0)
        self.sigma_[self.sigma_ < 1e-12] = 1.0
        Z = np.column_stack([(X - self.mu_) / self.sigma_, np.ones(len(X))])
        p = Z.shape[1]
        self.coef_ = np.linalg.solve(Z.T @ Z + self.alpha * np.eye(p), Z.T @ y)
        return self

    def predict(self, X):
        Z = np.column_stack([(X - self.mu_) / self.sigma_, np.ones(len(X))])
        return Z @ self.coef_


# --------------------------------------------------------------------------
# 主流程
# --------------------------------------------------------------------------


def main() -> None:
    t0 = time.time()
    print("=" * 84)
    print("解风险实验 02：24/48/72 h 多步预报（只用外场公开数据）")
    print("=" * 84)

    interim = ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
    outdoor = pd.read_csv(interim, index_col=0, parse_dates=True).sort_index()
    outdoor = outdoor[~outdoor.index.duplicated(keep="first")]

    print("\n[1] 生成窟内物理合成标签 ...")
    cave = CaveModel(CaveParams()).simulate(outdoor)
    cave.to_csv(ROOT / "data" / "interim" / "cave_synthetic_2001_2025.csv")
    y = cave["RH_in"].to_numpy(dtype=float)
    print(f"    RH_in: mean {np.nanmean(y):.2f}%  std {np.nanstd(y):.2f}  "
          f"max {np.nanmax(y):.2f}%")
    print(f"    凝结发生小时数: {int((cave['condensate_kg_s'] > 0).sum()):,} "
          f"({(cave['condensate_kg_s'] > 0).mean()*100:.2f}%)")
    for name, thr in THRESHOLDS.items():
        print(f"    超阈占比 {name}: {(y > thr).mean()*100:.2f}%")

    tr = outdoor.index <= pd.Timestamp(TRAIN_END, tz="UTC")
    va = (outdoor.index > pd.Timestamp(TRAIN_END, tz="UTC")) & \
         (outdoor.index <= pd.Timestamp(VAL_END, tz="UTC"))
    te = outdoor.index > pd.Timestamp(VAL_END, tz="UTC")
    print(f"\n[2] 时序切分  训练 {tr.sum():,} / 验证 {va.sum():,} / 测试 {te.sum():,} 小时")

    od_te = outdoor[te]
    y_te = y[te]

    # ---------- 特征矩阵：**必须全序列构造一次，再按时间切分** ----------
    # 慢变窗口最长 8760 h（1 年）。若在训练段 / 验证段 / 测试段的切片上分别
    # 调用 build_features，滑动均值会在每个切片起点重新起步：测试段前整整一年
    # 的慢变特征都是"只看了几天"的错值，训练段与测试段的特征分布也不再一致，
    # 测试指标被系统性污染。唯一正确的做法是全序列构造 Psi、再用行掩码切片。
    DRV = list(TransportConfig().drivers)
    print("\n[3] 在全序列上构造特征矩阵（避免切片起点重启慢变滑动均值）...")

    ABLATIONS = {
        "Operator-Full(本作品)": {},
        "Ablation-无慢变项": {"use_slow": False},
        "Ablation-无Magnus项": {"use_magnus": False},
        "Ablation-仅快变延迟": {"use_slow": False, "use_magnus": False},
        "Ablation-短延迟(12h)": {"n_fast_lags": 12},
    }
    #: 岭强度网格。**两端必须够远**：早前网格下界只到 1e-3，结果所有配置的
    #: β* 都被钉在下界上——那不是"最优"，而是"网格没覆盖到最优"。这里把下界
    #: 放到 1e-6（与 `TransportConfig.ridge_beta` 默认值一致）。
    BETA_GRID = (1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0)

    Psi_all: dict[str, np.ndarray] = {}
    for name, over in ABLATIONS.items():
        _cfg = TransportConfig(**over)
        Psi_all[name] = build_features(outdoor, _cfg)
        print(f"    {name:<24} Psi 形状 {Psi_all[name].shape}")

    # ---------- 每个配置**各自**选 beta ----------
    # 方法学要点：消融之间特征维度不同（240~258），同一 beta 对各配置的
    # 相对正则强度并不相同。若共用 beta，"某消融反超"可能只是正则强度错配的伪象，
    # 而非"该特征族无用"。因此**每个配置独立在验证段选 beta**。
    print("\n[4] 逐配置在验证段选择岭回归系数 beta ...")

    transports: dict[str, KoopmanTransport] = {}
    beta_of: dict[str, float] = {}
    val_r2_of: dict[str, float] = {}
    for name, over in ABLATIONS.items():
        best = None
        for beta in BETA_GRID:
            cfg = TransportConfig(ridge_beta=beta, **over)
            kt = KoopmanTransport(cfg).fit(
                outdoor[tr], y[tr], fit_koopman=False, Psi=Psi_all[name][tr])
            r2 = reg_metrics(y[va], kt.predict(outdoor[va], Psi=Psi_all[name][va]))["R2"]
            if best is None or r2 > best[1]:
                best = (beta, r2)
        beta_of[name] = best[0]
        val_r2_of[name] = best[1]
        print(f"    {name:<24} beta* = {best[0]:<8g} val R2 = {best[1]:+.4f}")

    # 用各自的最优 beta 重新拟合（Full 额外拟合 K 供谱分析）
    print("\n[5] 拟合模型 ...")
    for name, over in ABLATIONS.items():
        cfg = TransportConfig(ridge_beta=beta_of[name], **over)
        transports[name] = KoopmanTransport(cfg).fit(
            outdoor[tr], y[tr], fit_koopman=name.startswith("Operator-Full"),
            Psi=Psi_all[name][tr])
    kt = transports["Operator-Full(本作品)"]
    Psi_full = Psi_all["Operator-Full(本作品)"]
    beta_star = beta_of["Operator-Full(本作品)"]
    print(f"    Koopman 特征维度 p = {kt.n_features_in_}（Full 配置）")

    rd = RidgeDirect().fit(outdoor.loc[tr, DRV].to_numpy(), y[tr])
    fot = FirstOrderTransfer(lag_h=3).fit(outdoor.loc[tr, "RH2M"].to_numpy(), y[tr])
    print(f"    初稿一阶传递系数 a = {fot.pole:.6f}（|a|>=1 时递归推演必发散）"
          f"  b = {fot.coef_[1]:.6f}  c = {fot.coef_[2]:.6f}")
    print(f"    初稿原文形式（无自回归）a' = {fot.coef_lagged_[0]:.6f}"
          f"  b' = {fot.coef_lagged_[1]:.6f}")

    w_direct = {h: kt.fit_direct(outdoor[tr], y[tr], h, Psi=Psi_full[tr])
                for h in HORIZONS}
    w_abl = {name: {h: t.fit_direct(outdoor[tr], y[tr], h, Psi=Psi_all[name][tr])
                    for h in HORIZONS}
             for name, t in transports.items()}

    clim = pd.Series(y[tr], index=outdoor.index[tr]).groupby(
        lambda t: (t.month, t.day, t.hour)).mean()

    # ---------- 构造预测（可复用于验证段与测试段） ----------
    def build_preds(mask, h: int):
        od_slice = outdoor[mask]
        y_slice = y[mask]
        out: dict[str, np.ndarray] = {}
        n = len(y_slice) - h
        out["Operator-direct(本作品)"] = kt.predict_direct(
            od_slice, w_direct[h], Psi=Psi_full[mask])[:n]
        for name, t in transports.items():
            if name.startswith("Operator-Full"):
                continue
            out[name] = t.predict_direct(
                od_slice, w_abl[name][h], Psi=Psi_all[name][mask])[:n]
        rh2m = od_slice["RH2M"].to_numpy()
        # 初稿方案的三种推演口径（同一组系数，只差"怎么把一步方程变成多步"）
        out["FirstOrderTransfer-直接传递(初稿形式)"] = fot.forecast_direct(
            rh2m, y_slice, h)[:n]
        out["FirstOrderTransfer-仅外场滞后(初稿原文)"] = fot.forecast_lagged(
            rh2m, h)[:n]
        out["FirstOrderTransfer-递归推演(不稳定极点)"] = fot.forecast_recursive(
            rh2m, y_slice[0], h)[:n]
        out["RidgeDirect(无延迟嵌入)"] = rd.predict(od_slice[DRV].to_numpy())[:n]
        od_persist = od_slice.copy()
        for col in od_persist.columns:
            od_persist[col] = od_slice[col].to_numpy()[0]
        out["Persistence-operator(可部署)"] = kt.predict(
            od_persist, Psi=kt.feature_matrix(od_persist))[:n]
        out["[oracle]Persistence(需窟内实测)"] = y_slice[:n]
        out["Climatology(可部署)"] = np.array(
            [clim.get((t.month, t.day, t.hour), np.nan) for t in od_slice.index[:n]])
        return out

    od_va, y_va = outdoor[va], y[va]

    # ---------- 逐时效评估 ----------
    rows, ev_rows, dur_rows, lead_rows = [], [], [], []

    for h in HORIZONS:
        print(f"\n{'=' * 84}\n[5a] 点预报精度  h = {h} h\n{'=' * 84}")
        n = len(y_te) - h
        yt = y_te[h:]
        preds = build_preds(te, h)

        # 在**验证段**标定各模型的决策阈值（测试段只应用，无泄露）
        val_preds = build_preds(va, h)
        cuts: dict[str, float] = {}
        for tname, thr in THRESHOLDS.items():
            for name, pv in val_preds.items():
                cuts[f"{tname}|{name}"] = calibrate_cut(y_va[h:], pv, thr)
        # 递归推演口径在长时效会数值饱和，评估前做物理量程截断
        rk = "FirstOrderTransfer-递归推演(不稳定极点)"
        preds[rk] = np.clip(preds[rk], 0.0, 100.0)

        for name, p in preds.items():
            m = reg_metrics(yt, p)
            rows.append({"horizon_h": h, "model": name, **m})
        df_h = pd.DataFrame([r for r in rows if r["horizon_h"] == h])
        print(df_h[["model", "RMSE", "MAE", "R2", "bias"]].to_string(index=False))

        for tname, thr in THRESHOLDS.items():
            for name, p in preds.items():
                cut = cuts[f"{tname}|{name}"]
                e = event_metrics(yt, p, thr, cut=cut)
                e["cut"] = round(cut, 3)
                ev_rows.append({"horizon_h": h, "threshold": tname, "model": name, **e})
                d = duration_metrics(yt, p, thr, cut=cut)
                dur_rows.append({"horizon_h": h, "threshold": tname, "model": name, **d})
            for name in ("Operator-direct(本作品)",
                         "FirstOrderTransfer-直接传递(初稿形式)"):
                l = lead_time_metrics(yt, preds[name], thr,
                                      cut=cuts[f"{tname}|{name}"])
                lead_rows.append({"horizon_h": h, "threshold": tname,
                                  "model": name, **l})

    pd.DataFrame(rows).to_csv(RESULTS / "derisk02_accuracy.csv", index=False)
    pd.DataFrame(ev_rows).to_csv(RESULTS / "derisk02_events.csv", index=False)
    pd.DataFrame(dur_rows).to_csv(RESULTS / "derisk02_duration.csv", index=False)
    pd.DataFrame(lead_rows).to_csv(RESULTS / "derisk02_leadtime.csv", index=False)

    # ---------- 摘要：业务指标 ----------
    df_ev = pd.DataFrame(ev_rows)
    print(f"\n{'=' * 84}\n[6] 业务指标摘要：超阈事件 F1 / AUC\n{'=' * 84}")
    piv = df_ev.pivot_table(index=["threshold", "model"], columns="horizon_h",
                            values="F1")
    print(piv.round(3).to_string())

    print(f"\n[7] 超阈持续时长 —— 事件条件化口径（小时）\n{'=' * 84}")
    df_dur = pd.DataFrame(dur_rows)
    for col, label in (("joint_dur_MAE_h", "联合时长MAE（漏报按整块计，越小越好）"),
                       ("cond_dur_MAE_h", "条件时长MAE（仅命中窗口）"),
                       ("hit_window", "事件窗口检出率")):
        piv2 = df_dur.pivot_table(index=["threshold", "model"],
                                  columns="horizon_h", values=col)
        print(f"\n  {label}:")
        print(piv2.round(3).to_string())

    df_lead = pd.DataFrame(lead_rows)
    if not df_lead.empty:
        print(f"\n[8] 预警提前量（首次超阈检出率 / 平均提前小时）\n{'=' * 84}")
        print(df_lead.to_string(index=False))

    # ---------- 算子可解释性 ----------
    print(f"\n{'=' * 84}\n[9] 算子物理可解释性\n{'=' * 84}")
    print("\n特征族权重占比:")
    print(kt.group_importance().to_string())
    print("\nTop-12 读出特征:")
    print(kt.readout_importance(top_k=12).to_string(index=False))
    kt.readout_importance(top_k=40).to_csv(RESULTS / "derisk02_readout.csv", index=False)
    try:
        sp = kt.spectrum(top_k=10)
        print("\n算子谱（提取到的物理时间常数）:")
        print(sp.to_string(index=False))
        sp.to_csv(RESULTS / "derisk02_spectrum.csv", index=False)
    except Exception as exc:  # noqa: BLE001
        print(f"谱分析失败: {exc}")

    # ---------- 特征族消融判读 ----------
    # 之前这一步只 print 表格、不做判读，读者（和审阅者）容易把"某消融在某段
    # 反超 Full"读成"该特征族无用"或直接忽略。这里显式给出**验证段与测试段
    # 双向**判读，并把"反超"如实标出来——**负结论也要写清楚**。
    print(f"\n{'=' * 84}\n[10] 特征族消融判读（验证段 vs 测试段）\n{'=' * 84}")
    acc = pd.DataFrame(rows)
    ev = pd.DataFrame(ev_rows)
    FULL = "Operator-direct(本作品)"
    for h in HORIZONS:
        d = acc[acc.horizon_h == h].set_index("model")
        full_r2 = float(d.loc[FULL, "R2"])
        print(f"\n  h = {h} h   Full: test R2 {full_r2:+.4f}"
              f"（验证段同时刻读出 R2 {val_r2_of['Operator-Full(本作品)']:+.4f}）")
        for name in ABLATIONS:
            if name.startswith("Operator-Full"):
                continue
            dv = val_r2_of[name] - val_r2_of["Operator-Full(本作品)"]
            dt = float(d.loc[name, "R2"]) - full_r2
            sel = ev[(ev.horizon_h == h) & (ev.model == name) &
                     (ev.threshold == "62%(业务预警)")]["F1"]
            f1s = f"  F1(62%) {float(sel.iloc[0]):.4f}" if len(sel) else ""
            flag = "   <== 测试段反超 Full，如实报告" if dt > 0 else ""
            print(f"    {name:<24} val ΔR2 {dv:+.4f} / test ΔR2 {dt:+.4f}{f1s}{flag}")

    print(f"\n总用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
