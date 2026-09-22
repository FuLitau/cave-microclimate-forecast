"""诊断：exp03 的 OperatorHead 特征排布是否与 KoopmanTransport 拟合时的特征排布一致。

背景
----
``build_features`` 生成的列排布是 **lag 主序、lag=0（最新时刻）在前**：

    [T2M_lag0, RH2M_lag0, ..., SW_lag0, T2M_lag1, ..., SW_lag1, ...]

即扁平索引 ``j = lag * V + v``，lag 越大越旧（**时间降序**）。

而 ``exp03_risk_aligned.py`` 的 ``OperatorHead.forward`` 把 48 h 窗口按
**时间升序** 展平（最早的在最前），且窗口的 ``idx`` 起点比应该的位置早 1 小时。
两处都会让 ``psi @ w_`` 对不上真实特征。

本脚本用真实数据量化这个错位造成的误差（RH 百分点），并给出修正后的误差。

用法::

    python experiments/diag_head_order.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from src.operator.transport import (  # noqa: E402
    KoopmanTransport,
    TransportConfig,
    build_features,
)
from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402
import exp03_risk_aligned as E  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)


def main() -> None:
    outdoor = pd.read_csv(
        ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv",
        index_col=0, parse_dates=True,
    ).sort_index()
    outdoor = outdoor[~outdoor.index.duplicated(keep="first")]
    drivers = ["T2M", "RH2M", "WS10M", "PSC", "ALLSKY_SFC_SW_DWN"]
    drivers = [c for c in drivers if c in outdoor.columns]

    cave = CaveModel(CaveParams()).simulate(outdoor)
    cave_rh = cave["RH_in"].to_numpy(dtype=float)

    tr_mask = outdoor.index <= pd.Timestamp(E.TRAIN_END, tz="UTC")
    transport = KoopmanTransport(TransportConfig(ridge_beta=10.0)).fit(
        outdoor[tr_mask], cave_rh[tr_mask], fit_koopman=False)
    P = transport.n_features_in_
    w = torch.tensor(transport.w_, dtype=torch.float32)
    mu = torch.tensor(transport.mu_, dtype=torch.float32)
    sigma = torch.tensor(transport.sigma_, dtype=torch.float32)

    psi_all = build_features(outdoor, transport.cfg)            # (N, P) 原始量纲
    n_fast = transport.cfg.n_fast_lags * len(drivers)

    X, Y, C, starts = E.make_windows(outdoor, cave_rh, drivers, stride=997)
    hist = torch.tensor(X[:, -E.HIST_FAST:, :], dtype=torch.float32)   # (B,48,V)
    fcst = torch.tensor(Y, dtype=torch.float32)                        # (B,72,V)
    slow = torch.tensor(psi_all[:, n_fast:][starts], dtype=torch.float32)
    B = hist.shape[0]

    # ---- 参考真值：build_features 在 t_pred=s+h-1 那一行（严格因果，与拟合口径一致）----
    # 注意 w_ 是在**标准化空间**求解的，参考值也必须先标准化再加截距，否则量纲不可比。
    # exp03 的设计是「72h 内慢变量近似冻结」：慢变/Magnus 块取 s 时刻，只有快变延迟块随 h 推进。
    # 因此给出两套参考：ref_freeze（与 exp03 设计一致）与 ref_full（慢变也取 t_pred）。
    t_pred = starts[:, None] + np.arange(1, E.H_MAX + 1)[None, :] - 1     # (B,72)
    psi_full = psi_all[t_pred.reshape(-1)]                                # (B*72, P)
    psi_freeze = psi_full.copy()
    psi_freeze[:, n_fast:] = np.repeat(psi_all[:, n_fast:][starts], E.H_MAX, axis=0)

    def readout(psi: np.ndarray) -> np.ndarray:
        z = (psi - transport.mu_) / transport.sigma_
        return (np.column_stack([z, np.ones(z.shape[0])]) @ transport.w_)

    ref = readout(psi_freeze).reshape(B, E.H_MAX)
    ref_full = readout(psi_full).reshape(B, E.H_MAX)

    def head_fast(offset: int, flip: bool) -> np.ndarray:
        seq = torch.cat([hist, fcst], dim=1)                              # (B,120,V)
        idx = (torch.arange(E.H_MAX)[:, None] + offset
               + torch.arange(E.HIST_FAST)[None, :])
        win = seq[:, idx]                                                 # (B,72,48,V)
        if flip:
            win = win.flip(2)                                             # 时间降序
        fast = win.reshape(B, E.H_MAX, -1)
        psi = torch.cat([fast, slow[:, None, :].expand(B, E.H_MAX, slow.shape[1])], dim=-1)
        psi = (psi - mu) / sigma
        psi = torch.cat([psi, torch.ones_like(psi[..., :1])], dim=-1)
        return (psi @ w).detach().numpy()

    variants = [
        ("现状：offset=0, 时间升序（代码当前行为）", 0, False),
        ("仅改偏移：offset=1, 时间升序", 1, False),
        ("仅改方向：offset=0, 时间降序", 0, True),
        ("修正后：offset=1, 时间降序", 1, True),
    ]

    out_rows = []
    print(f"样本数 B={B:,}   H_MAX={E.H_MAX}   HIST_FAST={E.HIST_FAST}   P={P}")
    print(f"参考值（慢变量冻结在 s，exp03 设计口径）均值 {ref.mean():.3f}  "
          f"标准差 {ref.std():.3f}  范围 [{ref.min():.2f}, {ref.max():.2f}]")
    print(f"参考值（慢变量随 h 推进）            均值 {ref_full.mean():.3f}  "
          f"标准差 {ref_full.std():.3f}  范围 [{ref_full.min():.2f}, {ref_full.max():.2f}]")
    print(f"两套参考之间 MAE = {np.abs(ref - ref_full).mean():.4f} pp"
          f"（即「慢变量冻结」假设本身的代价）")
    print()
    print(f"{'变体':<38}{'MAE(pp)':>10}{'Max|err|':>10}{'' :>2}"
          f"{'MAE(pp)':>10}{'Max|err|':>10}")
    print(f"{'':<38}{'— 对冻结口径 —':>22}{'— 对推进口径 —':>22}")
    for name, off, fl in variants:
        got = head_fast(off, fl)
        e1 = got - ref
        e2 = got - ref_full
        ss = float(((ref - ref.mean()) ** 2).sum())
        r2 = 1.0 - float((e1 ** 2).sum()) / ss
        print(f"{name:<38}{np.abs(e1).mean():>10.4f}{np.abs(e1).max():>10.4f}"
              f"{'':>2}{np.abs(e2).mean():>10.4f}{np.abs(e2).max():>10.4f}")
        out_rows.append({
            "variant": name, "offset": off, "time_desc": fl,
            "MAE_vs_frozen_pp": round(float(np.abs(e1).mean()), 4),
            "max_err_vs_frozen_pp": round(float(np.abs(e1).max()), 4),
            "R2_vs_frozen": round(r2, 6),
            "MAE_vs_advancing_pp": round(float(np.abs(e2).mean()), 4),
            "max_err_vs_advancing_pp": round(float(np.abs(e2).max()), 4),
        })

    # ---- 回归测试：直接实例化 exp03 真正的 OperatorHead，与参考口径比对 ----
    head = E.OperatorHead(transport, n_fast, E.INPUT_WINDOW)
    with torch.no_grad():
        got_real = head(hist, fcst.unsqueeze(-1), slow).squeeze(-1).numpy()
    e_real = got_real - ref
    mae_real = float(np.abs(e_real).mean())
    mx_real = float(np.abs(e_real).max())
    # float32 精度下残差 ~1e-6 pp；阈值取 1e-3 pp，仍比 bug 造成的 1.72 pp 小三个量级。
    TOL_PP = 1e-3
    status = (f"✅ 通过（残差 {mae_real:.2e} pp，仅 float32 舍入）"
              if mae_real < TOL_PP else "❌ 未通过（特征排布仍错位）")
    print()
    print(f"回归测试（exp03.OperatorHead 真身）：MAE = {mae_real:.6f} pp，"
          f"最大误差 = {mx_real:.6f} pp   {status}")
    if mae_real >= TOL_PP:
        raise SystemExit(1)

    out_rows.append({
        "variant": "回归测试：exp03.OperatorHead 真身", "offset": 1, "time_desc": True,
        "MAE_vs_frozen_pp": round(mae_real, 6),
        "max_err_vs_frozen_pp": round(mx_real, 6),
        "R2_vs_frozen": None,
        "MAE_vs_advancing_pp": round(float(np.abs(got_real - ref_full).mean()), 4),
        "max_err_vs_advancing_pp": round(float(np.abs(got_real - ref_full).max()), 4),
    })

    dst = RESULTS / "diag_head_order.csv"
    pd.DataFrame(out_rows).to_csv(dst, index=False, encoding="utf-8-sig")
    (RESULTS / "diag_head_order.json").write_text(
        json.dumps({"n_samples": int(B), "P": int(P), "rows": out_rows},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ 已写入 {dst.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
