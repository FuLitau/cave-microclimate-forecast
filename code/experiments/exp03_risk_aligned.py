"""实验 03（核心实验）：风险对齐训练 —— A/B/C 消融。

本实验是整个作品的**算法主张验证**。

要证明的问题
------------
实验 02 得到一个决定性的观察：

    Ridge / MSE 训练下，窟内 RH 的 R2 = 0.42（看起来不错），
    但**超阈事件 F1 = 0.000**——模型从不预报任何一次超阈。

这不是调参问题，而是**目标函数错配**：MSE 关心的是全体样本的平均偏差，
而阈值超越是尾部事件，在 MSE 意义下"永远预报不超阈"几乎不损失什么，
却在业务上意味着**预警完全失效**。壁画盐害正由这些尾部事件驱动。

三组对照
--------
====  ==========================================================
方案   训练目标
====  ==========================================================
A     MSE（现有全部工作的做法）
B     MSE + twCRPS，权重为**固定阈值**（标准 twCRPS）
C     MSE + twCRPS，权重由**输运算子传播的窟内 RH** 驱动（本作品）
====  ==========================================================

**判据：只有 C 显著优于 B，"算子导出内生权重"才算真正的算法贡献；
若 C ≈ B，则贡献退化为"换了个损失函数"，创新性主张不成立。**
本脚本会把这一判据显式打印出来，包括失败的情形。

梯度链路
--------
::

    室外预报网络 ──► 室外分位数轨迹 ──► (冻结) 输运算子 ──► 窟内 RH 分位数 ──► twCRPS
          ▲                                                                      │
          └──────────────────── 梯度经算子回传 ────────────────────────────────┘

算子对预报网络参数可微，因此误差信号会精确回传到"对窟内风险真正有影响"
的那些室外要素与时段上——这是纯 MSE 训练做不到的。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.losses.twcrps import (                       # noqa: E402
    endogenous_weights,
    risk_to_decision,
    weighted_quantile_loss,
)
from src.operator.transport import KoopmanTransport, TransportConfig  # noqa: E402
from src.physics.cave_model import CaveModel, CaveParams              # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

torch.manual_seed(0)
np.random.seed(0)
torch.set_num_threads(8)

TRAIN_END = "2019-12-31"
VAL_END = "2020-12-31"
H_MAX = 72
HIST_FAST = 48          # 快变延迟坐标阶数（与 TransportConfig 保持一致）
INPUT_WINDOW = 168      # 预报网络的输入窗口（小时）
N_QUANTILES = 5
TAUS = torch.linspace(0.1, 0.9, N_QUANTILES)

RH_WARN, RH_CRIT, RH_CLOSE = 62.0, 67.0, 75.0
THRESHOLDS = {"62%(业务预警)": RH_WARN, "67%(潮解起始)": RH_CRIT,
              "75%(吸湿突变)": RH_CLOSE}


# ==========================================================================
# 预报网络
# ==========================================================================


class QuantileForecaster(nn.Module):
    """多时效分位数预报网络。

    输入：过去 ``INPUT_WINDOW`` 小时的多要素外场序列
    输出：未来 1..H_MAX 小时、每个要素在 N_QUANTILES 个分位水平上的预报

    刻意做得简单（MLP），因为本实验要验证的是**目标函数**的贡献，
    不是骨干结构的贡献——骨干换成 LSTM/Transformer 是后续工作。
    """

    def __init__(self, n_vars: int, window: int = INPUT_WINDOW, h_max: int = H_MAX,
                 n_q: int = N_QUANTILES, hidden: int = 384):
        super().__init__()
        self.n_vars, self.h_max, self.n_q = n_vars, h_max, n_q
        self.net = nn.Sequential(
            nn.Flatten(),
            nn.Linear(n_vars * window, hidden), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(hidden, hidden), nn.GELU(), nn.Dropout(0.1),
            nn.Linear(hidden, h_max * n_vars * n_q),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, window, n_vars) -> (B, h_max, n_vars, n_q)，已按分位水平排序。"""
        out = self.net(x)
        out = out.view(-1, self.h_max, self.n_vars, self.n_q)
        # 强制分位数单调（沿分位维排序），避免分位交叉
        return torch.sort(out, dim=-1).values


# ==========================================================================
# 算子前向（可微）
# ==========================================================================


