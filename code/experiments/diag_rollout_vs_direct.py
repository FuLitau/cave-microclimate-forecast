"""诊断：Koopman :math:`K^h` 闭式前推 vs 直接多步读出，逐时效对照。

为什么需要这个脚本
------------------
文档里长期写着一句「:math:`K^h` 前推的 R² ≈ 0.00，直接读出 0.42」，但
``results/`` 目录里**找不到任何支撑该数字的落盘文件**——它是早期探索中
口头记下的量级，被反复转抄成了 0.00 / 0.003 / 0.42 / 0.424 四种写法
（见 ``docs/01_技术路线.md``、``docs/03_作品方案.md``、``docs/06_佐证材料.md``）。

本脚本把这句话**变成可复现的实测**：在同一训练/测试切分、同一特征矩阵上，
对每个时效分别计算

* **direct**：为每个时效单独拟合一个读出层（:meth:`KoopmanTransport.fit_direct`）；
* **rollout**：用 :math:`\\Psi_{t+h} = K^h \\Psi_t` 前推状态，再套用**同一个**
  零时效读出 :math:`w`（:meth:`KoopmanTransport.rollout_features`）。

两者的**起点 t 与目标 t+h 完全一致**，因此 R² 可以直接比较。

结论口径
--------
若 rollout 显著劣于 direct，则「慢变滑动均值是**外生汇总量**、不是不变
Koopman 可观测量」这一解释成立，算子应定位为「作用在室外轨迹上的可微
输运读出」而非「可自行演化的动力系统」。本脚本产出的数字即为文档中该
论断的唯一出处。

产出：``results/diag_rollout.csv`` 与 ``results/diag_rollout.json``。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operator.transport import (                 # noqa: E402
    KoopmanTransport,
    TransportConfig,
    build_features,
)
from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402

RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

TRAIN_END = "2020-12-31"
HORIZONS = (6, 12, 24, 48, 72)
#: 读出层的岭强度与 :mod:`derisk_02` 的默认口径保持一致，便于交叉引用。
RIDGE_BETA = 1.0


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    yt, yp = y_true[ok], y_pred[ok]
    ss_res = float(((yp - yt) ** 2).sum())
    ss_tot = float(((yt - yt.mean()) ** 2).sum())
    return 1.0 - ss_res / ss_tot


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ok = np.isfinite(y_true) & np.isfinite(y_pred)
    return float(np.sqrt(((y_pred[ok] - y_true[ok]) ** 2).mean()))


def main() -> None:
    interim = ROOT / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
    if not interim.exists():
        print(f"[ERROR] 未找到 {interim}，请先运行 src/data/power.py")
        sys.exit(1)

    outdoor = pd.read_csv(interim, index_col=0, parse_dates=True)
    outdoor = outdoor[~outdoor.index.duplicated(keep="first")].sort_index()
    print(f"[1] 外场数据 {outdoor.shape[0]:,} 行 x {outdoor.shape[1]} 要素")

    cave_path = ROOT / "data" / "interim" / "cave_synthetic_2001_2025.csv"
    if cave_path.exists():
        cave = pd.read_csv(cave_path, index_col=0, parse_dates=True)
        cave = cave.loc[outdoor.index]
        print(f"[2] 复用已缓存的窟内合成标签 {cave_path.name}")
    else:
        print("[2] 生成窟内合成标签（文献参数化物理模型）...")
        t1 = time.time()
        cave = CaveModel(CaveParams()).simulate(outdoor)
        cave.to_csv(cave_path)
        print(f"    完成，用时 {time.time() - t1:.1f}s")

    y = cave["RH_in"].to_numpy(dtype=float)

    cfg = TransportConfig(ridge_beta=RIDGE_BETA)
    print(f"[3] 全序列构造提升特征（p = {len(cfg.drivers)} 驱动，"
          f"{cfg.n_fast_lags} 阶快变延迟）...")
    t1 = time.time()
    Psi = build_features(outdoor, cfg)
    print(f"    Psi 形状 {Psi.shape}，用时 {time.time() - t1:.1f}s")

    tr = np.asarray(outdoor.index <= pd.Timestamp(TRAIN_END, tz="UTC"), dtype=bool)
    pos = np.arange(len(y))
    te_pos = pos[~tr]
    print(f"[4] 切分：训练 {tr.sum():,} h / 测试 {len(te_pos):,} h")

    kt = KoopmanTransport(cfg)
    t1 = time.time()
    kt.fit(outdoor.iloc[pos[tr]], y[tr], Psi=Psi[tr], fit_koopman=True)
    print(f"[5] 算子拟合（含 K 演化矩阵）完成，用时 {time.time() - t1:.1f}s")

    # K 的谱半径 > 1 意味着状态前推会指数放大，先如实报出来
    eig = np.linalg.eigvals(kt.K_)
    print(f"    谱半径 max|λ| = {np.abs(eig).max():.6f}")

    rows: list[dict] = []
    for h in HORIZONS:
        origins = te_pos[te_pos + h < len(y)]
        y_true = y[origins + h]
        od_origins = outdoor.iloc[origins]

        # --- 策略一：直接多步读出（w 只在**训练起点**上拟合，再拿到测试起点评估，
        #     与 derisk_02 的公平协议一致；若在测试起点上拟合会高估 direct 一方）---
        tr_origins = pos[tr]
        tr_origins = tr_origins[tr_origins + h < len(y)]
        w_d = kt.fit_direct(outdoor.iloc[tr_origins], y[tr_origins], horizon=h,
                            Psi=Psi[tr_origins])
        p_direct = kt.predict_direct(od_origins, w_d, Psi=Psi[origins])

        # --- 策略二：K^h 闭式前推 + 零时效读出 w ---
        psi_h = kt.rollout_features(Psi[origins], h)
        p_rollout = kt._add_intercept(psi_h) @ kt.w_

        for name, pred in (("direct", p_direct), ("rollout_Kh", p_rollout)):
            rows.append({
                "horizon_h": h,
                "strategy": name,
                "R2": round(r2(y_true, pred), 5),
                "RMSE": round(rmse(y_true, pred), 4),
                "n_origins": int(len(origins)),
            })
            print(f"    h={h:2d}h  {name:11s}  R2={r2(y_true, pred):+.5f}  "
                  f"RMSE={rmse(y_true, pred):8.4f}")

    df = pd.DataFrame(rows)
    df.to_csv(RESULTS / "diag_rollout.csv", index=False)

    summary: dict[str, object] = {
        "train_end": TRAIN_END,
        "ridge_beta": RIDGE_BETA,
        "spectral_radius_K": round(float(np.abs(eig).max()), 6),
        "n_train": int(tr.sum()),
        "n_test": int(len(te_pos)),
        "by_horizon": {
            str(h): {
                "direct_R2": float(df[(df.horizon_h == h) & (df.strategy == "direct")]["R2"].iloc[0]),
                "rollout_R2": float(df[(df.horizon_h == h) & (df.strategy == "rollout_Kh")]["R2"].iloc[0]),
            }
            for h in HORIZONS
        },
    }
    (RESULTS / "diag_rollout.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n[6] 判读")
    worst_h = max(HORIZONS)
    d_worst = summary["by_horizon"][str(worst_h)]["direct_R2"]      # type: ignore[index]
    r_worst = summary["by_horizon"][str(worst_h)]["rollout_R2"]     # type: ignore[index]
    print(f"    h={worst_h}h：direct R²={d_worst:+.5f} vs rollout R²={r_worst:+.5f}")
    if r_worst < d_worst:
        print("    -> K^h 前推劣于直接读出，算子应定位为「室外轨迹上的可微输运读出」，")
        print("       而非可自行演化的动力系统（慢变滑动均值是外生汇总量）。")
    else:
        print("    -> K^h 前推不劣于直接读出，原文档的否定结论需要改写。")
    print(f"\n结果已写入 {RESULTS / 'diag_rollout.csv'} 与 diag_rollout.json")


if __name__ == "__main__":
    main()
