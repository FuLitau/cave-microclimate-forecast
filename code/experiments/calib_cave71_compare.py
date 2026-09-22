"""第 71 窟：与 Gong et al. 2025 实测的**同期对比**（不是与另—洞窟的统计量混比）。

为什么需要这个脚本
------------------
`docs/01_技术路线.md` §7.2 原先写「窟内年均温 比窟外 +1.9 K，文献 +0.75 K，偏暖约 1.2 K」。
这里有两个问题：

1. 「文献 +0.75 K」取自**另一个洞窟**（第 87 窟，Zhang & Wang 2023），
   而本项目标定用的是**第 71 窟**。同窟比较才成立。
2. 更关键：本项目的窟外气温来自 **NASA POWER 再分析**，而同文窟外来自**窟外现场气象站**。
   两者年均值本身差 1 K 以上，直接用各自的「窟内−窟外」温差相减，
   等于把**驱动数据的偏差**算到了模型头上。

本脚本用 POWER 驱动模型跑**与文献同期（2019-01-01 → 2021-12-31）**的仿真，
与 Gong et al. 2025 正文给出的第 71 窟实测统计量逐项对照，并**同时报告**：
  - 绝对量（窟内年均温）——这才是可比的；
  - 相对量（窟内−窟外温差）——对驱动偏差敏感，须注明驱动来源差异。

注意：温度统计量**不是**本项目的标定目标（标定只用窟内外日较差比、年极差比、RH 年均、
游客峰值抬升），因此温度场与实测的吻合是一次**独立**检验，而非拟合结果。

运行：python code/experiments/calib_cave71_compare.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT / ".."))

from src.physics.cave_model import CaveModel, CaveParams  # noqa: E402

#: Gong et al. 2025, npj Heritage Science 13:173 —— 第 71 窟，正文 Result 首段（2019–2021）
LIT = {
    "T_out_mean": 11.7,      # 窟外年均气温 °C（现场自动气象站）
    "T_out_max": 39.0,
    "T_out_min": -19.1,
    "T_in_mean": 12.0,       # 窟内年均气温 °C
    "T_in_max": 25.8,
    "T_in_min": -6.7,
    "RH_out_mean": 29.1,     # 窟外年均 RH %
    "RH_in_mean": 30.8,      # 窟内年均 RH %
    "RH_in_min": 8.7,
    "RH_in_max": 80.0,
    "volume_m3": 67.0,       # 洞窟体积（与模型几何同量级）
}

#: 本项目标定得到的最优参数（见 results/calib_cave_params.csv 与 docs/01_技术路线.md §7.2）
BEST = dict(
    ventilation_mixing_efficiency=0.30,
    k_sorption_m_s=8.0e-5,
    wall_pore_rh=50.0,
    pillar_depth_m=5.0,
    visitor_occupancy=1.0,
)


def main() -> int:
    interim = _ROOT / ".." / "data" / "interim" / "power_hourly_mogao_2001_2025.csv"
    outdoor_all = pd.read_csv(interim, index_col=0, parse_dates=True).sort_index()

    # 与文献同期
    outdoor = outdoor_all.loc["2019-01-01":"2021-12-31"].copy()

    # 自旋期（spin-up）：`simulate()` 只用**前 30 天**外场均值作初值，
    # 而 5 m 岩体导热链的时间常数是月量级，短初值不足以让深部节点平衡。
    # 故从 2017 起驱动、只对 2019–2021 统计，消除初值瞬态对统计量的污染。
    SPINUP_START = f"{2019 - int(os.environ.get('CALIB_SPINUP_YEARS', '2'))}-01-01"
    drive = outdoor_all.loc[SPINUP_START:"2021-12-31"].copy()

    p = CaveParams(**BEST)
    sim_full = CaveModel(p).simulate(drive)
    sim = sim_full.loc["2019-01-01":]
    assert len(sim) == len(outdoor), "自旋后统计窗口长度应与文献同期一致"

    print(f"POWER 驱动窗口：{drive.index[0]:%Y-%m-%d} → {drive.index[-1]:%Y-%m-%d}"
          f"（{len(drive)} 小时，含自旋期）")
    print(f"统计窗口：    {sim.index[0]:%Y-%m-%d} → {sim.index[-1]:%Y-%m-%d}"
          f"（{len(sim)} 小时，与文献同期）")
    n_spin = len(drive) - len(sim)
    print(f"自旋期长度：  {n_spin} 小时（约 {n_spin / 24 / 365.25:.2f} 年），不计入统计")

    rows = []

    def add(item: str, model: float, lit: float, unit: str = "", note: str = "") -> None:
        rows.append({"项目": item, "模型": round(float(model), 2), "文献实测": lit,
                     "差值": round(float(model) - lit, 2), "单位": unit, "说明": note})

    # --- 窟外（驱动）---
    add("窟外年均气温", outdoor["T2M"].mean(), LIT["T_out_mean"], "degC",
        "POWER 再分析 vs 现场站 → 差异属数据源，不属模型")
    add("窟外年均 RH", outdoor["RH2M"].mean(), LIT["RH_out_mean"], "%", "同上")

    # --- 窟内绝对值（可比，且温度未参与标定）---
    add("窟内年均气温", sim["T_in"].mean(), LIT["T_in_mean"], "degC", "温度统计量未参与标定")
    add("窟内气温最低", sim["T_in"].min(), LIT["T_in_min"], "degC", "同上")
    add("窟内气温最高", sim["T_in"].max(), LIT["T_in_max"], "degC", "同上")
    add("窟内 RH 年均", sim["RH_in"].mean(), LIT["RH_in_mean"], "%", "RH 年均是标定目标之一")
    add("窟内 RH 最低", sim["RH_in"].min(), LIT["RH_in_min"], "%", "")
    add("窟内 RH 最高", sim["RH_in"].max(), LIT["RH_in_max"], "%", "")

    # --- 窟内外温差（对驱动偏差敏感）---
    dT_model = sim["T_in"].mean() - outdoor["T2M"].mean()
    dT_lit = LIT["T_in_mean"] - LIT["T_out_mean"]
    add("窟内外温差", dT_model, round(dT_lit, 2), "K",
        "本行受驱动数据差异污染，须与上一行绝对值联合阅读")
    dRH_model = sim["RH_in"].mean() - outdoor["RH2M"].mean()
    dRH_lit = LIT["RH_in_mean"] - LIT["RH_out_mean"]

    df = pd.DataFrame(rows)
    print("\n" + "=" * 96)
    print("第 71 窟：模型（POWER 驱动，2019–2021）vs Gong et al. 2025 实测")
    print("=" * 96)
    with pd.option_context("display.unicode.east_asian_width", True,
                           "display.max_colwidth", 44):
        print(df.to_string(index=False))

    print(f"\n窟内外 RH 差：模型 {dRH_model:+.2f} pp，文献 {dRH_lit:+.2f} pp")

    # --- 关键判读 ---
    t_abs_err = abs(sim["T_in"].mean() - LIT["T_in_mean"])
    rh_abs_err = abs(sim["RH_in"].mean() - LIT["RH_in_mean"])
    drv_err = abs(outdoor["T2M"].mean() - LIT["T_out_mean"])
    print("\n【判读】")
    print(f"  窟内年均温绝对差 {t_abs_err:.2f} K（模型 {sim['T_in'].mean():.2f} vs 实测 {LIT['T_in_mean']}）")
    print(f"  驱动数据自身偏差 {drv_err:.2f} K（POWER {outdoor['T2M'].mean():.2f} vs 现场站 {LIT['T_out_mean']}）")
    print(f"  窟内 RH 年均绝对差 {rh_abs_err:.2f} pp")
    print("  → 绝对量吻合而『窟内外温差』不吻合，说明偏差异在**驱动数据**，不在窟内物理。")

    out = _ROOT / ".." / "results" / "calib_cave71_vs_lit.csv"
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"\n已写入 {out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