class OperatorHead(nn.Module):
    """冻结的输运算子读出层，把室外分位数轨迹映射为窟内 RH 分位数。

    设计要点（**准静态慢状态近似**）
    --------------------------------
    快变延迟坐标（48 h）随预报时效变化，必须逐步重构；
    但 30/90/365 天滑动均值在 72 h 内几乎不变，因此**在 t 时刻取一次并冻结**。
    这既是物理上正确的近似（洞窟热惯性极大），也避免了把外生汇总量当作
    Koopman 可观测量去强行演化——实验 02 已证明后者会破坏信号。
    """

    def __init__(self, transport: KoopmanTransport, n_fast: int, window_len: int):
        super().__init__()
        self.n_fast = n_fast
        self.window_len = window_len
        device = torch.device("cpu")
        self.register_buffer("w", torch.tensor(transport.w_, dtype=torch.float32))
        self.register_buffer("mu", torch.tensor(transport.mu_, dtype=torch.float32))
        self.register_buffer("sigma", torch.tensor(transport.sigma_, dtype=torch.float32))
        self.h_max = H_MAX
        # 预生成滑窗索引 (h_max, HIST_FAST)
        idx = torch.arange(self.h_max)[:, None] + torch.arange(HIST_FAST)[None, :]
        self.register_buffer("idx", idx)
        self.to(device)

    def forward(self, hist_fast: torch.Tensor, fcst: torch.Tensor,
                slow_feat: torch.Tensor) -> torch.Tensor:
        """
        Parameters
        ----------
        hist_fast : (B, HIST_FAST, V)
            最近 HIST_FAST 小时的**实测**外场（原始量纲）。
        fcst : (B, h_max, V, Q)
            预报的分位数轨迹（原始量纲）。
        slow_feat : (B, S)
            t 时刻冻结的慢变＋Magnus 原始特征。

        Returns
        -------
        (B, h_max, Q) 窟内 RH 分位数预报
        """
        B, H, V, Q = fcst.shape
        # 实测历史对每个分位场景是同一段，沿分位维广播
        hist = hist_fast.unsqueeze(-1).expand(B, hist_fast.shape[1], V, Q)
        # 拼接：实测 48 h + 预报 72 h
        seq = torch.cat([hist, fcst], dim=1)                            # (B,120,V,Q)
        # 取出每个时效对应的 48 h 窗口 -> (B, H, HIST_FAST, V, Q)
        win = seq[:, self.idx]                                          # 广播索引
        fast = win.permute(0, 1, 4, 2, 3).reshape(B, H, Q, -1)          # (B,H,Q,240)

        # 拼接冻结的慢变特征
        slow = slow_feat[:, None, None, :].expand(B, H, Q, slow_feat.shape[1])
        psi = torch.cat([fast, slow], dim=-1)                           # (B,H,Q,P)

        psi = (psi - self.mu) / self.sigma
        psi = torch.cat([psi, torch.ones_like(psi[..., :1])], dim=-1)   # 截距
        return psi @ self.w                                             # (B,H,Q)


# ==========================================================================
# 数据准备
# ==========================================================================


def make_windows(outdoor: pd.DataFrame, cave_rh: np.ndarray, drivers: list[str],
                 stride: int = 3):
    """构造监督样本：输入过去 INPUT_WINDOW 小时外场，输出未来 H_MAX 小时外场＋窟内 RH。"""
    X = outdoor[drivers].to_numpy(dtype=np.float32)
    n = len(X)
    starts = np.arange(INPUT_WINDOW, n - H_MAX - 1, stride)
    xw = np.stack([X[s - INPUT_WINDOW:s] for s in starts])
    yw = np.stack([X[s:s + H_MAX] for s in starts])
    yc = np.stack([cave_rh[s:s + H_MAX] for s in starts]).astype(np.float32)
    # 与 yw 对齐：yw[:, h-1] 对应时刻 s+h-1；窟内 RH 目标取同一时刻
    return xw, yw, yc, starts


# ==========================================================================
# 评价
# ==========================================================================


