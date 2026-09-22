"""物理模型冒烟自检：确认热力学系统稳定、离散化有界、仿真输出有限且量级合理。

这是一个**断言式**自检（不是打印后人工看），可以直接放进 CI：

    python code/smoke_cave.py

它守的是本模型最容易静默失效的三件事：
1. 连续系统的谱横坐标必须全为负（否则矩阵指数离散化会发散）；
2. 离散化后的传播算子 max|Ad| 必须有界（否则数值爆炸）；
3. 仿真的窟内温湿度必须有限，且落在物理合理区间内。
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

# 允许从仓库根或 code/ 目录运行
_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402


def main() -> int:
    p = CaveParams()
    m = CaveModel(p)

    # --- 1) 两种门态下连续系统都必须稳定 ---
    for name, q in (("开门", p.q_open_m3h), ("关门", p.q_closed_m3h)):
        A, _ = m._build_thermal_system(q)
        ev = np.linalg.eigvals(A).real
        print(f"  {name:4s} (Q={q:6.1f} m^3/h)  谱横坐标 max = {ev.max():+.6g}")
        assert ev.max() < 0, f"{name}态谱横坐标为正在，离散化将发散"

    # --- 2) 离散化必须有界（历史上曾因网格过细而发散） ---
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        A, B = m._build_thermal_system(p.q_open_m3h)
        Ad, Bd = m._discretize(A, B, 3600.0)
    mx = float(np.abs(Ad).max())
    print(f"  离散化 max|Ad| = {mx:.6f}")
    assert np.isfinite(Ad).all() and np.isfinite(Bd).all(), "离散化出现非有限值"
    assert mx < 1e3, f"max|Ad| = {mx:.3g} 过大，数值不稳定"

    # --- 3) 一个月仿真：输出有限且量级合理 ---
    n = 24 * 30
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    h = np.arange(n)
    outdoor = pd.DataFrame(
        {
            "T2M": 5 + 10 * np.sin(h / 24 * 2 * np.pi),
            "RH2M": np.clip(40 + 20 * np.sin(h / 24 * 2 * np.pi + 1), 5, 95),
            "ALLSKY_SFC_SW_DWN": np.clip(600 * np.sin((h % 24 - 6) / 12 * np.pi), 0, None),
        },
        index=idx,
    )
    s = m.simulate(outdoor)
    print()
    print(s[["T_in", "RH_in", "T_wall", "Q_m3h"]].describe().round(3).to_string())

    for col in ("T_in", "RH_in", "T_wall"):
        assert np.isfinite(s[col].to_numpy()).all(), f"{col} 出现非有限值"
    assert -30 < s["T_in"].min() and s["T_in"].max() < 60, "窟内气温越出物理区间"
    assert 0 <= s["RH_in"].min() and s["RH_in"].max() <= 100, "窟内 RH 越出 0-100%"

    # 窟内日较差必须显著小于窟外（这是本模型的核心传递特征）
    ratio = float((s["T_in"].max() - s["T_in"].min()) / (outdoor["T2M"].max() - outdoor["T2M"].min()))
    print(f"\n  月内极差比 T_in/T_out = {ratio:.4f}（应 < 1，即存在衰减）")
    assert 0 < ratio < 1, "窟内极差不小于窟外，传递结构失效"

    print("\n✅ 物理模型自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