def evaluate(y_true: np.ndarray, y_pred: np.ndarray, thr: float) -> dict:
    from sklearn.metrics import roc_auc_score
    a, b = y_true >= thr, y_pred >= thr
    tp = int((a & b).sum()); fp = int((~a & b).sum()); fn = int((a & ~b).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    try:
        auc = float(roc_auc_score(a.astype(int), y_pred)) if a.any() and (~a).any() else np.nan
    except Exception:  # noqa: BLE001
        auc = np.nan
    r = y_pred - y_true
    ss = float(((y_true - y_true.mean()) ** 2).sum())
    return {
        "RMSE": round(float(np.sqrt((r ** 2).mean())), 4),
        "MAE": round(float(np.abs(r).mean()), 4),
        "R2": round(1.0 - float((r ** 2).sum()) / ss, 5) if ss > 0 else np.nan,
        "bias": round(float(r.mean()), 4),
        "precision": round(prec, 4), "recall": round(rec, 4), "F1": round(f1, 4),
        "AUC": round(auc, 4) if np.isfinite(auc) else np.nan,
        "base_rate": round(float(a.mean()), 4),
        # 预报的超越率 —— 若远低于 base_rate，说明预报被压缩、根本不敢报事件
        "pred_rate": round(float(b.mean()), 4),
        "pred_p95": round(float(np.percentile(y_pred, 95)), 2),
        "pred_max": round(float(y_pred.max()), 2),
    }


def duration_err(y_true, y_pred, thr, block=24) -> float:
    n = (len(y_true) // block) * block
    a = (y_true[:n] >= thr).reshape(-1, block).sum(axis=1)
    b = (y_pred[:n] >= thr).reshape(-1, block).sum(axis=1)
    return round(float(np.abs(b - a).mean()), 4)


# ==========================================================================
# 主流程
# ==========================================================================


def main() -> None:
    t0 = time.time()
    print("=" * 88)
    print("实验 03：风险对齐训练 A/B/C 消融（本作品的算法主张验证）")
    print("=" * 88)

    # ---------- 数据 ----------
    outdoor = pd.read_csv(ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
                          index_col=0, parse_dates=True).sort_index()
    outdoor = outdoor[~outdoor.index.duplicated(keep="first")]
    drivers = ["T2M", "RH2M", "WS10M", "PS", "ALLSKY_SFC_SW_DWN"]
    drivers = [c for c in drivers if c in outdoor.columns]

    print("\n[1] 窟内物理合成标签 ...")
    cave = CaveModel(CaveParams()).simulate(outdoor)
    cave_rh = cave["RH_in"].to_numpy(dtype=float)

    # ---------- 算子（在外场数据上闭式拟合，只用训练段） ----------
    tr_mask = outdoor.index <= pd.Timestamp(TRAIN_END, tz="UTC")
    print("[2] 闭式拟合输运算子（训练段）...")
    transport = KoopmanTransport(TransportConfig(ridge_beta=10.0)).fit(
        outdoor[tr_mask], cave_rh[tr_mask], fit_koopman=False)
    n_fast = transport.cfg.n_fast_lags * len(drivers)
    n_slow = transport.n_features_in_ - n_fast
    print(f"    特征维度 P = {transport.n_features_in_}  (快变 {n_fast} + 慢变/Magnus {n_slow})")

    # 冻结的慢变特征：对整条序列算一次，取每个样本起点那一行
    from src.operator.transport import build_features
    psi_all = build_features(outdoor, transport.cfg)          # (N, P) 原始量纲
    slow_all = psi_all[:, n_fast:].astype(np.float32)
    del psi_all

    # ---------- 监督样本 ----------
    print("[3] 构造监督样本 ...")
    X, Y, C, starts = make_windows(outdoor, cave_rh, drivers, stride=3)
    slow_win = slow_all[starts]
    print(f"    样本数 {len(X):,}  x_in {X.shape[1:]}  y_out {Y.shape[1:]}")

    # 标准化（用训练统计量）
    tr_s = outdoor.index[starts] <= pd.Timestamp(TRAIN_END, tz="UTC")
    va_s = (outdoor.index[starts] > pd.Timestamp(TRAIN_END, tz="UTC")) & \
           (outdoor.index[starts] <= pd.Timestamp(VAL_END, tz="UTC"))
    te_s = outdoor.index[starts] > pd.Timestamp(VAL_END, tz="UTC")
    print(f"    训练 {tr_s.sum():,} / 验证 {va_s.sum():,} / 测试 {te_s.sum():,}")

    x_mu, x_sd = X[tr_s].mean(axis=(0, 1)), X[tr_s].std(axis=(0, 1))
    y_mu, y_sd = Y[tr_s].mean(axis=(0, 1)), Y[tr_s].std(axis=(0, 1))
    sd = lambda a: np.where(a < 1e-8, 1.0, a)                  # noqa: E731
    x_sd, y_sd = sd(x_sd), sd(y_sd)

    Xn = (X - x_mu) / x_sd
    Yn = (Y - y_mu) / y_sd

    def to_t(a):
        return torch.tensor(a, dtype=torch.float32)

    # 输入窗口的最近 HIST_FAST 小时（原始量纲，供算子用）
    hist_fast_raw = X[:, -HIST_FAST:, :]

    # ---------- 训练工具 ----------
    def run(mode: str, epochs: int = 12, batch: int = 256, lr: float = 1e-3,
            seed: int = 0):
        torch.manual_seed(seed)
        net = QuantileForecaster(n_vars=len(drivers))
        head = OperatorHead(transport, n_fast, INPUT_WINDOW)
        for p in head.parameters():
            p.requires_grad_(False)
        opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

        idx_tr = np.where(tr_s)[0]
        n = len(idx_tr)
        med = N_QUANTILES // 2          # 中位分位索引，用于 MSE 项
        hist_b = to_t(hist_fast_raw)
        slow_b = to_t(slow_win)
        Xn_t, Yn_t, C_t = to_t(Xn), to_t(Yn), to_t(C)

        for ep in range(epochs):
            net.train()
            perm = np.random.permutation(idx_tr)
            tot, nb = 0.0, 0
            for i in range(0, n, batch):
                b = perm[i:i + batch]
                bt = torch.as_tensor(b, dtype=torch.long)
                qn = net(Xn_t[bt])                       # (B,H,V,Q) 标准化量纲
                # 反标准化回原始量纲，才能送进算子
                q_raw = qn * to_t(y_sd)[None, None, :, None] + to_t(y_mu)[None, None, :, None]

                # --- MSE 项：中位分位数 vs 实况（标准化量纲） ---
                loss = nn.functional.mse_loss(qn[..., med], Yn_t[bt])

                # --- 风险对齐项 ---
                if mode != "A":
                    rh_q = head(hist_b[bt], q_raw, slow_b[bt])       # (B,H,Q)
                    # **参考分位数必须是上分位数，不是中位数。**
                    # 风险是尾部事件：中位数预报几乎永不越过阈值，
                    # 用它做门控会让 gate≈0、权重退化为 1，C 就等价于无权分位数损失。
                    # 上分位数才会在事件临近时逼近阈值，门控才能被激活。
                    cave_ref = rh_q[..., -1]
                    gate_mode = "operator" if mode == "C" else "fixed"
                    w = endogenous_weights(
                        cave_ref, torch.arange(1, H_MAX + 1, dtype=torch.float32),
                        TAUS, rh_crit=RH_CRIT, gamma=4.0,
                        h_eff_hours=72.0, gate_mode=gate_mode,
                    )
                    loss = loss + 0.5 * weighted_quantile_loss(
                        rh_q, C_t[bt], TAUS, w)

                opt.zero_grad(); loss.backward()
                nn.utils.clip_grad_norm_(net.parameters(), 5.0)
                opt.step()
                tot += float(loss.detach()); nb += 1
            sched.step()
            if (ep + 1) % 4 == 0 or ep == 0:
                print(f"      [{mode}] epoch {ep+1:>2}/{epochs}  loss={tot/max(nb,1):.4f}")
        net.eval()
        return net, head

    def predict(net, head, mask, batch: int = 512):
        """返回 (中位数预报, 上分位数预报)，形状均为 (N, H_MAX)。

        中位数用于逐点精度指标（RMSE/R²）；
        **上分位数用于事件检测**——概率预报做极值预警本就应该用上分位数。
        """
        idx = np.where(mask)[0]
        med = N_QUANTILES // 2
        out_med = np.empty((len(idx), H_MAX), dtype=np.float32)
        out_up = np.empty((len(idx), H_MAX), dtype=np.float32)
        with torch.no_grad():
            for i in range(0, len(idx), batch):
                b = idx[i:i + batch]
                bt = torch.as_tensor(b, dtype=torch.long)
                qn = net(to_t(Xn)[bt])
                q_raw = qn * to_t(y_sd)[None, None, :, None] + to_t(y_mu)[None, None, :, None]
                rh_q = head(to_t(hist_fast_raw)[bt], q_raw, to_t(slow_win)[bt])
                out_med[i:i + batch] = rh_q[..., med].numpy()
                out_up[i:i + batch] = rh_q[..., -1].numpy()
        return out_med, out_up

    # ---------- 训练三组 ----------
    print("\n[4] 训练 A / B / C 三组 ...")
    models = {}
    for mode, desc in (("A", "MSE（现有做法）"),
                       ("B", "MSE + 固定阈值 twCRPS"),
                       ("C", "MSE + 算子导出内生权重（本作品）")):
        print(f"\n  --- 方案 {mode}：{desc} ---")
        models[mode] = run(mode)

    # ---------- 评估 ----------
    print(f"\n{'=' * 88}\n[5] 测试段评估（2021-2025）\n{'=' * 88}")
    y_true = C[te_s]                          # (N, H_MAX)
    rows = []
    for mode in ("A", "B", "C"):
        rh_med, rh_up = predict(*models[mode], te_s)
        for h in (24, 48, 72):
            yt = y_true[:, h - 1]
            # 逐点精度用中位数；事件检测用**上分位数**
            m_pt = evaluate(yt, rh_med[:, h - 1], 1e9)      # 只取 RMSE/R2/bias
            for tname, thr in THRESHOLDS.items():
                m = evaluate(yt, rh_up[:, h - 1], thr)
                m.update({"mode": mode, "horizon_h": h, "threshold": tname,
                          "dur_MAE_h": duration_err(yt, rh_up[:, h - 1], thr),
                          # 同时给出中位数口径的事件指标，证明"用错分位数"就是 F1=0 的原因
                          "med_F1": evaluate(yt, rh_med[:, h - 1], thr)["F1"],
                          **{f"pt_{k}": v for k, v in m_pt.items()
                             if k in ("RMSE", "R2", "bias")}})
                rows.append(m)
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "exp03_abc_ablation.csv", index=False)

    for h in (24, 48, 72):
        print(f"\n  --- 时效 h = {h} h ---")
        sub = df[df.horizon_h == h]
        print(sub[["threshold", "mode", "pt_RMSE", "pt_R2", "base_rate", "pred_rate",
                   "pred_p95", "pred_max", "precision", "recall", "F1", "AUC",
                   "med_F1", "dur_MAE_h"]].to_string(index=False))

    # ---------- 核心判据 ----------
    print(f"\n{'=' * 88}\n[6] 核心判据：C 是否显著优于 B？\n{'=' * 88}")
    verdict = []
    for h in (24, 48, 72):
        for tname in THRESHOLDS:
            b = df[(df.horizon_h == h) & (df.threshold == tname) & (df["mode"] == "B")].iloc[0]
            c = df[(df.horizon_h == h) & (df.threshold == tname) & (df["mode"] == "C")].iloc[0]
            d_f1 = c.F1 - b.F1
            d_auc = (c.AUC - b.AUC) if np.isfinite(c.AUC) and np.isfinite(b.AUC) else np.nan
            verdict.append({"horizon_h": h, "threshold": tname,
                            "F1_B": b.F1, "F1_C": c.F1, "dF1": round(d_f1, 4),
                            "AUC_B": b.AUC, "AUC_C": c.AUC,
                            "dAUC": round(d_auc, 4) if np.isfinite(d_auc) else np.nan,
                            "C_wins": bool(d_f1 > 0)})
    dv = pd.DataFrame(verdict)
    print(dv.to_string(index=False))
    dv.to_csv(RESULTS / "exp03_verdict.csv", index=False)
    win = dv.C_wins.mean()
    print(f"\n  C 优于 B 的比例：{win*100:.1f}%")
    if win >= 0.6:
        print("  => 判据通过：算子导出的内生权重带来实质增益，算法创新主张成立。")
    else:
        print("  => 判据未通过：增益不足以支撑'内生权重'这一创新主张，")
        print("     需回到特征设计或权重形式上重做，**不得在报告中夸大**。")

    (RESULTS / "exp03_config.json").write_text(json.dumps({
        "n_quantiles": N_QUANTILES, "input_window": INPUT_WINDOW,
        "h_max": H_MAX, "rh_crit": RH_CRIT,
        "ridge_beta": transport.cfg.ridge_beta,
        "n_features": int(transport.n_features_in_),
        "train_end": TRAIN_END, "val_end": VAL_END,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n总用时 {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
